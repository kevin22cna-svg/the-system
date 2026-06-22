"""
Wiley Strat EOD Scanner — Next-Day Setups
==================================================
Runs after market close (4pm+ ET) to build a watchlist for the
NEXT trading day. Combines:

  1. Today's price action + volume (the technical movers)
  2. NEWS & CATALYSTS (web search — earnings, FDA, contracts, PR)
  3. EARNINGS calendar (who reports tomorrow / after-hours)
  4. SOCIAL SENTIMENT — r/wallstreetbets trending tickers + sentiment

Output: ranked next-day watchlist with the WHY for each.

Run: python eod_lead_scanner.py
     (best run at 4:15pm ET or later after close)

NOTE: Reddit feed uses Reddit's public JSON API (no auth needed for
reading public subreddits). Your Reddit account isn't required for
read-only access, but if you connect it via MCP you get higher limits.
"""

import anthropic
import json
import os
import urllib.request
from datetime import datetime
import pytz
try:
    from config import CONFIG, get_account, get_share_targets, get_option_targets, get_universe, get_position_size
    _HAS_CONFIG = True
except ImportError:
    _HAS_CONFIG = False  # falls back to file-local defaults

ET = pytz.timezone("America/New_York")

MCP_SERVER = {
    "type": "url",
    "url": "https://agent.robinhood.com/mcp/trading",
    "name": "robinhood-mcp"
}

# ── Insider / Whale / Political Data Sources ─────────────────────────────────
# These are free public APIs / sites we web-search for each scan
INSIDER_SOURCES = {
    "insider_buys":   "https://www.openinsider.com/screener",   # SEC Form 4 filings
    "whale_tracker":  "finviz.com unusual options volume",       # large options flow
    "political":      "https://www.capitoltrades.com",           # Congress trades
    "quiver":         "https://www.quiverquant.com",             # aggregates all 3
}

# These keywords in web search catch the freshest signals
SIGNAL_SEARCHES = [
    "insider buying today large purchase SEC Form 4",
    "unusual options activity today whale alert",
    "congress stock trades this week senate house",
    "political trades today quiverquant",
]

# Base watchlist to evaluate for tomorrow
WATCHLIST = [
    "SPCX","FCEL","CRWV","HIMS","SOFI","CIFR","AAL","CCL","CLSK","RIOT",
    "WULF","MARA","RKT","OPEN","NU","KMI","DAL","LUNR","RDW","JOBY",
    "SOUN","BBAI","QBTS","IONQ","HIVE","PLTR","RIVN","NIO","ASTS","RKLB",
]

# ── Free Order Flow Feeds ─────────────────────────────────────────────────────
ORDERFLOW_SOURCES = {
    "barchart_unusual":  "https://www.barchart.com/options/unusual-activity/stocks",
    "barchart_volume":   "https://www.barchart.com/stocks/stocks-by-option-volume",
    "openinsider":       "https://openinsider.com/screener?s=&o=&pl=&ph=&ls=&lh=&fd=1&td=0&tdr=&fdp=0&tdp=0&xp=1&xs=1&vl=100000&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc=&sortcol=0&cnt=20&page=1",
    "capitoltrades":     "https://www.capitoltrades.com/trades?period=1w",
    "wsb":               "https://www.reddit.com/r/wallstreetbets/hot.json",
    "options_reddit":    "https://www.reddit.com/r/options/hot.json",
    "stocks_reddit":     "https://www.reddit.com/r/stocks/hot.json",
}

# News sources for catalysts
NEWS_SOURCES = {
    "reuters_markets":   "https://www.reuters.com/markets/",
    "reuters_tech":      "https://www.reuters.com/technology/",
    "reuters_business":  "https://www.reuters.com/business/",
    "zacks_earnings":    "https://www.zacks.com/earnings/earnings-calendar.php",
    "zacks_upgrades":    "https://www.zacks.com/research/reports/zacks-recommendations.php",
}

def fetch_reuters_headlines():
    """Fetch latest Reuters market headlines for catalyst detection."""
    import urllib.request, re
    results = []
    for name, url in [
        ("markets",  "https://www.reuters.com/markets/"),
        ("tech",     "https://www.reuters.com/technology/"),
    ]:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            # Extract headlines
            headlines = re.findall(r'"headline":"([^"]{20,120})"', html)
            headlines += re.findall(r'<h3[^>]*>([^<]{20,120})</h3>', html)
            headlines = list(set(headlines))[:15]
            results.extend(headlines)
            print(f"    ✅ Reuters {name}: {len(headlines)} headlines")
        except Exception as e:
            print(f"    ⚠️  Reuters {name}: {str(e)[:40]}")
    return results[:20]


