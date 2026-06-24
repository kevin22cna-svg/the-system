"""
Wiley Strat — MASTER CONFIG
=======================================
ONE file to control the entire system. Every scanner, the profit monitor,
the options system, and the EOD lead scanner all import from here.

Change a value ONCE here and it updates everywhere.

Usage in any script:
    from config import CONFIG
    target = CONFIG["shares"]["profit_target"]
"""

CONFIG = {

    # ── ACCOUNT ──────────────────────────────────────────────────────────────
    "account": {
        "agentic_number": "666042577",   # Your Agentic-enabled account
        "position_size_usd": 25.0,        # Lowered — fund account to restore to $50
    },

    # ── SHARES TRADING ───────────────────────────────────────────────────────
    "shares": {
        "profit_target": 0.05,    # +5% — sell intraday the moment this hits
        "stop_loss": 0.05,        # -5% stop
        "take_profit_intraday": True,   # PROFIT FIRST — don't wait for close
    },

    # ── OPTIONS TRADING ──────────────────────────────────────────────────────
    "options": {
        "default_dte": 2,         # 0, 1, 2, 3, or 5 — 2DTE is the sweet spot
        "instruments": ["SPY", "QQQ", "IWM"],
        "take_profit_intraday": True,   # PROFIT FIRST
        # Casey's complete A+ setup framework
    "casey_framework": {

        # Day type classification (first thing every morning)
        "day_types": {
            "bull_trend":  "Break PDH = buyers in control = favor CALLS",
            "bear_trend":  "Break PDL = sellers in control = favor PUTS",
            "balanced":    "Holds both PDH & PDL = range day = be cautious",
        },

        # Level hierarchy (priority order)
        "level_order": ["PDH", "PDL", "PMH", "PML", "VWAP", "S/D_ZONES", "SR_FLIPS"],

        # 3 zone play types (Casey's personal fav = break & retest)
        "zone_plays": {
            "breakout":    "Price breaks zone with momentum — enter on break",
            "rejection":   "Price hits zone and rejects — play the bounce back",
            "break_retest": "Price breaks zone, retests it, holds — enter on hold (BEST)",
        },

        # EMA rules
        "ema": {
            "spans": [13, 48, 200],
            "colors": {"13": "yellow", "48": "purple", "200": "red"},
            "bullish": "13>48>200 aligned + spacing out = smooth predictable trend",
            "bearish": "200>48>13 aligned + spacing out = smooth predictable trend",
            "choppy":  "EMAs closely spaced/crossing = unpredictable = NO TRADE",
            "entry":   "2-min 13 EMA dip/pullback = entry with clear risk level",
        },

        # Candlestick patterns for zone confirmation
        "patterns": {
            "bear_flag":       "Puts entry on flag support break",
            "bull_flag":       "Calls entry on flag resistance break",
            "falling_wedge":   "Calls on upper trendline break into demand zone",
            "break_retest":    "Enter on candle that holds the retest",
        },

        # Casey's 4 official levels (mark every day pre-market)
        "four_levels": ["PDH", "PDL", "PMH", "PML"],

        # Day type scoring (strongest to weakest)
        "day_signals": {
            "strongest_bull":   "Break PDH + PMH both = buyers total control = CALLS",
            "bull_trend":       "Break PDH = buyers in control = favor calls",
            "breakout_watch":   "Break PMH = first bullish sign = watch PDH next",
            "chop_zone":        "Between PML and PMH = wait for expansion",
            "breakdown_watch":  "Break PML = first bearish sign = watch PDL next",
            "bear_trend":       "Break PDL = sellers in control = favor puts",
            "balanced":         "Holds all 4 = range day = cautious",
        },

        # PMH/PML specific rules
        "pmh_pml_rules": {
            "long_trigger":    "Wait for price to break ABOVE PMH before going long",
            "short_trigger":   "Wait for price to break UNDER PML before going short",
            "chop_avoid":      "Price between PML and PMH = choppier = avoid, wait for expansion",
            "sr_flip_bull":    "PMH becomes support after broken = calls off PMH support",
            "sr_flip_bear":    "PML becomes resistance after broken = puts off PML resistance",
            "200ema_rule":     "Want price BELOW 200 EMA before entering puts — avoid 200 EMA bounces",
        },

        # Casey's scanner rule (strongest stock signal)
        "scanner_rule": "Break BOTH PDH + PMH = strongest calls signal = buyers in total control",
        "scanner_note": "Never short stocks breaking resistance — join the trend",

        # Zone numbering system (price target map)
        "zone_system": {
            "zone_1": "PDH — breakout point. Draw from wick to following candle body. Break = momentum.",
            "zone_2": "First resistance after Zone 1 break. Look back on chart. = first price target.",
            "zone_3": "Second resistance above Zone 2. Look back further. = second price target.",
            "zone_4": "Third resistance above Zone 3. Same process.",
            "zone_5": "Fourth resistance. Continue repeating upward.",
            "clean_air": "No resistance between zones = explosive move zone to zone.",
            "demand_zone": "PDH + PML together define next day's demand zone.",
            "zone_draw": "Draw from wick tip to body of following candle (creates a zone not a line).",
        },

        # Price structure rules (HH/HL/LH/LL)
        "price_structure": {
            "bullish": "HH + HL = no shorting. Bull flags on pullbacks = entries. Wait for shift.",
            "bearish": "LH + LL = no longing. Bear flags on bounces = put entries. Wait for shift.",
            "no_short_rule": "H/H & H/L = NO SHORTING — bullish structure intact",
            "no_long_rule":  "L/H & L/L = NO LONGING — bearish structure intact",
            "shift_bull": "Support holds on retest + first Bull Flag = bullish shift confirmed",
            "shift_bear": "Support rejects on retest + first Bear Flag = bearish shift confirmed",
            "range_trading": "Demand→Supply = Bull Flag entries. Supply→Demand = Bear Flag entries.",
        },

        # Confirmation gates
        "calls_confirm": "PMH",    # first bullish sign = PMH break
        "puts_confirm":  "PML",    # first bearish sign = PML break
        "strongest_confirm": "PDH+PMH",  # both broken = max conviction
        "lower_high_rule": True,   # bearish: PDH reject + lower high required
        "higher_low_rule": True,   # bullish: PDL hold + higher low required
        "chop_threshold": 0.002,   # PDH/PMH within 0.2% = balanced day, skip

        # Exit rules
        "exits": {
            "primary":   "Scale out HEAVY at next supply/demand zone",
            "trail":     "Trail runners with 13 EMA after partial exit",
            "avoid":     "Don't give back profits on zone bounces/rejections",
            "target_use": "Use zones as price targets WHILE in the trade",
        },
    },

    # DTE-based targets (from multi-DTE backtest)
        "dte_targets": {
            0: {"profit": 0.25, "stop": 0.25},   # 0DTE
            1: {"profit": 0.40, "stop": 0.30},   # 1DTE
            2: {"profit": 0.50, "stop": 0.30},   # 2DTE — strong win rate
            3: {"profit": 0.60, "stop": 0.35},   # 3DTE — best win rate 86.5%
            5: {"profit": 0.75, "stop": 0.35},   # 5DTE — highest total P&L
        },
    },

    # ── CONFLUENCE SCORING (Wiley Strat (Kevin + Casey)) ───────────────────────────────────
    "scoring": {
        "min_entry": 5,           # Minimum score to consider a trade
        "prime_entry": 7,         # Auto-trade threshold
        "entry_window": {"start": "09:45", "end": "15:45"},  # ET
        "force_close": "15:45",   # 0DTE force-close time
    },

    # ── SCANNER SETTINGS ─────────────────────────────────────────────────────
    "scanner": {
        "scan_interval_sec": 300,        # Every 5 min
        "profit_check_interval_sec": 60, # Position check every 60s
        "price_range": {"min": 10.0, "max": 25.0},  # $10-$25 — clean fills, 1-2 shares at $25 position
    },

    # ── TICKER UNIVERSE (single source of truth) ─────────────────────────────
    "tickers": {
        # Primary watchlist — $10-$25 rotation universe (fallback after ETFs)
        # Rotated in/out based on price staying in range — scanner filters by price live
        "primary": [
            # High-volume momentum ($10-$25 range)
            "SOFI","AAL","CIFR","FCEL","CLSK","RIOT","WULF","HIVE",
            "SOUN","BBAI","JOBY","LUNR","RDW","ASTS","NIO","RIVN",
            "NU","RKT","OPEN","HIMS","IONQ","QBTS",
            # User-added regulars
            "NOK","AMC","BAC","SNAP","HTZ","PFE",
            # Quantum computing — Trump EO June 2026 catalyst
            "RGTI","QUBT",
        ],
        # On watch — stocks near $10-$25 range, rotate in when price qualifies
        "on_watch": [
            "MARA","CCL","DAL","KMI","RKLB","CRWV","PLTR","HOOD",
            "SPCX","BBAI","POET","BABA","GME",
        ],
        # Volume Trades watchlist
        "volume_trades": [
            "CSCO","UBER","SOFI","AAL","ORCL","MU","HOOD","ARM","CRWV",
        ],
        # Rotating watchlist
        "rotating": [
            "DUOL","RDDT","DAL","ANET","CVS","BMY",
        ],
        # 0DTE options universe
        "options_0dte": ["SPY","QQQ","IWM"],
        # Catalyst plays — any price, fractional shares, profit at all times
        # No price ceiling — $25 buys fractional shares regardless of share price
        # Trigger: score 7+ AND moving 3%+ on the day OR breaking a key level
        "catalyst_plays": [
            # Mega-cap tech movers (high price = fractional only, same % profit)
            "NVDA","AMD","MU","AVGO","ARM","MSFT","AAPL","META","GOOGL","AMZN","TSLA",
            # High-momentum tech (above $25 range)
            "PLTR","CRWV","HOOD","RKLB",
            # Nuclear — Trump $17.5B / 10 reactor commitment (June 2026)
            "CCJ","BAM","BWXT","CW","LEU",
            # Nuclear ETFs
            "URA","URNM","NUKZ",
        ],
    },

    # ── LEVERAGED ETFs (intraday only — NEVER held overnight) ────────────────
    "leveraged_etfs": {
        # SPY 2x: SSO (long) / SDS (short)
        # QQQ 2x: QLD (long) / QID (short)
        # IWM 2x: UWM (long) / TWM (short)
        "tickers": ["SSO", "SDS", "QLD", "QID", "UWM", "TWM"],
        "spy_long":  "SSO",   # 2x S&P long
        "spy_short": "SDS",   # 2x S&P short
        "qqq_long":  "QLD",   # 2x QQQ long
        "qqq_short": "QID",   # 2x QQQ short
        "iwm_long":  "UWM",   # 2x IWM long
        "iwm_short": "TWM",   # 2x IWM short
        "premarket_window": "12am",  # use midnight overnight high/low for PMH/PML
        "scan_priority": "first",  # check these FIRST before explosion scanner every cycle
        "scan_interval_sec": 120,   # 2-min scan — faster than main 5-min to catch midday SPY/QQQ moves
        "intraday_only": True,
        "force_close_by": "15:45",   # ET — same as 0DTE force-close
        "profit_target": 0.05,   # +5% — sell full position, reinvest everything
        "stop_loss":     0.05,   # -5% full position
        "use_full_buying_power": True,  # compound — use all available cash each trade
        "price_range": {"min": 10.0, "max": 150.0},  # overrides scanner range — QLD ~$92
        # Direction logic: SPY/QQQ up = buy SSO/QLD | SPY/QQQ down = buy SDS/QID
        "direction_trigger": {
            "spy_drop_pct": 0.005,   # SPY drops 0.5% from session high = buy SDS
            "qqq_drop_pct": 0.005,   # QQQ drops 0.5% from session high = buy QID
            "spy_rise_pct": 0.005,   # SPY rises 0.5% from session low = buy SSO
            "qqq_rise_pct": 0.005,   # QQQ rises 0.5% from session low = buy QLD
        },
        "note": "Never hold overnight — decay and gap risk make EOD exit mandatory",
    },

    # ── SOCIAL / NEWS FEEDS ──────────────────────────────────────────────────
    "feeds": {
        "wsb_enabled": True,
        "wsb_url": "https://www.reddit.com/r/wallstreetbets/hot.json",
        "wsb_limit": 30,
        "extra_subreddits": ["stocks", "options", "pennystocks"],
        # If you register a Reddit app, fill these for higher limits + comments:
        "reddit_client_id": "",      # optional — from reddit.com/prefs/apps
        "reddit_client_secret": "",  # optional
        "reddit_user_agent": "KevinTrader/1.0",
        "news_search_enabled": True,    # web search for catalysts
        "earnings_check_enabled": True,
    },

    # ── EOD LEAD SCANNER ─────────────────────────────────────────────────────
    "eod": {
        "run_time": "16:15",      # 4:15pm ET — after close
        "top_n_leads": 10,        # How many next-day candidates to surface
    },
}


