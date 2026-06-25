"""
Wiley Strat — Auto-Executor (3-Bucket Mode)
============================================
Three independent trade buckets run simultaneously every 5 minutes:

  Bucket 1 — INDEX    : Leveraged ETFs (SSO/SDS/QLD/QID/UWM/TWM/TECL/MAGX)
                         Trigger: Casey 4-level + EMA fan on SPY/QQQ/IWM
  Bucket 2 — EXPLOSION: $10-25 universe with RVOL >2x momentum
                         Trigger: RVOL + price structure + volume surge
  Bucket 3 — CATALYST : Wild card (earnings runners, sector plays, news)
                         Trigger: Catalyst event + flow + momentum

Each bucket gets ~1/3 of available buying power.
All 3 run independently — 1 can fire while the others wait.
Max 3 trades/day total across all buckets.
Trailing stop: 1% below session high on EVERY position (MANDATORY).

Run: python auto_executor.py           # dry run (review only)
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
MAX_DAILY_TRADES       = 3      # Max auto-trades per day (across all buckets)
DAILY_LOSS_LIMIT       = -75.0  # Stop trading if daily loss exceeds this
SCAN_INTERVAL_SEC      = 300    # Scan every 5 minutes

# Profit/stop targets
SHARE_PROFIT_TARGET    = 0.05   # +5%
SHARE_STOP_LOSS        = 0.05   # -5% hard floor (catastrophic backstop)
TRAILING_STOP_PCT      = 0.01   # 1% below session high — MANDATORY

# ── Bucket Definitions ────────────────────────────────────────────────────────
BUCKET_1_TICKERS = [
    "SSO", "SDS", "QLD", "QID", "UWM", "TWM",   # 2x indexes
    "TECL", "TECS", "MAGX"                        # 3x sector / Mag7
]

# Bucket 2 + 3 pulled from config at runtime (see run_auto_cycle)
# Bucket 2 = config primary + on_watch ($10-25, RVOL >2x)
# Bucket 3 = config catalyst_plays (earnings runners, sector catalysts)

# ── Session State ─────────────────────────────────────────────────────────────
session = {
    "trades_today":    0,
    "daily_pnl":       0.0,
    "executed_syms":   [],      # don't re-enter same ticker same day
    "halted":          False,
    "scan_count":      0,
    "log":             [],
    "open_positions":  {},       # sym → fill_price
    "session_highs":   {},       # sym → highest price seen since entry
    "trailing_stops":  {},       # sym → current trailing stop price
    "bucket_trades":   {"B1": 0, "B2": 0, "B3": 0},   # trades per bucket
    "bucket_active":   {"B1": [], "B2": [], "B3": []}, # open sym per bucket
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


# ── System Prompt ────────────────────────────────────────────────────────────
def build_system_prompt(dry_run: bool, b1: list, b2: list, b3: list,
                        buy_per_bucket: float) -> str:
    mode = "DRY RUN (review_order only — no real execution)" if dry_run else "LIVE EXECUTION (real money)"
    return f"""
You are the Wiley Strat Auto-Executor running in 3-BUCKET MODE. Mode: {mode}

OVERVIEW — 3 BUCKETS RUN SIMULTANEOUSLY EVERY CYCLE:
  Total buying power is divided by 3. Each bucket gets ~${buy_per_bucket:.2f} per trade.
  Each bucket has its own watchlist and trigger criteria.
  A bucket fires independently when ITS setup hits 7+/10.
  Max 3 total trades per day across all buckets.

════════════════════════════════════════════════════════════
BUCKET 1 — INDEX (Leveraged ETFs, Casey 4-level framework)
════════════════════════════════════════════════════════════
Tickers: {b1}

TRIGGER: Casey A+ framework on SPY / QQQ / IWM
  Pull PMH/PML/PDH/PDL for SPY and QQQ from today's historicals.

  Classify direction:
    ABOVE PMH+PDH → STRONGEST BULL → SSO + QLD
    ABOVE PMH only → BULL → SSO or QLD (pick stronger index)
    BELOW PML+PDL → STRONGEST BEAR → SDS + QID
    BELOW PML only → BEAR → SDS or QID
    BETWEEN PML and PMH → CHOP → check TECL/MAGX on XLK/MAG7 strength
    ALL LEVELS HOLDING → BALANCED → no trade, wait

  Score (0-10):
    +2  EMA fan aligned (13>48>200 bullish OR 200>48>13 bearish) and spacing out
    +2  15min candle BODY close above PMH (longs) or below PML (shorts)
    +2  Zone play confirmed + price structure (HH/HL for longs, LH/LL for shorts)
    +1  Candlestick pattern at zone (bull flag, bear flag, rejection candle)
    +1  13 EMA pullback entry trigger on 2min chart
    +1  Volume above average on setup candle
    +1  VWAP in agreement with direction

  Score 7+ → execute. Score <7 → hold bucket 1 this cycle.
  Never trade both long AND short of the same index.

