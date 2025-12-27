import math

from ..models.market import Platform


class FeeCalculator:
    """Calculate trading fees for both platforms."""

    # Kalshi fee constants
    # Taker: ceil(0.07 * contracts * price * (1 - price))
    KALSHI_TAKER_COEFFICIENT = 0.07

    # Polymarket fee (approximately 0% for now, but keeping structure)
    POLY_TAKER_RATE = 0.0

    @classmethod
    def kalshi_taker_fee(cls, contracts: int, price: float) -> float:
        """
        Calculate Kalshi taker fee.

        Formula: ceil(0.07 * contracts * price * (1 - price)) in cents
        Price should be in 0.0-1.0 scale.

        Returns fee in dollars.
        """
        fee_cents = math.ceil(
            cls.KALSHI_TAKER_COEFFICIENT * contracts * price * (1 - price) * 100
        )
        return fee_cents / 100.0

    @classmethod
    def polymarket_taker_fee(cls, contracts: int, price: float) -> float:
        """
        Calculate Polymarket taker fee.

        Currently Polymarket has minimal fees.
        Returns fee in dollars.
        """
        return contracts * price * cls.POLY_TAKER_RATE

    @classmethod
    def estimate_total_fees(
        cls,
        buy_yes_platform: Platform,
        buy_yes_price: float,
        buy_no_platform: Platform,
        buy_no_price: float,
        contracts: int = 100,
    ) -> tuple[float, float]:
        """
        Estimate total fees for an arbitrage trade.

        Assumes taker fees (aggressive orders).

        Returns:
            Tuple of (kalshi_fee, poly_fee) in dollars.
        """
        kalshi_fee = 0.0
        poly_fee = 0.0

        if buy_yes_platform == Platform.KALSHI:
            kalshi_fee += cls.kalshi_taker_fee(contracts, buy_yes_price)
        else:
            poly_fee += cls.polymarket_taker_fee(contracts, buy_yes_price)

        if buy_no_platform == Platform.KALSHI:
            kalshi_fee += cls.kalshi_taker_fee(contracts, buy_no_price)
        else:
            poly_fee += cls.polymarket_taker_fee(contracts, buy_no_price)

        return (kalshi_fee, poly_fee)
