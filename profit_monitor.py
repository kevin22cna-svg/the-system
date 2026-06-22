"""
Wiley Strat Profit Monitor — Auto Take-Profit
===================================================
Monitors open positions (shares AND options) and triggers an
automatic SELL the moment the profit target is hit intraday.

CORE RULE: Profit comes first. If the target is hit intraday,
           take the profit immediately — don't wait for close.

Targets:
  SHARES:   +5% default (configurable per position)
  OPTIONS:  DTE-based — 0DTE +25%, 2DTE +50%, 3DTE +60%, 5DTE +75%

Also enforces stop losses on the downside.

Run alongside the scanner during market hours:
  python profit_monitor.py            # monitor only (alerts)
  python profit_monitor.py --auto     # auto-sell on target (dry run)
  python profit_monitor.py --live     # auto-sell with real orders
"""

import anthropic
import json
import os
import time
import uuid
from datetime import datetime
import pytz
try:
    from config import CONFIG, get_account, get_share_targets, get_option_targets, get_universe, get_position_size
    _HAS_CONFIG = True
except ImportError:
    _HAS_CONFIG = False  # falls back to file-local defaults

try:
    from tax_reserve import reserve_on_close, summary as tax_summary
    _HAS_TAX_RESERVE = True
except ImportError:
    _HAS_TAX_RESERVE = False

ET = pytz.timezone("America/New_York")
ACCOUNT = "666042577"  # Agentic account

MCP_SERVER = {
    "type": "url",
    "url": "https://agent.robinhood.com/mcp/trading",
    "name": "robinhood-mcp"
}

# ── Profit Targets ────────────────────────────────────────────────────────────
SHARE_PROFIT_TARGET = 0.05   # +5% on shares
SHARE_STOP_LOSS     = 0.05   # -5% stop on shares

OPTION_DTE_TARGETS = {
    0: {"profit": 0.25, "stop": 0.25},
    1: {"profit": 0.40, "stop": 0.30},
    2: {"profit": 0.50, "stop": 0.30},
    3: {"profit": 0.60, "stop": 0.35},
    5: {"profit": 0.75, "stop": 0.35},
}

CHECK_INTERVAL_SEC = 60   # Check positions every 60 seconds

def now_et():
    return datetime.now(ET)

def in_market_hours():
    n = now_et()
    if n.weekday() >= 5: return False
    h, m = n.hour, n.minute
    return (h > 9 or (h == 9 and m >= 30)) and h < 16

SYSTEM_PROMPT = f"""
You are Kevin's intraday profit monitor. Your job: watch open positions and
trigger SELLS the moment profit targets are hit. PROFIT COMES FIRST.

Account: {ACCOUNT}

For SHARES:
  - Get equity positions
  - For each, compare current price to average buy price
  - If gain >= +{int(SHARE_PROFIT_TARGET*100)}% → SELL immediately (take profit)
  - If loss <= -{int(SHARE_STOP_LOSS*100)}% → SELL immediately (stop loss)

For OPTIONS:
  - Get option positions
  - Compare current premium to entry premium
  - Use DTE-based targets:
      0DTE: +25%/-25%   2DTE: +50%/-30%   3DTE: +60%/-35%   5DTE: +75%/-35%
  - If profit target hit intraday → SELL/close immediately
  - If stop hit → close immediately

RULE: The instant a profit target is reached intraday, take the profit.
Do not wait for end of day. Profit first.

Report each position's status: HOLD, TAKE PROFIT (selling), or STOP (selling).
Output JSON:
{{
  "timestamp": "...",
  "positions": [
    {{"symbol":"SPCX","type":"share","entry":214.18,"current":225.00,
      "pct":5.05,"action":"TAKE_PROFIT","reason":"hit +5% target"}}
  ],
  "actions_taken": ["Sold SPCX at +5.05%"]
}}
"""

def monitor_cycle(client, auto_sell=False, dry_run=True):
    now = now_et().strftime("%Y-%m-%d %H:%M:%S ET")
    print(f"\n  🔍 Checking positions — {now}")

    instruction = f"""
Check all open positions in account {ACCOUNT} for profit targets.

1. Get equity positions and option positions
2. For each, compute current P&L %
3. Identify any that hit profit target or stop loss
4. {"Execute the sells for any that hit targets" if auto_sell else "Report which would trigger (monitor only)"}
{"Use review then place orders (DRY RUN — simulate only)" if auto_sell and dry_run else ""}
{"Use place orders for REAL execution" if auto_sell and not dry_run else ""}

Remember: PROFIT FIRST. Sell the instant target is hit intraday.
Time: {now}
"""

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": instruction}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"]
    )

    raw = ""
    for block in response.content:
        if hasattr(block, "text"): raw += block.text
        elif getattr(block, "type", "") == "mcp_tool_use":
            print(f"    🔧 {block.name}")

    try:
        clean = raw.strip()
        if "```" in clean:
            for p in clean.split("```"):
                if p.strip().startswith("{") or p.startswith("json"):
                    clean = p.replace("json","",1).strip(); break
        data = json.loads(clean)
        positions = data.get("positions", [])
        if not positions:
            print("    📭 No open positions.")
        for p in positions:
            sym = p.get("symbol","?")
            pct = p.get("pct",0)
            action = p.get("action","HOLD")
            emoji = {"TAKE_PROFIT":"💰","STOP":"🛑","HOLD":"⏳"}.get(action,"")
            print(f"    {emoji} {sym}: {pct:+.2f}% — {action}")
            # TAX_RESERVE_HOOK — fires on every realized share gain
            if action == "TAKE_PROFIT" and p.get("type") == "share" and _HAS_TAX_RESERVE:
                entry   = p.get("entry", 0)
                current = p.get("current", 0)
                qty     = p.get("qty", 1)
                reserved = reserve_on_close(sym, entry, current, qty)
                print(f"    🏦 Tax reserve: ${reserved:.2f} set aside  |  {tax_summary()}")
        for a in data.get("actions_taken", []):
            print(f"    ✅ {a}")
    except Exception:
        print("    " + raw[:400])

def main():
    import sys
    auto_sell = "--auto" in sys.argv or "--live" in sys.argv
    dry_run   = "--live" not in sys.argv
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Set ANTHROPIC_API_KEY"); sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)

    mode = "LIVE AUTO-SELL 💰" if not dry_run else ("DRY RUN" if auto_sell else "MONITOR ONLY")
    print(f"""
╔══════════════════════════════════════════════════════════╗
║   💰 INTRADAY PROFIT MONITOR — PROFIT FIRST             ║
║   Shares: +5%/-5%  |  Options: DTE-based targets        ║
║   Mode: {mode:20s}  Check every 60s          ║
╚══════════════════════════════════════════════════════════╝
""")

    checks = 0
    try:
        while True:
            if in_market_hours():
                checks += 1
                monitor_cycle(client, auto_sell, dry_run)
                time.sleep(CHECK_INTERVAL_SEC)
            else:
                print(f"  🕐 Market closed ({now_et().strftime('%I:%M %p ET')}). Pausing 5 min...")
                time.sleep(300)
    except KeyboardInterrupt:
        print(f"\n  🛑 Stopped after {checks} checks.")

if __name__ == "__main__":
    main()
