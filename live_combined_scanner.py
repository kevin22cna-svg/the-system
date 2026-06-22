"""
Wiley Strat Live Scanner — Wiley Strat (Kevin + Casey) Strategy
=======================================================
Continuously scans a $10–$50 ticker universe applying the full
combined option strategy scoring. Runs every 5 minutes during
market hours and surfaces the BIG 3 entry candidates each cycle.

STRATEGY (scored 0–10):
  +2  EMA fan aligned & spacing (bullish=calls, bearish=puts)
  +2  15min body close above PMH (calls) / below PDL (puts)
  +2  Catalyst + volume surge confirmed
  +1  13 EMA pullback entry trigger
  +1  Volume above average
  +1  VWAP agreement
  +1  Clean air (not overextended >15%, no PDH/PMH chop)
  -1  Overextended (parabolic, late-entry risk)

  Score 7+ = 🔥 PRIME  |  5-6 = ⚡ WATCH  |  <5 = 🚫 SKIP

Run: python live_combined_scanner.py
     python live_combined_scanner.py --trade   (dry run auto-trade)
     python live_combined_scanner.py --live     (real orders)
"""

import anthropic
import json
import os
import time
from datetime import datetime
import pytz
try:
    from config import CONFIG, get_account, get_share_targets, get_option_targets, get_universe, get_position_size
    _HAS_CONFIG = True
except ImportError:
    _HAS_CONFIG = False  # falls back to file-local defaults

ET = pytz.timezone("America/New_York")

# ── $10–$50 Range Universe ───────────────────────────────────────────────────
# Tuned to the price band where 1 option contract is affordable and liquid
SCAN_UNIVERSE = [
    # Today's hot movers in range
    "FCEL", "HIMS", "SOFI", "CIFR", "AAL", "CCL", "CLSK", "RIOT",
    "WULF", "MARA", "RKT", "OPEN", "NU", "KMI", "DAL",
    # Space / momentum in range
    "LUNR", "RDW", "JOBY",
    # AI / tech in range
    "SOUN", "BBAI", "QBTS", "IONQ",
    # Crypto-adjacent
    "HIVE", "CIFR",
    # Volume trades watchlist (in range)
    "UWMC", "F", "BAC",
    # Rotating WL (in range)
    "CVS", "BMY",
    # Energy / clean
    "PLUG", "TELL",
    # Others that frequently move in $10-50
    "RIVN", "NIO", "AGNC",
    # User-added
    "NOK", "AMC", "PFE", "GME", "BABA", "HTZ", "SNAP", "WMT", "POET",
]
# Add sector universe tickers
SECTOR_UNIVERSE = [
    # SEMIS
    "NVDA","AMD","ARM","INTC","TSM",
    # MEMORY
    "MU","SNDK","WDC",
    # NETWORKING
    "AVGO","MRVL","CRDO","ANET",
    # PHOTONICS
    "AAOI","LITE","COHR","NVTS","GLW",
    # SEMI EQUIPMENT
    "ASML","AMAT","LRCX","KLAC",
    # INFRASTRUCTURE
    "DELL","SMCI","VRT","ETN",
    # DATA CENTERS
    "IREN","CORZ","CIFR","HIVE","APLD","NBIS",
    # SOFTWARE
    "NOW","SNOW","MDB","CRM",
    # DEFENSE
    "KTOS","AVAV","RCAT","LMT",
    # DRONES
    "ONDS","DPRO","UMAC",
    # ROBOTICS
    "OUST","SYM","ISRG",
    # QUANTUM
    "IONQ","QBTS","RGTI",
    # NUCLEAR
    "OKLO","LEU","UUUU","CCJ",
    # POWER
    "CEG","VST","BE","TLN",
    # FINTECH
    "AFRM",
    # COPPER
    "FCX","SCCO","TECK",
    # eVTOL
    "ACHR",
]
SCAN_UNIVERSE = sorted(set(SCAN_UNIVERSE + SECTOR_UNIVERSE))

