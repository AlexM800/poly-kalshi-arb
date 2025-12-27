from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
from datetime import datetime
import re


class Platform(Enum):
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"


@dataclass
class UnifiedMarket:
    """Platform-agnostic market representation."""

    platform: Platform
    market_id: str
    title: str
    yes_token_id: Optional[str] = None
    no_token_id: Optional[str] = None
    close_time: Optional[datetime] = None
    yes_ask: Optional[float] = None
    no_ask: Optional[float] = None
    raw_data: Optional[dict[str, Any]] = field(default=None, repr=False)

    @property
    def normalized_title(self) -> str:
        """Normalize title for fuzzy matching."""
        title = self.title.lower()
        title = re.sub(r"[^\w\s]", " ", title)
        title = " ".join(title.split())
        return title

    @property
    def url(self) -> Optional[str]:
        """Get the URL for this market."""
        if self.platform == Platform.KALSHI and self.raw_data:
            # Extract series ticker from event_ticker by removing numeric suffixes
            # e.g., KXFRENCHPRES-27 -> KXFRENCHPRES
            # e.g., KXNEXTISRAELPM-45JAN01-YLAP -> KXNEXTISRAELPM
            event_ticker = self.raw_data.get("event_ticker", "") or self.market_id
            # Find the first hyphen followed by a digit
            series_ticker = event_ticker
            match = re.search(r"-\d", event_ticker)
            if match:
                series_ticker = event_ticker[: match.start()]
            return f"https://kalshi.com/markets/{series_ticker.lower()}"
        elif self.platform == Platform.POLYMARKET and self.raw_data:
            # Polymarket markets are often part of event groups
            events = self.raw_data.get("events", [])
            if events and len(events) > 0:
                event_slug = events[0].get("slug", "")
                if event_slug:
                    return f"https://polymarket.com/event/{event_slug}"
            # Fallback to direct slug
            slug = self.raw_data.get("slug", "")
            if slug:
                return f"https://polymarket.com/event/{slug}"
        return None

    def __hash__(self):
        return hash((self.platform, self.market_id))

    def __eq__(self, other):
        if not isinstance(other, UnifiedMarket):
            return False
        return self.platform == other.platform and self.market_id == other.market_id
