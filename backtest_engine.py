"""
Kevin's 0DTE Backtest Engine v3 — Delta-Correct Premium Model
"""
import numpy as np
import pandas as pd
import json, os

INSTRUMENTS = {
    "SPY": {"start_price": 480.0, "daily_vol": 0.011, "drift": 0.0003,
             "avg_volume": 80_000_000, "avg_spread_pct": 0.01},
    "QQQ": {"start_price": 415.0, "daily_vol": 0.014, "drift": 0.0004,
             "avg_volume": 45_000_000, "avg_spread_pct": 0.012},
    "IWM": {"start_price": 200.0, "daily_vol": 0.013, "drift": 0.0002,
             "avg_volume": 35_000_000, "avg_spread_pct": 0.015},
}

TRADING_DAYS    = 252
BARS_PER_DAY    = 195
ENTRY_BAR_START = 50
ENTRY_BAR_END   = 175
MAX_DAY_TRADES  = 3
POSITION_USD    = 50.0  # Updated from $15
PROFIT_TARGET   = 0.25  # +25%
STOP_LOSS       = 0.25  # -25%
MIN_CONFLUENCE  = 5
DELTA_ATM       = 0.50  # ATM 0DTE delta

np.random.seed(42)

def generate_day(prev_close, params):
    n   = BARS_PER_DAY
    vol = params["daily_vol"] / np.sqrt(n)
    trending  = np.random.random() < 0.60
    direction = 1 if np.random.random() < 0.55 else -1

    prices = [prev_close]
    for _ in range(n - 1):
        noise = np.random.normal(direction * vol * 0.3 if trending else 0, vol)
        prices.append(prices[-1] * (1 + noise))
    prices = np.array(prices)

    highs  = prices * (1 + np.abs(np.random.normal(0, vol * 0.4, n)))
    lows   = prices * (1 - np.abs(np.random.normal(0, vol * 0.4, n)))
    closes = prices * (1 + np.random.normal(0, vol * 0.2, n))
    vols   = np.random.lognormal(np.log(params["avg_volume"] / n), 0.4, n).astype(int)

    df = pd.DataFrame({"open": prices, "high": highs, "low": lows, "close": closes, "volume": vols})
    df.reset_index(drop=True, inplace=True)

    open0     = prices[0]
    df["PMH"] = open0 * (1 + np.random.uniform(0.002, 0.006))
    df["PML"] = open0 * (1 - np.random.uniform(0.002, 0.006))
    df["PDH"] = prev_close * (1 + np.random.uniform(0.005, 0.015))
    df["PDL"] = prev_close * (1 - np.random.uniform(0.005, 0.015))

    typical   = (highs + lows + closes) / 3
    df["VWAP"]   = np.cumsum(typical * vols) / np.cumsum(vols)
    df["EMA13"]  = df["close"].ewm(span=13, adjust=False).mean()
    df["EMA48"]  = df["close"].ewm(span=48, adjust=False).mean()
    df["EMA200"] = df["close"].ewm(span=200, adjust=False).mean()

    df["close_15m"] = np.nan
    for i in range(7, n, 8):
        df.loc[i, "close_15m"] = closes[i]
    df["close_15m"] = df["close_15m"].ffill()
    df["trending"]  = trending
    return df