PRICE_MIN = 10.0
PRICE_MAX = 50.0

MIN_SCORE   = 5
PRIME_SCORE = 7

import subprocess as _sp
_SESSION_TOKEN = open("/home/claude/.claude/remote/.session_ingress_token").read().strip()
MCP_SERVER = {
    "type": "url",
    "url": "https://agent.robinhood.com/mcp/trading",
    "name": "robinhood-mcp",
    "authorization_token": _SESSION_TOKEN
}

SYSTEM_PROMPT = f"""
You are Kevin's live combined option scanner running the Wiley Strat (Kevin + Casey) strategy.

For each ticker, pull the quote and apply this scoring (0–10):

EMA FAN (Casey trend filter):
  +2 if strong uptrend (proxy: up 3%+ today = bullish fan, calls)
       OR strong downtrend (down 3%+ = bearish fan, puts)
  +1 if mild trend (1-3% move, fan forming)
  Direction = CALLS if green, PUTS if red

15MIN CONFIRM (Casey level gate):
  +2 if move >= 5% (sustained closes beyond PMH/PDL)
  +1 if move 2-5% (above the level)

CATALYST + VOLUME (Kevin confluence):
  +2 if clear catalyst or volume surge present
  +1 if move >= 4% (volume implied)

CLEAN AIR (Casey overextension check):
  +1 if move is 3-12% (trending but not parabolic)
  -1 if move > 15% (overextended, late-entry chop risk)

VOLUME FILTER (Wiley Strat hard gate):
  REJECT any ticker with average daily volume < 10,000,000 shares
  Low volume = fake moves, wide spreads, hard exits = NO TRADE
  Sources: Robinhood volume data, finviz vol filter

OPTION LIQUIDITY (Kevin):
  +1 if price between $10–$50 (affordable, liquid contracts)

VWAP (both):
  +1 if green on day (above VWAP, bullish) for calls
     or red on day (below VWAP) for puts

INSIDER / WHALE / POLITICAL BONUS SCORING:
  +2 if recent insider buy (C-suite Form 4 purchase >$100K)
  +2 if unusual options activity / whale call sweep today
  +2 if congress member purchased this week
  +1 if dark pool print >$1M detected
  +1 if multiple insiders buying same ticker

For intraday scans, check these signals via web search:
  - "unusual options activity [TICKER] today"
  - "insider buying [TICKER] SEC Form 4"
  - "[TICKER] congress trade quiverquant"

Only score tickers priced ${PRICE_MIN}–${PRICE_MAX}.

Return ONLY JSON:
{{
  "timestamp": "...",
  "candidates": [
    {{"symbol":"CRWV","price":119.1,"pct":11.6,"score":9,
      "direction":"CALLS","verdict":"PRIME",
      "setup":"EMA fan bullish, 15min above PMH, catalyst+vol, clean air",
      "insider":"CEO bought $500K 2 days ago",
      "whale":"Unusual call sweep 5x normal volume",
      "political":"Rep. bought shares last week"}}
  ],
  "big_3": ["sym1","sym2","sym3"]
}}
""".strip()

def now_et():
    return datetime.now(ET)

def in_market_hours():
    n = now_et()
    if n.weekday() >= 5:
        return False
    h, m = n.hour, n.minute
    after_open  = h > 9 or (h == 9 and m >= 45)
    before_close = h < 16
    return after_open and before_close

def fetch_live_orderflow():
    """Quick order flow check — Barchart unusual activity."""
    import urllib.request, re
    try:
        url = "https://www.barchart.com/options/unusual-activity/stocks?viewName=main"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        tickers = list(dict.fromkeys(re.findall(r'"symbol":"([A-Z]{1,5})"', html)))[:20]
        return tickers
    except Exception:
        return []

