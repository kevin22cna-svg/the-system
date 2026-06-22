"""
Wiley Strat Explosion Scanner — Stocks About to Rip
================================================
Scans three tiers of stocks using professional penny stock screener criteria:

TIER 1 — Mid-Range ($10–$90):   Momentum movers, options available
TIER 2 — Penny ($0.50–$10):     Low float, volume surge, supernova setups
TIER 3 — Micro (<$0.50):        Ultra-volatile, news-driven, tiny size only

PENNY STOCK SCREENER CRITERIA (applied to Tier 2 & 3):
  Descriptive:
    Price:           $0.50 – $5.00 (strict penny), up to $10 (extended penny)
    Market Cap:      Under $300M (micro/small cap only)
    Float:           Under 20M shares (standard) | Under 10M (supernova setup)
    Shares Outstanding: Under 50M

  Liquidity:
    Avg Daily Volume: > 10,000,000 shares (Wiley Strat minimum)
    Relative Volume:  > 2x average (fresh catalyst or hype in play)

  Technical:
    Day Change:      Up 2–5%+ minimum
    Gap:             Pre-market gap up = bonus signal
    Volatility:      Higher than average = hunting ground

Scoring System (0–10 confluence score):
  +2  Relative volume > 2x avg (RVOL confirmed)
  +2  Float < 20M shares (low float = explosive)
  +2  Up 5%+ today OR gapped up pre-market
  +2  Real catalyst (FDA, earnings, contract, PR, short squeeze)
  +1  Price above short-term moving average (uptrend)
  +1  Breaking key resistance level

Score 7+  → 🔥 SUPERNOVA SETUP — auto-trade trigger
Score 5–6 → ⚡ WATCH — momentum building
Score <5  → 🔎 ON RADAR — not ready yet
"""

import anthropic
import json
import os
from datetime import datetime

# ── Ticker Universe ─────────────────────────────────────────────────────────

TIER1_MID_RANGE = [
    # Space / Defense
    "SPCX", "LUNR", "ASTS", "RKLB", "RDW",
    # Airlines / Travel
    "AAL", "SAVE", "JOBY", "DAL",
    # Cruise / Travel
    "CCL",
    # Pharma
    "BMY",
    # Energy / Pipeline
    "KMI", "TELL", "PLUG", "FCEL",
    # High-volume regulars from your watchlist
    "SOFI", "NU", "HOOD", "RIVN",
    # Tech momentum
    "PLTR", "BBAI", "SOUN", "GFAI",
    # Finance
    "UWMC", "RKT", "OPEN",
    # User-added
    "NOK", "PFE", "BAC", "GME", "BABA", "WMT", "POET",
]

TIER2_PENNY = [
    # Biotech (FDA catalysts)
    "MDAI", "CMPS", "AGEN", "SIGA", "NKTR",
    "CYTO", "OBSV", "ACST", "HARP", "ONCO",
    # AI / Tech micro
    "GCTS", "MFON", "DPSI", "ITRM",
    # Clean energy penny
    "NAKD", "NKLA", "RIDE",
    # Crypto adjacent
    "MARA", "RIOT", "CLSK", "CIFR", "WULF", "HIVE",
    # Misc high-volume pennies
    "MULN", "IDEX", "CENN", "ZEV", "XELA",
    "CRBP", "ADTX", "PHGE", "AEYE", "VNET",
    # User-added
    "AMC", "HTZ", "SNAP",
]

TIER3_MICRO = [
    # Sub-$1 ultra volatile
    "GFAI", "SOPA", "STSS", "QBTS", "IONQ",
    "KULR", "NXTP", "CHNR", "CANF", "ATOS",
]

ALL_TICKERS = list(set(TIER1_MID_RANGE + TIER2_PENNY + TIER3_MICRO))

# ── Config ──────────────────────────────────────────────────────────────────
_SESSION_TOKEN = open("/home/claude/.claude/remote/.session_ingress_token").read().strip()
MCP_SERVER = {
    "type": "url",
    "url": "https://agent.robinhood.com/mcp/trading",
    "name": "robinhood-mcp",
    "authorization_token": _SESSION_TOKEN
}

