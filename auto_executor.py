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

# Load .env if present (never commit .env to git)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

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
POSITION_SIZE_USD      = 25.0   # Per trade — lowered to match account cash
MAX_DAILY_TRADES       = 3      # Max auto-trades per day
DAILY_LOSS_LIMIT       = -75.0  # Stop trading for the day if hit (3x $25)
SCAN_INTERVAL_SEC      = 300    # Scan every 5 minutes

# Option targets (2DTE default)
OPTION_PROFIT_TARGET   = 0.50   # +50%
OPTION_STOP_LOSS       = 0.30   # -30%
SHARE_PROFIT_TARGET    = 0.05   # +5%
SHARE_STOP_LOSS        = 0.05   # -5% hard floor (catastrophic backstop)
TRAILING_STOP_PCT      = 0.01   # 1% below session high — MANDATORY

# ── Session State ─────────────────────────────────────────────────────────────
session = {
    "trades_today":   0,
    "daily_pnl":      0.0,
    "executed_syms":  [],    # don't re-enter same ticker
    "halted":         False,
    "scan_count":     0,
    "log":            [],
    "open_positions": {},    # sym → fill_price
    "session_highs":  {},    # sym → highest price seen since entry
    "trailing_stops": {},    # sym → current trailing stop price (high × 0.99)
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

PRIORITY ORDER THIS WEEK:
  1st → Check SSO / SDS / QLD / QID (2x leveraged ETFs) using Casey's full framework
  2nd → If NONE of the 4 ETFs score 7+, fall back to explosion scanner universe

WHY THIS ORDER:
  - These are traded as fractional shares with $50 position size (same as options)
  - 2x leverage gives options-like moves without theta decay
  - Same Casey system: 4 levels, EMA fan, zone plays, price structure
  - Direction: if market bullish → SSO (SPY) or QLD (QQQ) | if bearish → SDS (SPY) or QID (QQQ)
  - Never trade both the long and short of the same index on the same day

STEP 1 — PRIORITY ETF CHECK (do this first every cycle)
  Get quotes for: SSO, SDS, QLD, QID
  Pre-market levels (set ONCE at 9:20am, hold all session):
    PMH = highest price SPY/QQQ traded since 12:00am midnight
    PML = lowest price SPY/QQQ traded since 12:00am midnight
    Pull these using get_equity_historicals (1min bars from midnight).
    These are your Casey zones for the entire session — do not recalculate.

  Determine market direction from SPY/QQQ price action:
    - SPY breaking above PMH/PDH → bullish → evaluate SSO (SPY long) and/or QLD (QQQ long) and/or UWM (IWM long)
    - SPY breaking below PML/PDL → bearish → evaluate SDS (SPY short) and/or QID (QQQ short) and/or TWM (IWM short)
    - SPY between PML and PMH    → chop → skip all 6, go to Step 3

  Score each relevant ETF using Casey's A+ framework (0-10):
    +2  EMA fan aligned on SPY/QQQ (13>48>200 bullish OR 200>48>13 bearish) and spacing out
    +2  15min candle body close above PMH (longs) or below PML (shorts)
    +2  Zone play confirmed + price structure (HH/HL for longs, LH/LL for shorts)
    +1  Candlestick pattern at zone (bull flag, bear flag, wedge, rejection)
    +1  13 EMA pullback entry trigger on 2min chart
    +1  Volume above average on setup candle
    +1  VWAP in agreement with direction

  If any ETF scores 7+ → execute that trade (STOP, skip Step 3)
  If no ETF scores 7+ → proceed to Step 3 (explosion scanner fallback)

STEP 2 — EXECUTE ETF TRADE (if ETF scored 7+)
  1. Check available buying power from get_portfolio — use ALL of it (not a fixed amount)
  2. review_equity_order FIRST for the ETF symbol
  3. If review clean: {"simulate only" if dry_run else "place_equity_order — fractional market buy using full buying power"}
  4. After fill, place ONE limit sell for ALL shares at fill_price * 1.05  (+5% profit target)
  5. DO NOT place a fixed stop-loss order — trailing stop is managed dynamically by the
     Python monitor every 5 minutes (sells if price drops 1% below its session high).
     Initial trailing stop = fill_price * 0.99. It rises with the price, never falls.
  6. Profits roll back into buying power automatically — next trade uses the larger balance
  7. Report: symbol, direction, shares, fill_price, target_price (+5%)

STEP 3 — EXPLOSION SCANNER FALLBACK (only if no ETF setup found)
  Get quotes for the full explosion scanner universe. Score each ticker 0-12:
    +2  EMA fan aligned (proxy: >3% move = fan forming)
    +2  15min above PMH (proxy: >5% = confirmed, 2-5% = forming)
    +2  Zone play + structure confirmed
    +2  ORDER FLOW: appears in Barchart unusual options today
    +1  Barchart top options volume
    +2  Insider buy >$100K today (OpenInsider)
    +1  Volume above 10M average
    -1  Overextended >15%

  Filter:
    → Price $10–$25 (rotation range — skip anything outside this band)
    → Avg daily volume >= 500K shares
    → Score >= {AUTO_EXECUTE_THRESHOLD} for auto-execution
    → Not already in position today

  For score 7+: review_equity_order then {"simulate" if dry_run else "place_equity_order — full buying power market buy"}
  After fill: place ONE limit sell at +5% (profit target only — NO fixed stop order,
  trailing stop managed dynamically by Python monitor at 1% below session high)

STEP 4 — REPORT
Return JSON:
{{
  "scan_time": "...",
  "etf_check": {{
    "market_direction": "BULL/BEAR/CHOP",
    "etf_scores": [{{"sym":"SSO","score":8,"direction":"LONG","reason":"EMA fan + PMH break"}}],
    "etf_executed": true
  }},
  "scores": [{{"sym":"SOFI","score":9,"direction":"LONG","flow":["unusual options"]}}],
  "executed": [{{"sym":"SSO","type":"shares","direction":"LONG",
                 "shares":0.38,"fill_price":64.38,"cost":25.00,
                 "target_price":"$67.60 (+5%, sell all shares)","target_order_id":"...",
                 "trailing_stop_initial":"$63.74 (-1% from fill, rises with price)",
                 "order_id":"...", "status":"filled"}}],
  "alerts": [{{"sym":"QLD","score":6,"reason":"EMA fan forming but not confirmed yet"}}],
  "skipped": [{{"sym":"SDS","reason":"market bullish, wrong direction"}}]
}}

ACCOUNTS: {ACCOUNT}
MODE: {mode}
MAX TRADES TODAY: {MAX_DAILY_TRADES}
POSITION SIZE: ${POSITION_SIZE_USD} (fractional shares ok)
""".strip()


# ── Trailing Stop Monitor ─────────────────────────────────────────────────────
def monitor_positions(client, dry_run=True):
    """Check open positions, update trailing highs, sell if stop hit."""
    if not session["open_positions"]:
        return

    now = now_et()
    positions_data = []
    for sym, fill_price in session["open_positions"].items():
        current_high = session["session_highs"].get(sym, fill_price)
        current_stop = session["trailing_stops"].get(sym, round(fill_price * (1 - TRAILING_STOP_PCT), 4))
        positions_data.append({
            "sym": sym,
            "fill_price": fill_price,
            "session_high": current_high,
            "trailing_stop": current_stop,
        })

    print(f"\n  📡 TRAILING STOP MONITOR | {now.strftime('%I:%M:%S %p ET')}")
    for p in positions_data:
        print(f"     {p['sym']}: high ${p['session_high']:.2f} | stop ${p['trailing_stop']:.2f}")

    monitor_prompt = f"""
TRAILING STOP MONITOR — {now.strftime('%I:%M:%S %p ET')}

Open positions to check:
{json.dumps(positions_data, indent=2)}

INSTRUCTIONS:
1. Call get_equity_positions to confirm which symbols are still held
2. Call get_equity_quotes for each confirmed symbol to get current bid/ask/last price
3. For each position evaluate:
   a. If current_price > session_high → this is a new session high (stop rises with it)
   b. If current_price <= trailing_stop → TRAILING STOP HIT → sell immediately
      {"Use review_equity_order only (DRY RUN — no real sell)" if dry_run else
       "Use place_equity_order: type=market, side=sell, quantity=shares_available_for_sells"}
   c. Otherwise → HOLD, report current price

TRAILING STOP RULE: stop = session_high × {1 - TRAILING_STOP_PCT:.4f} (1% below peak)
The stop only moves UP, never down. Locks in profits as price rises.

Return JSON only:
{{
  "checks": [
    {{
      "sym": "SSO",
      "current_price": 64.50,
      "new_session_high": 65.00,
      "trailing_stop": 64.35,
      "action": "HOLD",
      "reason": "price above stop",
      "shares_sold": null,
      "sell_order_id": null
    }}
  ]
}}
""".strip()

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": monitor_prompt}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"],
    )

    raw = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw += block.text
        elif getattr(block, "type", "") == "mcp_tool_use":
            print(f"  🔧 {block.name}...")

    try:
        clean = raw.strip()
        if "```" in clean:
            for part in clean.split("```"):
                stripped = part.strip()
                if stripped.startswith("{") or stripped.startswith("json"):
                    clean = stripped.replace("json", "", 1).strip()
                    break
        result = json.loads(clean)
    except Exception:
        print(f"  ⚠️  Monitor parse error — raw: {raw[:400]}")
        return

    for check in result.get("checks", []):
        sym = check.get("sym")
        if not sym or sym not in session["open_positions"]:
            continue

        current_price = check.get("current_price", 0)
        new_high = check.get("new_session_high", current_price)
        action = check.get("action", "HOLD")

        # Update trailing high if price made a new peak
        if new_high > session["session_highs"].get(sym, 0):
            session["session_highs"][sym] = new_high
            session["trailing_stops"][sym] = round(new_high * (1 - TRAILING_STOP_PCT), 4)
            print(f"  📈 {sym}: new high ${new_high:.2f} → trailing stop ${session['trailing_stops'][sym]:.2f}")

        if action == "SELL":
            fill_price = session["open_positions"][sym]
            pnl = (current_price - fill_price) / fill_price * POSITION_SIZE_USD
            session["daily_pnl"] += pnl
            del session["open_positions"][sym]
            session["session_highs"].pop(sym, None)
            session["trailing_stops"].pop(sym, None)
            print(f"  🔴 {sym}: TRAILING STOP HIT @ ${current_price:.2f} "
                  f"({'SIMULATED' if dry_run else 'SOLD'}) | "
                  f"P&L: ${pnl:+.2f} | Daily: ${session['daily_pnl']:+.2f}")
            if check.get("sell_order_id"):
                print(f"     Sell order: {check['sell_order_id']}")
            if session["daily_pnl"] <= DAILY_LOSS_LIMIT:
                session["halted"] = True
                print(f"  🛑 Daily loss limit hit (${session['daily_pnl']:.2f}). HALTED.")
        else:
            print(f"  ✅ {sym}: ${current_price:.2f} | "
                  f"stop ${session['trailing_stops'].get(sym, 0):.2f} | HOLD")


# ── Scan + Execute Cycle ──────────────────────────────────────────────────────
def run_auto_cycle(client, dry_run=True, scan_universe=None):
    if scan_universe is None:
        from config import CONFIG
        etfs     = CONFIG["leveraged_etfs"]["tickers"]   # SSO, SDS, QLD, QID — checked first
        primary  = CONFIG["tickers"].get("primary", [])
        on_watch = CONFIG["tickers"].get("on_watch", [])
        catalyst = CONFIG["tickers"].get("catalyst_plays", [])  # any price, fractional only
        # ETFs first; then $10-$25 rotation universe + on-watch; catalyst plays appended last
        explosion = list(dict.fromkeys(primary + on_watch))  # deduped, order preserved
        scan_universe = etfs + [t for t in explosion if t not in etfs] + \
                        [t for t in catalyst if t not in etfs and t not in explosion]

    # Monitor open positions first (trailing stop logic)
    monitor_positions(client, dry_run=dry_run)

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

    from config import CONFIG
    etf_tickers      = CONFIG["leveraged_etfs"]["tickers"]
    catalyst_tickers = CONFIG["tickers"].get("catalyst_plays", [])
    explosion_tickers = [t for t in scan_universe
                         if t not in etf_tickers and t not in catalyst_tickers]

    user_msg = f"""
Run the Wiley Strat scan. PRIORITY ORDER:

1. FIRST — check the leveraged ETFs using Casey's full framework:
   {etf_tickers}
   SPY→SSO/SDS | QQQ→QLD/QID | IWM→UWM/TWM — pick highest scoring, execute best setup
   Determine SPY/QQQ direction, score each relevant ETF, execute if 7+.
   If any ETF scores 7+ → execute it and STOP (skip explosion scanner).

2. FALLBACK — only if NO ETF scored 7+, scan the explosion universe ($10-$25):
   {json.dumps(explosion_tickers[:50])}

3. CATALYST PLAYS — score alongside fallback scan (any price, fractional shares):
   {json.dumps(catalyst_tickers)}
   No price filter — $25 buys fractional shares regardless of share price.
   GOAL: capture upside on any strong mover at all times.
   Score using full Casey framework. Execute if score 7+ AND:
     - Up 3%+ on the day OR breaking a key resistance level on volume
     - For nuclear names (CCJ/BAM/BWXT/CW/LEU/URA/URNM/NUKZ): confirmed Trump EO catalyst = +2 pts
     - For mega-cap tech (NVDA/AMD/MU/AVGO/ARM etc): earnings/product catalyst OR sector rotation surge
   Fractional fill: place $25 order — Robinhood handles the fraction automatically.

Already executed today (skip these): {json.dumps(session['executed_syms'])}
Trades used today: {session['trades_today']}/{MAX_DAILY_TRADES}
Current time: {now.strftime('%I:%M:%S %p ET')}
Option window open: {in_option_window()}
Past 3:45pm force-close: {past_force_close()}

{"USE review_equity_order ONLY — do NOT place real orders (DRY RUN)" if dry_run else
 "EXECUTE LIVE — place_equity_order for real money, fractional shares ok"}
"""

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=build_system_prompt(dry_run),
        messages=[{"role": "user", "content": user_msg}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"],
        tools=[{"type": "web_search_20260209", "name": "web_search"}]
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
            fill_price = t.get("fill_price", 0)
            session["trades_today"] += 1
            session["executed_syms"].append(sym)

            # Initialize trailing stop tracking for this position
            if fill_price > 0:
                session["open_positions"][sym] = fill_price
                session["session_highs"][sym]  = fill_price
                session["trailing_stops"][sym] = round(fill_price * (1 - TRAILING_STOP_PCT), 4)

            trailing_stop_price = session["trailing_stops"].get(sym, 0)
            print(f"  ✅ {sym}: {t.get('type','?')} | {t.get('direction','')} | "
                  f"Cost ${cost:.2f} | Fill ${fill_price:.2f} | "
                  f"Target {t.get('target_price','')} | "
                  f"Trail stop ${trailing_stop_price:.2f} (1% below peak)")
            if t.get("order_id"):
                print(f"     Order ID: {t['order_id']} | Status: {t.get('status','')}")
            session["log"].append({
                "time": now.isoformat(), "sym": sym,
                "type": t.get("type"), "cost": cost, "fill_price": fill_price,
                "trailing_stop_initial": trailing_stop_price, "dry_run": dry_run
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
  ✅ Trailing stop: 1% below session high (MANDATORY — managed every 5 min)
  ✅ Profit target: +5% limit order placed immediately after fill
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