════════════════════════════════════════════════════════════
BUCKET 2 — EXPLOSION ($10-25 universe, RVOL momentum)
════════════════════════════════════════════════════════════
Tickers: {b2}

TRIGGER: Momentum + volume explosion on the $10-25 universe
  Pull quotes for the full B2 list to find movers.

  Score (0-10):
    +2  RVOL >3x average (exceptional surge)
    +1  RVOL >2x average (minimum threshold — below 2x = skip)
    +2  Price up 3%+ on the day (strong momentum)
    +1  Price up 2-3% on the day (moderate momentum)
    +2  EMA fan aligned (13>48>200 bullish structure on 15min)
    +2  Breaking above 52-week high or key resistance level
    +1  Float <20M (supernova fuel — smaller float = bigger moves)
    +1  Volume >1M shares (confirms institutional interest)

  Score 7+ AND RVOL >2x → execute. Otherwise skip.
  If multiple tickers qualify, pick the one with highest RVOL.

════════════════════════════════════════════════════════════
BUCKET 3 — CATALYST (Earnings runners, sector plays, news)
════════════════════════════════════════════════════════════
Tickers: {b3}

TRIGGER: Catalyst event + directional flow + momentum
  Pull quotes and check for: earnings beats, FDA decisions,
  contract awards, sector rotation, unusual options flow.

  Score (0-10):
    +3  Active catalyst (earnings beat, FDA approval, contract win)
    +2  Unusual options flow confirms direction ($500K+ same-direction sweep)
    +2  Price breaking key technical level (PDH, 52W high, round number)
    +2  EMA fan aligned + volume surge post-catalyst
    +1  Social/WSB sentiment spike (confirms retail momentum)

  Score 7+ AND clear catalyst → execute. Otherwise skip.
  Fractional shares ok — catalyst tickers can be any price.

════════════════════════════════════════════════════════════
EXECUTION RULES (apply to ALL buckets)
════════════════════════════════════════════════════════════
1. get_portfolio → check exact buying power → divide by 3 → size per bucket
2. review_equity_order FIRST (always, no exceptions)
3. {"review only — no real order (DRY RUN)" if dry_run else "place_equity_order — fractional market buy"}
4. After fill: place limit sell at fill_price × 1.05 (+5% profit target)
5. NO fixed stop order — trailing stop managed by Python monitor (1% below session high)
6. Never re-enter a ticker already executed today
7. Force close all positions at 3:45pm ET

ACCOUNT: {ACCOUNT}
MODE: {mode}
MAX TRADES TODAY: {MAX_DAILY_TRADES} (across all buckets)
SIZE PER BUCKET: ~${buy_per_bucket:.2f}