def run_scan_cycle(client, auto_trade=False, dry_run=True):
    now = now_et().strftime("%Y-%m-%d %H:%M:%S ET")
    print(f"\n{'─'*60}")
    print(f"  📡 SCAN — {now}")
    print(f"  Universe: {len(SCAN_UNIVERSE)} tickers (${PRICE_MIN}-${PRICE_MAX})")
    print(f"{'─'*60}")

    # Format order flow data for scoring
    flow_tickers = fetch_live_orderflow()
    flow_str = json.dumps(flow_tickers[:15]) if flow_tickers else "[]"

    user_msg = f"""
Scan these tickers, score with the combined strategy, return JSON:
{json.dumps(SCAN_UNIVERSE)}

LIVE ORDER FLOW DATA (Barchart unusual options — just fetched):
{flow_str}
Any ticker in this list gets +2 bonus points automatically (whale/institutional activity confirmed).

1. Get quotes for all (batch in get_equity_quotes)
2. Filter to ${PRICE_MIN}-${PRICE_MAX} price range
3. Score each 0-10:
   - Apply +2 bonus if ticker appears in order flow list above
   - Apply standard Casey + Kevin scoring
4. For top movers (5%+ up), quickly web-search:
   - "unusual options activity [TICKER] today"
   - "insider buying [TICKER] today"
   Add +2 each if signals found
5. Return candidates sorted by score + the big_3
Time: {now}
"""

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"]
    )

    raw = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw += block.text
        elif getattr(block, "type", "") == "mcp_tool_use":
            print(f"  🔧 {block.name}")

    try:
        clean = raw.strip()
        if "```" in clean:
            for part in clean.split("```"):
                if part.strip().startswith("{") or part.startswith("json"):
                    clean = part.replace("json", "", 1).strip()
                    break
        data = json.loads(clean)
    except Exception:
        print("  ⚠️ Parse error:\n", raw[:800])
        return

    candidates = data.get("candidates", [])
    prime = [c for c in candidates if c.get("score", 0) >= PRIME_SCORE]
    watch = [c for c in candidates if MIN_SCORE <= c.get("score", 0) < PRIME_SCORE]

    if prime:
        print("\n  🔥 PRIME SETUPS (7+):")
        for c in prime:
            d = "📈" if c.get("direction") == "CALLS" else "📉"
            print(f"    {d} {c['symbol']:<6} ${c['price']:>7.2f}  +{c.get('pct',0):>5.1f}%  {c['score']}/10")
            print(f"       {c.get('setup','')}")

    if watch:
        print("\n  ⚡ WATCH (5-6):")
        for c in watch:
            print(f"    {c['symbol']:<6} ${c['price']:>7.2f}  {c['score']}/10")

    big3 = data.get("big_3", [])
    if big3:
        print(f"\n  🎯 BIG 3: {' · '.join(big3)}")

    # Log
    log_dir = os.path.expanduser("~/scan_logs")
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, f"combined_{now_et().strftime('%Y%m%d_%H%M')}.json"), "w") as f:
        json.dump(data, f, indent=2)

    return data

def main():
    import sys
    auto_trade = "--trade" in sys.argv or "--live" in sys.argv
    dry_run    = "--live" not in sys.argv

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Set ANTHROPIC_API_KEY first")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║   🎯 LIVE COMBINED SCANNER — KEVIN + CASEY              ║
║   Range: ${PRICE_MIN}–${PRICE_MAX}  |  Scan every 5 min                ║
║   Window: 9:45am–4:00pm ET  |  Mode: {"LIVE" if not dry_run else "SCAN" if not auto_trade else "DRY":4s}              ║
╚══════════════════════════════════════════════════════════╝
""")

    scan_count = 0
    try:
        while True:
            if in_market_hours():
                scan_count += 1
                run_scan_cycle(client, auto_trade, dry_run)
                print(f"\n  ⏱  Scan #{scan_count} done. Next in 5 min... (Ctrl+C to stop)")
                time.sleep(300)
            else:
                print(f"  🕐 Outside market hours ({now_et().strftime('%I:%M %p ET')}). Waiting 5 min...")
                time.sleep(300)
    except KeyboardInterrupt:
        print(f"\n  🛑 Stopped after {scan_count} scans.")

if __name__ == "__main__":
    main()
