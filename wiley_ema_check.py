"""
wiley_ema_check.py

Pulls daily price history for the Wiley Strat options universe via OpenBB
(yfinance provider, no API key needed) and computes a simple EMA fan
(9/21/50), then cross-references dealer gamma exposure (GEX) pulled
directly from CBOE's free delayed-quote endpoint (no key needed either).

GEX calc adapted from Matteo-Ferrara/gex-tracker
(https://github.com/Matteo-Ferrara/gex-tracker).

Usage (PowerShell, with the openbb-venv activated):
    python wiley_ema_check.py

Output:
    Prints a combined EMA + GEX summary table to the console and writes
    wiley_ema_check.csv in the current directory.
"""

from datetime import datetime, timedelta

import pandas as pd
import requests
from openbb import obb

# 8/20/26 "Option Universe" watchlist from Wiley Strat
# SPX and XSP don't resolve on yfinance under their normal symbols —
# ^SPX is the index; XSP (mini-SPX) isn't available on yfinance at all,
# so ^SPX is used as its proxy for this cross-check.
TICKERS = ["SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAL", "^SPX"]

# Cosmetic display names for tickers whose yfinance symbol differs from
# what you'd normally call them
DISPLAY_NAMES = {"^SPX": "SPX"}

# CBOE ticker symbols differ from yfinance: indices get a leading underscore.
# Map yfinance ticker -> CBOE ticker.
CBOE_TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "IWM": "IWM",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
    "AAL": "AAL",
    "^SPX": "_SPX",
}

EMA_PERIODS = [13, 48, 200]
LOOKBACK_DAYS = 320  # enough bars to warm up a 200-period EMA
CONTRACT_SIZE = 100


# ---------------------------------------------------------------------------
# EMA section (OpenBB / yfinance)
# ---------------------------------------------------------------------------


def fetch_history(ticker: str) -> pd.DataFrame:
    start = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    try:
        data = obb.equity.price.historical(ticker, provider="yfinance", start_date=start)
        df = data.to_df()
        if df.empty:
            print(f"[{ticker}] no price data returned")
            return pd.DataFrame()
        return df
    except Exception as e:  # noqa: BLE001
        print(f"[{ticker}] price fetch failed: {e}")
        return pd.DataFrame()


def compute_emas(df: pd.DataFrame) -> pd.DataFrame:
    for period in EMA_PERIODS:
        df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()
    return df


def classify_fan(row: pd.Series) -> str:
    e13, e48, e200 = row["ema_13"], row["ema_48"], row["ema_200"]
    if e13 > e48 > e200:
        return "bullish fan"
    if e13 < e48 < e200:
        return "bearish fan"
    return "mixed / no fan"


# ---------------------------------------------------------------------------
# GEX section (CBOE delayed quotes — free, no key)
# ---------------------------------------------------------------------------


def fetch_gex(cboe_ticker: str) -> dict:
    """Fetch option chain from CBOE and compute total GEX, gamma flip,
    call wall, and put wall for a single ticker."""
    url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{cboe_ticker}.json"
    try:
        resp = requests.get(url, timeout=15)
        raw = resp.json()
    except Exception as e:  # noqa: BLE001
        print(f"[{cboe_ticker}] GEX fetch failed: {e}")
        return {}

    try:
        data = pd.DataFrame.from_dict(raw)
        spot = data.loc["current_price", "data"]
        options = pd.DataFrame(data.loc["options", "data"])

        options["type"] = options.option.str.extract(r"\d([A-Z])\d")
        options["strike"] = options.option.str.extract(r"\d[A-Z](\d+)\d\d\d").astype(int)

        # Per-contract notional GEX; puts treated as negative (dealers assumed
        # short gamma on puts, long gamma on calls)
        options["GEX"] = spot * options.gamma * options.open_interest * CONTRACT_SIZE * spot * 0.01
        options["GEX"] = options.apply(lambda x: -x.GEX if x.type == "P" else x.GEX, axis=1)

        total_gex_bn = round(options.GEX.sum() / 10**9, 3)

        by_strike = options.groupby("strike")["GEX"].sum().sort_index()

        # Gamma flip: strike nearest where cumulative GEX crosses zero
        cumulative = by_strike.cumsum()
        sign_changes = cumulative[(cumulative.shift(1) < 0) & (cumulative >= 0)]
        gamma_flip = sign_changes.index[0] if not sign_changes.empty else None

        call_wall = by_strike.idxmax() if not by_strike.empty else None
        put_wall = by_strike.idxmin() if not by_strike.empty else None

        return {
            "spot": spot,
            "total_gex_bn": total_gex_bn,
            "gamma_flip": gamma_flip,
            "call_wall": call_wall,
            "put_wall": put_wall,
            "regime": "positive (range-bound)" if total_gex_bn > 0 else "negative (trending/volatile)",
        }
    except Exception as e:  # noqa: BLE001
        print(f"[{cboe_ticker}] GEX calc failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Combined run
# ---------------------------------------------------------------------------


def main() -> None:
    results = []

    for ticker in TICKERS:
        display = DISPLAY_NAMES.get(ticker, ticker)

        df = fetch_history(ticker)
        ema_row = {}
        if not df.empty:
            df = compute_emas(df)
            last = df.iloc[-1]
            ema_row = {
                "date": df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else str(df.index[-1]),
                "close": round(last["close"], 2),
                "ema_13": round(last["ema_13"], 2),
                "ema_48": round(last["ema_48"], 2),
                "ema_200": round(last["ema_200"], 2),
                "fan": classify_fan(last),
            }

        cboe_ticker = CBOE_TICKERS.get(ticker, ticker)
        gex_row = fetch_gex(cboe_ticker)

        row = {"ticker": display}
        row.update(ema_row)
        row.update(gex_row)
        results.append(row)

    if not results:
        print("No data pulled for any ticker — check network/provider.")
        return

    summary = pd.DataFrame(results)
    pd.set_option("display.width", 160)
    print("\nWiley Strat EMA + GEX cross-check\n")
    print(summary.to_string(index=False))

    summary.to_csv("wiley_ema_check.csv", index=False)
    print("\nSaved to wiley_ema_check.csv")


if __name__ == "__main__":
    main()

