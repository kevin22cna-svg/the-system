"""
tax_reserve.py
--------------
Sweeps a fixed % of every REALIZED gain into a tax-reserve ledger.

Wiley Strat note: all Agentic account gains are short-term -> taxed as
ordinary income (~27-28% Philadelphia combined). Default reserve 30%.

Usage (from profit_monitor.py, on a green close):
    from tax_reserve import reserve_on_close, summary
    reserve_on_close("FCEL", entry=1.64, exit_=1.74, qty=3.0)
    print(summary())
"""

import json, os
from datetime import datetime, timezone

LEDGER = os.path.join(os.path.dirname(__file__), "tax_reserve.json")
RESERVE_RATE = 0.30   # set-aside fraction of each realized gain


def _load():
    if not os.path.exists(LEDGER):
        return {"reserve_rate": RESERVE_RATE, "total_reserved": 0.0,
                "total_realized_gain": 0.0, "trades": []}
    with open(LEDGER) as f:
        return json.load(f)


def _save(d):
    with open(LEDGER, "w") as f:
        json.dump(d, f, indent=2)


def reserve_on_close(ticker, entry, exit_, qty, rate=RESERVE_RATE):
    """Log a closed trade. Only reserves when realized P/L is positive.
    Returns the dollar amount reserved for this trade (0.0 on a loss)."""
    realized = round((exit_ - entry) * qty, 4)
    reserved = round(realized * rate, 4) if realized > 0 else 0.0

    d = _load()
    d["reserve_rate"] = rate
    d["total_realized_gain"] = round(d["total_realized_gain"] + realized, 4)
    d["total_reserved"] = round(d["total_reserved"] + reserved, 4)
    d["trades"].append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ticker": ticker, "entry": entry, "exit": exit_, "qty": qty,
        "realized": realized, "reserved": reserved,
    })
    _save(d)
    return reserved


def summary():
    d = _load()
    return (f"TAX RESERVE  set-aside={d['reserve_rate']*100:.0f}%  "
            f"reserved=${d['total_reserved']:.2f}  "
            f"(of ${d['total_realized_gain']:.2f} realized gains, "
            f"{len(d['trades'])} closes)")


if __name__ == "__main__":
    # smoke test
    for t, e, x, q in [("FCEL", 1.64, 1.74, 3.0),   # +win
                       ("AAL", 12.0, 11.4, 1.0),    # loss -> no reserve
                       ("SOFI", 8.0, 8.40, 2.0)]:   # +win
        amt = reserve_on_close(t, e, x, q)
        print(f"{t}: reserved ${amt:.4f}")
    print(summary())
