@echo off
REM setup_mcp_config.bat
REM Double-click this to create your Claude Code MCP config for TradingView.
REM Requires: tradingview-mcp already in your home folder.

setlocal

set "CLAUDE_DIR=%USERPROFILE%\.claude"
set "CONFIG=%CLAUDE_DIR%\.mcp.json"
set "TV_PATH=%USERPROFILE%\tradingview-mcp\src\server.js"
set "JACKSON_PATH=%USERPROFILE%\tradingview-mcp-jackson\src\server.js"

echo.
echo === TradingView MCP Config Writer ===
echo.

REM Create .claude folder if missing
if not exist "%CLAUDE_DIR%" (
    mkdir "%CLAUDE_DIR%"
    echo Created %CLAUDE_DIR%
)

REM Write .mcp.json  (backslashes must be doubled inside JSON strings)
set "TV_ARG=%TV_PATH:\=\\%"
set "JACKSON_ARG=%JACKSON_PATH:\=\\%"

(
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
) > "%CONFIG%"

echo Written: %CONFIG%
echo.

REM Check if tradingview-mcp is installed
if not exist "%TV_PATH%" (
    echo WARNING: tradingview-mcp not found at %TV_PATH%
    echo          Download it, extract to %USERPROFILE%\tradingview-mcp, then run npm install inside that folder.
) else (
    echo OK: tradingview-mcp found.
)

REM Check if tradingview-mcp-jackson is installed
if not exist "%JACKSON_PATH%" (
    echo WARNING: tradingview-mcp-jackson not found at %JACKSON_PATH%
    echo          Download it, extract to %USERPROFILE%\tradingview-mcp-jackson, then run npm install inside that folder.
) else (
    echo OK: tradingview-mcp-jackson found.
)

echo.
echo Done! Now:
echo   1. Restart Claude Code
echo   2. Launch TradingView Desktop with: tradingview-mcp\scripts\launch_tv_debug.bat
echo.
pause