def fetch_zacks_data():
    """Fetch Zacks earnings calendar and analyst upgrades."""
    import urllib.request, re
    zacks_data = {"earnings_today": [], "upgrades": [], "surprises": []}
    # Earnings calendar
    try:
        url = "https://www.zacks.com/earnings/earnings-calendar.php"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        tickers = re.findall(r'quote/([A-Z]{1,5})"', html)
        tickers = list(dict.fromkeys(tickers))[:20]
        zacks_data["earnings_today"] = tickers
        print(f"    ✅ Zacks earnings: {len(tickers)} companies — {', '.join(tickers[:8])}")
    except Exception as e:
        print(f"    ⚠️  Zacks earnings: {str(e)[:40]}")
    # Strong buys / upgrades
    try:
        url = "https://www.zacks.com/research/reports/zacks-recommendations.php"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        tickers = re.findall(r'quote/([A-Z]{1,5})"', html)
        tickers = list(dict.fromkeys(tickers))[:20]
        zacks_data["upgrades"] = tickers
        print(f"    ✅ Zacks upgrades: {len(tickers)} stocks — {', '.join(tickers[:8])}")
    except Exception as e:
        print(f"    ⚠️  Zacks upgrades: {str(e)[:40]}")
    return zacks_data

def fetch_barchart_unusual():
    """
    Fetch unusual options activity from Barchart free page.
    Returns list of tickers with unusual activity detected.
    Falls back to web search if direct fetch fails.
    """
    import urllib.request, re
    url = "https://www.barchart.com/options/unusual-activity/stocks?viewName=main"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # Extract ticker symbols from the page
        tickers = re.findall(r'"symbol":"([A-Z]{1,5})"', html)
        tickers = list(dict.fromkeys(tickers))[:25]  # dedupe, top 25
        if tickers:
            print(f"    ✅ Barchart unusual options: {len(tickers)} tickers — {', '.join(tickers[:10])}")
            return {"source": "barchart", "tickers": tickers, "method": "direct"}
    except Exception as e:
        print(f"    ⚠️ Barchart direct fetch failed: {str(e)[:50]}")

    # Fallback: use web search queries (already in EOD scanner)
    print("    📡 Using web search fallback for order flow")
    return {"source": "web_search", "tickers": [], "method": "fallback"}


def fetch_barchart_volume():
    """Fetch top stocks by options volume from Barchart."""
    import urllib.request, re
    url = "https://www.barchart.com/stocks/stocks-by-option-volume?viewName=main"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        tickers = re.findall(r'"symbol":"([A-Z]{1,5})"', html)
        tickers = list(dict.fromkeys(tickers))[:20]
        if tickers:
            print(f"    ✅ Barchart options volume: {len(tickers)} tickers — {', '.join(tickers[:10])}")
            return tickers
    except Exception as e:
        print(f"    ⚠️ Barchart volume fetch: {str(e)[:50]}")
    return []


def fetch_openinsider():
    """Fetch latest insider buys from OpenInsider free screener."""
    import urllib.request, re
    url = ("https://openinsider.com/screener?s=&o=&pl=&ph=&ls=&lh=&fd=1&td=0"
           "&xp=1&xs=1&vl=100000&sortcol=0&cnt=20&page=1")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        tickers = re.findall(r'ticker=([A-Z]{1,5})', html)
        tickers = list(dict.fromkeys(tickers))[:15]
        if tickers:
            print(f"    ✅ Insider buys today: {len(tickers)} tickers — {', '.join(tickers[:8])}")
            return tickers
    except Exception as e:
        print(f"    ⚠️ OpenInsider fetch: {str(e)[:50]}")
    return []


# ── Reddit WallStreetBets Feed ────────────────────────────────────────────────
def fetch_wsb_trending(limit=25):
    """
    Pull hot posts from r/wallstreetbets via Reddit's public JSON API.
    Extracts ticker mentions and basic sentiment from titles.
    No auth needed for public read access.
    """
    url = f"https://www.reddit.com/r/wallstreetbets/hot.json?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "KevinTrader/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e), "posts": []}

    posts = []
    for child in data.get("data", {}).get("children", []):
        p = child.get("data", {})
        posts.append({
            "title": p.get("title", ""),
            "score": p.get("score", 0),
            "comments": p.get("num_comments", 0),
            "flair": p.get("link_flair_text", ""),
            "url": "https://reddit.com" + p.get("permalink", ""),
        })
    return {"posts": posts}

