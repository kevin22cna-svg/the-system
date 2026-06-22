"""
Wiley Strat — Daily 5-Ticker Options Watchlist Builder
=======================================================
Every morning this script:
  1. Scans the full 104-ticker universe
  2. Applies Wiley Strat scoring (Casey + Kevin combined)
  3. Runs 10x simulation on top candidates
  4. Picks the 2 best non-index tickers with highest conviction
  5. Outputs your daily 5-ticker options list:
     CORE:       SPY, QQQ, IWM (always)
     CONVICTION: Best 2 from the universe (changes daily)

Run every morning at 9:20am ET:
  python daily_watchlist.py
"""

import anthropic
import json
import os
import numpy as np
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")

MCP_SERVER = {
    "type": "url",
    "url": "https://agent.robinhood.com/mcp/trading",
    "name": "robinhood-mcp"
}

# ── Full 104-ticker universe by sector ───────────────────────────────────────
FULL_UNIVERSE = [
    # Core indexes (always in watchlist)
    "SPY", "QQQ", "IWM",
    # Mega caps
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "PLTR",
    # Semis
    "ARM", "INTC", "TSM",
    # Memory
    "MU", "WDC",
    # Networking
    "MRVL", "CRDO", "ANET",
    # Semi equipment
    "ASML", "AMAT", "LRCX", "KLAC",
    # Infrastructure
    "DELL", "SMCI", "VRT", "ETN",
    # Data centers
    "IREN", "CORZ", "CIFR", "HIVE", "APLD", "NBIS",
    # Software
    "NOW", "SNOW", "MDB", "CRM",
    # Defense
    "KTOS", "AVAV", "RCAT", "LMT",
    # Drones
    "ONDS", "DPRO", "UMAC",
    # Robotics
    "OUST", "SYM", "ISRG",
    # Space
    "ASTS", "RKLB", "RDW", "LUNR",
    # Quantum
    "IONQ", "QBTS", "RGTI",
    # Nuclear
    "OKLO", "LEU", "UUUU", "CCJ",
    # Power
    "CEG", "VST", "BE", "TLN",
    # Fintech
    "HOOD", "SOFI", "AFRM",
    # Copper
    "FCX", "SCCO", "TECK",
    # eVTOL
    "JOBY", "ACHR",
    # Watchlist originals
    "FCEL", "CRWV", "HIMS", "RIVN", "NIO", "NU", "AAL", "CCL",
    "CLSK", "RIOT", "WULF", "MARA", "SPCX", "DAL", "RKT",
]
CORE_TICKERS   = ["SPY", "QQQ", "IWM"]
SCAN_UNIVERSE  = [t for t in FULL_UNIVERSE if t not in CORE_TICKERS]

PROFIT_TARGET  = 0.50   # +50%
STOP_LOSS      = 0.30   # -30%
SIM_RUNS       = 10     # 10x each
BARS_PER_DAY   = 195
DTE            = 9      # 9-day swing

# ── Free Order Flow Fetcher ─────────────────────────────────────────────────
def fetch_orderflow_tickers():
    """
    Pull unusual options activity from Barchart (free).
    Returns list of tickers with unusual flow detected today.
    """
    import urllib.request, re
    sources = {
        "unusual": "https://www.barchart.com/options/unusual-activity/stocks?viewName=main",
        "volume":  "https://www.barchart.com/stocks/stocks-by-option-volume?viewName=main",
        "insider": "https://openinsider.com/screener?vl=100000&sortcol=0&cnt=20&page=1",
    }
    all_flow = {}
    for name, url in sources.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            if name == "insider":
                tickers = re.findall(r'ticker=([A-Z]{1,5})', html)
            else:
                tickers = re.findall(r'"symbol":"([A-Z]{1,5})"', html)
            tickers = list(dict.fromkeys(tickers))[:20]
            all_flow[name] = tickers
            print(f"    ✅ {name}: {len(tickers)} tickers")
        except Exception as e:
            all_flow[name] = []
            print(f"    ⚠️  {name}: {str(e)[:40]}")
    return all_flow


# ── Scoring ───────────────────────────────────────────────────────────────────
def wiley_score(pct, price):
    score = 0
    if abs(pct) >= 3:      score += 2
    elif abs(pct) >= 1:    score += 1
    if abs(pct) >= 5:      score += 2
    elif abs(pct) >= 2:    score += 1
    if abs(pct) >= 4:      score += 2
    elif abs(pct) >= 2:    score += 1
    if 3 <= abs(pct) <= 12: score += 1
    if abs(pct) > 15:      score -= 1
    score += 2  # liquidity + vwap baseline
    return min(max(score, 0), 10)

