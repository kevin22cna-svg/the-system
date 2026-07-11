"""
leveraged_universe.py — Master Leveraged ETF Reference
=======================================================
Single source of truth for every leveraged play in the system.
Organized by: Sector ETFs → Mag 7 basket → Single-stock 2x

SAME RULES AS SSO/SDS (from config.py):
  - Intraday ONLY — never hold overnight (decay + gap risk)
  - Force close by 3:45pm ET
  - +5% profit target | trailing stop 1% below session high
  - Use Casey's full framework — 4 levels, EMA fan, zone plays
  - Direction: underlying ETF/stock up → buy the LONG | down → buy the SHORT

Usage in any script:
    from leveraged_universe import SECTORS, MAG7, SINGLE_STOCK, get_pair, all_tickers
"""

# ── SECTOR LEVERAGED ETFs ─────────────────────────────────────────────────────
# Each entry: underlying XL ETF → (3x long, 3x short, notes)
# Direction trigger: use underlying ETF (XLK, XLF, etc.) for Casey framework
# then trade the leveraged version in that direction

SECTORS = {

    "XLK": {
        "name":     "Technology",
        "price":    183.05,          # June 24 2026 close — AH $187 (MU earnings)
        "change":   -0.62,           # % today (AH surge due to MU beat)
        "top5":     ["AAPL", "MSFT", "NVDA", "AVGO", "AMD"],
        "long":     "TECL",          # Direxion Daily Technology Bull 3x
        "short":    "TECS",          # Direxion Daily Technology Bear 3x
        "leverage": "3x",
        "note":     "Biggest sector. MU earnings AH = XLK gap up tomorrow. TECL > TECS bias.",
    },

    "XLF": {
        "name":     "Financials",
        "price":    53.71,
        "change":   -0.32,
        "top5":     ["BRK.B", "JPM", "V", "MA", "BAC"],
        "long":     "FAS",           # Direxion Daily Financial Bull 3x
        "short":    "FAZ",           # Direxion Daily Financial Bear 3x
        "leverage": "3x",
        "note":     "JPM near 52-wk high. Fed rate hike fears = headwind. PCE Thursday = key.",
    },

    "XLE": {
        "name":     "Energy",
        "price":    53.56,
        "change":   -1.65,           # RED today — oil below $70
        "top5":     ["XOM", "CVX", "COP", "WMB", "VLO"],
        "long":     "ERX",           # Direxion Daily Energy Bull 2x
        "short":    "ERY",           # Direxion Daily Energy Bear 2x
        "leverage": "2x",            # only 2x available for energy (not 3x)
        "note":     "Oil below $70 = XLE weak today. Airlines benefiting. ERY setup possible.",
    },

    "XLV": {
        "name":     "Health Care",
        "price":    153.36,
        "change":   +0.77,           # GREEN today
        "top5":     ["LLY", "JNJ", "ABBV", "UNH", "MRK"],
        "long":     "CURE",          # Direxion Daily Healthcare Bull 3x
        "short":    "LABD",          # Direxion Daily S&P Biotech Bear 3x (biotech focus)
        "leverage": "3x",
        "note":     "LLY = GLP-1 weight-loss mega-trend. XLV green today. CURE watch.",
    },

    "XLI": {
        "name":     "Industrials",
        "price":    180.25,
        "change":   +1.18,           # GREEN today — strong
        "top5":     ["CAT", "GE", "GEV", "RTX", "BA"],
        "long":     "DUSL",          # Direxion Daily Industrials Bull 3x
        "short":    "DFEN",          # Direxion Daily Aerospace & Defense Bull 3x (sub-sector)
        "leverage": "3x",
        "note":     "Defense + AI infrastructure = industrial strength. DUSL setup today.",
    },

    "XLC": {
        "name":     "Communication Services",
        "price":    106.53,
        "change":   -0.69,
        "top5":     ["META", "GOOGL", "GOOGL-C", "LYV", "TTWO"],
        "long":     None,            # no liquid 3x XLC-specific ETF
        "short":    None,
        "leverage": "N/A",
        "note":     "META+GOOGL = 30%+ weight. Trade META/GOOGL individually instead of XLC.",
    },

    "XLY": {
        "name":     "Consumer Discretionary",
        "price":    115.05,
        "change":   +1.13,           # GREEN today
        "top5":     ["AMZN", "TSLA", "HD", "MCD", "NKE"],
        "long":     "WANT",          # Direxion Daily Consumer Discretionary Bull 3x
        "short":    None,
        "leverage": "3x",
        "note":     "AMZN+TSLA = big weight. Consumer resilience theme. WANT if XLY breaks out.",
    },

    "XLP": {
        "name":     "Consumer Staples",
        "price":    84.44,
        "change":   +0.86,           # GREEN today — defensive bid
        "top5":     ["PG", "WMT", "COST", "KO", "PEP"],
        "long":     None,            # no liquid leveraged XLP ETF
        "short":    None,
        "leverage": "N/A",
        "note":     "Defensive sector. Trade individual names (WMT, COST) on momentum.",
    },

    "XLB": {
        "name":     "Materials",
        "price":    51.17,
        "change":   +0.59,           # GREEN today
        "top5":     ["LIN", "SHW", "FCX", "ECL", "NEM"],
        "long":     None,
        "short":    None,
        "leverage": "N/A",
        "note":     "Nuclear/uranium overlap (NEM = gold miner). Use URA/URNM for that theme.",
    },

    "XLRE": {
        "name":     "Real Estate",
        "price":    44.50,
        "change":   -0.31,
        "top5":     ["AMT", "PLD", "EQIX", "WELL", "CCI"],
        "long":     "DRN",           # Direxion Daily Real Estate Bull 3x
        "short":    "DRV",           # Direxion Daily Real Estate Bear 3x
        "leverage": "3x",
        "note":     "Rate sensitive — PCE Thursday could move this hard. DRV if PCE hot.",
    },

    "XLU": {
        "name":     "Utilities",
        "price":    45.56,
        "change":   +1.09,           # GREEN today — AI power demand + defensive
        "top5":     ["NEE", "SO", "DUK", "SRE", "D"],
        "long":     "UTSL",          # Direxion Daily Utilities Bull 3x
        "short":    None,
        "leverage": "3x",
        "note":     "AI data center power demand = utilities tailwind. Bloom Energy catalyst today.",
    },
}