def extract_tickers(posts, universe):
    """Count ticker mentions across WSB post titles."""
    import re
    mentions = {}
    sentiment = {}
    for post in posts:
        title = post["title"].upper()
        # Look for $TICKER or standalone caps
        found = set(re.findall(r'\$([A-Z]{1,5})', title))
        found |= set(t for t in universe if f" {t} " in f" {title} " or f" {t}," in title)
        for t in found:
            mentions[t] = mentions.get(t, 0) + 1
            # Crude sentiment from flair + title keywords
            bull = any(w in title for w in ["CALL", "MOON", "BUY", "LONG", "🚀", "BULL", "SQUEEZE"])
            bear = any(w in title for w in ["PUT", "SHORT", "CRASH", "BEAR", "DUMP", "PUTS"])
            if t not in sentiment: sentiment[t] = {"bull": 0, "bear": 0}
            if bull: sentiment[t]["bull"] += 1
            if bear: sentiment[t]["bear"] += 1
    return mentions, sentiment

SYSTEM_PROMPT = """
You are Kevin's end-of-day lead scanner. After market close, build a ranked
watchlist for the NEXT trading day combining technicals, news, catalysts,
insider buying, whale activity, and political trades.

For the provided tickers and WSB social data:

1. Get today's closing quotes (price + % change)

2. Search the web for NEWS & CATALYSTS:
   - Earnings (reported today AH or reporting tomorrow)
   - FDA decisions, drug approvals
   - Contract wins, partnerships, product launches
   - Analyst upgrades/downgrades
   - Breaking news driving the move

3. Search for INSIDER BUYS (SEC Form 4):
   - Search: "insider buying today SEC Form 4 large purchase"
   - Look for: C-suite purchases >$100K (CEO, CFO, COO buying own stock)
   - Cross-reference against watchlist tickers
   - Insiders buying = strong conviction signal

4. Search for WHALE / UNUSUAL OPTIONS ACTIVITY:
   - Search: "unusual options activity today whale alert dark pool"
   - Look for: large block options trades, sweep orders, dark pool prints
   - Tickers with unusual call sweeps = bullish whale positioning
   - Tickers with unusual put sweeps = bearish whale positioning

5. Search for POLITICAL / CONGRESS TRADES:
   - Search: "congress stock trades today senate house quiverquant capitoltrades"
   - Look for: recent purchases by senators or representatives
   - Political trades often front-run regulatory approvals, contracts, legislation
   - Bipartisan buys = strongest signal

6. Factor in WSB social sentiment data provided

7. RANK the top 10 next-day candidates combining ALL signals

For each top candidate output:
  - Symbol, close price, % change
  - PRIMARY CATALYST (what's driving it)
  - INSIDER signal (any Form 4 buys? who bought, how much?)
  - WHALE signal (unusual options? call sweeps? dark pool?)
  - POLITICAL signal (any congress trades? which member?)
  - WSB sentiment (trending? bull/bear?)
  - Setup type (continuation, earnings, squeeze, insider-driven)
  - Direction for tomorrow (calls/puts/shares)
  - Casey zone setup (Zone 1 = PDH, Zone 2 target, clean air?)

CONVICTION SCORING (add these as bonus to technical score):
  +2 = Insider buy >$500K by C-suite officer
  +2 = Large whale call sweep (unusual volume >5x normal)
  +2 = Congress member purchased this week
  +1 = Multiple insiders buying same ticker
  +1 = Dark pool print >$1M
  +1 = WSB trending with bullish sentiment

VOLUME FILTER: Only include tickers with average daily volume > 10,000,000 shares.
Low volume tickers have fake moves, wide option spreads, and are hard to exit.
This is a hard filter — skip any ticker that doesn't meet the 10M daily volume minimum.

Prioritize: CLEAR catalyst + whale/insider/political confirmation + technical setup.
Output a clean ranked watchlist with full reasoning for each pick.
"""

