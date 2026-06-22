# Wiley Strat

Complete automated trading system combining your 0DTE confluence rules with Casey's EMA fan methodology. Trades shares AND options through Robinhood's Agentic MCP.

## Quick Start

1. Put this whole folder on your phone (Termux) or PC
2. Open a terminal in this folder
3. Run the installer:
   ```
   bash setup.sh
   ```
4. Follow the prompts (API key + optional Reddit setup)

That's it. The installer handles Python packages, your API key, and Reddit.

## The Files

**`config.py`** — THE CONTROL PANEL. Change any setting here and it updates every script. Position size, profit targets, DTE, ticker lists, feeds — all in one place.

**Shares trading:**
- `explosion_scanner.py` — scans 89 tickers across 3 tiers for breakouts
- `auto_trader.py` — simple auto-buyer for movers

**Options trading:**
- `kevin_0dte_system.py` — combined Kevin + Casey strategy, 0-5 DTE (defaults to 2DTE)

**Live monitoring:**
- `live_combined_scanner.py` — scans $10-50 universe every 5 min, surfaces Big 3
- `profit_monitor.py` — auto-sells the instant profit target hits intraday (PROFIT FIRST)

**End of day:**
- `eod_lead_scanner.py` — builds next-day watchlist with news, catalysts, earnings, and r/wallstreetbets sentiment

**Backtesting:**
- `backtest_engine.py` — validate the strategy on historical-style data
- `scheduler.py` — runs scans automatically during market hours

**Dashboards** (in `/dashboards`): React visualizers for backtests and strategy reference.

## The Strategy

Entry only when trend + level + timing agree:
1. **EMA fan** (13/48/200) must be aligned and spacing out — bunched = no trade
2. **15-min candle** must close body above PMH (calls) or below PDL (puts)
3. **13 EMA pullback** on the 2-min times the entry
4. **Confluence score** 5+ to enter, 7+ for full size
5. **Exits:** profit target first (intraday), stop loss, or 3:45pm force-close

## Profit-First Rule

Both shares and options: the moment the profit target hits intraday, it sells. No waiting for close.
- Shares: +5% / -8% stop
- Options: scales by DTE (2DTE = +50%/-30%)

## Running Continuously

Use tmux so it survives closing the terminal:
```
tmux new -s trading
python3 live_combined_scanner.py --trade
# Ctrl+B then D to detach
tmux attach -t trading   # to check back in
```

## Reddit / WSB Feed

The WallStreetBets feed works without login via Reddit's public API. For richer data (comments, higher limits), register a free app at reddit.com/prefs/apps and the installer will save your credentials to config.py.

## Modes

Every trading script supports:
- (no flag) — analysis/scan only, no trades
- `--trade` — auto-trade in DRY RUN (simulated)
- `--live` — REAL orders with real money

Always test with `--trade` first.
