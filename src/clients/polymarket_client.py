import time
import hmac
import base64
import hashlib
import asyncio
import json
from typing import Optional
from datetime import datetime

import httpx

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


class PolymarketClient:
    """Polymarket API client combining Gamma and CLOB APIs."""

    def __init__(
        self,
        clob_url: str = "https://clob.polymarket.com",
        gamma_url: str = "https://gamma-api.polymarket.com",
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        requests_per_second: float = 10.0,
    ):
        self.clob_url = clob_url.rstrip("/")
        self.gamma_url = gamma_url.rstrip("/")
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self.rate_limiter = RateLimiter(requests_per_second)

        self._client = httpx.AsyncClient(timeout=30.0)

        # Cache for token_id to market_id mapping
        self._token_to_market: dict[str, tuple[str, str]] = {}
        # Cache for market_id to token IDs
        self._market_tokens: dict[str, tuple[str, str]] = {}

    def _sign_request(
        self, method: str, path: str, body: str = ""
    ) -> dict[str, str]:
        """Generate HMAC-SHA256 signature for L2 authentication."""
        if not self.api_key or not self.secret or not self.passphrase:
            return {}

        timestamp = str(int(time.time()))

        # Message to sign: timestamp + method + path + body
        message = f"{timestamp}{method.upper()}{path}{body}"

        # HMAC-SHA256 signature
        signature = hmac.new(
            base64.b64decode(self.secret),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        return {
            "POLY_API_KEY": self.api_key,
            "POLY_PASSPHRASE": self.passphrase,
            "POLY_TIMESTAMP": timestamp,
            "POLY_SIGNATURE": base64.b64encode(signature).decode("utf-8"),
        }

    async def get_markets(self, active_only: bool = True) -> list[UnifiedMarket]:
        """Fetch markets from Gamma API with metadata."""
        markets = []
        offset = 0
        limit = 100

        while True:
            await self.rate_limiter.acquire()

            params = {
                "limit": limit,
                "offset": offset,
            }
            if active_only:
                params["active"] = "true"
                params["closed"] = "false"

            response = await self._client.get(
                f"{self.gamma_url}/markets", params=params
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            for m in data:
                # Skip markets that aren't actually tradeable
                if not m.get("enableOrderBook") or not m.get("acceptingOrders"):
                    continue

                # Get token IDs for YES and NO from clobTokenIds
                # clobTokenIds is a JSON string that needs to be parsed
                clob_token_ids_raw = m.get("clobTokenIds", "[]")
                try:
                    if isinstance(clob_token_ids_raw, str):
                        clob_token_ids = json.loads(clob_token_ids_raw)
                    else:
                        clob_token_ids = clob_token_ids_raw or []
                except (json.JSONDecodeError, TypeError):
                    continue

                if len(clob_token_ids) < 2:
                    continue

                # Convention: first token is YES, second is NO
                yes_token = clob_token_ids[0]
                no_token = clob_token_ids[1]

                # Parse close time
                close_time = None
                end_date = m.get("endDate")
                if end_date:
                    try:
                        close_time = datetime.fromisoformat(
                            end_date.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                condition_id = m.get("conditionId", "")

                market = UnifiedMarket(
                    platform=Platform.POLYMARKET,
                    market_id=condition_id,
                    title=m.get("question", ""),
                    yes_token_id=yes_token,
                    no_token_id=no_token,
                    close_time=close_time,
                    raw_data=m,
                )
                markets.append(market)

                # Cache token mappings
                self._token_to_market[yes_token] = (condition_id, "yes")
                self._token_to_market[no_token] = (condition_id, "no")
                self._market_tokens[condition_id] = (yes_token, no_token)

            offset += limit
            if len(data) < limit:
                break

        return markets

    async def get_orderbook(self, market: UnifiedMarket) -> Optional[Orderbook]:
        """Fetch orderbook for a Polymarket market using CLOB API."""
        yes_token_id = market.yes_token_id
        no_token_id = market.no_token_id

        if not yes_token_id or not no_token_id:
            # Try to get from cache
            tokens = self._market_tokens.get(market.market_id)
            if tokens:
                yes_token_id, no_token_id = tokens
            else:
                return None

        # Fetch orderbooks for both tokens
        await self.rate_limiter.acquire()

        try:
            yes_response = await self._client.get(
                f"{self.clob_url}/book", params={"token_id": yes_token_id}
            )
            yes_response.raise_for_status()
            yes_book = yes_response.json()
        except httpx.HTTPError:
            yes_book = {}

        await self.rate_limiter.acquire()

        try:
            no_response = await self._client.get(
                f"{self.clob_url}/book", params={"token_id": no_token_id}
            )
            no_response.raise_for_status()
            no_book = no_response.json()
        except httpx.HTTPError:
            no_book = {}

        # Parse orderbook data
        yes_bids = []
        yes_asks = []
        no_bids = []
        no_asks = []

        for b in yes_book.get("bids", []):
            try:
                price = float(b.get("price", 0))
                size = float(b.get("size", 0))
                yes_bids.append(OrderbookLevel(price=price, size=size))
            except (ValueError, TypeError):
                continue

        for a in yes_book.get("asks", []):
            try:
                price = float(a.get("price", 0))
                size = float(a.get("size", 0))
                yes_asks.append(OrderbookLevel(price=price, size=size))
            except (ValueError, TypeError):
                continue

        for b in no_book.get("bids", []):
            try:
                price = float(b.get("price", 0))
                size = float(b.get("size", 0))
                no_bids.append(OrderbookLevel(price=price, size=size))
            except (ValueError, TypeError):
                continue

        for a in no_book.get("asks", []):
            try:
                price = float(a.get("price", 0))
                size = float(a.get("size", 0))
                no_asks.append(OrderbookLevel(price=price, size=size))
            except (ValueError, TypeError):
                continue

        # Sort: bids descending, asks ascending
        yes_bids.sort(key=lambda x: x.price, reverse=True)
        yes_asks.sort(key=lambda x: x.price)
        no_bids.sort(key=lambda x: x.price, reverse=True)
        no_asks.sort(key=lambda x: x.price)

        return Orderbook(
            market_id=market.market_id,
            yes_bids=yes_bids,
            yes_asks=yes_asks,
            no_bids=no_bids,
            no_asks=no_asks,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