# ── MAG 7 / MAG 10 BASKET ETFs ───────────────────────────────────────────────
# Trade the basket instead of individual names for broad tech momentum

MAG7 = {
    "MAGS": {
        "name":     "Roundhill Magnificent 7 ETF",
        "leverage": "1x",
        "components": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA"],
        "note":     "Pure 1x basket. Use as signal — if MAGS strong, long MAGX.",
    },
    "MAGX": {
        "name":     "Roundhill Daily 2X Long Magnificent 7",
        "leverage": "2x",
        "components": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA"],
        "long":     "MAGX",
        "short":    None,            # no 2x short basket yet
        "note":     "MU earnings tonight = chip sector bid tomorrow. MAGX long bias.",
    },
    "QQQU": {
        "name":     "Direxion Daily Concentrated Qs Bull 2x",
        "leverage": "2x",
        "components": ["Top 7 Nasdaq by weight = Mag 7"],
        "note":     "Alternative to MAGX. Tracks top 7 QQQ names at 2x.",
    },
}

# Mag 10 = Mag 7 + AVGO + PLTR + AMD (extended universe)
MAG10_ADDITIONS = ["AVGO", "PLTR", "AMD"]  # add to Mag 7 for full Mag 10


# ── SINGLE-STOCK LEVERAGED ETFs ───────────────────────────────────────────────
# GraniteShares, Direxion, Tuttle Capital — daily reset, intraday only

SINGLE_STOCK = {
    "NVDA": {"long": "NVDX",  "short": "NVDS",  "leverage": "2x", "note": "AI GPU king"},
    "TSLA": {"long": "TSLL",  "short": "TSLQ",  "leverage": "1.5x/1x", "note": "Volatile — wide swings"},
    "MSFT": {"long": "MSFU",  "short": None,     "leverage": "2x", "note": "Steady AI/cloud"},
    "AMZN": {"long": "AMZU",  "short": None,     "leverage": "2x", "note": "AWS + retail"},
    "META": {"long": "METU",  "short": None,     "leverage": "2x", "note": "AI ads machine"},
    "AAPL": {"long": "AAPU",  "short": None,     "leverage": "2x", "note": "Steady — less volatile"},
    "GOOGL": {"long": "GGLL", "short": None,     "leverage": "2x", "note": "AI search + YouTube"},
    "AMD":  {"long": None,    "short": None,     "leverage": "N/A", "note": "Trade directly — high vol"},
    "AVGO": {"long": None,    "short": None,     "leverage": "N/A", "note": "Trade directly"},
}


