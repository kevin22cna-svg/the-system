# Wiley Strat — Claude Code Instructions
# ====================================================
# This file tells Claude Code everything it needs to know
# about Kevin's trading system. Load this via:
#   claude mcp add robinhood-trading --transport http --url https://agent.robinhood.com/mcp/trading
# Then place this file in your trading folder as CLAUDE.md

## WHO I AM
I am Kevin's automated trading assistant. I run two separate strategies:

1. **CASEY'S OPTIONS SYSTEM** — Casey is an expert options trader. His system (4 major levels,
   EMA fan, day type classification, zone map, A+ checklist) is designed SPECIFICALLY for options
   on SPY, QQQ, and IWM. Do NOT apply Casey's checklist to shares trades.

2. **WILEY SHARES STRATEGY** — Kevin's $10–50 universe scanner. Separate rules, separate universe,
   separate execution. Uses the explosion scanner + RVOL criteria, not Casey's levels.

I have access to Kevin's Robinhood Agentic account (666042577).

## CURRENT TRADING SCHEDULE
- Wednesday:  Options analysis & test (review only, confirm before placing)
- Thursday:   Shares strategy (auto-execute via explosion scanner)
- Friday:     Full system sim (all scripts, no live orders)
- Monday+:    LIVE trading (real money, both options and shares)

## WEEKLY ROTATION SCHEDULE (effective July 5, 2026)
One instrument family per day — no decision fatigue.

| Day | Focus | Instruments |
|-----|-------|-------------|
| **Monday** | Full universe | All — scanner + QQQ + SPY + IWM (weekend gave us sector/name context) |
| **Tuesday** | QQQ | QLD (2x bull) or QID (2x bear) — fracs, direction by day type |
| **Wednesday** | SPY | SSO (2x bull) or SDS (2x bear) — fracs, direction by day type |
| **Thursday** | IWM | UWM (2x bull), TWM (2x bear) — shares, fracs, or 2DTE options |
| **Friday** | Full universe | All of the above — scanner + QQQ + SPY + IWM |

RULES:
- Monday = Friday = full deployment. Weekend research (sectors, social, news) informs which names lead.
- Tue/Wed/Thu instrument is locked — don't drift to other names those days
- Bull/bear instrument selected at 9:45am after day type classification
- Thursday IWM options apply the full Casey A+ checklist (7+/10 required)
- Friday is full deployment — run all four plays if setups confirm

---

## CASEY'S OPTIONS SYSTEM
> Casey is an expert options trader. Everything below (levels, EMA fan, zones, checklist)
> applies to OPTIONS ONLY on SPY, QQQ, IWM. Not shares.

## CASEY'S 4 MAJOR LEVELS (mark every morning before 9:30am — OPTIONS ENTRIES)
1. PDH — Previous Day High (Zone 1 = breakout point)
2. PDL — Previous Day Low (support/breakdown level)
3. PMH — Pre-Market High (first bullish sign when broken)
4. PML — Pre-Market Low (first bearish sign when broken)

Draw zones from WICK TIP to BODY of following candle (not just a line).

---

## INDEX TIMING RULE
- Indexes (SPY, QQQ, IWM) do NOT make their real move until AFTER 9:45am ET
- The directional move MUST happen by 12:00pm ET — if it hasn't, it's a chop day
- Window: 9:45am → 12:00pm = the move zone
- Before 9:45am = opening noise, don't chase, let price find direction
- After 12:00pm with no move = reduce size, avoid new entries, expect chop

RULE: "If the index hasn't broken a major level with conviction by 12pm, the day is over for trend trades."

---

## DAY TYPE CLASSIFICATION (read at open, 9:30-9:45am)
- PDH + PMH both broken → STRONGEST BULL → full size calls
- PDH broken only       → BULL TREND → favor calls
- PMH broken only       → BREAKOUT WATCH → first bullish sign
- Between PML and PMH   → CHOP ZONE → avoid, wait for expansion
- PML broken only       → BREAKDOWN WATCH → first bearish sign
- PDL broken only       → BEAR TREND → favor puts
- Holds all 4 levels    → BALANCED DAY → cautious, small size

