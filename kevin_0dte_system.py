"""
Kevin's Combined 0DTE + Casey EMA System
=========================================
Merges Kevin's 0DTE confluence rules with Casey's EMA fan methodology.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEVIN'S 0DTE RULES (baseline):
  Instruments:  SPY / QQQ / IWM
  Window:       9:45am – 3:45pm ET
  Entry:        3/5 confluence score minimum
  Profit:       +25% on option premium
  Stop:         -25% on option premium
  Size:         $15 per trade

CASEY'S EMA FAN RULES (layered on top):
  EMAs:         13 / 48 / 200 on 2min chart
  Confirm:      15min candle close above/below key level
  Bullish fan:  13 on top → 48 middle → 200 bottom (spaced out)
  Bearish fan:  200 on top → 48 middle → 13 bottom (spaced out)
  No trade:     EMAs bunched/crossed — no momentum present
  Entry:        2min 13 EMA pullback after 15min confirms

KEY LEVELS (priority order):
  1. PDH / PDL  (Previous Day High/Low)
  2. PMH / PML  (Pre-Market High/Low)
  3. VWAP
  4. Multiday support/resistance zones

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMBINED CONFLUENCE SCORING (0–10):

  TREND FILTER (must pass — no trade if fails):
    ✅ EMA fan aligned + spaced out (bullish OR bearish)
    ✅ 15min candle closed above PMH (calls) OR below PDL (puts)
    ❌ EMAs bunched = NO TRADE regardless of other signals

  VOLUME FILTER (Hard Gate — checked BEFORE scoring):
    → Underlying stock: avg daily volume >= 10,000,000 shares
    → Option contract: volume >= 500 contracts today (real activity)
    → Option open interest: >= 1,000 contracts (real liquidity)
    → Bid/ask spread: <= $0.10 on options under $1.00
                      <= 5% of mark price on options over $1.00
    → REJECT if any of these fail — wide spreads kill profitability
    → "You lose 10-20% of premium just on the spread if you ignore this"

  CONFLUENCE POINTS:
    +2  EMA fan fully aligned & spacing out (13/48/200 ordered)
    +2  15min close confirms direction (above PMH = calls, below PDL = puts)
    +2  Price at key level retest (PDH/PDL/PMH/VWAP acting as support/resistance)
    +1  2min 13 EMA pullback in trend direction (Casey entry trigger)
    +1  Volume above average on the setup candle
    +1  VWAP in agreement with trade direction
    +1  No chop zone between PDH and PMH (clean air above/below)

  Score 7–10 → 🔥 PRIME SETUP — enter 0DTE
  Score 5–6  → ⚡ DEVELOPING — wait for one more confirmation
  Score <5   → 🚫 NO TRADE — EMAs not aligned or level not confirmed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOLES PLUGGED:
  1. Fake breakout filter: require 15min CLOSE not just a wick
  2. Chop filter: EMAs must be spaced, not bunched
  3. Retest trap: first 2 candles wick = wait for 3rd close (Casey rule)
  4. PDH/PMH gap trap: if PDH and PMH are close (<0.2%) = chop zone, skip
  5. Time filter: no new entries after 3:45pm ET (theta decay too aggressive)
  6. Direction lock: once bearish fan confirmed, only puts — no flip-flopping
  7. Exit rule: 25% profit OR 25% stop OR 3:45pm forced exit (whichever first)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import anthropic
import json
import os
from datetime import datetime
import pytz

# ── Config ───────────────────────────────────────────────────────────────────
ET = pytz.timezone("America/New_York")

# Casey's full universe — indexes + mega caps
# Same 4-level system applies to all
INSTRUMENTS = [
    # Indexes (primary — most liquid, tightest spreads)
    "SPY", "QQQ", "IWM",
    # Mega caps (Casey's secondary universe)
    # Better level respect, more whale data, deeper options chains
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
    "META", "TSLA", "AVGO", "AMD", "PLTR",
]

# Why mega caps work with Casey's system:
# 1. PDH/PDL/PMH/PML levels watched by millions = self-fulfilling zones
# 2. Tighter bid/ask = cleaner fills on options
# 3. More whale/unusual flow data available
# 4. Higher liquidity = easier in/out without slippage
# 5. Same exact EMA fan + zone play + structure rules apply

ENTRY_WINDOW_START = (9, 45)   # 9:45am ET
ENTRY_WINDOW_END   = (15, 45)  # 3:45pm ET

MIN_CONFLUENCE     = 5         # Minimum to consider entry (7 = prime)
PRIME_CONFLUENCE   = 7         # Auto-trigger threshold
# DTE-based targets (from multi-DTE backtest — 2-3 DTE is the sweet spot)
DTE_TARGETS = {
    0: {"profit": 25, "stop": 25},   # 0DTE: tight, theta-driven
    1: {"profit": 40, "stop": 30},   # 1DTE
    2: {"profit": 50, "stop": 30},   # 2DTE — strong win rate
    3: {"profit": 60, "stop": 35},   # 3DTE — best win rate 86.5%
    5: {"profit": 75, "stop": 35},   # 5DTE — highest total P&L
}
DEFAULT_DTE        = 2         # Default to 2DTE swing (best risk/reward)
PROFIT_TARGET_PCT  = DTE_TARGETS[DEFAULT_DTE]["profit"]
STOP_LOSS_PCT      = DTE_TARGETS[DEFAULT_DTE]["stop"]
POSITION_SIZE_USD  = 15        # Per trade

MCP_SERVER = {
    "type": "url",
    "url": "https://agent.robinhood.com/mcp/trading",
    "name": "robinhood-mcp"
}

# ── Master System Prompt ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are Kevin's 0DTE options trading assistant combining two proven systems:
  1. Kevin's 3/5 confluence 0DTE rules (SPY/QQQ/IWM)
  2. Casey's EMA fan + key level methodology

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — GET CURRENT DATA
Pull real-time quotes for SPY, QQQ, IWM.
You need: current price, % change from previous close, previous close.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — EMA FAN CHECK (Casey's Filter — HARD GATE)
Using the current price vs prior close, assess EMA alignment:

BULLISH FAN (calls only):
  - 13 EMA > 48 EMA > 200 EMA
  - EMAs spreading apart (not bunched)
  - Price pulling back to 13 EMA on 2min = entry trigger

BEARISH FAN (puts only):
  - 200 EMA > 48 EMA > 13 EMA
  - EMAs spreading apart downward
  - Price bouncing up to 13 EMA on 2min = short entry trigger

CHOPPY (NO TRADE):
  - EMAs bunched together / crossing / no clear order
  - Do NOT enter any trade in chop — wait for fan to develop

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2.5 — DAY READING FRAMEWORK (Casey's 4 Levels)

PRE-MARKET PREP (mark ALL 4 before open every single day):
  ① PDH — Previous Day High    → major resistance
  ② PDL — Previous Day Low     → major support
  ③ PMH — Pre-Market High      → first bullish sign if broken
  ④ PML — Pre-Market Low       → first bearish sign if broken

DAY TYPE CLASSIFICATION (read in this order):
  STRONGEST BULL:  Breaks BOTH PDH + PMH → buyers in total control → CALLS, join the trend
  BULL TREND:      Breaks PDH only → buyers in control → favor CALLS until next resistance
  BREAKOUT WATCH:  Breaks PMH only → first bullish sign → watch for PDH break next
  CHOP ZONE:       Price between PML and PMH → avoid, wait for expansion
  BREAKDOWN WATCH: Breaks PML only → first bearish sign → watch for PDL break next
  BEAR TREND:      Breaks PDL only → sellers in control → favor PUTS until next support
  BALANCED DAY:    Holds all 4 levels → range day → cautious, reduced size

KEY RULES:
  → "Wait for price to break ABOVE PMH before going long"
  → "Wait for price to break UNDER PML before going short"  
  → "Never try to short stocks that are breaking resistance — join the trend"
  → Price between PML and PMH = choppier conditions = wait for expansion
  → PMH becomes SUPPORT after broken above (S/R flip) → calls off PMH support
  → PML becomes RESISTANCE after broken below (S/R flip) → puts off PML resistance
  → Want price BELOW 200 EMA before entering puts (avoid bounces off 200 EMA)
  → Place stops BELOW the zone so if wrong you know quickly

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CASEY'S SCANNER RULE (for finding A+ stocks):
  "One of the best ways to scan for a strong stock is to look for a break
   of BOTH the previous day resistance AND the pre market high"
  → Breaks PDH + PMH = STRONGEST CALLS signal, buyers in total control
  → Example: AMD breaks PMH + PDH → flag to 13 EMA → calls entry → winner
  → Score this as maximum confluence — it's the strongest possible setup

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CASEY'S ZONE NUMBERING SYSTEM (price target map):
  ZONE 1 = PDH (Previous Day High) — THE BREAKOUT POINT
    → Draw from: high of day WICK to following candle BODY (creates a zone not a line)
    → Breaking above = out of range = higher high = momentum = calls
    → "Zone 1 is my breakout point — use to determine if in range or broken out"

  ZONE 2 = Next resistance after Zone 1 break (FIRST PRICE TARGET)
    → To find: look back on 15min chart for where price hit resistance last
    → May only be 1-2 days back
    → Use as price target AND place to be cautious of rejection/reversal

  ZONE 3 = Next resistance above Zone 2 (SECOND PRICE TARGET)
    → Same process: look back for last resistance above Zone 2

  ZONE 4, 5 = Continue the process upward (additional targets)

  KEY PRINCIPLE: "Because there is no resistance between Zone X and Y,
    price is able to move freely from one zone to the next"
  → Clean air between zones = EXPLOSIVE MOVES
  → Resistance between zones = price struggles, slows, may reject

  DEMAND ZONE CONSTRUCTION:
    → PDH + PML together define next day's demand zone
    → "Used the Previous Day High and Pre Market Low to create today's demand zone"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CASEY'S PRICE STRUCTURE RULES (HH/HL/LH/LL):
  BULLISH STRUCTURE = Higher Highs (HH) + Higher Lows (HL)
    → H/H & H/L = NO SHORTING — structure is bullish
    → Bull flags form on pullbacks (HL formation) = entries
    → "Do NOT try to time the top while structure is bullish"
    → "Wait for trend shift confirmation before entering short"

  BEARISH STRUCTURE = Lower Highs (LH) + Lower Lows (LL)
    → L/H & L/L = NO LONGING — structure is bearish
    → Bear flags form on bounces (LH formation) = put entries
    → "Do NOT try to time the bottom while structure is bearish"
    → "Wait for confirmation of trend shift before attacking"

  STRUCTURE SHIFT SIGNALS:
    → Price rejects support on retest → first Bear Flag → bearish structure
    → Price holds resistance breakout → first Bull Flag → bullish structure

  SUPPLY/DEMAND RANGE TRADING:
    → Demand → Supply move: Bull Flag forms along the way → calls on flag break
    → Supply → Demand move: Bear Flag forms along the way → puts on flag break

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3 — KEY LEVEL ANALYSIS (Casey's Official 4 Levels)
Identify and evaluate in this EXACT priority order:
  1. PDH (Previous Day High) — major resistance zone
  2. PDL (Previous Day Low) — major support zone, target on trend days
  3. PMH (Pre-Market High) — intraday gatekeeper for calls
  4. PML (Pre-Market Low) — intraday gatekeeper for puts
  5. VWAP — intraday mean reversion line

CASEY'S BEARISH SETUP (the 1,000% pattern):
  → Price rejects PDH resistance (fails to break above)
  → First bounce creates a LOWER HIGH (below PDH) = bearish structure confirmed
  → Bearish EMA fan fans out (200>48>13)
  → 15min candle body closes below PML = puts confirmed
  → Enter puts on 2min 13 EMA bounce
  → Target: PDL zone | Runners: below PDL = "where runners go nuts"

CASEY'S BULLISH SETUP (mirror):
  → Price holds PDL support
  → First pullback creates a HIGHER LOW = bullish structure confirmed
  → Bullish EMA fan fans out (13>48>200)
  → 15min candle body closes above PMH = calls confirmed
  → Enter calls on 2min 13 EMA dip

CASEY'S LEVEL RULES:
  → 15min candle BODY must close (not just wick) above PMH (calls) or below PML (puts)
  → First 2 candles wick a level = WAIT. Enter on 3rd candle close
  → PDH rejection = watch for lower high → puts setup loading
  → PDL break = watch for runners below — "under PDL is where it gets nuts"
  → PDH and PMH within 0.2% = CHOP ZONE, skip entirely
  → Smoothest money = PDH down to PDL range on trend days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 4 — CONFLUENCE SCORING + SMART MONEY (0–12)
Before scoring, ALWAYS check whale flow direction for SPY/QQQ/IWM:
  → "unusual options activity SPY today" / "QQQ options flow today"
  → Whale direction must AGREE with your technical setup or reduce/skip

Score each instrument:

  +2  EMA fan fully aligned AND spacing out (ordered 13/48/200)
  +2  15min candle BODY closed above PMH (calls) OR below PDL (puts)
  +2  Price retesting a key level with confirmation (3rd candle rule)
  +1  2min 13 EMA pullback in direction of trend (Casey entry)
  +1  Volume above average on the setup candle
  +1  VWAP supports trade direction (above VWAP = bullish, below = bearish)
  +1  Clean air above/below (no chop zone between PDH and PMH)

HARD VETO — score automatically 0 if:
  - EMAs are bunched/choppy (no fan)
  - 15min hasn't confirmed direction yet
  - Price is in chop zone between PDH and PMH (<0.2% apart)
  - Time is after 3:45pm ET

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 5 — TRADE RECOMMENDATION
For each instrument scoring 5+:

  Direction:    CALLS or PUTS (based on EMA fan + 15min confirm + whale flow)
  Strike:       ATM or 1 strike OTM in trend direction
                → If whale sweep is DEEP ITM strike = follow the whale strike
                → Large whale call sweep at $X strike = that strike has conviction
  Expiry:       Default 2DTE — but if whale sweep is 0DTE follow their expiry
  Entry:        On 2min 13 EMA pullback after 15min confirms
  Profit exit:  DTE-based (+50% for 2DTE) — or at next Casey zone
  Stop loss:    DTE-based (-30% for 2DTE)
  Time cutoff:  No new entries after 3:45pm ET on 0DTE
  Size:         $50 per trade (full) if whale confirms | $25 (half) if no whale data

  OPTION LIQUIDITY SIZING:
    High volume (OI >5K, vol >2K) = full $50 — tight spreads, easy fills
    Medium volume (OI >1K, vol >500) = full $50 — acceptable
    Low volume (OI <1K, vol <500) = SKIP — wide spreads, bad fills

  WHALE-INFORMED SIZING:
    Technical 7+ + Whale confirms same direction = FULL $50
    Technical 7+ + No whale data               = FULL $50
    Technical 7+ + Whale OPPOSITE direction    = SKIP or $25 max
    Technical 5-6 + Whale confirms             = $25 (B setup boosted)
    Technical 5-6 + No whale                   = WAIT for better setup

CASEY'S EXIT WISDOM:
  "I would rather exit too early than too late"
  "Don't be afraid to lock in gains on the way up"
  "Trail stop with 13 EMA support — those are also nice dip buys"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — return ONLY this JSON:
{
  "timestamp": "2026-06-16 10:30:00 ET",
  "market_bias": "BULLISH | BEARISH | CHOPPY",
  "ema_status": "FANNING BULLISH | FANNING BEARISH | BUNCHED - NO TRADE",
  "instruments": [
    {
      "symbol": "SPY",
      "price": 549.12,
      "pct_change": 0.8,
      "prev_close": 544.80,
      "ema_fan": "BULLISH",
      "ema_spacing": "WIDE",
      "key_levels": {
        "PDH": 551.20,
        "PDL": 543.10,
        "PMH": 548.90,
        "PML": 545.20,
        "VWAP": 547.80
      },
      "level_status": "15min closed above PMH — CALLS confirmed",
      "confluence_score": 8,
      "confluence_breakdown": {
        "ema_fan": 2,
        "15min_confirm": 2,
        "level_retest": 2,
        "13ema_pullback": 1,
        "volume": 1,
        "vwap": 0,
        "clean_air": 0
      },
      "trade": {
        "direction": "CALLS",
        "strike": "549C",
        "expiry": "0DTE",
        "entry_trigger": "Wait for 2min 13 EMA pullback toward 548.50",
        "profit_target": "+25% on premium",
        "stop_loss": "-25% on premium",
        "position_size": "$15",
        "notes": "Lock in partials at +15%, trail with 13 EMA after"
      },
      "verdict": "PRIME SETUP 🔥"
    }
  ],
  "best_trade": "SPY",
  "casey_note": "SPY held PDH retest. 3rd candle closed above PMH. EMA fan wide and bullish. Enter on next 13 EMA dip.",
  "no_trade_reasons": []
}
""".strip()