# ── PRIORITY SCAN ORDER (morning routine) ────────────────────────────────────
# Check these in order every scan cycle — highest conviction first

SCAN_PRIORITY = [
    # Tier 1: Index leveraged (most liquid, tightest spreads)
    "SSO", "SDS",    # SPY 2x
    "QLD", "QID",    # QQQ 2x
    "UWM", "TWM",    # IWM 2x

    # Tier 2: Mag 7 basket
    "MAGX",          # 2x Mag 7 long
    "QQQU",          # 2x Concentrated QQQ

    # Tier 3: Sector (pick based on day type + flow)
    "TECL", "TECS",  # Tech 3x — XLK direction
    "FAS",  "FAZ",   # Financial 3x — XLF direction
    "CURE", "LABD",  # Healthcare 3x
    "DUSL",          # Industrial 3x
    "ERX",  "ERY",   # Energy 2x
    "UTSL",          # Utilities 3x
    "DRN",  "DRV",   # Real Estate 3x
    "WANT",          # Consumer Disc 3x

    # Tier 4: Single-stock 2x (highest vol — only on A+ setups)
    "NVDX", "TSLL", "MSFU", "METU", "AMZU", "AAPU", "GGLL",
]


# ── RULES (same as config.py leveraged_etfs section) ─────────────────────────
RULES = {
    "intraday_only":        True,
    "force_close_by":       "15:45",   # ET — no exceptions
    "profit_target":        0.05,      # +5%
    "trailing_stop":        True,
    "trailing_stop_pct":    0.01,      # 1% below session high — MANDATORY
    "stop_loss_hard_floor": 0.05,      # -5% catastrophic backstop
    "position_size_usd":    25.0,      # fractional shares — use full buying power
    "use_full_buying_power": True,
    "min_score":            7,         # Casey score 7+ required
    "premarket_window":     "12am",    # midnight = PMH/PML start
    "scan_interval_sec":    120,       # 2-min scan for leveraged ETFs
    "never_hold_overnight": "Decay and gap risk make EOD exit MANDATORY",
}


# ── Convenience helpers ───────────────────────────────────────────────────────
def get_pair(underlying: str):
    """
    Given a sector ETF (XLK, XLF, etc.) or stock (NVDA, TSLA),
    return (long_ticker, short_ticker, leverage_note).
    """
    if underlying in SECTORS:
        s = SECTORS[underlying]
        return s.get("long"), s.get("short"), s.get("leverage", "?")
    if underlying in SINGLE_STOCK:
        s = SINGLE_STOCK[underlying]
        return s.get("long"), s.get("short"), s.get("leverage", "?")
    return None, None, None


def all_tickers():
    """Return flat list of all leveraged tickers in the universe (no Nones)."""
    out = list(SCAN_PRIORITY)
    # Add any in SINGLE_STOCK not already in SCAN_PRIORITY
    for v in SINGLE_STOCK.values():
        for t in [v.get("long"), v.get("short")]:
            if t and t not in out:
                out.append(t)
    return [t for t in out if t]


def today_snapshot():
    """Print today's sector ETF performance at a glance."""
    print("\n  SECTOR ETF SNAPSHOT — June 24 2026")
    print(f"  {'ETF':<6} {'Sector':<22} {'Price':>7} {'Change':>7}  {'Long':>5} / {'Short':<6}  Top Holding")
    print("  " + "─" * 78)
    for sym, s in SECTORS.items():
        chg = s['change']
        icon = "📈" if chg > 0 else "📉"
        lng  = s.get('long',  '—') or '—'
        shrt = s.get('short', '—') or '—'
        top  = s['top5'][0] if s['top5'] else '—'
        print(f"  {sym:<6} {s['name']:<22} ${s['price']:>6.2f} {icon}{chg:>+5.2f}%  "
              f"{lng:>5} / {shrt:<6}  {top}")
    print()


if __name__ == "__main__":
    today_snapshot()
    print(f"  All leveraged tickers ({len(all_tickers())} total):")
    print(f"  {', '.join(all_tickers())}")
    print()
    print("  Mag 7 basket:")
    for sym, d in MAG7.items():
        print(f"    {sym}: {d['leverage']} — {d['note']}")
    print()
    print("  Single-stock 2x:")
    for sym, d in SINGLE_STOCK.items():
        lng = d.get('long') or '—'
        print(f"    {sym} → long: {lng:<6} {d['leverage']}  {d['note']}")
