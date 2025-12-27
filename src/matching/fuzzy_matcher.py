from dataclasses import dataclass
import numpy as np
from rapidfuzz import fuzz
from rapidfuzz.process import cdist

from ..models.market import UnifiedMarket


@dataclass
class MarketPair:
    """A matched pair of markets from different platforms."""

    kalshi_market: UnifiedMarket
    poly_market: UnifiedMarket
    match_score: float

    @property
    def pair_id(self) -> str:
        return f"{self.kalshi_market.market_id}:{self.poly_market.market_id}"


class FuzzyMatcher:
    """Fuzzy string matching for market titles across platforms."""

    def __init__(self, threshold: int = 80):
        """
        Args:
            threshold: Minimum similarity score (0-100) to consider a match.
        """
        self.threshold = threshold

    def find_matches(
        self,
        kalshi_markets: list[UnifiedMarket],
        poly_markets: list[UnifiedMarket],
    ) -> list[MarketPair]:
        """
        Find matching markets between platforms using fuzzy matching.

        Returns:
            List of MarketPair objects with match scores.
        """
        if not kalshi_markets or not poly_markets:
            return []

        # Get normalized titles
        kalshi_titles = [m.normalized_title for m in kalshi_markets]
        poly_titles = [m.normalized_title for m in poly_markets]

        # Compute full similarity matrix using all CPU cores
        # Shape: (len(kalshi_titles), len(poly_titles))
        scores = cdist(
            kalshi_titles,
            poly_titles,
            scorer=fuzz.token_sort_ratio,
            workers=-1,  # Use all CPU cores
        )

        # Find best match for each Kalshi market
        matches = []
        matched_poly_indices: set[int] = set()

        # Get best poly match for each kalshi market
        best_poly_indices = np.argmax(scores, axis=1)
        best_scores = np.max(scores, axis=1)

        # Create pairs, sorted by score (best first)
        sorted_indices = np.argsort(best_scores)[::-1]

        for kalshi_idx in sorted_indices:
            poly_idx = best_poly_indices[kalshi_idx]
            score = best_scores[kalshi_idx]

            # Check threshold and prevent duplicate poly matches
            if score >= self.threshold and poly_idx not in matched_poly_indices:
                matches.append(
                    MarketPair(
                        kalshi_market=kalshi_markets[kalshi_idx],
                        poly_market=poly_markets[poly_idx],
                        match_score=float(score),
                    )
                )
                matched_poly_indices.add(poly_idx)

        return matches
