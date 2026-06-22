"""
Wiley Strat Trade Simulator — SOFI $18C June 18
=================================================
Simulates holding the SOFI $18C 2DTE position in real-time.
Pulls live SOFI price every 60 seconds, calculates estimated
option value using delta model, tracks P&L, and alerts when
profit target or stop loss is hit.

Trade Setup:
  Symbol:     SOFI
  Strike:     $18.00 Call
  Expiry:     June 18, 2026 (2DTE)
  Entry:      $0.26 mark (pre-market)
  Contracts:  1 (= $26 cost)
  Target:     +50% → $0.39 (2DTE rule)
  Stop:       -30% → $0.182
  Force close: 3:45pm ET

Strategy Context (Wiley Strat (Kevin + Casey)):
  - Wait for 9:45am ET
  - Confirm bullish EMA fan on 2-min (13>48>200 spaced)
  - 15-min candle body close above PMH
  - Enter on 13 EMA pullback
  - PROFIT FIRST — sell the instant +50% hits intraday
"""

import anthropic
import json
import os
import time
import math
from datetime import datetime, timezone
import pytz

ET = pytz.timezone("America/New_York")
MCP_SERVER = {
    "type": "url",
    "url": "https://agent.robinhood.com/mcp/trading",
    "name": "robinhood-mcp"
}

# ── Trade Parameters ──────────────────────────────────────────────────────────
SYMBOL         = "SOFI"
STRIKE         = 18.00
EXPIRY         = "2026-06-18"
OPTION_TYPE    = "call"
ENTRY_PREMIUM  = 0.26       # Mark at time of entry
CONTRACTS      = 1
COST           = ENTRY_PREMIUM * 100 * CONTRACTS   # $26

PROFIT_TARGET  = 0.50       # +50% (2DTE rule)
STOP_LOSS      = 0.30       # -30%
FORCE_CLOSE_H  = 15         # 3:45pm ET
FORCE_CLOSE_M  = 45

# Option greeks at entry (from pre-market pull)
ENTRY_DELTA    = 0.393
ENTRY_IV       = 0.813
ENTRY_THETA    = -0.1136    # per day
ENTRY_GAMMA    = 0.398
ENTRY_STOCK    = 18.17      # pre-market stock price at entry decision

BARS_PER_DAY   = 195        # 2-min bars
DTE_AT_ENTRY   = 2.0        # days to expiry

# Instrument ID for live quote pulls
OPTION_INSTRUMENT_ID = "f81c7053-f826-4e77-9391-20cd5735a21e"  # SOFI $18C Jun18

def now_et():
    return datetime.now(ET)

def time_remaining_days():
    """Fraction of DTE remaining from now."""
    n = now_et()
    # Expiry is June 18 at 3:30pm ET
    expiry_dt = ET.localize(datetime(2026, 6, 18, 15, 30, 0))
    remaining = (expiry_dt - n).total_seconds() / 86400
    return max(remaining, 0.001)

def est_option_value(stock_price, entry_stock, entry_premium, dte_remaining):
    """
    Delta-gamma approximation for option value.
    Uses entry greeks to estimate current premium.
    """
    price_move   = stock_price - entry_stock
    delta_pnl    = ENTRY_DELTA * price_move
    gamma_pnl    = 0.5 * ENTRY_GAMMA * (price_move ** 2)
    # Theta decay: proportional to time elapsed since entry
    time_elapsed = DTE_AT_ENTRY - dte_remaining
    theta_decay  = ENTRY_THETA * time_elapsed
    # IV crush approximation (mild during regular session)
    estimated = entry_premium + delta_pnl + gamma_pnl + theta_decay
    return max(estimated, 0.01)

def format_pnl(pnl, cost):
    pct = (pnl / cost) * 100
    arrow = "▲" if pnl >= 0 else "▼"
    sign  = "+" if pnl >= 0 else ""
    return f"{arrow} {sign}${pnl:.2f} ({sign}{pct:.1f}%)"

