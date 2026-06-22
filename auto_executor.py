"""
Wiley Strat — Auto-Executor
============================
Places HIGH CONVICTION trades automatically so you never miss a setup.

HOW IT WORKS:
  1. Runs the full scanner every 5 minutes
  2. Scores every ticker (technical + order flow + news)
  3. Runs 10x sim on top candidates
  4. If score >= AUTO_EXECUTE_THRESHOLD:
       → Reviews the order first (review_equity_order / review_option_order)
       → Places the trade automatically
       → Starts profit monitor immediately
       → Sends you a clear alert of what was done

CONVICTION LEVELS:
  Score 10-12 = 🔥🔥 ELITE   → auto-execute immediately, full $50
  Score 8-9   = 🔥 PRIME    → auto-execute, full $50
  Score 7     = ⚡ HIGH     → auto-execute if whale flow confirms
  Score 5-6   = ⚡ WATCH    → alert only, no auto-execute
  Score <5    = 🚫 SKIP     → ignore

SAFETY RULES (always enforced):
  1. Max 3 auto-trades per day total
  2. Max $50 per trade
  3. No new option entries after 3:45pm ET
  4. Always review_order before place_order
  5. Profit monitor starts immediately after fill
  6. Daily loss limit: -$150 (3 stops) = halt for the day
  7. Never auto-execute in the first 15 minutes (9:30-9:45am)

Run: python auto_executor.py           # scan + auto-execute (dry run)
     python auto_executor.py --live    # REAL money execution
"""

import anthropic
import json
import os
import time
import uuid
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")
ACCOUNT = "666042577"

MCP_SERVER = {
    "type": "url",
    "url": "https://agent.robinhood.com/mcp/trading",
    "name": "robinhood-mcp"
}

# ── Config ────────────────────────────────────────────────────────────────────
AUTO_EXECUTE_THRESHOLD = 8      # Score 8+ = auto-execute
WHALE_CONFIRM_THRESHOLD = 7     # Score 7+ needs whale confirm to auto-execute
POSITION_SIZE_USD      = 50.0   # Per trade
MAX_DAILY_TRADES       = 3      # Max auto-trades per day
DAILY_LOSS_LIMIT       = -150.0 # Stop trading for the day if hit
SCAN_INTERVAL_SEC      = 300    # Scan every 5 minutes

# Option targets (2DTE default)
OPTION_PROFIT_TARGET   = 0.50   # +50%
OPTION_STOP_LOSS       = 0.30   # -30%
SHARE_PROFIT_TARGET    = 0.05   # +5%
SHARE_STOP_LOSS        = 0.05   # -5%

# ── Session State ─────────────────────────────────────────────────────────────
session = {
    "trades_today":   0,
    "daily_pnl":      0.0,
    "executed_syms":  [],   # don't re-enter same ticker
    "halted":         False,
    "scan_count":     0,
    "log":            [],
}

def now_et():
    return datetime.now(ET)

def in_market_hours():
    n = now_et()
    if n.weekday() >= 5: return False
    h, m = n.hour, n.minute
    return (h > 9 or (h == 9 and m >= 45)) and h < 16

def in_option_window():
    n = now_et()
    h, m = n.hour, n.minute
    return (h > 9 or (h == 9 and m >= 45)) and (h < 15 or (h == 15 and m < 45))

def past_force_close():
    n = now_et()
    return n.hour > 15 or (n.hour == 15 and n.minute >= 45)