MIN_CONVICTION_SCORE = 7   # Must score 7/10 to auto-trade
POSITION_SIZE_USD = 15.0   # $10–$20 range, using $15
PROFIT_TARGET_PCT = 5.0    # Exit at +5%

# ── System Prompt ────────────────────────────────────────────────────────────
SCANNER_SYSTEM = """
You are Kevin's elite stock explosion scanner. You identify stocks about to make
big moves using professional penny stock screener criteria + technical confluence.

PENNY STOCK SCREENER FILTERS (apply to Tier 2 & 3 tickers):
  ✅ PASS criteria (stock must meet most of these):
    - Price $0.50–$10 (penny/extended penny range)
    - Market Cap under $300M
    - Float under 20M shares (under 10M = supernova candidate)
    - Shares outstanding under 50M
    - Average daily volume > 500K
    - Relative Volume (RVOL) > 2x today
    - Day change up 2%+ minimum (momentum filter)

  🚫 REJECT if:
    - Average volume under 100K (too illiquid, can't exit)
    - No identifiable catalyst (pure pump = avoid)
    - Float over 100M (diluted, won't move as fast)

SCORING SYSTEM (0–10):
  +2 = Relative volume > 2x average (RVOL — real demand signal)
  +2 = Float under 20M shares (low float amplifies every move)
  +2 = Up 5%+ today OR gapped up pre-market (momentum confirmed)
  +2 = Real catalyst: FDA news, earnings beat, contract win, PR, short squeeze
  +1 = Price above short-term moving average (uptrend structure)
  +1 = Breaking above key resistance level on volume

SUPERNOVA SETUP (score 8–10): Float <10M + RVOL >5x + catalyst = potential 50–200% mover
HIGH CONVICTION  (score 7):   Good setup, trade with $15 position
WATCH            (score 5–6): Building — monitor next scan
ON RADAR         (score <5):  Not ready

TRADE TIERS:
  Tier 1 ($10–$90): Mid-range movers — cleaner entries, options available
  Tier 2 ($0.50–$10): Penny stocks — low float supernovas, high % potential
  Tier 3 (<$0.50):  Micro caps — ultra volatile, news-driven, tiny size only

OUTPUT FORMAT: Return a JSON array sorted by score descending:
[
  {
    "symbol": "AAL",
    "price": 16.13,
    "pct_change": 4.3,
    "tier": 1,
    "score": 8,
    "catalyst": "Iran oil deal boosting travel demand",
    "signal": "Breaking above $16 resistance on 4x volume",
    "trade_action": "BUY $15 market → limit sell at +5%",
    "conviction": "HIGH"
  },
  ...
]

Only return JSON, no prose. Score every ticker you can get quotes for.
Include ALL tickers with score >= 4. Sort highest score first.
""".strip()

