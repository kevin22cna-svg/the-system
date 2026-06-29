@echo off
REM setup_mcp_config.bat — Full TradingView MCP setup for Windows
REM Double-click to run. Finds ZIPs, extracts, npm installs, writes all config files.
REM
REM Looks for ZIPs in: C:\  Downloads\  Desktop\  Documents\

setlocal enabledelayedexpansion

set "CLAUDE_DIR=%USERPROFILE%\.claude"
set "CONFIG=%CLAUDE_DIR%\.mcp.json"
set "TV_DIR=%USERPROFILE%\tradingview-mcp"
set "JACKSON_DIR=%USERPROFILE%\tradingview-mcp-jackson"
set "TV_PATH=%TV_DIR%\src\server.js"
set "JACKSON_PATH=%JACKSON_DIR%\src\server.js"
set "RULES_PATH=%JACKSON_DIR%\rules.json"

set "DOWNLOADS=%USERPROFILE%\Downloads"
set "DESKTOP=%USERPROFILE%\Desktop"
set "DOCUMENTS=%USERPROFILE%\Documents"

echo.
echo =========================================
echo   TradingView MCP  ^|  Full Setup
echo =========================================
echo.

REM ── Check Node.js ─────────────────────────────────────────────────────────
where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found.
    echo        Install from https://nodejs.org then re-run this script.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set NODE_VER=%%v
echo [OK] Node.js %NODE_VER%
echo.

REM ── Extract tradingview-mcp ───────────────────────────────────────────────
echo [1/5] Looking for tradingview-mcp ZIP...
set "TV_ZIP="
for %%Z in (
    "C:\tradingview-mcp-main.zip"
    "C:\tradingview-mcp.zip"
    "%DOWNLOADS%\tradingview-mcp-main.zip"
    "%DOWNLOADS%\tradingview-mcp.zip"
    "%DESKTOP%\tradingview-mcp-main.zip"
    "%DESKTOP%\tradingview-mcp.zip"
    "%DOCUMENTS%\tradingview-mcp-main.zip"
    "%DOCUMENTS%\tradingview-mcp.zip"
) do (
    if "!TV_ZIP!"=="" if exist %%Z set "TV_ZIP=%%~Z"
)

if defined TV_ZIP (
    echo       Found: !TV_ZIP!
    if exist "%TV_DIR%" (
        echo       Already extracted — skipping.
    ) else (
        echo       Extracting...
        powershell -Command "Expand-Archive -Path '!TV_ZIP!' -DestinationPath '%USERPROFILE%\tv-mcp-tmp' -Force"
        for /d %%D in ("%USERPROFILE%\tv-mcp-tmp\*") do (
            move "%%D" "%TV_DIR%" >nul
        )
        rmdir /s /q "%USERPROFILE%\tv-mcp-tmp" 2>nul
        echo       Extracted to %TV_DIR%
    )
) else (
    if exist "%TV_DIR%\package.json" (
        echo       ZIP not found but folder exists — skipping extract.
    ) else (
        echo       NOT FOUND. Put the ZIP in C:\  or Downloads\  then re-run.
        echo       Download: https://github.com/tradesdontlie/tradingview-mcp/archive/refs/heads/main.zip
    )
)

REM ── Extract tradingview-mcp-jackson ──────────────────────────────────────
echo.
echo [2/5] Looking for tradingview-mcp-jackson ZIP...
set "JACKSON_ZIP="
for %%Z in (
    "C:\tradingview-mcp-jackson-main.zip"
    "C:\tradingview-mcp-jackson.zip"
    "%DOWNLOADS%\tradingview-mcp-jackson-main.zip"
    "%DOWNLOADS%\tradingview-mcp-jackson.zip"
    "%DESKTOP%\tradingview-mcp-jackson-main.zip"
    "%DESKTOP%\tradingview-mcp-jackson.zip"
    "%DOCUMENTS%\tradingview-mcp-jackson-main.zip"
    "%DOCUMENTS%\tradingview-mcp-jackson.zip"
) do (
    if "!JACKSON_ZIP!"=="" if exist %%Z set "JACKSON_ZIP=%%~Z"
)

