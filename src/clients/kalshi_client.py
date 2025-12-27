import time
import base64
import asyncio
from typing import Optional
from datetime import datetime

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ..models.market import UnifiedMarket, Platform
from ..models.orderbook import Orderbook, OrderbookLevel


class RateLimiter:
    """Simple token bucket rate limiter."""

    def __init__(self, requests_per_second: float):
        self.interval = 1.0 / requests_per_second
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait_time = self._last_request + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request = time.monotonic()


class KalshiClient:
    """Kalshi API client with RSA-PSS authentication."""

    def __init__(
        self,
        api_key_id: str,
        private_key_pem: str,
        base_url: str = "https://api.elections.kalshi.com/trade-api/v2",
        requests_per_second: float = 5.0,
    ):
        self.api_key_id = api_key_id
        self.base_url = base_url.rstrip("/")
        self.rate_limiter = RateLimiter(requests_per_second)

        # Load RSA private key
        self.private_key: rsa.RSAPrivateKey = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None
        )

        self._client = httpx.AsyncClient(timeout=30.0)

    def _sign_request(self, method: str, path: str) -> tuple[str, str]:
        """Generate RSA-PSS signature for request."""
        timestamp_ms = str(int(time.time() * 1000))
        message = f"{timestamp_ms}{method}{path}"

        signature = self.private_key.sign(
            message.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )

        return timestamp_ms, base64.b64encode(signature).decode("utf-8")

    def _get_auth_headers(self, method: str, path: str) -> dict[str, str]:
        """Generate authentication headers for a request."""
        timestamp, signature = self._sign_request(method, path)
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json",
        }

    async def get_markets(
        self, status: str = "open", max_markets: int = 0
    ) -> list[UnifiedMarket]:
        """Fetch open markets from Kalshi with pagination."""
        markets = []
        cursor: Optional[str] = None
        path = "/markets"

        while max_markets == 0 or len(markets) < max_markets:
            await self.rate_limiter.acquire()

            params = {"limit": 1000, "status": status}
            if cursor:
                params["cursor"] = cursor

            headers = self._get_auth_headers("GET", path)

            response = await self._client.get(
                f"{self.base_url}{path}", headers=headers, params=params
            )
            response.raise_for_status()
            data = response.json()

            for m in data.get("markets", []):
                close_time = None
                if m.get("close_time"):
                    try:
                        close_time = datetime.fromisoformat(
                            m["close_time"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                # Get best prices from the market data
                yes_ask = None
                no_ask = None

                # Kalshi prices are in cents (0-100)
                if m.get("yes_ask"):
                    yes_ask = m["yes_ask"] / 100.0
                if m.get("no_ask"):
                    no_ask = m["no_ask"] / 100.0

                markets.append(
                    UnifiedMarket(
                        platform=Platform.KALSHI,
                        market_id=m["ticker"],
                        title=m.get("title", ""),
                        close_time=close_time,
                        yes_ask=yes_ask,
                        no_ask=no_ask,
                        raw_data=m,
                    )
                )

            cursor = data.get("cursor")
            if not cursor:
                break

        return markets

    async def get_orderbook(self, ticker: str, depth: int = 10) -> Orderbook:
        """Fetch orderbook for a Kalshi market."""
        await self.rate_limiter.acquire()

        path = f"/markets/{ticker}/orderbook"
        headers = self._get_auth_headers("GET", path)

        response = await self._client.get(
            f"{self.base_url}{path}", headers=headers, params={"depth": depth}
        )
        response.raise_for_status()
        data = response.json()

        orderbook_data = data.get("orderbook") or {}

        # Kalshi returns yes and no bids only
        # A yes bid at price P is equivalent to a no ask at (1-P)
        yes_bids = []
        no_bids = []

        for level in orderbook_data.get("yes") or []:
            if isinstance(level, list) and len(level) >= 2:
                price, size = level[0] / 100.0, level[1]
                yes_bids.append(OrderbookLevel(price=price, size=size))

        for level in orderbook_data.get("no") or []:
            if isinstance(level, list) and len(level) >= 2:
                price, size = level[0] / 100.0, level[1]
                no_bids.append(OrderbookLevel(price=price, size=size))

        # Derive asks from opposite side bids
        # YES ask = 1 - NO bid, NO ask = 1 - YES bid
        yes_asks = [
            OrderbookLevel(price=1.0 - lvl.price, size=lvl.size) for lvl in no_bids
        ]
        no_asks = [
            OrderbookLevel(price=1.0 - lvl.price, size=lvl.size) for lvl in yes_bids
        ]

        # Sort: bids descending, asks ascending
        yes_bids.sort(key=lambda x: x.price, reverse=True)
        yes_asks.sort(key=lambda x: x.price)
        no_bids.sort(key=lambda x: x.price, reverse=True)
        no_asks.sort(key=lambda x: x.price)

        return Orderbook(
            market_id=ticker,
            yes_bids=yes_bids,
            yes_asks=yes_asks,
            no_bids=no_bids,
            no_asks=no_asks,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