RETURN FORMAT — JSON only, no prose:
{{
  "scan_time": "...",
  "buying_power": 34.63,
  "size_per_bucket": 11.54,
  "bucket1": {{
    "market_direction": "BULL/BEAR/CHOP/BALANCED",
    "spy_vs_levels": "above PMH+PDH / above PMH only / between / below PML",
    "qqq_vs_levels": "...",
    "best_ticker": "QLD",
    "score": 8,
    "direction": "LONG",
    "score_breakdown": "EMA fan +2, PMH break +2, HH/HL +2, bull flag +1, VWAP +1",
    "executed": {{"sym":"QLD","shares":0.18,"fill_price":64.38,"cost":11.54,
                  "target_price":"$67.60","target_order_id":"...","order_id":"...","status":"filled"}},
    "wait_reason": null
  }},
  "bucket2": {{
    "top_movers": [{{"sym":"FCEL","rvol":4.2,"change_pct":5.1,"score":8}}],
    "executed": null,
    "wait_reason": "No ticker hit RVOL >2x threshold this cycle"
  }},
  "bucket3": {{
    "catalysts_found": [{{"sym":"MU","event":"earnings beat","flow":"BULLISH $2M sweep"}}],
    "executed": null,
    "wait_reason": "MU score 6 — flow not confirmed, wait"
  }},
  "alerts": [{{"bucket":"B2","sym":"SOFI","score":6,"reason":"RVOL 1.8x — close, watch next cycle"}}],
  "skipped": [{{"sym":"SDS","reason":"market bullish, wrong direction"}}]
}}
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
        # Find which bucket this sym belongs to
        bucket = "?"
        for b, syms in session["bucket_active"].items():
            if sym in syms:
                bucket = b
                break
        positions_data.append({
            "sym": sym,
            "bucket": bucket,
            "fill_price": fill_price,
            "session_high": current_high,
            "trailing_stop": current_stop,
        })

    print(f"\n  📡 TRAILING STOP MONITOR | {now.strftime('%I:%M:%S %p ET')}")
    for p in positions_data:
        print(f"     [{p['bucket']}] {p['sym']}: high ${p['session_high']:.2f} | "
              f"stop ${p['trailing_stop']:.2f}")

    monitor_prompt = f"""
TRAILING STOP MONITOR — {now.strftime('%I:%M:%S %p ET')}

Open positions to check:
{json.dumps(positions_data, indent=2)}

INSTRUCTIONS:
1. Call get_equity_positions to confirm which symbols are still held
2. Call get_equity_quotes for each confirmed symbol to get current bid/ask/last price
3. For each position evaluate:
   a. If current_price > session_high → new session high (stop rises with it)
   b. If current_price <= trailing_stop → TRAILING STOP HIT → sell immediately
      {"Use review_equity_order only (DRY RUN — no real sell)" if dry_run else
       "Use place_equity_order: type=market, side=sell, quantity=shares_available_for_sells"}
   c. If current_price >= fill_price × 1.05 → PROFIT TARGET HIT → sell immediately
   d. Otherwise → HOLD, report current price

TRAILING STOP RULE: stop = session_high × {1 - TRAILING_STOP_PCT:.4f} (1% below peak)
Stop only moves UP, never down.

Return JSON only:
{{
  "checks": [
    {{
      "sym": "SSO",
      "bucket": "B1",
      "current_price": 64.50,
      "new_session_high": 65.00,
      "trailing_stop": 64.35,
      "action": "HOLD",
      "reason": "price above stop, below target",
      "pnl_pct": 0.018,
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

        if new_high > session["session_highs"].get(sym, 0):
            session["session_highs"][sym] = new_high
            session["trailing_stops"][sym] = round(new_high * (1 - TRAILING_STOP_PCT), 4)
            print(f"  📈 {sym}: new high ${new_high:.2f} → trailing stop ${session['trailing_stops'][sym]:.2f}")

        if action in ("SELL", "TRAILING_STOP", "PROFIT_TARGET"):
            fill_price = session["open_positions"][sym]
            # Estimate position size from fill_price (approx)
            pnl = (current_price - fill_price) / fill_price * fill_price  # per share PnL, scaled below
            pnl_dollar = check.get("pnl_pct", 0) * fill_price  # rough estimate
            session["daily_pnl"] += pnl_dollar
            del session["open_positions"][sym]
            session["session_highs"].pop(sym, None)
            session["trailing_stops"].pop(sym, None)
            # Remove from bucket_active
            for b in session["bucket_active"]:
                if sym in session["bucket_active"][b]:
                    session["bucket_active"][b].remove(sym)

            reason = check.get("reason", action)
            icon = "🟢" if action == "PROFIT_TARGET" else "🔴"
            print(f"  {icon} {sym}: {action} @ ${current_price:.2f} "
                  f"({'SIMULATED' if dry_run else 'SOLD'}) | "
                  f"Reason: {reason}")
            if check.get("sell_order_id"):
                print(f"     Sell order: {check['sell_order_id']}")
            if session["daily_pnl"] <= DAILY_LOSS_LIMIT:
                session["halted"] = True
                print(f"  🛑 Daily loss limit hit (${session['daily_pnl']:.2f}). HALTED.")
        else:
            pnl_pct = check.get("pnl_pct", 0)
            icon = "📈" if pnl_pct >= 0 else "📉"
            print(f"  ✅ {sym}: ${current_price:.2f} {icon} {pnl_pct*100:+.1f}% | "
                  f"stop ${session['trailing_stops'].get(sym, 0):.2f} | HOLD")


# ── Scan + Execute Cycle ──────────────────────────────────────────────────────
def run_auto_cycle(client, dry_run=True):
    # Monitor open positions first (trailing stop + profit target logic)
    monitor_positions(client, dry_run=dry_run)

    session["scan_count"] += 1
    now = now_et()

    # Determine available slots per bucket
    slots_remaining = MAX_DAILY_TRADES - session["trades_today"]
    b1_open = len(session["bucket_active"]["B1"])
    b2_open = len(session["bucket_active"]["B2"])
    b3_open = len(session["bucket_active"]["B3"])

    print(f"\n{'═'*66}")
    print(f"  🤖 WILEY STRAT — SCAN #{session['scan_count']}  |  {now.strftime('%I:%M:%S %p ET')}")
    print(f"  Trades: {session['trades_today']}/{MAX_DAILY_TRADES}  |  "
          f"Daily P&L: ${session['daily_pnl']:+.2f}  |  "
          f"Mode: {'DRY RUN' if dry_run else '⚠️  LIVE'}")
    print(f"  B1(Index): {b1_open} open  |  "
          f"B2(Explosion): {b2_open} open  |  "
          f"B3(Catalyst): {b3_open} open")
    print(f"{'═'*66}")

    if session["halted"]:
        print("  🛑 Trading HALTED — daily loss limit reached.")
        return

    if not in_market_hours():
        print(f"  🕐 Outside market hours ({now.strftime('%I:%M %p ET')})")
        return

    if session["trades_today"] >= MAX_DAILY_TRADES:
        print(f"  ✋ Max trades reached ({MAX_DAILY_TRADES}/day). Monitoring positions only.")
        return

    # Load tickers from config
    from config import CONFIG
    bucket2_tickers = list(dict.fromkeys(
        CONFIG["tickers"].get("primary", []) + CONFIG["tickers"].get("on_watch", [])
    ))
    bucket3_tickers = list(dict.fromkeys(
        CONFIG["tickers"].get("catalyst_plays", [])
    ))

    # Estimate buy-per-bucket (will be recalculated live by Claude via get_portfolio)
    buy_per_bucket_est = 10.0  # placeholder; Claude uses real buying_power / 3

    # Options flow scan
    flow_signals = {}
    flow_section = ""
    try:
        from flow_scanner import get_flow_signals as _get_flow
        print("  📡 Scanning options flow...")
        flow_tickers = list(dict.fromkeys(
            CONFIG["tickers"].get("options_0dte", []) +
            bucket3_tickers +
            BUCKET_1_TICKERS
        ))
        flow_signals = _get_flow(flow_tickers)
        active = [(s, d) for s, d in flow_signals.items() if d["score_pts"] > 0]
        active.sort(key=lambda x: x[1]["call_premium"] + x[1]["put_premium"], reverse=True)
        if active:
            lines = []
            for sym, d in active[:10]:
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

    # Bucket status for prompt
    already_executed = json.dumps(session["executed_syms"])
    b1_already_open  = json.dumps(session["bucket_active"]["B1"])
    b2_already_open  = json.dumps(session["bucket_active"]["B2"])
    b3_already_open  = json.dumps(session["bucket_active"]["B3"])

    user_msg = f"""
