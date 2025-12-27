import asyncio
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import Settings
from .clients.kalshi_client import KalshiClient
from .clients.polymarket_client import PolymarketClient
from .matching.fuzzy_matcher import FuzzyMatcher
from .arbitrage.calculator import ArbitrageCalculator
from .display.console import ArbotDisplay


class ArbitrageBot:
    """Main arbitrage bot orchestrator."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.running = False
        self.display = ArbotDisplay()

        # Load Kalshi private key
        private_key_pem = settings.kalshi_private_key_path.read_text()

        # Initialize clients
        self.kalshi_client = KalshiClient(
            api_key_id=settings.kalshi_api_key_id,
            private_key_pem=private_key_pem,
            base_url=settings.kalshi_base_url,
            requests_per_second=settings.kalshi_requests_per_second,
        )

        self.poly_client = PolymarketClient(
            clob_url=settings.poly_clob_url,
            gamma_url=settings.poly_gamma_url,
            api_key=settings.poly_api_key,
            secret=settings.poly_secret,
            passphrase=settings.poly_passphrase,
            requests_per_second=settings.poly_requests_per_second,
        )

        # Initialize components
        self.matcher = FuzzyMatcher(threshold=settings.fuzzy_match_threshold)
        self.calculator = ArbitrageCalculator(
            min_profit_threshold=settings.min_profit_threshold
        )

    async def run(self):
        """Main polling loop."""
        self.running = True
        self.display.show_info("Starting arbitrage bot...")
        self.display.show_info(
            f"Polling every {self.settings.poll_interval_seconds} seconds"
        )
        self.display.show_info(
            f"Minimum profit threshold: {self.settings.min_profit_threshold:.0%}"
        )

        while self.running:
            try:
                await self._poll_cycle()
                await asyncio.sleep(self.settings.poll_interval_seconds)
            except asyncio.CancelledError:
                break
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.display.show_error(f"Poll cycle error: {e}")
                await asyncio.sleep(5)  # Brief pause before retry

        await self._cleanup()

    async def _poll_cycle(self):
        """Single polling cycle: fetch, match, calculate, display."""
        # 1. Fetch markets from both platforms concurrently
        self.display.show_info("Fetching markets from both platforms...")
        try:
            kalshi_markets, poly_markets = await asyncio.gather(
                self.kalshi_client.get_markets(status="open"),
                self.poly_client.get_markets(active_only=True),
            )
        except Exception as e:
            self.display.show_error(f"Failed to fetch markets: {e}")
            return

        self.display.show_info(
            f"Found {len(kalshi_markets)} Kalshi markets, {len(poly_markets)} Polymarket markets"
        )

        # 2. Find matching markets
        self.display.show_info("Matching markets...")
        pairs = self.matcher.find_matches(kalshi_markets, poly_markets)
        self.display.show_info(f"Found {len(pairs)} matched pairs")

        # 3. Fetch orderbooks for matched pairs
        kalshi_orderbooks = {}
        poly_orderbooks = {}

        if pairs:
            self.display.show_info(f"Fetching orderbooks for {len(pairs)} pairs...")

            # Fetch orderbooks concurrently
            kalshi_tasks = [
                self.kalshi_client.get_orderbook(p.kalshi_market.market_id)
                for p in pairs
            ]
            poly_tasks = [
                self.poly_client.get_orderbook(p.poly_market)
                for p in pairs
            ]

            kalshi_results = await asyncio.gather(*kalshi_tasks, return_exceptions=True)
            poly_results = await asyncio.gather(*poly_tasks, return_exceptions=True)

            for pair, result in zip(pairs, kalshi_results):
                if not isinstance(result, Exception) and result:
                    kalshi_orderbooks[pair.kalshi_market.market_id] = result

            for pair, result in zip(pairs, poly_results):
                if not isinstance(result, Exception) and result:
                    poly_orderbooks[pair.poly_market.market_id] = result

            self.display.show_info(
                f"Got {len(kalshi_orderbooks)} Kalshi and {len(poly_orderbooks)} Polymarket orderbooks"
            )

        # 4. Calculate arbitrage opportunities
        opportunities = self.calculator.find_all_opportunities(
            pairs, kalshi_orderbooks, poly_orderbooks
        )

        # 5. Display results
        self.display.clear_and_display(
            opportunities=opportunities,
            kalshi_count=len(kalshi_markets),
            poly_count=len(poly_markets),
            matched_count=len(pairs),
        )

    async def _cleanup(self):
        """Cleanup resources."""
        await self.kalshi_client.close()
        await self.poly_client.close()
        self.display.show_info("Bot stopped.")

    def stop(self):
        """Signal the bot to stop."""
        self.running = False


def main():
    """Entry point."""
    # Load environment variables
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    try:
        settings = Settings()
    except Exception as e:
        print(f"Error loading settings: {e}")
        print("Make sure .env file exists with required configuration.")
        sys.exit(1)

    bot = ArbitrageBot(settings)

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        bot.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the bot
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