# ── Convenience accessors ─────────────────────────────────────────────────────
def get_option_targets(dte=None):
    """Get profit/stop targets for a given DTE (defaults to config default)."""
    if dte is None:
        dte = CONFIG["options"]["default_dte"]
    return CONFIG["options"]["dte_targets"].get(dte, CONFIG["options"]["dte_targets"][2])

def get_share_targets():
    return CONFIG["shares"]["profit_target"], CONFIG["shares"]["stop_loss"]

def get_account():
    return CONFIG["account"]["agentic_number"]

def get_universe(name="primary"):
    return CONFIG["tickers"].get(name, CONFIG["tickers"]["primary"])

def get_position_size():
    return CONFIG["account"]["position_size_usd"]


if __name__ == "__main__":
    import json
    print("Wiley Strat — Master Config\n")
    print(json.dumps(CONFIG, indent=2))
    print("\n── Quick checks ──")
    print(f"Account: {get_account()}")
    print(f"Position size: ${get_position_size()}")
    print(f"Share targets: +{get_share_targets()[0]*100:.0f}% / -{get_share_targets()[1]*100:.0f}%")
    dte = CONFIG['options']['default_dte']
    t = get_option_targets()
    print(f"Option targets ({dte}DTE): +{t['profit']*100:.0f}% / -{t['stop']*100:.0f}%")
    print(f"Primary universe: {len(get_universe())} tickers")
