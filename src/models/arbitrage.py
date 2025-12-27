from dataclasses import dataclass, field
from .market import UnifiedMarket, Platform


@dataclass
class ArbitrageLevel:
    """A single price level in an arbitrage opportunity."""

    buy_yes_platform: Platform
    buy_yes_price: float
    buy_no_platform: Platform
    buy_no_price: float
    quantity: float  # Available quantity at this level
    total_cost: float  # yes_price + no_price
    profit_percentage: float  # Gross profit % at this level
    max_profit_dollars: float  # quantity * profit per contract


@dataclass
class ArbitrageOpportunity:
    """Represents a potential arbitrage opportunity between two platforms."""

    kalshi_market: UnifiedMarket
    poly_market: UnifiedMarket
    match_score: float  # Fuzzy match confidence (0-100)

    # All profitable levels
    levels: list[ArbitrageLevel] = field(default_factory=list)

    @property
    def best_level(self) -> ArbitrageLevel | None:
        """Get the most profitable level."""
        return self.levels[0] if self.levels else None

    @property
    def total_quantity(self) -> float:
        """Total quantity across all levels."""
        return sum(lvl.quantity for lvl in self.levels)

    @property
    def total_max_profit(self) -> float:
        """Total max profit in dollars across all levels."""
        return sum(lvl.max_profit_dollars for lvl in self.levels)

    @property
    def best_profit_percentage(self) -> float:
        """Best profit percentage (from first level)."""
        return self.levels[0].profit_percentage if self.levels else 0.0

    @property
    def is_profitable(self) -> bool:
        return len(self.levels) > 0
