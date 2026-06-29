@echo off
REM setup_mcp_config.bat — Full TradingView MCP setup for Windows
REM Double-click to run. Does everything: npm install, rules.json, .mcp.json
REM Only requirement: Node.js installed + repos already extracted to your home folder.
REM
REM Expected folder structure:
REM   %USERPROFILE%\tradingview-mcp\          (from tradesdontlie/tradingview-mcp)
REM   %USERPROFILE%\tradingview-mcp-jackson\  (from LewisWJackson/tradingview-mcp-jackson)

setlocal enabledelayedexpansion

set "CLAUDE_DIR=%USERPROFILE%\.claude"
set "CONFIG=%CLAUDE_DIR%\.mcp.json"
set "TV_DIR=%USERPROFILE%\tradingview-mcp"
set "JACKSON_DIR=%USERPROFILE%\tradingview-mcp-jackson"
set "TV_PATH=%TV_DIR%\src\server.js"
set "JACKSON_PATH=%JACKSON_DIR%\src\server.js"
set "RULES_PATH=%JACKSON_DIR%\rules.json"

echo.
echo =========================================
echo   TradingView MCP  ^|  Full Setup
echo =========================================
echo.

REM ── Check Node.js ────────────────────────────────────────────────────────────
where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found.
    echo        Install from https://nodejs.org then re-run this script.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set NODE_VER=%%v
echo [OK] Node.js %NODE_VER%

REM ── tradingview-mcp npm install ───────────────────────────────────────────────
echo.
echo [1/4] tradingview-mcp npm install...
if not exist "%TV_DIR%\package.json" (
    echo       MISSING: extract tradingview-mcp to %TV_DIR%
    echo       Download: https://github.com/tradesdontlie/tradingview-mcp/archive/refs/heads/main.zip
    goto skip_tv_npm
)
pushd "%TV_DIR%"
call npm install
popd
echo       Done.
:skip_tv_npm

REM ── tradingview-mcp-jackson npm install ──────────────────────────────────────
echo.
echo [2/4] tradingview-mcp-jackson npm install...
if not exist "%JACKSON_DIR%\package.json" (
    echo       MISSING: extract tradingview-mcp-jackson to %JACKSON_DIR%
    echo       Download: https://github.com/LewisWJackson/tradingview-mcp-jackson/archive/refs/heads/main.zip
    goto skip_jackson_npm
)
pushd "%JACKSON_DIR%"
call npm install
popd
echo       Done.
:skip_jackson_npm

REM ── Write rules.json ─────────────────────────────────────────────────────────
echo.
echo [3/4] Writing Wiley Strat rules.json...
if not exist "%JACKSON_DIR%" (
    echo       Skipped — jackson folder not found.
    goto skip_rules
)