# ── Main Analysis ─────────────────────────────────────────────────────────────
def run_0dte_analysis(auto_trade: bool = False, dry_run: bool = True):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY=your_key")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    now_et = datetime.now(ET)
    now_str = now_et.strftime("%Y-%m-%d %H:%M:%S ET")

    # Time gate check
    h, m = now_et.hour, now_et.minute
    in_window = (
        (h > ENTRY_WINDOW_START[0] or (h == ENTRY_WINDOW_START[0] and m >= ENTRY_WINDOW_START[1]))
        and
        (h < ENTRY_WINDOW_END[0] or (h == ENTRY_WINDOW_END[0] and m <= ENTRY_WINDOW_END[1]))
    )

    print(f"""
╔══════════════════════════════════════════════════════════╗
║   🎯 WILEY STRAT 0DTE — CASEY EMA + CONFLUENCE       ║
║   {now_str:52s}║
║   Window: 9:45am–3:45pm ET  |  {"✅ IN WINDOW" if in_window else "⛔ OUTSIDE WINDOW":20s}         ║
║   Instruments: SPY / QQQ / IWM                          ║
║   Target: +25% | Stop: -25% | Size: $15                 ║
╚══════════════════════════════════════════════════════════╝
""")

    if not in_window:
        opens_at = "9:45am ET"
        print(f"  ⏰ Outside trading window. Analysis available but no trades until {opens_at}.")
        print(f"  Running analysis anyway for preparation...\n")

    user_msg = f"""
Run the full 0DTE analysis for today.

Current time: {now_str}
Trading window active: {in_window}
Instruments to analyze: {INSTRUMENTS}

Steps:
1. Get real-time quotes for SPY, QQQ, IWM
2. Apply EMA fan check (bullish/bearish/choppy)
3. Identify key levels (PDH, PDL, PMH, PML, VWAP) from price data
4. Score each instrument 0–10 using the confluence system
5. Generate trade recommendations for anything scoring 5+
6. Return the complete JSON analysis

{"AUTO-TRADE MODE: After analysis, execute the best trade if score >= " + str(PRIME_CONFLUENCE) + " and we are in the trading window." if auto_trade else "ANALYSIS ONLY MODE: Generate recommendations but do not place orders."}
{"Use review_equity_order to simulate (DRY RUN)" if auto_trade and dry_run else ""}
{"Use place_equity_order for LIVE execution" if auto_trade and not dry_run else ""}
"""

    print("📡 Pulling quotes and running analysis...\n")

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"]
    )

    # Parse response
    raw_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            raw_text += block.text
        elif hasattr(block, 'type') and block.type == "mcp_tool_use":
            print(f"  🔧 {block.name}...")

    # Extract JSON
    analysis = None
    try:
        clean = raw_text.strip()
        if "```" in clean:
            parts = clean.split("```")
            for part in parts:
                if part.startswith("json"):
                    clean = part[4:].strip()
                    break
                elif part.strip().startswith("{"):
                    clean = part.strip()
                    break
        analysis = json.loads(clean)
    except Exception:
        print("⚠️  Could not parse JSON. Raw output:\n")
        print(raw_text[:2000])
        return None

    # ── Display Results ───────────────────────────────────────────────────────
    if not analysis:
        return None

    bias    = analysis.get("market_bias", "UNKNOWN")
    ema_st  = analysis.get("ema_status", "UNKNOWN")
    best    = analysis.get("best_trade", "—")
    casey   = analysis.get("casey_note", "")

    bias_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "CHOPPY": "🟡"}.get(bias, "⚪")

    print(f"{'━'*58}")
    print(f"  {bias_emoji} MARKET BIAS: {bias}")
    print(f"  📊 EMA STATUS: {ema_st}")
    print(f"  🎯 BEST TRADE: {best}")
    print(f"{'━'*58}\n")

    instruments = analysis.get("instruments", [])
    for inst in instruments:
        sym     = inst.get("symbol", "?")
        score   = inst.get("confluence_score", 0)
        trade   = inst.get("trade", {})
        verdict = inst.get("verdict", "")
        levels  = inst.get("key_levels", {})
        status  = inst.get("level_status", "")
        fan     = inst.get("ema_fan", "UNKNOWN")
        price   = inst.get("price", 0)
        pct     = inst.get("pct_change", 0)

        score_bar = "█" * score + "░" * (10 - score)
        arrow = "▲" if pct >= 0 else "▼"
        fan_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "BUNCHED": "🟡"}.get(fan, "⚪")

        print(f"  {'─'*54}")
        print(f"  {sym}  ${price:.2f}  {arrow}{abs(pct):.2f}%  |  Score: {score}/10  [{score_bar}]")
        print(f"  EMA Fan: {fan_emoji} {fan}  |  {status}")

        if levels:
            lvl_str = "  ".join([f"{k}:{v}" for k, v in levels.items() if v])
            print(f"  Levels: {lvl_str}")

        if score >= MIN_CONFLUENCE and trade:
            direction = trade.get("direction", "?")
            strike    = trade.get("strike", "?")
            trigger   = trade.get("entry_trigger", "?")
            notes     = trade.get("notes", "")
            d_emoji   = "📈" if direction == "CALLS" else "📉"
            print(f"\n  {d_emoji} {direction} | Strike: {strike} | 0DTE")
            print(f"  Entry:  {trigger}")
            print(f"  Exit:   +25% profit | -25% stop | force close 3:45pm")
            if notes:
                print(f"  Note:   {notes}")
            print(f"\n  {verdict}")
        elif score < MIN_CONFLUENCE:
            no_trade = inst.get("no_trade_reasons", analysis.get("no_trade_reasons", []))
            if no_trade:
                for reason in no_trade[:2]:
                    print(f"  🚫 {reason}")
            else:
                print(f"  🚫 Score {score} — below minimum {MIN_CONFLUENCE}. No trade.")
        print()

    if casey:
        print(f"{'━'*58}")
        print(f"  💬 CASEY NOTE: {casey}")

    # Save log
    log_dir = os.path.expanduser("~/scan_logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"0dte_{now_et.strftime('%Y%m%d_%H%M')}.json")
    with open(log_path, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"\n  💾 Log saved: {log_path}")
    print(f"{'━'*58}\n")

    return analysis


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    auto_trade = "--trade" in sys.argv or "--live" in sys.argv
    dry_run    = "--live" not in sys.argv

    if not dry_run:
        print("\n⚠️  LIVE MODE — real options orders will be placed.")
        if input("Type YES to confirm: ").strip() != "YES":
            print("Aborted.")
            exit()

    run_0dte_analysis(auto_trade=auto_trade, dry_run=dry_run)
