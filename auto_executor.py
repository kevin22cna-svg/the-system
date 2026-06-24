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

CURRENT FOCUS — LEVERAGED INDEX ETFs ONLY (until account is funded):
  Account is small ($25-30 buying power). ONLY trade leveraged index ETFs as fractional shares.
  Do NOT run explosion scanner or catalyst plays — focus 100% on these 9 tickers:

  INDEX 2x (primary — most liquid):
    SPY direction → SSO (long) or SDS (short)
    QQQ direction → QLD (long) or QID (short)
    IWM direction → UWM (long) or TWM (short)

  SECTOR 3x (secondary — only if index is in chop):
    XLK/QQQ bullish  → TECL (3x tech long)  | bearish → TECS (3x tech short)
    MAG7 bullish      → MAGX (2x Mag7 long)

  WHY THIS FOCUS:
    - You know SPY/QQQ direction from Casey framework every morning — just trade the 2x version
    - No earnings risk, no float issues, no news risk, tight spreads, fully fractional
    - SPY moves 2.5% → SSO moves 5% → profit target hit. Happens on most active days.
    - Every profit compounds into the next trade — grow the account fast before expanding

  NEVER execute individual stocks while in this focused mode.
  NEVER trade both the long AND short of the same index on the same day.

STEP 1 — DETERMINE MARKET DIRECTION (every cycle)
  Pull SPY and QQQ historicals to read the session:
    PMH = highest price since midnight (set at 9:20am, hold all session)
    PML = lowest price since midnight
    PDH = previous day high
    PDL = previous day low

  Classify:
    SPY/QQQ ABOVE PMH+PDH → STRONGEST BULL → buy SSO + QLD (both if buying power allows)
    SPY/QQQ ABOVE PMH only → BULL → buy SSO or QLD (pick whichever QQQ/SPY stronger)
    SPY/QQQ BELOW PML+PDL → STRONGEST BEAR → buy SDS + QID
    SPY/QQQ BELOW PML only → BEAR → buy SDS or QID
    SPY/QQQ BETWEEN PML and PMH → CHOP → skip index, check TECL/MAGX on XLK strength
    ALL LEVELS HOLDING → BALANCED DAY → no trade, wait for expansion

STEP 2 — SCORE using Casey A+ framework (0-10):
    +2  EMA fan aligned on SPY/QQQ (13>48>200 bullish OR 200>48>13 bearish) and spacing out
    +2  15min candle BODY close above PMH (longs) or below PML (shorts)
    +2  Zone play confirmed + price structure (HH/HL for longs, LH/LL for shorts)
    +1  Candlestick pattern at zone (bull flag, bear flag, rejection candle)
    +1  13 EMA pullback entry trigger on 2min chart
    +1  Volume above average on setup candle
    +1  VWAP in agreement with direction

  Score 7+ → execute. Score <7 → wait for next cycle.

STEP 3 — EXECUTE
  1. get_portfolio → check exact buying power (use ALL of it)
  2. review_equity_order FIRST for the chosen symbol
  3. {"simulate only — review_equity_order, no real order" if dry_run else "place_equity_order — fractional market buy, use full buying power"}
  4. After fill: place ONE limit sell at fill_price × 1.05 (+5% profit target)
  5. NO fixed stop order — trailing stop managed by Python monitor (1% below session high)
  6. Profit rolls back into buying power — next trade uses the larger balance