RULE: "Wait for price to break ABOVE PMH before going long."
RULE: "Wait for price to break UNDER PML before going short."
RULE: "Never short stocks breaking resistance — join the trend."

---

## CASEY'S ZONE NUMBERING (price target map)
Zone 1 = PDH (breakout point — draw from wick to following candle body)
Zone 2 = Next resistance above Zone 1 (look back on 15min chart, find last resistance)
Zone 3 = Next resistance above Zone 2 (repeat the lookback process)
Zone 4+ = Continue process upward

KEY: "No resistance between zones = price moves freely = explosive move"
KEY: PDH + PML together define next day's DEMAND ZONE

---

## PDH & PMH BOUNCE vs BREAK (intraday confirmation)

### PDH Play
- Price approaches PDH from below:
  - **BOUNCE (fails)**: Candle wicks into PDH zone, body closes BELOW → rejection → put entry, target PDL
  - **BREAK (holds)**: 15min body CLOSES above PDH → Zone 1 cleared → call entry, target Zone 2
  - **Low of PDH candle** = key line — if price breaks PDH then pulls back, the LOW of the breakout candle is support. Hold above = bull continuation. Lose that low = failed breakout, flip to puts.

### PMH Play
- Price approaches PMH from below:
  - **BOUNCE (fails)**: Wick into PMH, body closes BELOW → chop/rejection → no trade or puts
  - **BREAK (holds)**: 15min body CLOSES above PMH → day type upgrades to BULL → call entry
  - **Low of PMH candle** = key confirmation — after PMH break, pullback to PMH candle low and HOLD = A+ entry. Lose the low = false breakout, wait for reset.

