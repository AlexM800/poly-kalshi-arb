from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel

from ..models.arbitrage import ArbitrageOpportunity
from ..models.market import Platform


class ArbotDisplay:
    """Console display manager for the arbitrage bot."""

    def __init__(self):
        self.console = Console()

    def _create_arbitrage_table(
        self, opportunities: list[ArbitrageOpportunity]
    ) -> Table:
        """Create a Rich table displaying arbitrage opportunities."""
        table = Table(
            title="[bold cyan]Arbitrage Opportunities[/bold cyan]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
        )

        table.add_column("#", justify="center", width=3)
        table.add_column("Market", style="cyan", min_width=45)
        table.add_column("Strategy", justify="center", width=26)
        table.add_column("Qty", justify="right", width=6)
        table.add_column("Profit", justify="right", style="green bold", width=7)
        table.add_column("Max $", justify="right", style="yellow", width=8)

        for i, opp in enumerate(opportunities, 1):
            # Get URLs
            kalshi_url = opp.kalshi_market.url or "N/A"
            poly_url = opp.poly_market.url or "N/A"

            # Truncate title
            title = opp.kalshi_market.title
            if len(title) > 43:
                title = title[:41] + ".."

            # Add each level as a row
            for lvl_idx, lvl in enumerate(opp.levels):
                yes_plat = "K" if lvl.buy_yes_platform == Platform.KALSHI else "P"
                no_plat = "K" if lvl.buy_no_platform == Platform.KALSHI else "P"
                strategy = (
                    f"YES@{yes_plat}({lvl.buy_yes_price:.1%}) + "
                    f"NO@{no_plat}({lvl.buy_no_price:.1%})"
                )

                if lvl_idx == 0:
                    # First row: show market info
                    market_cell = f"{title}\n[dim]K: {kalshi_url}[/dim]\n[dim]P: {poly_url}[/dim]"
                    row_num = str(i)
                else:
                    # Subsequent rows: empty market info
                    market_cell = ""
                    row_num = ""

                table.add_row(
                    row_num,
                    market_cell,
                    strategy,
                    f"{lvl.quantity:.0f}",
                    f"[green]{lvl.profit_percentage:.1%}[/green]",
                    f"[yellow]${lvl.max_profit_dollars:.2f}[/yellow]",
                )

        return table

    def _create_status_table(
        self,
        kalshi_count: int,
        poly_count: int,
        matched_count: int,
        opportunity_count: int,
        level_count: int,
    ) -> Table:
        """Create a status summary table."""
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Kalshi Markets", f"[cyan]{kalshi_count}[/cyan]")
        table.add_row("Polymarket Markets", f"[blue]{poly_count}[/blue]")
        table.add_row("Matched Pairs", f"[yellow]{matched_count}[/yellow]")
        table.add_row("Markets w/ Arb (>=2%)", f"[green bold]{opportunity_count}[/green bold]")
        table.add_row("Total Arb Levels", f"[green]{level_count}[/green]")
        table.add_row("Last Update", f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim]")

        return table

    def clear_and_display(
        self,
        opportunities: list[ArbitrageOpportunity],
        kalshi_count: int,
        poly_count: int,
        matched_count: int,
    ):
        """Clear console and display current state."""
        # Only clear in interactive mode
        if self.console.is_terminal:
            self.console.clear()

        # Header
        self.console.print(
            Panel(
                "[bold white]Polymarket-Kalshi Arbitrage Bot[/bold white]\n"
                "[dim]Scanning for arbitrage opportunities...[/dim]",
                style="cyan",
            )
        )

        # Count total levels across all opportunities
        total_levels = sum(len(opp.levels) for opp in opportunities)

        # Status summary
        status_table = self._create_status_table(
            kalshi_count=kalshi_count,
            poly_count=poly_count,
            matched_count=matched_count,
            opportunity_count=len(opportunities),
            level_count=total_levels,
        )
        self.console.print(status_table)
        self.console.print()

        # Opportunities table
        if opportunities:
            arb_table = self._create_arbitrage_table(opportunities)
            self.console.print(arb_table)
        else:
            self.console.print(
                "[dim]No arbitrage opportunities found above 2% threshold.[/dim]"
            )

        self.console.print()
        self.console.print("[dim]Press Ctrl+C to stop[/dim]")

    def show_error(self, message: str):
        """Display an error message."""
        self.console.print(f"[red bold]Error:[/red bold] {message}")

    def show_info(self, message: str):
        """Display an info message."""
        self.console.print(f"[cyan]Info:[/cyan] {message}")

    def show_warning(self, message: str):
        """Display a warning message."""
        self.console.print(f"[yellow]Warning:[/yellow] {message}")
