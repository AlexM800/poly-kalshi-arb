# Polymarket-Kalshi Arbitrage Finder

Scans [Polymarket](https://polymarket.com) and [Kalshi](https://kalshi.com) prediction markets to find arbitrage opportunities.

> **Note:** This bot only finds and displays opportunities. It does not execute trades.

## What is Arbitrage?

When the same event is priced differently on two platforms, you can profit by betting on both outcomes:

```
Example: "Will X happen?"

Polymarket:  YES = 2.2¢
Kalshi:      NO  = 86¢
                  ─────
Total cost:       88.2¢

Payout (guaranteed): $1.00
Profit:              11.8%
```

Since either YES or NO must happen, you get $1 back no matter what.

## Sample Output

```
╭─────┬─────────────────────────────┬────────────────────────────┬────────┬─────────┬──────────╮
│  #  │ Market                      │ Strategy                   │    Qty │  Profit │    Max $ │
├─────┼─────────────────────────────┼────────────────────────────┼────────┼─────────┼──────────┤
│  1  │ Will X win the election?    │ YES@P(2.2%) + NO@K(86.0%)  │     22 │   11.8% │    $2.60 │
│     │ K: https://kalshi.com/...   │ YES@P(2.2%) + NO@K(88.0%)  │     32 │    9.8% │    $3.14 │
│     │ P: https://polymarket.com/..│ YES@P(2.2%) + NO@K(89.0%)  │     44 │    8.8% │    $3.87 │
╰─────┴─────────────────────────────┴────────────────────────────┴────────┴─────────┴──────────╯
```

- **Qty** - Contracts available at that price level
- **Profit** - Guaranteed profit percentage
- **Max $** - Maximum profit in dollars at that level

## Requirements

- Python 3.11+
- [Kalshi API key](https://kalshi.com/account/settings/developer) (API key + RSA private key)
- Polymarket API credentials

## Quick Start

```bash
git clone https://github.com/AlexM800/poly-kalshi-arb.git
cd poly-kalshi-arb

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# Edit .env with your API credentials

python3 -m src.main
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

| Variable | Description |
|----------|-------------|
| `KALSHI_API_KEY_ID` | Your Kalshi API key ID |
| `KALSHI_PRIVATE_KEY_PATH` | Path to RSA private key (.pem) |
| `POLY_API_KEY` | Polymarket API key (optional) |
| `POLY_SECRET` | Polymarket secret (optional) |
| `POLY_PASSPHRASE` | Polymarket passphrase (optional) |
| `POLL_INTERVAL_SECONDS` | How often to scan (default: 30) |
| `MIN_PROFIT_THRESHOLD` | Minimum profit to show (default: 0.02 = 2%) |
| `FUZZY_MATCH_THRESHOLD` | Market title match threshold (default: 95) |

## How It Works

1. Fetches all open markets from both platforms
2. Matches similar markets using fuzzy text matching
3. Fetches orderbooks for matched pairs
4. Calculates arbitrage across all price levels
5. Displays opportunities ≥2% profit

Runs continuously, refreshing every 30 seconds. Press `Ctrl+C` to stop.