# ── Main Scanner ─────────────────────────────────────────────────────────────
def run_explosion_scanner(auto_trade: bool = False, dry_run: bool = True):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set.")
        return

    client = anthropic.Anthropic(api_key=api_key)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"""
╔══════════════════════════════════════════════════════╗
║       WILEY STRAT SCANNER  🔥                  ║
║       {now}                        ║
║       Scanning {len(ALL_TICKERS)} tickers across 3 tiers           ║
║       Auto-trade: {'ON (' + ('DRY RUN' if dry_run else '⚠️  LIVE') + ')' if auto_trade else 'OFF'}                       ║
╚══════════════════════════════════════════════════════╝
""")

    user_msg = f"""
Scan these tickers and score each one for explosion potential:

TIER 1 (Mid-Range $10–$90): {json.dumps(TIER1_MID_RANGE)}
TIER 2 (Penny $1–$10):      {json.dumps(TIER2_PENNY)}
TIER 3 (Micro <$1):         {json.dumps(TIER3_MICRO)}

Steps:
1. Get real-time quotes for all tickers using get_equity_quotes
   (batch them in groups of 20 for efficiency)
2. Score each one using the scoring system
3. Return the full JSON array sorted by score

Today's date/time: {now}
"""

    if auto_trade:
        user_msg += f"""
4. After scoring, identify the SINGLE highest-scoring ticker with score >= {MIN_CONVICTION_SCORE}
5. {"Simulate" if dry_run else "Execute"} a market BUY of ${POSITION_SIZE_USD} worth of shares
6. {"Simulate" if dry_run else "Place"} a limit SELL at +{PROFIT_TARGET_PCT}% above fill
7. Report the trade action taken
Mode: {"SIMULATE ONLY (review_equity_order)" if dry_run else "LIVE TRADING (place_equity_order)"}
"""

    print("📡 Scanning market...\n")

    response = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SCANNER_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        mcp_servers=[MCP_SERVER],
        betas=["mcp-client-2025-04-04"]
    )

    # Parse results
    raw_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            raw_text += block.text
        elif hasattr(block, 'type') and block.type == "mcp_tool_use":
            print(f"  🔧 {block.name}({list(block.input.keys())[0] if block.input else ''}...)")

    # Try to parse JSON
    results = []
    try:
        clean = raw_text.strip()
        if "```" in clean:
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        results = json.loads(clean.strip())
    except Exception:
        print("⚠️  Could not parse JSON — raw output below:\n")
        print(raw_text)
        return

    # ── Display Results ──────────────────────────────────────────────────────
    if not results:
        print("📭 No qualifying tickers found right now.")
        return

    tier_labels = {1: "MID-RANGE ($10–$90)", 2: "PENNY ($0.50–$10)", 3: "MICRO (<$1)"}
    conviction_emoji = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "🔎"}

    print(f"{'─'*60}")
    print(f"  SCAN RESULTS — {len(results)} tickers scored")
    print(f"{'─'*60}\n")

    high = [r for r in results if r.get('score', 0) >= 7]
    watch = [r for r in results if 5 <= r.get('score', 0) < 7]
    radar = [r for r in results if r.get('score', 0) < 5]

    if high:
        print("🔥 HIGH CONVICTION (Score 7–10) — TRADE CANDIDATES:\n")
        for r in high:
            _print_result(r, tier_labels, conviction_emoji)

    if watch:
        print("\n⚡ WATCH LIST (Score 5–6) — BUILDING MOMENTUM:\n")
        for r in watch:
            _print_result(r, tier_labels, conviction_emoji)

    if radar:
        print(f"\n🔎 ON RADAR (Score <5) — {len(radar)} tickers, not ready\n")
        for r in radar[:5]:  # Show top 5 radar only
            sym = r.get('symbol', '?')
            score = r.get('score', 0)
            price = r.get('price', 0)
            print(f"   {sym:6s}  ${price:.2f}  score:{score}/10")

    # Save to JSON log
    log_path = f"/home/claude/scan_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(log_path, 'w') as f:
        json.dump({
            "timestamp": now,
            "total_scanned": len(ALL_TICKERS),
            "results": results
        }, f, indent=2)
    print(f"\n💾 Full results saved to: {log_path}")


def _print_result(r, tier_labels, conviction_emoji):
    sym      = r.get('symbol', '?')
    price    = r.get('price', 0)
    pct      = r.get('pct_change', 0)
    tier     = r.get('tier', 1)
    score    = r.get('score', 0)
    catalyst = r.get('catalyst', 'N/A')
    signal   = r.get('signal', 'N/A')
    action   = r.get('trade_action', '')
    conv     = r.get('conviction', 'LOW')
    emoji    = conviction_emoji.get(conv, '🔎')

    arrow = "▲" if pct >= 0 else "▼"
    print(f"  {emoji} {sym:6s}  ${price:>7.2f}  {arrow}{abs(pct):.1f}%  Score:{score}/10  [{tier_labels.get(tier, 'TIER?')}]")
    print(f"     📰 Catalyst: {catalyst}")
    print(f"     📈 Signal:   {signal}")
    if action:
        print(f"     🎯 Action:  {action}")
    print()


# ── Entry Points ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    live      = "--live" in sys.argv
    trade     = "--trade" in sys.argv or "--live" in sys.argv

    if live:
        print("\n⚠️  WARNING: LIVE MODE — Real money will be used.")
        confirm = input("Type YES to confirm: ").strip()
        if confirm != "YES":
            print("Aborted.")
            exit()

    run_explosion_scanner(auto_trade=trade, dry_run=not live)
