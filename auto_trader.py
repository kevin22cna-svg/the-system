"""
Auto Scanner + Equity Trader — Kevin's Volume Mover Bot
Logic:
  1. Scan watchlist tickers for movers: price $10–$30, up >5% intraday
  2. Pick the best mover (highest % gain with volume confirmation)
  3. Buy $10–$20 worth of shares (market order)
  4. Immediately place limit sell at +5% above fill price

Run via Claude Code with Robinhood MCP connected.
"""

import anthropic
import json
import time

# ── Config ─────────────────────────────────────────────────────────────────
SCAN_TICKERS = [
    "AAL", "SOFI", "NU", "HOOD", "SPCX", "LUNR", "ASTS", "RKLB",
    "RIVN", "F", "BAC", "SPAL", "AMD", "PLTR", "MARA", "RIOT",
    "CLSK", "CIFR", "WULF", "HIMS", "OPEN", "UWMC", "RKT"
]

MIN_PRICE = 10.0
MAX_PRICE = 30.0
MIN_PCT_GAIN = 5.0        # Must be up at least 5% today
POSITION_SIZE_USD = 15.0  # ~middle of $10–$20 range
PROFIT_TARGET_PCT = 5.0   # Exit at +5%

MCP_SERVER = {
    "type": "url",
    "url": "https://agent.robinhood.com/mcp/trading",
    "name": "robinhood-mcp"
}

SYSTEM_PROMPT = """
You are an automated equity trading assistant connected to Robinhood.

Your job:
1. Get quotes for the provided ticker list
2. Filter for stocks with:
   - Current price between $10–$30
   - Up more than 5% from previous close
3. Pick the single best candidate (highest % gain)
4. Place a market BUY order for $15 worth of shares (round down to whole shares)
5. After confirming the fill price, place a LIMIT SELL at exactly +5% above fill price
6. Report what you did in a brief summary

IMPORTANT:
- Only trade ONE ticker per run (the best mover)
- Always confirm the buy fill before placing the sell
- If no tickers qualify, report that clearly and do NOT trade
- Use review_equity_order first to simulate, then place_equity_order to execute

Ticker list to scan: {tickers}
""".strip()

# ── Main ────────────────────────────────────────────────────────────────────
def run_auto_trader(dry_run: bool = True):
    """
    dry_run=True  → uses review_equity_order (simulate only, no real money)
    dry_run=False → uses place_equity_order (REAL trades)
    """
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\u274c ANTHROPIC_API_KEY not set. Run via Claude Code or export ANTHROPIC_API_KEY=your_key")
        return
    client = anthropic.Anthropic(api_key=api_key)

    mode = "DRY RUN (simulation)" if dry_run else "⚠️  LIVE TRADING — REAL MONEY"
    print(f"\n{'='*50}")
    print(f"  Kevin's Auto Trader — {mode}")
    print(f"  Scan: {len(SCAN_TICKERS)} tickers")
    print(f"  Criteria: ${MIN_PRICE}–${MAX_PRICE}, >{MIN_PCT_GAIN}% gain")
    print(f"  Position: ${POSITION_SIZE_USD} | Exit: +{PROFIT_TARGET_PCT}%")
    print(f"{'='*50}\n")

    user_prompt = f"""
Run the auto trader scan now.

Tickers to scan: {json.dumps(SCAN_TICKERS)}

Price range: ${MIN_PRICE} to ${MAX_PRICE}
Minimum % gain today: {MIN_PCT_GAIN}%
Position size: ${POSITION_SIZE_USD}
Profit target: +{PROFIT_TARGET_PCT}%
Mode: {"SIMULATE ONLY - use review_equity_order, do NOT place real orders" if dry_run else "LIVE - use place_equity_order for real execution"}

Steps:
1. Get quotes for all tickers
2. Filter and rank by % gain today
3. Pick the top qualifying mover
4. {"Simulate" if dry_run else "Execute"} the buy
5. {"Simulate" if dry_run else "Place"} the +5% limit sell
6. Give me a clear summary of what happened
"""

    print("📡 Connecting to Robinhood MCP...\n")

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT.format(tickers=", ".join(SCAN_TICKERS)),
        messages=[{"role": "user", "content": user_prompt}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"]
    )

    # Extract and print result
    print("📊 TRADER RESULT:\n")
    for block in response.content:
        if block.type == "text":
            print(block.text)
        elif block.type == "mcp_tool_use":
            print(f"  🔧 Tool called: {block.name}")
            if hasattr(block, 'input'):
                inp = block.input
                if 'symbol' in inp:
                    print(f"     Symbol: {inp['symbol']}")
                if 'quantity' in inp:
                    print(f"     Quantity: {inp['quantity']}")
                if 'price' in inp:
                    print(f"     Price: ${inp['price']}")
        elif block.type == "mcp_tool_result":
            # Just confirm tool ran, don't dump raw JSON
            print(f"  ✅ Tool executed")

    print(f"\n{'='*50}")
    print("  Run complete.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    import sys

    # Default: dry run (safe)
    # Pass --live to execute real trades
    live = "--live" in sys.argv

    if live:
        print("\n⚠️  WARNING: LIVE MODE — This will place REAL orders with REAL money.")
        confirm = input("Type YES to confirm: ").strip()
        if confirm != "YES":
            print("Aborted.")
            exit()

    run_auto_trader(dry_run=not live)
