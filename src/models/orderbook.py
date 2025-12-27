from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderbookLevel:
    """Single price level in an orderbook."""

    price: float  # 0.0-1.0 scale (probability)
    size: float  # Number of contracts


@dataclass
class Orderbook:
    """Orderbook for a market."""

    market_id: str
    yes_bids: list[OrderbookLevel]
    yes_asks: list[OrderbookLevel]
    no_bids: list[OrderbookLevel]
    no_asks: list[OrderbookLevel]

    @property
    def best_yes_bid(self) -> Optional[float]:
        return self.yes_bids[0].price if self.yes_bids else None

    @property
    def best_yes_ask(self) -> Optional[float]:
        return self.yes_asks[0].price if self.yes_asks else None

    @property
    def best_no_bid(self) -> Optional[float]:
        return self.no_bids[0].price if self.no_bids else None

    @property
    def best_no_ask(self) -> Optional[float]:
        return self.no_asks[0].price if self.no_asks else None