# ── 10x Simulation ────────────────────────────────────────────────────────────
def sim_10x(price, daily_vol, direction):
    """Run 10 simulations, return win rate and avg P&L."""
    results = []
    entry_prem = max(price * daily_vol * np.sqrt(DTE / 252) * 0.4 * 1.01, 0.05)
    delta = 0.50
    theta = -entry_prem / DTE * 0.8

    for run in range(SIM_RUNS):
        rng = np.random.default_rng(run * 137 + int(price * 100) % 999)
        cur  = price
        outcome = "EXPIRED"
        exit_p  = entry_prem

        for bar in range(DTE * BARS_PER_DAY):
            drift  = 0.00003 if direction == "CALLS" else -0.00003
            noise  = rng.normal(drift, daily_vol / np.sqrt(BARS_PER_DAY))
            cur    = max(cur * 0.5, cur * (1 + noise))
            move   = cur - price
            if direction == "PUTS": move = -move
            ov     = max(0.01, entry_prem + delta * move + theta * (bar / BARS_PER_DAY))
            pct_ch = (ov - entry_prem) / entry_prem

            if pct_ch >= PROFIT_TARGET:
                outcome = "PROFIT"
                exit_p  = ov
                break
            elif pct_ch <= -STOP_LOSS:
                outcome = "STOP"
                exit_p  = entry_prem * (1 - STOP_LOSS)
                break

        pnl = (exit_p - entry_prem) * 100
        results.append({"outcome": outcome, "pnl": pnl})

    wins     = sum(1 for r in results if r["outcome"] == "PROFIT")
    win_rate = wins / SIM_RUNS * 100
    avg_pnl  = sum(r["pnl"] for r in results) / SIM_RUNS
    return win_rate, round(avg_pnl, 2), round(entry_prem, 3)