def in_trading_window():
    n = now_et()
    if n.weekday() >= 5: return False
    h, m = n.hour, n.minute
    after_entry = h > 9 or (h == 9 and m >= 45)
    before_force = h < FORCE_CLOSE_H or (h == FORCE_CLOSE_H and m < FORCE_CLOSE_M)
    return after_entry and before_force

def past_force_close():
    n = now_et()
    h, m = n.hour, n.minute
    return h > FORCE_CLOSE_H or (h == FORCE_CLOSE_H and m >= FORCE_CLOSE_M)

def run_simulator():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Set ANTHROPIC_API_KEY"); return
    client = anthropic.Anthropic(api_key=api_key)

    target_price = ENTRY_PREMIUM * (1 + PROFIT_TARGET)
    stop_price   = ENTRY_PREMIUM * (1 - STOP_LOSS)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║   📊 LIVE TRADE SIMULATOR — SOFI $18C Jun 18            ║
║   Entry premium: ${ENTRY_PREMIUM:.2f}  |  Cost: ${COST:.2f}/contract     ║
║   🎯 Target: ${target_price:.3f} (+{PROFIT_TARGET*100:.0f}%)  |  🛑 Stop: ${stop_price:.3f} (-{STOP_LOSS*100:.0f}%)  ║
║   ⏰ Force close: 3:45pm ET                             ║
╚══════════════════════════════════════════════════════════╝

  Strategy: Wait for 9:45am | Bullish EMA fan | 15min above PMH
  Entry trigger: 13 EMA pullback on 2-min after 15min confirms
  Exit rule: PROFIT FIRST — sell the instant +50% hits

  Tracking live every 60 seconds...
  Press Ctrl+C to stop.