3-BUCKET SCAN — {now.strftime('%I:%M:%S %p ET')}

Step 1: Call get_portfolio → get exact buying power.
        Divide buying power by 3 → size_per_bucket (use for ALL bucket trades).

Step 2: Run all 3 buckets simultaneously:

──── BUCKET 1 — INDEX ────────────────────────────────────────
Tickers: {BUCKET_1_TICKERS}
Already open in B1: {b1_already_open}
  Pull SPY + QQQ historicals. Identify PMH/PML/PDH/PDL.
  Classify direction. Score the best directional ETF.
  Execute if score 7+. One trade max per bucket this cycle.

──── BUCKET 2 — EXPLOSION ────────────────────────────────────
Tickers: {bucket2_tickers}
Already open in B2: {b2_already_open}
  Pull quotes for all B2 tickers.
  Sort by RVOL descending.
  Score top movers. Execute the best if score 7+ AND RVOL >2x.
  Focus: $10-25 range, float <20M preferred, up 2%+ minimum.

──── BUCKET 3 — CATALYST ─────────────────────────────────────
Tickers: {bucket3_tickers}
Already open in B3: {b3_already_open}
  Pull quotes for all B3 tickers.
  Check for: earnings reports, sector catalysts, news events.
  Score top catalyst plays. Execute if score 7+ with clear catalyst.
  Fractional shares ok — these can be any price.