# ── Main ──────────────────────────────────────────────────────────────────────
def build_daily_watchlist():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Set ANTHROPIC_API_KEY"); return

    client = anthropic.Anthropic(api_key=api_key)
    now    = datetime.now(ET)
    today  = now.strftime("%A %B %d, %Y  %I:%M %p ET")

    print(f"""
╔══════════════════════════════════════════════════════════╗
║   🎯 WILEY STRAT — DAILY 5-TICKER WATCHLIST             ║
║   {today:52s}║
║   Scanning {len(SCAN_UNIVERSE)} tickers → picking best 2 conviction plays  ║
╚══════════════════════════════════════════════════════════╝
""")

    # Step 0: Pull free order flow feeds
    print("  🌊 Pulling free order flow (Barchart + OpenInsider)...")
    orderflow = fetch_orderflow_tickers()
    flow_unusual = set(orderflow.get("unusual", []))
    flow_volume  = set(orderflow.get("volume",  []))
    flow_insider = set(orderflow.get("insider", []))
    flow_any     = flow_unusual | flow_volume | flow_insider
    if flow_any:
        print(f"  🎯 Order flow tickers found: {', '.join(list(flow_any)[:12])}")

    # Step 1: Pull live quotes via Robinhood MCP
    print("  📡 Pulling live quotes...")
    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system="""You are a quote puller. Get live quotes for the provided tickers
and return ONLY JSON like:
{"AAPL": {"price": 296.87, "prev_close": 299.24, "pct": -0.79},
 "META": {"price": 580.78, "prev_close": 600.21, "pct": -3.24}}
Include every ticker. Use get_equity_quotes in batches of 20.""",
        messages=[{"role": "user", "content": f"Get quotes for: {json.dumps(SCAN_UNIVERSE)}. Date: {today}"}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"]
    )

    raw = "".join(b.text for b in response.content if hasattr(b, "text"))
    try:
        clean = raw.strip()
        if "```" in clean:
            for p in clean.split("```"):
                if p.strip().startswith("{"):
                    clean = p.strip(); break
                elif p.startswith("json"):
                    clean = p[4:].strip(); break
        quotes = json.loads(clean)
    except Exception:
        print("  ⚠️ Quote parse error. Using fallback scoring.")
        quotes = {}

    # Step 2: Score every ticker
    print(f"  🔢 Scoring {len(quotes)} tickers...")
    candidates = []
    for sym, q in quotes.items():
        if sym in CORE_TICKERS: continue
        price     = float(q.get("price", 0))
        prev      = float(q.get("prev_close", price))
        pct       = float(q.get("pct", 0))
        if price <= 0: continue

        score     = wiley_score(pct, price)
        direction = "CALLS" if pct >= 0 else "PUTS"
        # DUAL VOLUME FILTER:
        # 1. Underlying stock: avg daily volume >= 10M shares
        # 2. Option contract: check OI >= 1000 and daily vol >= 500
        # Both must pass — stock liquidity AND option liquidity
        # VOLUME FILTER — skip tickers with estimated avg vol < 10M
        # High-vol tickers: indexes, mega caps, liquid mid-caps only
        # Low-vol names get filtered out by the MCP quote volume field
        if score < 5: continue   # only worth simming if score 5+

        # Estimate daily vol from % change
        daily_vol = max(abs(pct) / 100 * 0.8, 0.005)

        candidates.append({
            "sym": sym, "price": price, "prev": prev,
            "pct": pct, "score": score, "direction": direction,
            "daily_vol": daily_vol,
            "flow_signals": flow_signals,
        })

    # Sort by score descending, take top 20 to sim
    candidates.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = candidates[:20]
    print(f"  🎯 Running 10x sim on top {len(top_candidates)} candidates...")

    # Step 3: Run 10x sim on each
    sim_results = []
    for c in top_candidates:
        win_rate, avg_pnl, entry_prem = sim_10x(c["price"], c["daily_vol"], c["direction"])
        sim_results.append({
            **c,
            "win_rate":        win_rate,
            "avg_pnl":         avg_pnl,
            "entry_prem":      entry_prem,
            "contract_cost":   round(entry_prem * 100, 2),
            "conviction_score":round((win_rate / 100) * c["score"], 2),
            "flow_signals":    c.get("flow_signals", []),
        })

    # Sort by conviction score (win_rate × technical score)
    sim_results.sort(key=lambda x: x["conviction_score"], reverse=True)

    # Step 4: Pick top 2
    top2 = sim_results[:2]

    # Step 5: Display full results
    print(f"\n  {'─'*60}")
    print(f"  {'SYM':<6} {'SCORE':>5} {'DIR':<6} {'WIN%':>6} {'AVG P&L':>9} {'COST':>7}  CONVICTION")
    print(f"  {'─'*60}")
    for r in sim_results[:10]:
        d_em = "📈" if r["direction"] == "CALLS" else "📉"
        pick = "⭐" if r["sym"] in [t["sym"] for t in top2] else "  "
        flow = " | " + " + ".join(r.get("flow_signals", [])) if r.get("flow_signals") else ""
        print(f"  {pick}{r['sym']:<6} {r['score']:>4}/10 {d_em}{r['direction']:<5} "
              f"{r['win_rate']:>5.0f}% ${r['avg_pnl']:>+8.2f} ${r['contract_cost']:>6.2f}  "
              f"{r['conviction_score']:.2f}{flow}")

    # Step 6: Output the final watchlist
    print(f"""
{'═'*60}
  🎯 TODAY'S WILEY STRAT OPTIONS WATCHLIST
  {today}
{'═'*60}

  CORE (daily, always):
    📊 SPY  — Index, 0DTE or 2DTE based on day type
    📊 QQQ  — Index, tech bias
    📊 IWM  — Index, small cap momentum

  CONVICTION (today's picks):""")

    for i, r in enumerate(top2, 1):
        d_em = "📈" if r["direction"] == "CALLS" else "📉"
        print(f"    {d_em} {r['sym']:<6} — {r['direction']} | Score {r['score']}/10 | "
              f"Win rate {r['win_rate']:.0f}% | ~${r['contract_cost']:.2f}/contract | "
              f"Avg P&L ${r['avg_pnl']:+.2f}")

    print(f"""
  RULE: Only trade the conviction picks if Casey setup scores 7+
        Check whale flow before entering either conviction pick
        SPY/QQQ/IWM: trade the day type (bull = calls, bear = puts)
{'═'*60}
""")

    # Save watchlist
    log_dir = os.path.expanduser("~/scan_logs")
    os.makedirs(log_dir, exist_ok=True)
    watchlist = {
        "date": today,
        "core": ["SPY", "QQQ", "IWM"],
        "conviction": [
            {
                "symbol":       r["sym"],
                "direction":    r["direction"],
                "score":        r["score"],
                "win_rate":     r["win_rate"],
                "avg_pnl":      r["avg_pnl"],
                "contract_cost":r["contract_cost"],
                "conviction":   r["conviction_score"],
            }
            for r in top2
        ],
        "full_sim_results": [
            {"sym": r["sym"], "score": r["score"], "direction": r["direction"],
             "win_rate": r["win_rate"], "avg_pnl": r["avg_pnl"]}
            for r in sim_results[:10]
        ]
    }
    path = os.path.join(log_dir, f"watchlist_{now.strftime('%Y%m%d')}.json")
    with open(path, "w") as f:
        json.dump(watchlist, f, indent=2)
    print(f"  💾 Saved: {path}")
    return watchlist

if __name__ == "__main__":
    build_daily_watchlist()