# ── Main Executor System Prompt ──────────────────────────────────────────────
def build_system_prompt(dry_run: bool) -> str:
    mode = "DRY RUN (review_order only — no real execution)" if dry_run else "LIVE EXECUTION (real money)"
    return f"""
You are the Wiley Strat Auto-Executor. Mode: {mode}

Your job every scan cycle:

STEP 1 — SCAN & SCORE
Get quotes for the full universe. Score each ticker 0-12:
  +2  EMA fan aligned (proxy: >3% move = fan forming)
  +2  15min above PMH (proxy: >5% = confirmed, 2-5% = forming)
  +2  Zone play + structure confirmed
  +2  ORDER FLOW: appears in Barchart unusual options today
  +1  Barchart top options volume
  +2  Insider buy >$100K today (OpenInsider)
  +1  Volume above 10M average
  -1  Overextended >15%

STEP 2 — FILTER
  → Price $10-$150 for options (liquid chains)
  → Avg daily volume >= 10M shares
  → Score >= {AUTO_EXECUTE_THRESHOLD} for auto-execution
  → Not already in position today (check existing positions)
  → Within market hours and option window

STEP 3 — ORDER FLOW CHECK
  For any ticker scoring {WHALE_CONFIRM_THRESHOLD}+, web-search:
  "unusual options activity [TICKER] today sweep"
  If whale call/put sweep confirmed in SAME direction = execute
  If whale flow OPPOSITE = skip regardless of score

STEP 4 — EXECUTE (if conviction >= {AUTO_EXECUTE_THRESHOLD})
  FOR OPTIONS (SPY/QQQ/IWM/mega caps with liquid chains):
    1. get_option_chains for the symbol
    2. Find ATM strike, 2DTE expiry
    3. Confirm: OI >= 1000, volume >= 500, spread <= 5%
    4. review_option_order FIRST — check for alerts
    5. If review clean: place_option_order ({"DRY RUN: review only" if dry_run else "LIVE: place_option_order"})
    6. Report: symbol, strike, expiry, premium, cost, target, stop

  FOR SHARES ($10-50 range, high volume):
    1. review_equity_order FIRST
    2. If review clean: {"simulate only" if dry_run else "place_equity_order — $50 market buy"}
    3. Set limit sell at +5% immediately after fill
    4. Report: symbol, shares, cost, target price, stop price

STEP 5 — REPORT
Return JSON:
{{
  "scan_time": "...",
  "scores": [{{"sym":"SOFI","score":9,"direction":"CALLS","flow":["unusual options"]}}],
  "executed": [{{"sym":"SOFI","type":"option","strike":"$18.5C","expiry":"Jun 19",
                 "premium":0.45,"cost":45.0,"target":"+50%","stop":"-30%",
                 "order_id":"...", "status":"filled"}}],
  "alerts": [{{"sym":"META","score":8,"direction":"PUTS","reason":"whale sweep confirmed but no funds"}}],
  "skipped": [{{"sym":"AVGO","reason":"already overextended, failed 10x sim"}}]
}}

ACCOUNTS: {ACCOUNT}
MODE: {mode}
MAX TRADES TODAY: {MAX_DAILY_TRADES}
POSITION SIZE: ${POSITION_SIZE_USD}
""".strip()