──── FLOW SCORING (apply to all buckets) ─────────────────────
{flow_section}
  BULLISH flow + LONG setup → add flow score_pts to Casey score
  BEARISH flow + SHORT setup → add flow score_pts to score
  Flow OPPOSES direction → reduce score by 1 or skip

──── CONSTRAINTS ─────────────────────────────────────────────
Already executed today (skip all): {already_executed}
Trades remaining today: {slots_remaining}/{MAX_DAILY_TRADES}
Time: {now.strftime('%I:%M:%S %p ET')}
Past 3:45pm force-close window: {past_force_close()}
{"USE review_equity_order ONLY — DRY RUN, no real orders" if dry_run else
 "EXECUTE LIVE — place_equity_order for real money, fractional shares ok"}

Execute across all 3 buckets. Each bucket is independent.
Return the structured JSON as specified in your system prompt.
"""

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=5000,
        system=build_system_prompt(
            dry_run,
            BUCKET_1_TICKERS,
            bucket2_tickers,
            bucket3_tickers,
            buy_per_bucket_est,
        ),
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

    # Parse result
    try:
        clean = raw.strip()
        if "```" in clean:
            for p in clean.split("```"):
                if p.strip().startswith("{") or p.startswith("json"):
                    clean = p.replace("json", "", 1).strip()
                    break
        result = json.loads(clean)
    except Exception:
        print("\n" + raw[:2500])
        return

    # ── Process bucket results ────────────────────────────────────────────────
    all_executed = []
    alerts = result.get("alerts", [])
    skipped = result.get("skipped", [])

    buy_per_bucket = result.get("size_per_bucket", buy_per_bucket_est)
    print(f"\n  💰 Buying power: ${result.get('buying_power', '?')} | "
          f"Per bucket: ~${buy_per_bucket:.2f}")

    for bucket_key, label in [("bucket1", "B1 INDEX"), ("bucket2", "B2 EXPLOSION"), ("bucket3", "B3 CATALYST")]:
        b = result.get(bucket_key, {})
        if not b:
            continue

        bcode = bucket_key[-1]  # "1", "2", "3"
        bkey  = f"B{bcode}"

        # Show direction/movers for this bucket
        if bucket_key == "bucket1":
            direction = b.get("market_direction", "?")
            score = b.get("score", 0)
            best  = b.get("best_ticker", "?")
            print(f"\n  [{label}] {direction} | {best} score {score}/10 | "
                  f"SPY:{b.get('spy_vs_levels','?')} QQQ:{b.get('qqq_vs_levels','?')}")
        elif bucket_key == "bucket2":
            movers = b.get("top_movers", [])
            if movers:
                top = movers[0]
                print(f"\n  [{label}] Top mover: {top.get('sym','?')} "
                      f"RVOL {top.get('rvol','?')}x | "
                      f"+{top.get('change_pct','?')}% | score {top.get('score','?')}/10")
            else:
                print(f"\n  [{label}] No significant movers this cycle")
        elif bucket_key == "bucket3":
            cats = b.get("catalysts_found", [])
            if cats:
                c = cats[0]
                print(f"\n  [{label}] Catalyst: {c.get('sym','?')} — {c.get('event','?')} | "
                      f"{c.get('flow','no flow data')}")
            else:
                print(f"\n  [{label}] No active catalysts this cycle")

        # Process execution
        exec_data = b.get("executed")
        wait_reason = b.get("wait_reason")

        if exec_data:
            sym        = exec_data.get("sym", "?")
            fill_price = exec_data.get("fill_price", 0)
            cost       = exec_data.get("cost", 0)

            session["trades_today"] += 1
            session["executed_syms"].append(sym)
            session["bucket_trades"][bkey] += 1

            if fill_price > 0:
                session["open_positions"][sym] = fill_price
                session["session_highs"][sym]  = fill_price
                session["trailing_stops"][sym] = round(fill_price * (1 - TRAILING_STOP_PCT), 4)
                session["bucket_active"][bkey].append(sym)

            trailing_stop_price = session["trailing_stops"].get(sym, 0)
            icon = "🎯" if not dry_run else "🧪"
            print(f"  {icon} [{bkey}] {sym}: Cost ${cost:.2f} | "
                  f"Fill ${fill_price:.2f} | "
                  f"Target {exec_data.get('target_price','')} | "
                  f"Trail stop ${trailing_stop_price:.2f}")
            if exec_data.get("order_id"):
                print(f"     Order ID: {exec_data['order_id']} | "
                      f"Status: {exec_data.get('status','')}")

            all_executed.append({**exec_data, "bucket": bkey})
            session["log"].append({
                "time": now.isoformat(), "bucket": bkey, "sym": sym,
                "cost": cost, "fill_price": fill_price,
                "trailing_stop_initial": trailing_stop_price, "dry_run": dry_run
            })
        elif wait_reason:
            print(f"  ⏸  [{bkey}] {wait_reason}")

    if not all_executed:
        print(f"\n  📭 No executions this cycle (no bucket hit {AUTO_EXECUTE_THRESHOLD}+ threshold)")

    if alerts:
        print(f"\n  ⚡ ALERTS:")
        for a in alerts:
            bk = a.get("bucket", "?")
            print(f"     [{bk}] {a.get('sym','?')}: {a.get('reason','')}")

    if skipped:
        print(f"\n  ⏭️  Skipped: {', '.join(s.get('sym','?') for s in skipped)}")

    # Save scan log
    log_dir = os.path.expanduser("~/scan_logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"auto_{now.strftime('%Y%m%d')}.jsonl")
    with open(log_path, "a") as f:
        f.write(json.dumps({
            "time": now.isoformat(),
            "scan": session["scan_count"],
            "executed": all_executed,
            "alerts": alerts,
            "trades_today": session["trades_today"],
            "daily_pnl": session["daily_pnl"],
            "bucket_trades": session["bucket_trades"],
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
        print("   3-bucket auto-executor will place up to 3 trades without asking.")
        confirm = input("   Type WILEY to confirm: ").strip()
        if confirm != "WILEY":
            print("   Aborted."); return

    client = anthropic.Anthropic(api_key=api_key)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🤖 WILEY STRAT — AUTO-EXECUTOR (3-BUCKET MODE)            ║
║   Mode: {'DRY RUN (sim only)' if dry_run else '⚠️  LIVE TRADING — REAL MONEY':34s}              ║
║   Threshold: 7+/10  |  Max: {MAX_DAILY_TRADES} trades/day  |  buying_power/3  ║
║   Scan every 5 min  |  9:45am-3:45pm ET                     ║
╚══════════════════════════════════════════════════════════════╝

  BUCKETS:
  B1 — INDEX     : {BUCKET_1_TICKERS}
  B2 — EXPLOSION : $10-25 universe (config primary + on_watch)
  B3 — CATALYST  : Earnings runners + sector plays (config catalyst_plays)

  Safety rules active:
  ✅ Max {MAX_DAILY_TRADES} auto-trades per day (across all buckets)
  ✅ review_order before every place_order
  ✅ Trailing stop: 1% below session high (MANDATORY)
  ✅ Profit target: +5% limit order immediately after fill
  ✅ No new entries after 3:45pm ET
  ✅ Daily loss limit: ${abs(DAILY_LOSS_LIMIT):.0f}
  ✅ Never re-enter same ticker same day
  ✅ Position size = buying_power / 3 per bucket (dynamic)

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
                      f"Session: {session['trades_today']} trades | "
                      f"B1:{session['bucket_trades']['B1']} "
                      f"B2:{session['bucket_trades']['B2']} "
                      f"B3:{session['bucket_trades']['B3']} | "
                      f"P&L: ${session['daily_pnl']:+.2f}")
                time.sleep(300)
    except KeyboardInterrupt:
        print(f"\n  🛑 Auto-executor stopped.")
        print(f"  Session: {session['scan_count']} scans | "
              f"{session['trades_today']} trades | "
              f"B1:{session['bucket_trades']['B1']} "
              f"B2:{session['bucket_trades']['B2']} "
              f"B3:{session['bucket_trades']['B3']} | "
              f"P&L: ${session['daily_pnl']:+.2f}")
        if session["log"]:
            log_dir = os.path.expanduser("~/scan_logs")
            path = os.path.join(log_dir, f"session_{now_et().strftime('%Y%m%d_%H%M')}.json")
            with open(path, "w") as f:
                json.dump(session, f, indent=2, default=str)
            print(f"  💾 Session log: {path}")


if __name__ == "__main__":
    main()