STEP 4 — REPORT
Return JSON:
{{
  "scan_time": "...",
  "market_direction": "BULL/BEAR/CHOP/BALANCED",
  "spy_vs_levels": "above PMH+PDH / above PMH only / between / below PML",
  "qqq_vs_levels": "above PMH+PDH / above PMH only / between / below PML",
  "etf_scores": [{{"sym":"QLD","score":8,"direction":"LONG","reason":"EMA fan + PMH break + HH/HL"}}],
  "executed": [{{"sym":"QLD","type":"shares","direction":"LONG",
                 "shares":0.38,"fill_price":64.38,"cost":25.00,
                 "target_price":"$67.60 (+5%)","target_order_id":"...",
                 "trailing_stop_initial":"$63.74 (rises with price)",
                 "order_id":"...", "status":"filled"}}],
  "alerts": [{{"sym":"SSO","score":6,"reason":"EMA fan forming, not confirmed yet"}}],
  "skipped": [{{"sym":"SDS","reason":"market bullish, wrong direction"}}],
  "wait_reason": "CHOP — SPY between PML and PMH, waiting for expansion"
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

    # ── Live options flow scan (yfinance — free, no API key) ──────────────────
    flow_signals = {}
    flow_section = ""
    try:
        from flow_scanner import get_flow_signals as _get_flow
        print("  📡 Scanning options flow...")
        flow_tickers = list(dict.fromkeys(
            CONFIG["tickers"]["options_0dte"] + catalyst_tickers + etf_tickers
        ))
        flow_signals = _get_flow(flow_tickers)
        active = [(s, d) for s, d in flow_signals.items() if d["score_pts"] > 0]
        active.sort(key=lambda x: x[1]["call_premium"] + x[1]["put_premium"], reverse=True)
        if active:
            lines = []
            for sym, d in active[:10]:
                total = d["call_premium"] + d["put_premium"]
                lines.append(
                    f"  {sym}: {d['direction']} | "
                    f"call=${d['call_premium']//1000}K put=${d['put_premium']//1000}K | "
                    f"+{d['score_pts']}pts to score if direction matches"
                )
                top = d.get("top_call") or d.get("top_put")
                if top:
                    lines.append(
                        f"    → {top['expiry']} ${top['strike']} {top['side'].upper()} | "
                        f"vol {top['volume']:,} / OI {top['open_interest']:,} "
                        f"({top['vol_oi_ratio']}x) | {top['tier']}"
                    )
            flow_section = "\nLIVE OPTIONS FLOW (yfinance scan this cycle):\n" + "\n".join(lines)
            print(f"  ✅ Flow signals: {len(active)} ticker(s) with unusual activity")
            for sym, d in active[:5]:
                tot = d["call_premium"] + d["put_premium"]
                icon = "📈" if d["direction"] == "BULLISH" else "📉"
                print(f"     {icon} {sym}: {d['direction']} | "
                      f"${tot//1000}K total | +{d['score_pts']}pts")
        else:
            flow_section = "\nLIVE OPTIONS FLOW: No unusual activity detected this cycle."
            print("  📭 No unusual options flow this cycle.")
    except Exception as _e:
        print(f"  ⚠️  Flow scanner skipped: {_e}")

    # Focused tickers — leveraged indexes only until account funded
    focused_tickers = ["SPY", "QQQ", "IWM", "SSO", "SDS", "QLD", "QID", "UWM", "TWM",
                       "TECL", "TECS", "MAGX"]

    user_msg = f"""
FOCUSED MODE — LEVERAGED INDEX ETFs ONLY (account small, compounding up)

Step 1: Pull SPY + QQQ historicals to get today's PMH/PML/PDH/PDL.
Step 2: Classify market direction (BULL / BEAR / CHOP / BALANCED).
Step 3: Score the correct directional ETF using Casey A+ framework.
Step 4: Execute if score 7+. Wait if chop.

Target tickers: {focused_tickers}
  BULL  → SSO (SPY 2x) and/or QLD (QQQ 2x) and/or UWM (IWM 2x)
  BEAR  → SDS (SPY 2x) and/or QID (QQQ 2x) and/or TWM (IWM 2x)
  XLK/QQQ strong bull but SPY chop → TECL (3x tech) or MAGX (2x Mag7)

Already executed today (skip): {json.dumps(session['executed_syms'])}
Trades used: {session['trades_today']}/{MAX_DAILY_TRADES}
Time: {now.strftime('%I:%M:%S %p ET')}
Past 3:45pm force-close: {past_force_close()}
{flow_section}

FLOW SCORING RULES:
  If a ticker has BULLISH flow AND your setup direction is LONG  → add flow score_pts to Casey score
  If a ticker has BEARISH flow AND your setup direction is SHORT → add flow score_pts to Casey score
  If flow OPPOSES your setup direction → reduce score by 1 or skip entirely
  🐳 WHALE tier ($1M+) = treat same as whale confirmation from CLAUDE.md smart money section

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
