"""
Wiley Strat Explosion Scanner — Market Hours Scheduler
===================================================
Runs the explosion scanner every 5 minutes from 9:45am to 3:45pm ET.

Features:
  - Auto-starts at 9:45am, stops at 3:45pm
  - Skips weekends automatically
  - Deduplicates alerts (won't re-alert same ticker within 30 mins)
  - Logs every scan to /home/claude/scan_logs/
  - Cooldown: won't re-trade same ticker for 60 minutes
  - Prints a live countdown between scans

Usage:
  python scheduler.py            # scan only, no trades
  python scheduler.py --trade    # scan + auto-buy best mover (dry run)
  python scheduler.py --live     # LIVE real money trades

Run this in a persistent terminal (tmux, screen, or Claude Code session).
"""

import time
import os
import sys
import json
import subprocess
from datetime import datetime, timezone
import pytz

# ── Config ───────────────────────────────────────────────────────────────────
ET = pytz.timezone("America/New_York")

MARKET_OPEN_H  = 9
MARKET_OPEN_M  = 45   # Start scanning at 9:45am ET
MARKET_CLOSE_H = 15
MARKET_CLOSE_M = 45   # Stop scanning at 3:45pm ET

SCAN_INTERVAL_SEC = 300   # Every 5 minutes
ALERT_COOLDOWN_MIN = 30   # Don't re-alert same ticker within 30 mins
TRADE_COOLDOWN_MIN = 60   # Don't re-trade same ticker within 60 mins