def run_eod_scan():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Set ANTHROPIC_API_KEY"); return
    client = anthropic.Anthropic(api_key=api_key)
    now = now_et = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")

    print(f"""
╔══════════════════════════════════════════════════════════╗
║   🌙 END-OF-DAY LEAD SCANNER — NEXT-DAY SETUPS         ║
║   {now:52s}║
║   Technicals + News + Earnings + WSB Sentiment          ║
╚══════════════════════════════════════════════════════════╝
""")

    # Step 1: Pull all free order flow feeds
    print("  📡 Pulling free order flow feeds...")
    print("    Layer 1: Barchart unusual options activity")
    barchart_flow   = fetch_barchart_unusual()
    barchart_volume = fetch_barchart_volume()

    print("    Layer 2: OpenInsider buys (>$100K today)")
    insider_tickers = fetch_openinsider()

    print("    Layer 3: Reuters market headlines")
    reuters_headlines = fetch_reuters_headlines()

    print("    Layer 4: Zacks earnings + upgrades")
    zacks_data = fetch_zacks_data()

    print("    Layer 5: Reddit WSB feed")
    # Step 1: Pull WSB feed
    print("  📱 Pulling r/wallstreetbets hot feed...")
    wsb = fetch_wsb_trending(limit=30)
    if "error" in wsb:
        print(f"    ⚠️ Reddit fetch failed: {wsb['error']}")
        print(f"    (May need Reddit connector via MCP for reliable access)")
        wsb_summary = "WSB feed unavailable this run."
    else:
        mentions, sentiment = extract_tickers(wsb["posts"], WATCHLIST)
        top_wsb = sorted(mentions.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"    ✅ {len(wsb['posts'])} posts pulled")
        if top_wsb:
            print("    🔥 WSB trending tickers:")
            for t, c in top_wsb:
                s = sentiment.get(t, {"bull":0,"bear":0})
                lean = "🟢 bull" if s["bull"]>s["bear"] else "🔴 bear" if s["bear"]>s["bull"] else "⚪ mixed"
                print(f"       {t}: {c} mentions, {lean}")
        wsb_summary = json.dumps({"trending": dict(top_wsb), "sentiment": sentiment})

    # Step 2: AI analysis combining everything
    print("\n  🔎 Running news + catalyst + technical analysis...")
    # Build order flow summary
    flow_summary = {
        "barchart_unusual":  barchart_flow.get("tickers", [])[:15],
        "barchart_volume":   barchart_volume[:15],
        "insider_buys":      insider_tickers[:10],
        "zacks_earnings":    zacks_data.get("earnings_today", [])[:10],
        "zacks_upgrades":    zacks_data.get("upgrades", [])[:10],
        "reuters_headlines": reuters_headlines[:10],
        "source":            "barchart + openinsider + reuters + zacks + wsb",
    }

    instruction = f"""
Build tomorrow's watchlist. Today is {now}.

Tickers to evaluate: {json.dumps(WATCHLIST)}

WSB social data (mentions + sentiment):
{wsb_summary}

FREE ORDER FLOW DATA (pulled live this scan):
{json.dumps(flow_summary, indent=2)}

Order flow + news interpretation:
- barchart_unusual: tickers with UNUSUAL options activity today (volume spike vs OI)
- barchart_volume: tickers with HIGHEST total options volume today
- insider_buys: C-suite insiders bought stock today (>$100K via SEC Form 4)
- zacks_earnings: companies reporting earnings today AH or tomorrow BMO
- zacks_upgrades: Zacks analyst upgrades/strong buys today
- reuters_headlines: latest Reuters market headlines (check for catalyst mentions)
If a ticker appears in MULTIPLE lists = maximum conviction signal
Cross-reference reuters_headlines for any mention of watchlist tickers

Steps:
1. Get closing quotes for the tickers
2. Web-search news and catalysts for the most promising movers
3. Cross-reference with order flow data above — flag any watchlist ticker appearing in flow lists
4. Web-search for whale activity: "unusual options activity today whale alert sweep {now[:10]}"
5. Web-search for political trades: "congress stock trades this week capitoltrades quiverquant"
6. Check earnings calendar for tomorrow
7. Combine ALL signals: technical + order flow + social + insider + political
8. Rank the top 10 next-day candidates

CONVICTION TIERS:
  🔥🔥 ELITE: Technical 7+ AND in barchart_unusual AND insider buy
  🔥 PRIME: Technical 7+ AND appears in any order flow list
  ⚡ WATCH: Technical 5-6 OR appears in order flow without technical confirm

For each candidate include: catalyst, order flow signal, insider signal, political signal, WSB sentiment, Casey zone setup, direction.
"""

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": instruction}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"],
        tools=[{"type": "web_search_20250305", "name": "web_search"}]
    )

    print("\n" + "="*60)
    print("  📋 TOMORROW'S WATCHLIST")
    print("="*60 + "\n")
    for block in response.content:
        if hasattr(block, "text") and block.text.strip():
            print(block.text)

    # Save
    os.makedirs(os.path.expanduser("~/scan_logs"), exist_ok=True)
    path = os.path.expanduser(f"~/scan_logs/eod_watchlist_{datetime.now(ET).strftime('%Y%m%d')}.txt")
    with open(path, "w") as f:
        for block in response.content:
            if hasattr(block, "text"):
                f.write(block.text)
    print(f"\n  💾 Saved: {path}")

if __name__ == "__main__":
    run_eod_scan()
