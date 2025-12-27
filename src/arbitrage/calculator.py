from typing import Optional

from ..models.market import Platform
from ..models.orderbook import Orderbook, OrderbookLevel
from ..models.arbitrage import ArbitrageOpportunity, ArbitrageLevel
from ..matching.fuzzy_matcher import MarketPair


class ArbitrageCalculator:
    """Calculate arbitrage opportunities between matched markets."""

    def __init__(self, min_profit_threshold: float = 0.02):
        """
        Args:
            min_profit_threshold: Minimum profit percentage (e.g., 0.02 = 2%)
        """
        self.min_profit_threshold = min_profit_threshold

    def _walk_orderbook(
        self,
        yes_asks: list[OrderbookLevel],
        no_asks: list[OrderbookLevel],
        yes_platform: Platform,
        no_platform: Platform,
    ) -> list[ArbitrageLevel]:
        """
        Walk through orderbook levels and find all profitable combinations.

        Returns list of ArbitrageLevel sorted by profit (best first).
        """
        levels = []

        # Track remaining quantity at each level
        yes_remaining = [(lvl.price, lvl.size) for lvl in yes_asks]
        no_remaining = [(lvl.price, lvl.size) for lvl in no_asks]

        yes_idx = 0
        no_idx = 0

        while yes_idx < len(yes_remaining) and no_idx < len(no_remaining):
            yes_price, yes_qty = yes_remaining[yes_idx]
            no_price, no_qty = no_remaining[no_idx]

            total_cost = yes_price + no_price
            gross_profit_pct = 1.0 - total_cost

            # Stop if no longer profitable
            if gross_profit_pct < self.min_profit_threshold:
                break

            # Take the minimum quantity available
            qty = min(yes_qty, no_qty)

            if qty > 0:
                # Calculate profit in dollars for this level
                max_profit_dollars = qty * gross_profit_pct

                levels.append(ArbitrageLevel(
                    buy_yes_platform=yes_platform,
                    buy_yes_price=yes_price,
                    buy_no_platform=no_platform,
                    buy_no_price=no_price,
                    quantity=qty,
                    total_cost=total_cost,
                    profit_percentage=gross_profit_pct,
                    max_profit_dollars=max_profit_dollars,
                ))

                # Update remaining quantities
                yes_remaining[yes_idx] = (yes_price, yes_qty - qty)
                no_remaining[no_idx] = (no_price, no_qty - qty)

            # Move to next level if exhausted
            if yes_remaining[yes_idx][1] <= 0:
                yes_idx += 1
            if no_remaining[no_idx][1] <= 0:
                no_idx += 1

        return levels

    def calculate_opportunity(
        self,
        pair: MarketPair,
        kalshi_orderbook: Orderbook,
        poly_orderbook: Orderbook,
    ) -> Optional[ArbitrageOpportunity]:
        """
        Calculate arbitrage opportunities across all orderbook levels.

        We check both strategies:
        1. Buy YES on Kalshi + Buy NO on Polymarket
        2. Buy YES on Polymarket + Buy NO on Kalshi
        """
        # Strategy 1: YES on Kalshi + NO on Polymarket
        levels_1 = self._walk_orderbook(
            kalshi_orderbook.yes_asks,
            poly_orderbook.no_asks,
            Platform.KALSHI,
            Platform.POLYMARKET,
        )

        # Strategy 2: YES on Polymarket + NO on Kalshi
        levels_2 = self._walk_orderbook(
            poly_orderbook.yes_asks,
            kalshi_orderbook.no_asks,
            Platform.POLYMARKET,
            Platform.KALSHI,
        )

        # Combine all levels and sort by profit percentage (best first)
        all_levels = levels_1 + levels_2
        all_levels.sort(key=lambda x: x.profit_percentage, reverse=True)

        if not all_levels:
            return None

        return ArbitrageOpportunity(
            kalshi_market=pair.kalshi_market,
            poly_market=pair.poly_market,
            match_score=pair.match_score,
            levels=all_levels,
        )

    def find_all_opportunities(
        self,
        pairs: list[MarketPair],
        kalshi_orderbooks: dict[str, Orderbook],
        poly_orderbooks: dict[str, Orderbook],
    ) -> list[ArbitrageOpportunity]:
        """Find all arbitrage opportunities from matched pairs."""
        opportunities = []

        for pair in pairs:
            kalshi_book = kalshi_orderbooks.get(pair.kalshi_market.market_id)
            poly_book = poly_orderbooks.get(pair.poly_market.market_id)

            if kalshi_book and poly_book:
                opp = self.calculate_opportunity(pair, kalshi_book, poly_book)
                if opp:
                    opportunities.append(opp)

        # Sort by best profit percentage descending
        return sorted(opportunities, key=lambda x: x.best_profit_percentage, reverse=True)