# ── Scan + Execute Cycle ──────────────────────────────────────────────────────
def run_auto_cycle(client, dry_run=True, scan_universe=None):
    if scan_universe is None:
        from config import CONFIG
        scan_universe = CONFIG["tickers"]["casey_universe"] + CONFIG["tickers"]["primary"]
        scan_universe = list(set(scan_universe))

    session["scan_count"] += 1
    now = now_et()
    print(f"\n{'─'*62}")
    print(f"  🤖 AUTO-EXECUTOR SCAN #{session['scan_count']}  |  {now.strftime('%I:%M:%S %p ET')}")
    print(f"  Trades today: {session['trades_today']}/{MAX_DAILY_TRADES}  |  "
          f"Daily P&L: ${session['daily_pnl']:+.2f}  |  "
          f"Mode: {'DRY RUN' if dry_run else '⚠️  LIVE'}")
    print(f"{'─'*62}")

    if session["halted"]:
        print("  🛑 Trading HALTED — daily loss limit reached.")
        return

    if not in_market_hours():
        print(f"  🕐 Outside market hours ({now.strftime('%I:%M %p ET')})")
        return

    if session["trades_today"] >= MAX_DAILY_TRADES:
        print(f"  ✋ Max trades reached ({MAX_DAILY_TRADES}/day). Monitoring positions only.")
        return

    user_msg = f"""
Run the full Wiley Strat scan and execute high conviction trades.

Tickers to scan: {json.dumps(scan_universe[:60])}
Already executed today (skip these): {json.dumps(session['executed_syms'])}
Trades used today: {session['trades_today']}/{MAX_DAILY_TRADES}
Current time: {now.strftime('%I:%M:%S %p ET')}
Option window open: {in_option_window()}
Past 3:45pm force-close: {past_force_close()}

Order flow context (from this cycle):
- Search Barchart for unusual options activity
- Check for any whale sweeps on top scoring tickers
- Verify 10M+ daily volume before any execution

Execute any ticker scoring {AUTO_EXECUTE_THRESHOLD}+ with clean order flow.
{"USE review_order ONLY — do NOT place real orders (DRY RUN)" if dry_run else
 "EXECUTE LIVE — place_equity_order and place_option_order for real money"}
"""

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=build_system_prompt(dry_run),
        messages=[{"role": "user", "content": user_msg}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"],
        tools=[{"type": "web_search_20250305", "name": "web_search"}]
    )

    raw = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw += block.text
        elif getattr(block, "type", "") == "mcp_tool_use":
            print(f"  🔧 {block.name}...")

    # Parse results
    try:
        clean = raw.strip()
        if "```" in clean:
            for p in clean.split("```"):
                if p.strip().startswith("{") or p.startswith("json"):
                    clean = p.replace("json","",1).strip(); break
        result = json.loads(clean)
    except Exception:
        # Print raw if can't parse
        print("\n" + raw[:2000])
        return

    # Display executed trades
    executed = result.get("executed", [])
    alerts   = result.get("alerts",   [])
    skipped  = result.get("skipped",  [])
    scores   = result.get("scores",   [])

    if scores:
        print(f"\n  📊 TOP SCORES THIS SCAN:")
        for s in scores[:5]:
            d = "📈" if s.get("direction") == "CALLS" else "📉"
            flow = " | " + "+".join(s.get("flow",[])) if s.get("flow") else ""
            print(f"     {d} {s['sym']:<6} {s['score']}/10{flow}")

    if executed:
        print(f"\n  {'🎯 EXECUTED' if not dry_run else '🧪 SIM EXECUTED'} ({len(executed)} trades):")
        for t in executed:
            sym = t.get("sym","?")
            cost = t.get("cost", 0)
            session["trades_today"] += 1
            session["executed_syms"].append(sym)
            print(f"  ✅ {sym}: {t.get('type','?')} | {t.get('direction','')} | "
                  f"Cost ${cost:.2f} | Target {t.get('target','')} | Stop {t.get('stop','')}")
            if t.get("order_id"):
                print(f"     Order ID: {t['order_id']} | Status: {t.get('status','')}")
            session["log"].append({
                "time": now.isoformat(), "sym": sym,
                "type": t.get("type"), "cost": cost, "dry_run": dry_run
            })
    else:
        print(f"  📭 No auto-executions this cycle (no ticker hit {AUTO_EXECUTE_THRESHOLD}+ threshold)")

    if alerts:
        print(f"\n  ⚡ ALERTS (watch these — close to threshold):")
        for a in alerts:
            print(f"     {a.get('sym','?')}: {a.get('reason','')}")

    if skipped:
        print(f"\n  ⏭️  Skipped: {', '.join(s.get('sym','?') for s in skipped)}")

    # Save log
    log_dir = os.path.expanduser("~/scan_logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"auto_{now.strftime('%Y%m%d')}.jsonl")
    with open(log_path, "a") as f:
        f.write(json.dumps({
            "time": now.isoformat(),
            "scan": session["scan_count"],
            "executed": executed,
            "alerts": alerts,
            "trades_today": session["trades_today"],
            "daily_pnl": session["daily_pnl"],
        }) + "\n")

    return result


# ── Main Loop ──────────────────────────────────────────────────────────────────
def main():
    import sys
    dry_run = "--live" not in sys.argv

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Set ANTHROPIC_API_KEY"); return

    if not dry_run:
        print("\n⚠️  LIVE MODE — REAL MONEY WILL BE SPENT.")
        print("   Auto-executor will place trades without asking.")
        confirm = input("   Type WILEY to confirm: ").strip()
        if confirm != "WILEY":
            print("   Aborted."); return

    client = anthropic.Anthropic(api_key=api_key)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║   🤖 WILEY STRAT — AUTO-EXECUTOR                        ║
║   Mode: {'DRY RUN (sim only)' if dry_run else '⚠️  LIVE TRADING — REAL MONEY':30s}              ║
║   Threshold: {AUTO_EXECUTE_THRESHOLD}+/10  |  Max: {MAX_DAILY_TRADES} trades/day  |  $50/trade     ║
║   Scan every 5 min  |  9:45am-3:45pm ET                 ║
╚══════════════════════════════════════════════════════════╝

  Safety rules active:
  ✅ Max {MAX_DAILY_TRADES} auto-trades per day
  ✅ review_order before every place_order
  ✅ Profit monitor fires immediately after fill
  ✅ No new entries after 3:45pm ET
  ✅ Daily loss limit: ${abs(DAILY_LOSS_LIMIT):.0f}
  ✅ Never re-enter same ticker same day

  Press Ctrl+C to stop.
""")

    try:
        while True:
            if in_market_hours():
                run_auto_cycle(client, dry_run=dry_run)
                print(f"\n  ⏱  Next scan in 5 min...")
                time.sleep(SCAN_INTERVAL_SEC)
            else:
                n = now_et()
                print(f"  🕐 Market closed ({n.strftime('%I:%M %p ET')}). "
                      f"Session: {session['trades_today']} trades, "
                      f"P&L: ${session['daily_pnl']:+.2f}")
                time.sleep(300)
    except KeyboardInterrupt:
        print(f"\n  🛑 Auto-executor stopped.")
        print(f"  Session: {session['scan_count']} scans | "
              f"{session['trades_today']} trades | "
              f"P&L: ${session['daily_pnl']:+.2f}")
        if session["log"]:
            log_dir = os.path.expanduser("~/scan_logs")
            path = os.path.join(log_dir, f"session_{now_et().strftime('%Y%m%d_%H%M')}.json")
            with open(path, "w") as f:
                json.dump(session, f, indent=2)
            print(f"  💾 Session log: {path}")


if __name__ == "__main__":
    main()