""")

    # Track simulation state
    sim = {
        "entry_time": None,
        "in_trade": False,
        "peak_premium": ENTRY_PREMIUM,
        "trough_premium": ENTRY_PREMIUM,
        "checks": 0,
        "history": [],   # list of (time, stock, option_est, pnl_pct)
        "exit_reason": None,
        "exit_premium": None,
    }

    # Pre-entry: wait for 9:45am and setup confirmation
    pre_entry_printed = False

    try:
        while True:
            now = now_et()
            sim["checks"] += 1

            # ── Pull live stock quote ────────────────────────────────────────
            response = client.beta.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=500,
                system="You are a quote puller. Get the live price for SOFI and return ONLY JSON: {\"price\": 18.17, \"pct_change\": 2.5}",
                messages=[{"role": "user", "content": f"Get live SOFI price now. Time: {now.strftime('%H:%M:%S ET')}"}],
                mcp_servers=[MCP_SERVER],
                betas=["mcp-client-2025-04-04"]
            )
            raw = "".join(b.text for b in response.content if hasattr(b, "text"))
            try:
                clean = raw.strip()
                if "```" in clean:
                    clean = [p for p in clean.split("```") if "{" in p][0].replace("json","").strip()
                quote = json.loads(clean)
                stock_price = float(quote.get("price", ENTRY_STOCK))
                pct_change  = float(quote.get("pct_change", 0))
            except Exception:
                stock_price = ENTRY_STOCK
                pct_change  = 0

            # ── Estimate option value ────────────────────────────────────────
            dte_rem    = time_remaining_days()
            opt_est    = est_option_value(stock_price, ENTRY_STOCK, ENTRY_PREMIUM, dte_rem)
            pnl        = (opt_est - ENTRY_PREMIUM) * 100 * CONTRACTS
            pnl_pct    = (opt_est - ENTRY_PREMIUM) / ENTRY_PREMIUM * 100
            pnl_str    = format_pnl(pnl, COST)

            sim["peak_premium"]   = max(sim["peak_premium"], opt_est)
            sim["trough_premium"] = min(sim["trough_premium"], opt_est)

            # ── Pre-entry window ─────────────────────────────────────────────
            h, m = now.hour, now.minute
            if h < 9 or (h == 9 and m < 45):
                if not pre_entry_printed:
                    mins_to_open = (9*60+45) - (h*60+m)
                    print(f"  ⏰ Pre-market — waiting for 9:45am entry window ({mins_to_open} min)")
                    print(f"     SOFI pre-market: ${stock_price:.2f} ({pct_change:+.2f}%)")
                    print(f"     Watching for: bullish EMA fan + 15min above PMH")
                    pre_entry_printed = True
                time.sleep(60)
                continue

            # ── Check exit conditions ────────────────────────────────────────
            if past_force_close() and not sim["exit_reason"]:
                sim["exit_reason"]  = "FORCE_CLOSE"
                sim["exit_premium"] = opt_est

            if pnl_pct >= PROFIT_TARGET * 100 and not sim["exit_reason"]:
                sim["exit_reason"]  = "PROFIT_TARGET 🎉"
                sim["exit_premium"] = opt_est

            if pnl_pct <= -(STOP_LOSS * 100) and not sim["exit_reason"]:
                sim["exit_reason"]  = "STOP_LOSS 🛑"
                sim["exit_premium"] = opt_est

            # ── Print status ─────────────────────────────────────────────────
            time_str  = now.strftime("%I:%M:%S %p ET")
            dte_str   = f"{dte_rem:.3f} DTE"
            pnl_color = "▲" if pnl >= 0 else "▼"

            # Trend indicator
            if len(sim["history"]) >= 2:
                prev_opt = sim["history"][-1][2]
                trend = "📈" if opt_est > prev_opt else "📉" if opt_est < prev_opt else "➖"
            else:
                trend = "➖"

            print(f"  {time_str}  SOFI: ${stock_price:.2f} ({pct_change:+.1f}%)  "
                  f"Option: ${opt_est:.3f} {trend}  P&L: {pnl_str}  [{dte_str}]")

            sim["history"].append((time_str, stock_price, opt_est, pnl_pct))

            # ── Exit triggered ────────────────────────────────────────────────
            if sim["exit_reason"]:
                exit_pnl     = (sim["exit_premium"] - ENTRY_PREMIUM) * 100 * CONTRACTS
                exit_pnl_pct = (sim["exit_premium"] - ENTRY_PREMIUM) / ENTRY_PREMIUM * 100

                print(f"""
{'='*60}
  🏁 TRADE CLOSED — {sim['exit_reason']}
{'='*60}
  Entry:      ${ENTRY_PREMIUM:.3f}  (${COST:.2f} total)
  Exit:       ${sim['exit_premium']:.3f}
  P&L:        ${exit_pnl:+.2f} ({exit_pnl_pct:+.1f}%)
  Peak val:   ${sim['peak_premium']:.3f} (+{(sim['peak_premium']/ENTRY_PREMIUM-1)*100:.1f}%)
  Trough:     ${sim['trough_premium']:.3f} ({(sim['trough_premium']/ENTRY_PREMIUM-1)*100:.1f}%)
  Checks:     {sim['checks']} updates
  Duration:   {len(sim['history'])} minutes tracked
{'='*60}
""")
                # Save trade log
                log = {
                    "symbol": SYMBOL, "strike": STRIKE, "expiry": EXPIRY,
                    "entry_premium": ENTRY_PREMIUM, "exit_premium": sim["exit_premium"],
                    "exit_reason": sim["exit_reason"],
                    "pnl_usd": round(exit_pnl, 2), "pnl_pct": round(exit_pnl_pct, 1),
                    "peak": sim["peak_premium"], "trough": sim["trough_premium"],
                    "history": sim["history"][-10:]  # last 10 readings
                }
                os.makedirs(os.path.expanduser("~/scan_logs"), exist_ok=True)
                with open(os.path.expanduser(f"~/scan_logs/sim_{now.strftime('%Y%m%d_%H%M')}.json"), "w") as f:
                    json.dump(log, f, indent=2)
                print(f"  💾 Trade log saved.")
                break

            time.sleep(60)  # Check every 60 seconds

    except KeyboardInterrupt:
        print(f"\n  🛑 Simulator stopped manually after {sim['checks']} checks.")
        if sim["history"]:
            last = sim["history"][-1]
            print(f"  Last reading: SOFI ${last[1]:.2f} | Option ${last[2]:.3f} | {last[3]:+.1f}%")

if __name__ == "__main__":
    run_simulator()