> "%RULES_PATH%" (
echo {
echo   "watchlist": [
echo     "QQQ", "SPY", "IWM",
echo     "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "PLTR",
echo     "NU", "FCEL", "CRWV", "HIMS", "SOFI", "CIFR", "AAL", "CCL", "CLSK", "RIOT",
echo     "WULF", "MARA", "RKT", "OPEN", "KMI", "DAL", "LUNR", "RDW", "JOBY",
echo     "SOUN", "BBAI", "QBTS", "IONQ", "HIVE", "RIVN", "NIO", "ASTS", "RKLB",
echo     "QLD", "SSO", "QID", "SDS", "UWM", "TWM", "NVDL",
echo     "BOTZ", "ARKQ", "SMH", "SOXX", "KWEB"
echo   ],
echo   "default_timeframe": "5",
echo   "timeframes": {
echo     "zone_map": "30",
echo     "day_type_confirmation": "15",
echo     "primary_signal": "5",
echo     "execution_trigger": "2"
echo   },
echo   "strategy": {
echo     "name": "Wiley Strat — Casey Options + Shares Scanner",
echo     "systems": {
echo       "casey_options": {
echo         "instruments": ["SPY", "QQQ", "IWM"],
echo         "secondary": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "PLTR"],
echo         "default_dte": 2,
echo         "position_size_usd": 50
echo       },
echo       "wiley_shares": {
echo         "universe": "$10-50 price range, HH/HL uptrend confirmed 3-5 days minimum",
echo         "position_size_usd": 50,
echo         "profit_target_pct": 5,
echo         "stop_loss_pct": 5,
echo         "max_trades_per_day": 3
echo       }
echo     }
echo   },
echo   "weekly_rotation": {
echo     "monday":    "Full universe — scanner + QQQ + SPY + IWM",
echo     "tuesday":   "QQQ only — QLD (bull) or QID (bear)",
echo     "wednesday": "SPY only — SSO (bull) or SDS (bear)",
echo     "thursday":  "IWM only — UWM (bull^), TWM (bear^), or 2DTE options",
echo     "friday":    "Full universe — all four plays if setups confirm"
echo   },
echo   "four_major_levels": {
echo     "PDH": "Previous Day High — Zone 1 breakout point",
echo     "PDL": "Previous Day Low — support/breakdown level",
echo     "PMH": "Pre-Market High — first bullish sign when broken by 15min body close",
echo     "PML": "Pre-Market Low — first bearish sign when broken by 15min body close",
echo     "rule": "Draw zones from WICK TIP to BODY of following candle"
echo   },
echo   "index_timing_rule": {
echo     "real_move_starts": "9:45am ET",
echo     "move_deadline": "12:00pm ET",
echo     "window": "9:45am to 12:00pm ET"
echo   },
echo   "day_type_classification": {
echo     "STRONGEST_BULL":  "PDH + PMH both broken — full size calls",
echo     "BULL_TREND":      "PDH broken only — favor calls",
echo     "BREAKOUT_WATCH":  "PMH broken only — first bullish sign",
echo     "CHOP_ZONE":       "Between PML and PMH — avoid",
echo     "BREAKDOWN_WATCH": "PML broken only — first bearish sign",
echo     "BEAR_TREND":      "PDL broken only — favor puts",
echo     "BALANCED":        "Holds all 4 levels — cautious small size"
echo   },
echo   "a_plus_checklist": {
echo     "minimum_score": 7,
echo     "scoring": {
echo       "ema_fan":       "+2 — 13/48/200 aligned and spacing out",
echo       "body_close":    "+2 — 15min body close above PMH (calls^) or below PML (puts^)",
echo       "zone_structure":"+2 — zone play confirmed + HH/HL or LH/LL",
echo       "candle_pattern":"+1 — flag, wedge, or rejection candle at zone",
echo       "ema_pullback":  "+1 — 13 EMA pullback entry on 2min",
echo       "rvol":          "+1 — RVOL >2x on setup candle",
echo       "vwap":          "+1 — VWAP agrees with direction"
echo     },
echo     "size": {
echo       "8-10": "A+ — full size",
echo       "7":    "HIGH — full size",
echo       "5-6":  "B — half size or wait",
echo       "<5":   "NO TRADE"
echo     }
echo   },
echo   "ema_fan": {
echo     "periods": [13, 48, 200],
echo     "bullish": "All three aligned upward, spacing out, price above all",
echo     "bearish": "All three aligned downward, spacing out, price below all",
echo     "bunched": "EMAs compressed — chop zone, avoid"
echo   },
echo   "risk_rules": {
echo     "max_per_trade": 50,
echo     "max_trades_per_day": 3,
echo     "no_entries_after": "3:45pm ET on 0DTE",
echo     "no_chop_zone": "No trades when price between PML and PMH",
echo     "profit_first": "Sell the instant target is hit intraday"
echo   },
echo   "account": {
echo     "number": "666042577",
echo     "type": "Agentic, option_level_2",
echo     "rule": "Always review_option_order BEFORE place_option_order"
echo   }
echo }
)
echo       Written: %RULES_PATH%
:skip_rules

REM ── Write .mcp.json ───────────────────────────────────────────────────────────
echo.
echo [4/4] Writing Claude Code .mcp.json...
if not exist "%CLAUDE_DIR%" mkdir "%CLAUDE_DIR%"

set "TV_ARG=%TV_PATH:\=\\%"
set "JACKSON_ARG=%JACKSON_PATH:\=\\%"

> "%CONFIG%" (
echo {
echo   "mcpServers": {
echo     "tradingview": {
echo       "command": "node",
echo       "args": ["%TV_ARG%"]
echo     },
echo     "tradingview-rules": {
echo       "command": "node",
echo       "args": ["%JACKSON_ARG%"]
echo     }
echo   }
echo }
)
echo       Written: %CONFIG%

REM ── Summary ───────────────────────────────────────────────────────────────────
echo.
echo =========================================
echo   Done!
echo =========================================
echo.
echo Next steps:
echo   1. Launch TradingView Desktop
echo   2. Run: %TV_DIR%\scripts\launch_tv_debug.bat
echo   3. Restart Claude Code
echo   4. TradingView tools will appear automatically
echo.
pause