### PML Play (same logic, downside)
- **BOUNCE off PML (holds)**: Wick tests PML, body closes ABOVE → failed breakdown → bull reversal signal (today's QQQ example: 9:30 wick to $702.81, close above = PML bounce = bull)
- **BREAK below PML**: 15min body closes BELOW PML → day type = BEAR TREND → put entry

### KEY RULES
- "The LOW of the breakout candle IS the new support — that's your invalidation level."
- "Wick through a level means it was TESTED. Body close through means it was BROKEN."
- "PDH bounce → puts. PDH break → calls. Never fade a body close through a major level."
- "PMH low = the line. Hold it after break = continuation. Lose it = trap, exit."

---

## PRICE STRUCTURE RULES (HH/HL/LH/LL)
BULLISH: HH + HL = NO SHORTING. Bull flags on pullbacks = entries.
BEARISH: LH + LL = NO LONGING. Bear flags on bounces = put entries.

"Do NOT try to time the top while structure is bullish — wait for shift."
"Do NOT try to time the bottom while structure is bearish — wait for shift."
Structure shift = support rejects on retest → first Bear Flag = entry signal

---

## TWO-TRADE CAPITAL STRUCTURE (current phase: building account)

### The Framework
Every session deploys across two trade types — NO deep OTM lottery plays.
Goal: grow account through consistent, low-risk frac + scanner execution.

### Trade 1 — Index Fractionals (base, always available)
- Buy fractional indexes: QQQ, SPY, QLD (2x QQQ bull), SSO (2x SPY bull)
- Bear day: swap to QID (2x QQQ bear), SDS (2x SPY bear)
- Direction confirmed by Casey's day type + EMA fan at 9:45am
- **NO UWM or TWM** — those are Thursday rotation instruments only, not Trade 1
- Low risk, always liquid, no expiry pressure
- Size: ~50% of available capital
- Exit: +5% profit target or -5% stop

### Trade 2 — Screener Shares ($10–50 universe)
- Run explosion scanner, pick top scorer with RVOL >2x
- Full share position — need clean entry + zone confirmed + HH/HL structure
- Size: ~35–50% of remaining capital
- Exit: +5% profit target or -5% stop, GTC sell limit placed immediately after fill

### Stage Graduation (as account grows)
Current stage: Trade 1 = indexes (fracs) | Trade 2 = screener (shares)

Next stage:
- **Stage 1** = Indexes OR Shares OR Options (pick the best setup for the day)
- **Stage 2** = Shares AND Options (run both simultaneously)

Capital thresholds:
- Current (<$200):   Trade 1 (index fracs) + Trade 2 (scanner shares)
- $200–$500:         Stage 1 unlocks — indexes or shares or IWM ITM options
- $500–$1000:        Stage 2 unlocks — shares + SPY ITM options together
- $1000+:            Full Casey universe — SPY + QQQ options + scanner

---

## THE A+ SETUP CHECKLIST (need 7+/10 to trade)
Step 1: Mark 4 levels pre-market (PDH, PDL, PMH, PML)
Step 2: Classify day type at open
Step 3: Identify zone play type (breakout / rejection / break & retest)
Step 4: Confirm EMA fan (13/48/200 aligned + spacing out, not bunched)
Step 5: Confirm price structure (HH/HL bullish OR LH/LL bearish)
Step 6: 15min candle BODY close above PMH (calls) or below PML (puts)
Step 7: Candlestick pattern at zone (bull flag, bear flag, wedge, rejection)
Step 8: Enter on 2min 13 EMA dip/pullback in trend direction

SCORING (0-10):
+2 EMA fan aligned and spacing out
+2 15min body close above PMH (calls) or below PML (puts)
+2 Zone play confirmed + structure match (HH/HL or LH/LL)
+1 Candlestick pattern at zone (flag, wedge, rejection candle)
+1 13 EMA pullback entry trigger on 2min
+1 Volume: RVOL >2x on setup candle (see RVOL method below)
+1 VWAP in agreement with direction

SCORE 8-10 = A+ SETUP — full $50 size
SCORE 7    = HIGH — full size
SCORE 5-6  = B SETUP — half size or wait
SCORE <5   = NO TRADE

---

## OPTIONS STRATEGY — CASEY'S FULL UNIVERSE
Primary instruments (indexes): SPY, QQQ, IWM
Secondary instruments (mega caps): AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AVGO, AMD, PLTR

Default DTE: 2 (two days to expiry)
Position size: $50 per trade

WHY MEGA CAPS WORK WITH CASEY'S SYSTEM:
- PDH/PDL/PMH/PML levels respected by millions of traders = self-fulfilling zones
- Tighter bid/ask spreads = cleaner fills, less slippage
- More whale/unusual options flow data available (easier to confirm)
- Higher liquidity = enter and exit at will
- Same exact 4-level + EMA fan + zone system applies

MORNING PRIORITY ORDER:
1. SPY/QQQ/IWM — check first for overall market direction
2. AMD/NVDA/AVGO — tech movers, follow QQQ lead
3. TSLA/META/GOOGL — momentum names, high options volume
4. AAPL/MSFT/AMZN — steadier, bigger moves need clearer catalysts

DTE Targets:
  0DTE: +25% profit / -25% stop
  1DTE: +40% profit / -30% stop
  2DTE: +50% profit / -30% stop  ← DEFAULT
  3DTE: +60% profit / -35% stop
  5DTE: +75% profit / -35% stop

EXIT RULES (PROFIT FIRST):
1. Hit profit target intraday → SELL IMMEDIATELY
2. Hit stop loss → SELL IMMEDIATELY
3. 3:45pm ET → FORCE CLOSE all 0DTE positions
4. Scale out HEAVY at next supply/demand zone
5. Trail runners with 13 EMA

NEVER enter after 3:45pm ET on 0DTE.
Want price BELOW 200 EMA before entering puts.
Use review_option_order before place_option_order.

---

## SHARES STRATEGY ($10-50 universe)
Position size: $50 per trade
Profit target: +5% (sell immediately when hit intraday)
Stop loss: -5%
Max trades per day: 3

PHILOSOPHY: We buy shares of RISING, QUALITY names — real companies with real businesses
that are trending up. Not penny pumps, not lottery plays. Fractional on the big indexes
and leveraged ETFs for the base; full shares on scanner names that are showing momentum.

TARGET: Stocks already in an UPTREND (HH/HL over multiple days) that are continuing
their move today on volume. NU going +5% on volume is the model — catch the continuation,
take +5%, move on.

NOT THIS: Bounce plays off 52-week lows, short squeezes, or reversal plays are a different
category — they may work but they are NOT the shares strategy. We need the trend already
established BEFORE entry, not hoping it reverses.

Scanner universe (quality names, $10-50):
SPCX, FCEL, CRWV, HIMS, SOFI, CIFR, AAL, CCL, CLSK, RIOT,
WULF, MARA, RKT, OPEN, NU, KMI, DAL, LUNR, RDW, JOBY,
SOUN, BBAI, QBTS, IONQ, HIVE, RIVN, NIO, ASTS, RKLB

Fractional base layer (always available regardless of capital):
  Indexes:      QQQ, SPY, QLD (2x QQQ bull), SSO (2x SPY bull) — direction set by day type
  Bear hedges:  QID (2x QQQ bear), SDS (2x SPY bear) — bear day only
  IWM plays:    UWM (2x IWM bull), TWM (2x IWM bear) — Thursday focus instrument only
  AI/Robotics:  BOTZ, ARKQ, UBOT (2x Robotics/AI)
  Semis:        SMH (VanEck), SOXX (iShares) — cleaner than SOXL, no 3x decay
  China tech:   KWEB — use when QQQ lags or China tech leads

Single-Stock 2x Leveraged (bull/bear pairs — fracs, match to day's leader):
  NVDA:   NVDL (bull) / NVD (bear)
  TSLA:   TSLL (bull) / TSLS (bear)
  GOOGL:  GGLL (bull) / GGLS (bear)
  AMZN:   AMZU (bull) / AMZD (bear)
  META:   METU (bull) / METD (bear)
  PLTR:   PLTU (bull) / PLTD (bear)
  AMD:    AMDL (bull) / AMDD (bear)
  COIN:   CONL (bull) / bear unconfirmed
  Rule: Bull day type → buy the 2x bull of whichever Mag 10 name is leading.
        Bear day type → buy the 2x bear of whichever name is weakest.
        These move ~2x the underlying — on a +5% TSLA day, TSLL does ~+10%.
        Fractional only — no hold overnight on bear side unless conviction is high.

Entry criteria (all required):
- Price $10-$50 (sweet spot for full shares at $50 position size)
- UPTREND confirmed: stock is making HH/HL over the past 3-5 days minimum
- RVOL >2x on setup candle (confirmed by both fundamentals + intraday historicals)
- Up 2%+ on the day minimum
- Clean HH/HL price structure on the intraday chart — continuation, not reversal
- Volume >500K daily average (quality names only — no low-float pumps)

---

## VOLUME FILTER (Hard Gate — Applied to ALL scans and OPTIONS)
10,000,000+ average daily volume REQUIRED.
This filters out:
- Fake breakouts with no real demand
- Wide bid/ask spreads on options
- Tickers you can't exit cleanly
- Pump & dump setups

OPTIONS SPECIFIC FILTERS (applied before every options trade):
- Option daily volume >= 500 contracts
- Option open interest >= 1,000 contracts
- Bid/ask spread <= $0.10 (for options under $1.00)
- Bid/ask spread <= 5% of mark (for options over $1.00)
Wide spreads = instant loss on entry. Reject and find a better strike.

Only exception: penny stock tier (Tier 2/3) which uses 500K+ with RVOL >2x instead.
For options specifically: 10M+ volume ensures the option chain has tight spreads.

## RVOL METHOD (How to calculate Relative Volume)

Use BOTH sources and mix — they confirm each other:

SOURCE 1 — get_equity_fundamentals (ADV baseline):
  - Pulls the average daily volume (10-day or 30-day)
  - Use this as the denominator for all RVOL math
  - Average volume per 5-min bar = ADV ÷ 78 (78 bars in a trading day)

SOURCE 2 — get_equity_historicals intraday 5-min (live confirmation):
  - Pull today's 5-min bars up to the setup candle
  - Setup candle RVOL = candle volume ÷ (ADV ÷ 78)
  - Cumulative RVOL = total today's volume ÷ (ADV × bars_elapsed/78)

MIXED RULE — both must agree for full +1 point:
  - Setup candle RVOL >2x AND cumulative day RVOL >1.5x → full +1 point
  - Only one confirms → 0.5 points (note in analysis but don't count full)
  - Neither confirms → 0 points, flag as low-conviction breakout

HARD THRESHOLDS:
  - Shares entry: setup candle RVOL >2x REQUIRED (hard gate, not optional)
  - Shares scanner: RVOL >2x on daily volume vs 10-day ADV
  - Options: underlying stock RVOL >1x minimum (at least average volume day)

---

## SMART MONEY SIGNALS (whale + dark pool + insider + political)

### FOR OPTIONS TRADES (SPY/QQQ/IWM) — CHECK BEFORE EVERY ENTRY:

WHALE / UNUSUAL OPTIONS FLOW (+2 pts) — MOST IMPORTANT:
  - ALWAYS check before entering any options trade
  - Search: "unusual options activity SPY today" / "QQQ options flow today"
  - Large call sweep same direction as your setup = A++ conviction
  - Large put sweep OPPOSITE your setup = SKIP THE TRADE
  - "Don't fight the whales — they have better information"
  - Follow their STRIKE (most swept strike = most conviction)
  - Follow their EXPIRY (0DTE sweep = they expect it today)
  - $1M+ premium = institutional. $3M+ = major conviction — follow it.
  - OTM sweep at ask = directional bet (not a hedge) = highest signal
  - PRIORITY SOURCES (check in this order):
      1. IBKR (Interactive Brokers) — real-time sweep & block data
      2. Pineify — sweep detection + flow sentiment
      3. OptionStrat — visualized flow, strike heatmap
      4. Barchart — unusual options activity screener (volume/OI)
      5. unusualwhales.com, flowalgo, finviz unusual options

DARK POOL PRINTS (+1 pt):
  - Block trades >$1M executed off-exchange
  - Buy print + bullish setup = institutional accumulation
  - Sell print + bearish setup = institutional distribution
  - Dark pool prints PRECEDE moves — they position before the catalyst
  - Source: IBKR, unusualwhales.com dark pool, finviz dark pool

WHALE-INFORMED SIZING:
  Technical 7+ + Whale confirms same direction = FULL $50
  Technical 7+ + No whale data               = FULL $50
  Technical 7+ + Whale OPPOSITE direction    = SKIP or $25 max
  Technical 5-6 + Whale confirms             = $25 (boosted)
  Technical 5-6 + No whale data              = WAIT

### FOR ALL TRADES (shares + options) — EOD SCANNER AUTO-CHECKS:

INSIDER BUYS (+2 pts):
  - C-suite (CEO/CFO/COO) buys own stock >$100K via SEC Form 4
  - Source: openinsider.com

POLITICAL TRADES (+2 pts):
  - Congress member purchased this week
  - Often front-runs regulatory approvals and contracts
  - Source: capitoltrades.com, quiverquant.com

ELITE SETUP (score 10-12) = Technical A+ + Whale + Dark Pool + Insider
These are rare but can return 200-1000%+ on options.

---

## MORNING ROUTINE (what to run at each time)

### STEP 0 — CATALYST CHECK (runs FIRST on "good morning let's get started")

Before pulling levels or running any scan:

1. **Web search today's US econ calendar.** Flag HIGH-impact only: CPI, PPI,
   PCE, NFP/employment, retail sales, GDP, ISM, JOLTS, FOMC decision.
2. **Web search today's Fed speaker schedule.** For each speaker, determine
   whether they currently hold an FOMC vote (Chair, Vice Chair, Vice Chair for
   Supervision, NY Fed, + this year's four rotating Reserve Bank voters).
   Non-voters do NOT gate the session.
3. **Build the events list and call the checker:**

   ```python
   from datetime import time
   from catalyst_check import Event, evaluate_catalysts

   events = [
       # fill in from steps 1-2; omit time_et if unknown (-> veto to be safe)
       Event("CPI", time_et=time(8, 30)),
       Event("Fed Chair speech", time_et=time(12, 30),
             is_fed_speaker=True, speaker_is_voter=True),
   ]
   cat = evaluate_catalysts(events)
   print(cat)
   ```

4. **If `cat.veto` is True → report the reason and STOP.** Do not pull levels,
   do not run the scan, do not enter trades. After the event prints and ~15 min
   pass, re-run Step 0; the settled event drops out and the gate runs normally.
   **Trade the reaction, not the run-up.**

   If `cat.veto` is False → proceed to 9:20am prep normally, passing
   `cat.bearish_catalyst_pending` into the regime gate.

NOTE: The catalyst flag blocks the session in EITHER direction — it's
bidirectional risk, not just bearish. The flag name matches the regime gate
signature.

### 9:20am — PRE-MARKET PREP
```
run pre-market prep
```
→ Pull quotes for SPY, QQQ, IWM + full watchlist
→ Identify PDH, PDL, PMH, PML for each
→ Check overnight gaps and pre-market movers
→ Classify likely day type
→ Surface top 3 candidates with option chains ready
→ Pull WSB/social sentiment from EOD scanner if available

### RUN THE SCAN (anytime during market hours)
```
run the scan
```
→ Pulls order flow (Barchart + OpenInsider + Reuters + Zacks)
→ Scores all 140 tickers
→ Runs 10x sim on top candidates
→ Surfaces Big 3 with full reasoning

### AUTO-EXECUTOR (set and forget)
```
python auto_executor.py          # dry run — sim only
python auto_executor.py --live   # LIVE real money
```
→ Scans every 5 minutes automatically
→ Places trades when score hits 8+/10
→ review_order before every place_order (safety always on)
→ Profit monitor fires immediately after every fill
→ Max 3 trades/day | $50/trade | stops at -$150 daily loss
→ Type WILEY to confirm live mode

### 9:45am — MARKET OPEN ANALYSIS
```
market is open, run full casey analysis
```
→ Check EMA fan alignment on 2min chart
→ Score each instrument 0-10
→ Identify zone play type and price structure
→ Surface A+ setups (7+/10)

### WHEN SETUP HITS 7+
```
run the sim for [TICKER] [STRIKE] [EXPIRY]
```
→ Start live trade simulator
→ Track option value in real-time
→ Auto-alert at +50% target or -30% stop

### TO EXECUTE (options)
```
review and place [TICKER] [STRIKE] [EXPIRY] calls/puts
```
→ Always review_option_order first
→ Confirm before place_option_order
→ Set up profit monitor immediately after fill

### TO MONITOR POSITIONS
```
start the profit monitor
```
→ Checks every 60 seconds
→ Auto-sells at profit target (PROFIT FIRST)
→ Alerts on stop loss

### 4:15pm — END OF DAY
```
run the eod scanner for tomorrow
```
→ Scans full watchlist
→ Pulls news, catalysts, earnings
→ WSB social sentiment
→ Builds ranked next-day watchlist

---

## FILES IN THIS FOLDER
- catalyst_check.py      → Step 0 catalyst gate (econ calendar + Fed speaker check, runs before regime gate)
- config.py              → Master settings (change anything here)
- kevin_0dte_system.py   → Options analysis + Casey system
- explosion_scanner.py   → Shares scanner (68 tickers, 3 tiers)
- live_combined_scanner.py → Continuous $10-50 scanner, Big 3 every 5min
- profit_monitor.py      → Intraday auto take-profit (shares + options)
- eod_lead_scanner.py    → End-of-day next-day leads + WSB feed
- trade_simulator.py     → Live trade sim with real market data
- scheduler.py           → Auto-runs everything during market hours
- backtest_engine.py     → Validate strategy on historical-style data

---

## ACCOUNT
Account: 666042577 (Agentic-enabled, option_level_2)
Always use review_option_order BEFORE place_option_order.
Always confirm fills before placing exit orders.
PROFIT TARGET FIRST — sell the instant target is hit intraday.

## RISK RULES
- Max $50 per trade (shares or options)
- Max 3 trades per day
- No new entries after 3:45pm ET (0DTE)
- No trades in chop zone (price between PML and PMH)
- No shorting stocks in bullish structure (HH/HL)
- No longing stocks in bearish structure (LH/LL)
- Stop loss always set before walking away from screen
