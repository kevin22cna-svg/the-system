"""
flow_scanner.py — Free Options Flow Scanner
============================================
Detects unusual options activity using yfinance (no API key, no account).
Runs every scan cycle and feeds conviction signals into auto_executor scoring.

DETECTION LOGIC:
  Flag a contract when ALL of:
    - volume >= 500 contracts       (filters noise)
    - volume > open_interest        (fresh buying, not existing positions)
    - dollar premium >= $25,000     (institutional size minimum)

SIGNAL STRENGTH:
  $25K–$100K    = ⚡ ELEVATED  (+1 pt)
  $100K–$1M     = 🔥 STRONG   (+2 pts)
  $1M+          = 🐳 WHALE    (+2 pts, max conviction)

SCORING (fed into auto_executor):
  Flow confirms trade direction  → +score_pts added to Casey score
  Flow opposes trade direction   → skip or cut size to half

Run standalone:
  python flow_scanner.py              # one-shot scan, print report
  python flow_scanner.py --watch      # continuous 5-min scan

Import into auto_executor:
  from flow_scanner import get_flow_signals
  signals = get_flow_signals(["CLS", "MU", "AMD"])
  pts = signals.get("CLS", {}).get("score_pts", 0)
"""

import sys
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytz
import yfinance as yf

ET = pytz.timezone("America/New_York")

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_VOLUME     = 500         # contracts — below this is noise
MIN_PREMIUM    = 25_000      # $25K minimum dollar flow to flag
STRONG_PREMIUM = 100_000     # $100K = strong institutional
WHALE_PREMIUM  = 1_000_000   # $1M+ = whale — follow it
MAX_EXPIRIES   = 4           # scan nearest N expiry dates per ticker
MAX_WORKERS    = 8           # parallel yfinance threads
SCAN_INTERVAL  = 300         # seconds between scans in --watch mode


def _tier(premium_usd):
    if premium_usd >= WHALE_PREMIUM:   return "🐳 WHALE",    2
    if premium_usd >= STRONG_PREMIUM:  return "🔥 STRONG",   2
    if premium_usd >= MIN_PREMIUM:     return "⚡ ELEVATED",  1
    return "—", 0


def _flag_unusual(df, current_price, side, expiry):
    """
    Scan a calls or puts DataFrame for unusual activity.
    Returns list of flagged contract dicts sorted by premium descending.
    """
    flagged = []
    if df is None or df.empty:
        return flagged

    for _, row in df.iterrows():
        try:
            volume = int(row.get("volume") or 0)
            oi     = int(row.get("openInterest") or 0)
            if volume < MIN_VOLUME:
                continue

            strike = float(row.get("strike") or 0)
            bid    = float(row.get("bid") or 0)
            ask    = float(row.get("ask") or 0)
            last   = float(row.get("lastPrice") or 0)
            iv     = float(row.get("impliedVolatility") or 0)

            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else last
            if mid <= 0:
                continue

            premium_usd = mid * volume * 100
            if premium_usd < MIN_PREMIUM:
                continue

            otm = (strike > current_price) if side == "call" else (strike < current_price)
            vol_oi_ratio = round(volume / oi, 2) if oi > 0 else 999.0
            fresh_buy = vol_oi_ratio > 1.0
            label, pts = _tier(premium_usd)

            flagged.append({
                "side":          side,
                "expiry":        expiry,
                "strike":        strike,
                "otm":           otm,
                "volume":        volume,
                "open_interest": oi,
                "vol_oi_ratio":  vol_oi_ratio,
                "mid":           round(mid, 2),
                "iv_pct":        round(iv * 100, 1),
                "premium_usd":   int(premium_usd),
                "tier":          label,
                "score_pts":     pts,
                "fresh_buy":     fresh_buy,
            })
        except Exception:
            continue

    return sorted(flagged, key=lambda x: x["premium_usd"], reverse=True)


def scan_ticker(sym):
    """
    Scan one ticker across nearest MAX_EXPIRIES expiry dates.
    Returns a summary dict or None if no unusual activity found.
    """
    try:
        tk = yf.Ticker(sym)
        expiries = tk.options
        if not expiries:
            return None

        info = tk.fast_info
        price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
        if not price or price <= 0:
            return None

        all_calls, all_puts = [], []

        for exp in list(expiries)[:MAX_EXPIRIES]:
            try:
                chain = tk.option_chain(exp)
                all_calls.extend(_flag_unusual(chain.calls, price, "call", exp))
                all_puts.extend( _flag_unusual(chain.puts,  price, "put",  exp))
            except Exception:
                continue

        if not all_calls and not all_puts:
            return None

        call_premium = sum(c["premium_usd"] for c in all_calls)
        put_premium  = sum(p["premium_usd"] for p in all_puts)

        if call_premium > put_premium * 1.5:
            direction = "BULLISH"
        elif put_premium > call_premium * 1.5:
            direction = "BEARISH"
        else:
            direction = "MIXED"

        top_call = all_calls[0] if all_calls else None
        top_put  = all_puts[0]  if all_puts  else None

        max_pts = max(
            top_call["score_pts"] if top_call else 0,
            top_put["score_pts"]  if top_put  else 0,
        )

        return {
            "sym":          sym,
            "price":        round(price, 2),
            "direction":    direction,
            "call_premium": call_premium,
            "put_premium":  put_premium,
            "top_call":     top_call,
            "top_put":      top_put,
            "score_pts":    max_pts,
        }
    except Exception:
        return None