def score_bar(df, bar):
    if bar < 50 or bar >= len(df) - 2:
        return {"score": 0, "direction": None}
    row  = df.iloc[bar]
    prev = df.iloc[bar - 1]
    e13, e48, e200 = row["EMA13"], row["EMA48"], row["EMA200"]
    price, pmh, pdl, pdh = row["close"], row["PMH"], row["PDL"], row["PDH"]
    vwap, c15 = row["VWAP"], row["close_15m"]

    # EMA fan — hard gate
    bull = e13 > e48 > e200 and (e13-e48)/e48 > 0.0002 and (e48-e200)/e200 > 0.0002
    bear = e200 > e48 > e13 and (e48-e13)/e13 > 0.0002 and (e200-e48)/e48 > 0.0002
    if not bull and not bear:
        return {"score": 0, "direction": None}
    direction = "CALLS" if bull else "PUTS"

    # 15min confirm — hard gate
    if pd.isna(c15):
        return {"score": 0, "direction": None}
    if direction == "CALLS" and c15 <= pmh:
        return {"score": 0, "direction": None}
    if direction == "PUTS" and c15 >= pdl:
        return {"score": 0, "direction": None}

    # Chop zone — hard gate
    if abs(pdh - pmh) / pmh < 0.002:
        return {"score": 0, "direction": None}

    score = 4  # EMA(+2) + 15min confirm(+2) already earned

    # Key level retest
    if bar >= 2:
        p2 = df.iloc[bar - 2]
        if direction == "CALLS":
            if p2["high"] > pmh and p2["close"] < pmh and prev["high"] > pmh and prev["close"] < pmh and price > pmh:
                score += 2
            elif price > pmh:
                score += 1
        else:
            if p2["low"] < pdl and p2["close"] > pdl and prev["low"] < pdl and prev["close"] > pdl and price < pdl:
                score += 2
            elif price < pdl:
                score += 1

    # 13 EMA pullback (Casey entry)
    if direction == "CALLS" and prev["close"] < e13 and price > e13:
        score += 1
    elif direction == "PUTS" and prev["close"] > e13 and price < e13:
        score += 1

    # Volume
    avg_v = df["volume"].iloc[max(0,bar-20):bar].mean()
    if avg_v > 0 and row["volume"] > avg_v * 1.5:
        score += 1

    # VWAP
    if (direction == "CALLS" and price > vwap) or (direction == "PUTS" and price < vwap):
        score += 1

    return {"score": min(score, 10), "direction": direction, "price": price}

def est_time_value(stock_price, params, bars_left):
    """BSM-inspired time value for ATM 0DTE."""
    T = max(bars_left / BARS_PER_DAY, 0.001)
    return max(stock_price * params["daily_vol"] * np.sqrt(T) * 0.4, 0.01)

def option_value(stock_price, entry_price, direction, params, bars_left, entry_premium):
    """Delta-based option P&L model."""
    tv       = est_time_value(stock_price, params, bars_left)
    move     = stock_price - entry_price
    if direction == "PUTS":
        move = -move
    intrinsic = max(0.0, move * DELTA_ATM)
    val       = max(0.01, tv + intrinsic)
    return val