LOG_DIR = os.path.expanduser("~/scan_logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ── State ─────────────────────────────────────────────────────────────────────
alerted_tickers: dict[str, datetime] = {}   # sym -> last alert time
traded_tickers:  dict[str, datetime] = {}   # sym -> last trade time
scan_count = 0

# ── Helpers ───────────────────────────────────────────────────────────────────
def now_et() -> datetime:
    return datetime.now(ET)

def is_market_hours() -> bool:
    now = now_et()
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open  = now.replace(hour=MARKET_OPEN_H,  minute=MARKET_OPEN_M,  second=0, microsecond=0)
    market_close = now.replace(hour=MARKET_CLOSE_H, minute=MARKET_CLOSE_M, second=0, microsecond=0)
    return market_open <= now <= market_close

def seconds_until_open() -> int:
    now = now_et()
    # Skip to next weekday if weekend
    days_ahead = 0
    if now.weekday() == 5:   days_ahead = 2  # Saturday → Monday
    elif now.weekday() == 6: days_ahead = 1  # Sunday → Monday

    target = now.replace(hour=MARKET_OPEN_H, minute=MARKET_OPEN_M, second=0, microsecond=0)
    if days_ahead > 0:
        from datetime import timedelta
        target = (now + timedelta(days=days_ahead)).replace(
            hour=MARKET_OPEN_H, minute=MARKET_OPEN_M, second=0, microsecond=0
        )
    elif now >= target:
        from datetime import timedelta
        target += timedelta(days=1)
        # Skip weekend again
        while target.weekday() >= 5:
            target += timedelta(days=1)

    delta = (target - now).total_seconds()
    return max(0, int(delta))

def format_time(secs: int) -> str:
    h, rem = divmod(secs, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    elif m:
        return f"{m}m {s}s"
    return f"{s}s"

def cooldown_ok(ticker: str, cooldown_dict: dict, cooldown_min: int) -> bool:
    if ticker not in cooldown_dict:
        return True
    elapsed = (now_et() - cooldown_dict[ticker]).total_seconds() / 60
    return elapsed >= cooldown_min

def print_header():
    now = now_et()
    print(f"""
╔══════════════════════════════════════════════════════════╗
║   🔥 WILEY STRAT SCANNER — SCHEDULER              ║
║   {now.strftime('%A, %B %d %Y  %I:%M:%S %p ET'):52s}║
║   Scan interval: every {SCAN_INTERVAL_SEC//60} min  |  Window: 9:45am–3:45pm ET  ║
╚══════════════════════════════════════════════════════════╝""")

def run_scan(auto_trade: bool, dry_run: bool) -> list:
    """Run explosion_scanner.py and parse results."""
    global scan_count
    scan_count += 1

    now = now_et()
    print(f"\n{'─'*58}")
    print(f"  📡 SCAN #{scan_count}  |  {now.strftime('%I:%M:%S %p ET')}")
    print(f"{'─'*58}")

    # Build args
    scanner_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "explosion_scanner.py")
    cmd = [sys.executable, scanner_path]
    if dry_run and auto_trade:
        cmd.append("--trade")
    elif not dry_run:
        cmd.append("--live")

    # Run scanner
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout

    # Print scanner output
    if output.strip():
        print(output)
    if result.stderr and "Traceback" in result.stderr:
        print(f"⚠️  Scanner error:\n{result.stderr[:500]}")

    # Parse latest scan JSON from log dir
    scan_results = []
    try:
        json_files = sorted([
            f for f in os.listdir(LOG_DIR)
            if f.startswith("scan_results_") and f.endswith(".json")
        ])
        # Also check home dir
        home_jsons = sorted([
            f for f in os.listdir(os.path.expanduser("~"))
            if f.startswith("scan_results_") and f.endswith(".json")
        ])
        latest_file = None
        if home_jsons:
            latest_file = os.path.join(os.path.expanduser("~"), home_jsons[-1])
        elif json_files:
            latest_file = os.path.join(LOG_DIR, json_files[-1])

        if latest_file and os.path.exists(latest_file):
            with open(latest_file) as f:
                data = json.load(f)
                scan_results = data.get("results", [])
    except Exception as e:
        pass  # Scanner may not have produced JSON yet

    return scan_results

def process_alerts(results: list, auto_trade: bool, dry_run: bool):
    """Check for new high-conviction tickers and alert/trade."""
    if not results:
        return

    high_conviction = [r for r in results if r.get("score", 0) >= 7]

    if not high_conviction:
        print("  📭 No high-conviction setups this scan.")
        return

    for ticker_data in high_conviction:
        sym     = ticker_data.get("symbol", "?")
        score   = ticker_data.get("score", 0)
        price   = ticker_data.get("price", 0)
        pct     = ticker_data.get("pct_change", 0)
        catalyst = ticker_data.get("catalyst", "N/A")
        signal  = ticker_data.get("signal", "N/A")

        # New alert?
        if cooldown_ok(sym, alerted_tickers, ALERT_COOLDOWN_MIN):
            alerted_tickers[sym] = now_et()
            arrow = "▲" if pct >= 0 else "▼"
            print(f"\n  🔥 ALERT: {sym}  ${price:.2f}  {arrow}{abs(pct):.1f}%  Score:{score}/10")
            print(f"     📰 {catalyst}")
            print(f"     📈 {signal}")

            # Log alert
            log_entry = {
                "time": now_et().isoformat(),
                "type": "ALERT",
                "ticker": sym,
                "score": score,
                "price": price,
                "pct": pct,
                "catalyst": catalyst
            }
            log_path = os.path.join(LOG_DIR, f"alerts_{now_et().strftime('%Y%m%d')}.jsonl")
            with open(log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        else:
            remaining = ALERT_COOLDOWN_MIN - int(
                (now_et() - alerted_tickers[sym]).total_seconds() / 60
            )
            print(f"  ⏳ {sym} on alert cooldown ({remaining}m remaining)")

def wait_with_countdown(seconds: int, label: str = "Next scan"):
    """Sleep with a live countdown display."""
    interval = 30  # Update every 30 seconds
    elapsed = 0
    while elapsed < seconds:
        remaining = seconds - elapsed
        print(f"\r  ⏱  {label} in {format_time(remaining)}   ", end="", flush=True)
        sleep_chunk = min(interval, remaining)
        time.sleep(sleep_chunk)
        elapsed += sleep_chunk
        # Check if market closed during wait
        if not is_market_hours():
            print(f"\r  🔴 Market closed. Stopping.{' '*20}")
            return False
    print(f"\r  {'─'*50}", end="")
    return True

# ── Main Loop ─────────────────────────────────────────────────────────────────
def main():
    auto_trade = "--trade" in sys.argv or "--live" in sys.argv
    dry_run    = "--live" not in sys.argv

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set. Export it first:")
        print("   export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    if not dry_run:
        print("\n⚠️  WARNING: LIVE MODE — Real money will be used.")
        confirm = input("Type YES to confirm: ").strip()
        if confirm != "YES":
            print("Aborted.")
            sys.exit(0)

    print_header()
    mode_str = "LIVE 💰" if not dry_run else ("DRY RUN 🧪" if auto_trade else "SCAN ONLY 📡")
    print(f"\n  Mode: {mode_str}")
    print(f"  Auto-trade: {'ON' if auto_trade else 'OFF'}")
    print(f"  Logs: {LOG_DIR}/")

    try:
        while True:
            now = now_et()

            if now.weekday() >= 5:
                secs = seconds_until_open()
                print(f"\n  📅 Weekend — market opens Monday.")
                wait_with_countdown(min(secs, 3600), "Market open")
                continue

            if not is_market_hours():
                secs = seconds_until_open()
                if secs > 0:
                    print(f"\n  🕐 Pre-market — scanning starts at 9:45am ET.")
                    wait_with_countdown(min(secs, 600), "Market open")
                else:
                    print(f"\n  🔴 Market closed for today. Waiting for tomorrow...")
                    wait_with_countdown(min(seconds_until_open(), 3600), "Next open")
                continue

            # ── IN MARKET HOURS ──
            results = run_scan(auto_trade, dry_run)
            process_alerts(results, auto_trade, dry_run)

            # Countdown to next scan (check market close during wait)
            still_open = wait_with_countdown(SCAN_INTERVAL_SEC, "Next scan")
            if not still_open:
                print(f"\n  🔴 Done for today. {scan_count} scans completed.")
                secs = seconds_until_open()
                print(f"  🌙 Next session opens in {format_time(secs)}.")
                wait_with_countdown(min(secs, 3600), "Tomorrow's open")

    except KeyboardInterrupt:
        print(f"\n\n  🛑 Stopped manually after {scan_count} scans.")
        print(f"  📁 Logs saved to: {LOG_DIR}/")
        sys.exit(0)

if __name__ == "__main__":
    main()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ADD THIS to your scheduler to run BOTH systems each cycle:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# In the "IN MARKET HOURS" block, after run_scan(), add:
#
#   from kevin_0dte_system import run_0dte_analysis
#   run_0dte_analysis(auto_trade=auto_trade, dry_run=dry_run)
#
# This runs the explosion scanner (equities) THEN
# the 0DTE analysis (SPY/QQQ/IWM options) every 5 minutes.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