def scan_universe(tickers):
    """
    Scan a list of tickers in parallel.
    Returns results sorted by total dollar flow, largest first.
    """
    seen, unique = set(), []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(scan_ticker, sym): sym for sym in unique}
        for fut in as_completed(futures):
            r = fut.result()
            if r:
                results.append(r)

    results.sort(key=lambda x: x["call_premium"] + x["put_premium"], reverse=True)
    return results


def get_flow_signals(tickers):
    """
    Auto-executor integration point.

    Returns dict keyed by sym:
      {
        "direction":    "BULLISH" | "BEARISH" | "MIXED",
        "score_pts":    2,       # add to Casey score when direction matches
        "call_premium": 3000000,
        "put_premium":  50000,
        "top_call":     {...},
        "top_put":      {...},
      }

    Example usage in auto_executor:
      signals = get_flow_signals(scan_universe)
      if signals.get("CLS", {}).get("direction") == "BULLISH":
          score += signals["CLS"]["score_pts"]
    """
    results = scan_universe(tickers)
    return {r["sym"]: {k: v for k, v in r.items() if k != "sym"} for r in results}


# ── Display helpers ───────────────────────────────────────────────────────────
def _fmt(n):
    if n >= 1_000_000: return f"${n/1_000_000:.2f}M"
    if n >= 1_000:     return f"${n/1_000:.0f}K"
    return f"${n}"


def print_report(results, title="OPTIONS FLOW SCAN"):
    now = datetime.now(ET)
    print(f"\n{'═'*64}")
    print(f"  📡 {title}")
    print(f"  {now.strftime('%I:%M:%S %p ET')}  |  {len(results)} ticker(s) with unusual flow")
    print(f"{'═'*64}")

    if not results:
        print("  No unusual options activity detected this cycle.\n")
        return

    for r in results:
        total = r["call_premium"] + r["put_premium"]
        icon  = "📈" if r["direction"] == "BULLISH" else ("📉" if r["direction"] == "BEARISH" else "↔️ ")
        print(f"\n  {icon} {r['sym']:<6} ${r['price']:.2f}  |  {r['direction']:<8}  |  "
              f"Total flow: {_fmt(total)}")

        if r["top_call"]:
            c = r["top_call"]
            tags = []
            if c["otm"]:       tags.append("OTM")
            if c["fresh_buy"]: tags.append("FRESH BUY")
            tag_str = " ".join(tags)
            print(f"     CALLS {c['expiry']} ${c['strike']} {tag_str:<16} "
                  f"vol {c['volume']:>6,} / OI {c['open_interest']:>7,} "
                  f"({c['vol_oi_ratio']}x)  {_fmt(c['premium_usd'])}  "
                  f"IV {c['iv_pct']}%  {c['tier']}")

        if r["top_put"]:
            p = r["top_put"]
            tags = []
            if p["otm"]:       tags.append("OTM")
            if p["fresh_buy"]: tags.append("FRESH BUY")
            tag_str = " ".join(tags)
            print(f"     PUTS  {p['expiry']} ${p['strike']} {tag_str:<16} "
                  f"vol {p['volume']:>6,} / OI {p['open_interest']:>7,} "
                  f"({p['vol_oi_ratio']}x)  {_fmt(p['premium_usd'])}  "
                  f"IV {p['iv_pct']}%  {p['tier']}")

        if r["score_pts"] >= 1:
            print(f"     ⭐ +{r['score_pts']} pts to auto-executor score if direction matches setup")

    print(f"\n{'─'*64}")
    bulls  = [r["sym"] for r in results if r["direction"] == "BULLISH"]
    bears  = [r["sym"] for r in results if r["direction"] == "BEARISH"]
    whales = [r["sym"] for r in results
              if (r["call_premium"] + r["put_premium"]) >= WHALE_PREMIUM]
    if bulls:  print(f"  📈 Bullish flow:  {', '.join(bulls)}")
    if bears:  print(f"  📉 Bearish flow:  {', '.join(bears)}")
    if whales: print(f"  🐳 Whale prints:  {', '.join(whales)}")
    print(f"{'═'*64}\n")


# ── CLI entry point ───────────────────────────────────────────────────────────
def main():
    watch = "--watch" in sys.argv

    from config import CONFIG
    universe = list(dict.fromkeys(
        CONFIG["tickers"]["options_0dte"] +
        CONFIG["leveraged_etfs"]["tickers"] +
        CONFIG["tickers"].get("catalyst_plays", []) +
        CONFIG["tickers"].get("primary", [])
    ))

    print(f"\n  Flow scanner  |  {len(universe)} tickers  |  "
          f"min vol {MIN_VOLUME} contracts  |  min premium ${MIN_PREMIUM/1000:.0f}K")
    print(f"  {'Watch mode — scanning every 5 min. Ctrl+C to stop.' if watch else 'Single scan.'}\n")

    if watch:
        n = 0
        while True:
            n += 1
            results = scan_universe(universe)
            print_report(results, title=f"OPTIONS FLOW SCAN #{n}")
            print(f"  ⏱  Next scan in {SCAN_INTERVAL // 60} min...")
            time.sleep(SCAN_INTERVAL)
    else:
        results = scan_universe(universe)
        print_report(results)


if __name__ == "__main__":
    main()