if defined JACKSON_ZIP (
    echo       Found: !JACKSON_ZIP!
    if exist "%JACKSON_DIR%" (
        echo       Already extracted — skipping.
    ) else (
        echo       Extracting...
        powershell -Command "Expand-Archive -Path '!JACKSON_ZIP!' -DestinationPath '%USERPROFILE%\jackson-tmp' -Force"
        for /d %%D in ("%USERPROFILE%\jackson-tmp\*") do (
            move "%%D" "%JACKSON_DIR%" >nul
        )
        rmdir /s /q "%USERPROFILE%\jackson-tmp" 2>nul
        echo       Extracted to %JACKSON_DIR%
    )
) else (
    if exist "%JACKSON_DIR%\package.json" (
        echo       ZIP not found but folder exists — skipping extract.
    ) else (
        echo       NOT FOUND. Put the ZIP in C:\  or Downloads\  then re-run.
        echo       Download: https://github.com/LewisWJackson/tradingview-mcp-jackson/archive/refs/heads/main.zip
    )
)

REM ── npm install both ──────────────────────────────────────────────────────
echo.
echo [3/5] Running npm install...
if exist "%TV_DIR%\package.json" (
    echo       tradingview-mcp...
    pushd "%TV_DIR%" & call npm install & popd
) else (
    echo       SKIP: tradingview-mcp folder not found.
)
if exist "%JACKSON_DIR%\package.json" (
    echo       tradingview-mcp-jackson...
    pushd "%JACKSON_DIR%" & call npm install & popd
) else (
    echo       SKIP: tradingview-mcp-jackson folder not found.
)

REM ── Write rules.json ─────────────────────────────────────────────────────
echo.
echo [4/5] Writing Wiley Strat rules.json...
if not exist "%JACKSON_DIR%" (
    echo       SKIP: jackson folder not found.
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
echo         "secondary": ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","AMD","PLTR"],
echo         "default_dte": 2,
echo         "position_size_usd": 50
echo       },
echo       "wiley_shares": {
echo         "universe": "$10-50, HH/HL uptrend 3-5 days minimum",
echo         "position_size_usd": 50,
echo         "profit_target_pct": 5,
echo         "stop_loss_pct": 5,
echo         "max_trades_per_day": 3
echo       }
echo     }
echo   },
echo   "weekly_rotation": {
echo     "monday":    "Full universe — scanner + QQQ + SPY + IWM",
echo     "tuesday":   "QQQ only — QLD (bull^) or QID (bear^)",
echo     "wednesday": "SPY only — SSO (bull^) or SDS (bear^)",
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
echo       "ema_fan":        "+2 — 13/48/200 aligned and spacing out",
echo       "body_close":     "+2 — 15min body close above PMH or below PML",
echo       "zone_structure": "+2 — zone play confirmed + HH/HL or LH/LL",
echo       "candle_pattern": "+1 — flag, wedge, or rejection candle at zone",
echo       "ema_pullback":   "+1 — 13 EMA pullback entry on 2min",
echo       "rvol":           "+1 — RVOL >2x on setup candle",
echo       "vwap":           "+1 — VWAP agrees with direction"
echo     },
echo     "size": {
echo       "8-10": "A+ — full size",
echo       "7":    "HIGH — full size",
echo       "5-6":  "B — half size or wait",
echo       "<5":   "NO TRADE"
echo     }
echo   },
echo   "ema_fan": { "periods": [13, 48, 200] },
echo   "risk_rules": {
echo     "max_per_trade": 50,
echo     "max_trades_per_day": 3,
echo     "no_entries_after": "3:45pm ET on 0DTE",
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

REM ── Write .mcp.json ───────────────────────────────────────────────────────
echo.
echo [5/5] Writing Claude Code .mcp.json...
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

REM ── Done ─────────────────────────────────────────────────────────────────
echo.
echo =========================================
echo   Done!
echo =========================================
echo.
echo Next steps:
echo   1. Launch TradingView Desktop
echo   2. Run: %TV_DIR%\scripts\launch_tv_debug.bat
echo   3. Restart Claude Code
echo.
pause