def run_backtest():
    all_results = {}

    print("""
╔══════════════════════════════════════════════════════════╗
║   📊 KEVIN'S 0DTE BACKTEST — COMBINED CASEY SYSTEM v3   ║
║   252 Trading Days  |  SPY / QQQ / IWM                  ║
║   +25% profit / -25% stop  |  Delta-correct model       ║
╚══════════════════════════════════════════════════════════╝
""")

    for sym, params in INSTRUMENTS.items():
        print(f"  🔄 {sym}...", end="", flush=True)
        trades     = []
        prev_close = params["start_price"]
        equity     = 0.0

        for day in range(TRADING_DAYS):
            df         = generate_day(prev_close, params)
            day_trades = 0

            for bar in range(ENTRY_BAR_START, ENTRY_BAR_END):
                if day_trades >= MAX_DAY_TRADES:
                    break
                r = score_bar(df, bar)
                if r["score"] < MIN_CONFLUENCE:
                    continue

                direction    = r["direction"]
                entry_price  = r["price"]
                bars_left    = BARS_PER_DAY - bar
                entry_prem   = est_time_value(entry_price, params, bars_left)
                entry_prem  *= (1 + params["avg_spread_pct"])
                # Scale factor: how many $15 units fit in POSITION_USD
                # 1 contract costs ~$100-200, so we scale P&L proportionally
                scale_factor = POSITION_USD / 15.0
                contracts    = 1  # always 1 contract per signal
                cost         = entry_prem * 100 * scale_factor
                exit_pnl     = None
                exit_reason  = "TIME_EXPIRE"

                for fwd in range(1, min(bars_left - 1, 80)):
                    fbar    = df.iloc[bar + fwd]
                    fwd_p   = fbar["close"]
                    bl_rem  = bars_left - fwd
                    curr_v  = option_value(fwd_p, entry_price, direction, params, bl_rem, entry_prem)
                    pct_chg = (curr_v - entry_prem) / entry_prem

                    if pct_chg >= PROFIT_TARGET:
                        exit_pnl    = (curr_v - entry_prem) * 100 * scale_factor
                        exit_reason = "PROFIT_TARGET"
                        break
                    elif pct_chg <= -STOP_LOSS:
                        exit_pnl    = -entry_prem * STOP_LOSS * 100 * scale_factor
                        exit_reason = "STOP_LOSS"
                        break

                if exit_pnl is None:
                    end_bar  = min(bar + bars_left - 2, BARS_PER_DAY - 1)
                    fwd_p    = df.iloc[end_bar]["close"]
                    final_v  = option_value(fwd_p, entry_price, direction, params, 3, entry_prem)
                    exit_pnl = (final_v - entry_prem) * 100 * scale_factor

                equity    += exit_pnl
                day_trades += 1

                trades.append({
                    "day": day, "bar": bar, "sym": sym,
                    "dir": direction, "score": r["score"],
                    "entry": round(entry_price, 2),
                    "prem": round(entry_prem, 2),
                    "scale": round(scale_factor, 2),
                    "pnl": round(exit_pnl, 2),
                    "exit": exit_reason,
                    "equity": round(equity, 2),
                })

            prev_close = df["close"].iloc[-1]

        if not trades:
            print(" ⚠️  0 trades"); continue

        t  = pd.DataFrame(trades)
        w  = t[t["pnl"] > 0]
        l  = t[t["pnl"] <= 0]
        wr = len(w) / len(t) * 100
        pf = abs(w["pnl"].sum() / l["pnl"].sum()) if len(l) > 0 and l["pnl"].sum() != 0 else 999
        total_pnl = t["pnl"].sum()
        peak = 0; max_dd = 0
        for eq in t["equity"]:
            if eq > peak: peak = eq
            max_dd = max(max_dd, peak - eq)

        by_score = {}
        for sc, grp in t.groupby("score"):
            by_score[int(sc)] = {
                "count": int(len(grp)),
                "win_rate": round(len(grp[grp["pnl"]>0])/len(grp)*100, 1),
                "avg_pnl": round(grp["pnl"].mean(), 2),
                "total_pnl": round(grp["pnl"].sum(), 2),
            }

        all_results[sym] = {
            "symbol": sym,
            "total_trades":   len(t),
            "trades_per_day": round(len(t)/TRADING_DAYS, 2),
            "win_rate":       round(wr, 1),
            "total_pnl":      round(total_pnl, 2),
            "avg_win":        round(w["pnl"].mean() if len(w) else 0, 2),
            "avg_loss":       round(l["pnl"].mean() if len(l) else 0, 2),
            "profit_factor":  round(pf, 2),
            "max_drawdown":   round(max_dd, 2),
            "profit_targets": int((t["exit"]=="PROFIT_TARGET").sum()),
            "stop_losses":    int((t["exit"]=="STOP_LOSS").sum()),
            "time_expires":   int((t["exit"]=="TIME_EXPIRE").sum()),
            "calls_pnl":      round(t[t["dir"]=="CALLS"]["pnl"].sum(), 2),
            "puts_pnl":       round(t[t["dir"]=="PUTS"]["pnl"].sum(), 2),
            "by_score":       by_score,
            "equity_curve":   [r["equity"] for r in trades],
        }

        pt_pct = (t["exit"]=="PROFIT_TARGET").sum()/len(t)*100
        sl_pct = (t["exit"]=="STOP_LOSS").sum()/len(t)*100
        ex_pct = (t["exit"]=="TIME_EXPIRE").sum()/len(t)*100
        print(f" {len(t)} trades | WR:{wr:.1f}% | P&L:${total_pnl:+.0f} | PF:{pf:.2f} | MaxDD:${max_dd:.0f} | +25%:{pt_pct:.0f}% SL:{sl_pct:.0f}% Exp:{ex_pct:.0f}%")

    os.makedirs(os.path.expanduser("~/scan_logs"), exist_ok=True)
    path = os.path.expanduser("~/scan_logs/backtest_v3.json")
    with open(path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  💾 {path}")
    return all_results

if __name__ == "__main__":
    results = run_backtest()
