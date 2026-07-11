# setup_tradingview_windows.ps1
# One-click TradingView MCP setup for Windows + Claude Code
#
# HOW TO RUN:
#   1. Open PowerShell (right-click Start → Windows PowerShell)
#   2. Paste this command and press Enter:
#      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   3. Then run:
#      .\setup_tradingview_windows.ps1

$userHome    = $env:USERPROFILE
$tvMcpPath   = "$userHome\tradingview-mcp"
$jacksonPath = "$userHome\tradingview-mcp-jackson"
$claudeDir   = "$userHome\.claude"
$mcpJson     = "$claudeDir\.mcp.json"

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  TradingView MCP — Windows Setup    " -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check Node.js ─────────────────────────────────────────────────────────
Write-Host "[1/6] Checking Node.js..." -ForegroundColor Yellow
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Node.js not found." -ForegroundColor Red
    Write-Host "       Download from https://nodejs.org and install, then re-run this script."
    exit 1
}
$nodeVer = node --version
Write-Host "      Node.js $nodeVer found." -ForegroundColor Green

# ── 2. tradingview-mcp (tradesdontlie — 77 tools) ────────────────────────────
Write-Host ""
Write-Host "[2/6] Installing tradingview-mcp..." -ForegroundColor Yellow
if (Test-Path "$tvMcpPath\src\server.js") {
    Write-Host "      Already installed at $tvMcpPath" -ForegroundColor Green
} else {
    $zip = "$env:TEMP\tradingview-mcp.zip"
    $tmp = "$env:TEMP\tv-mcp-extract"
    Write-Host "      Downloading..."
    Invoke-WebRequest -Uri "https://github.com/tradesdontlie/tradingview-mcp/archive/refs/heads/main.zip" `
                      -OutFile $zip -UseBasicParsing
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $tmp
    $extracted = Get-ChildItem $tmp -Directory | Select-Object -First 1
    Move-Item $extracted.FullName $tvMcpPath
    Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "      Downloaded to $tvMcpPath" -ForegroundColor Green
}
Write-Host "      Running npm install..."
Push-Location $tvMcpPath
npm install --silent
Pop-Location
Write-Host "      Done." -ForegroundColor Green

# ── 3. tradingview-mcp-jackson (LewisWJackson — rules system) ────────────────
Write-Host ""
Write-Host "[3/6] Installing tradingview-mcp-jackson..." -ForegroundColor Yellow
if (Test-Path "$jacksonPath\src\server.js") {
    Write-Host "      Already installed at $jacksonPath" -ForegroundColor Green
} else {
    $zip = "$env:TEMP\tradingview-mcp-jackson.zip"
    $tmp = "$env:TEMP\tv-jackson-extract"
    Write-Host "      Downloading..."
    Invoke-WebRequest -Uri "https://github.com/LewisWJackson/tradingview-mcp-jackson/archive/refs/heads/main.zip" `
                      -OutFile $zip -UseBasicParsing
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $tmp
    $extracted = Get-ChildItem $tmp -Directory | Select-Object -First 1
    Move-Item $extracted.FullName $jacksonPath
    Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "      Downloaded to $jacksonPath" -ForegroundColor Green
}
Write-Host "      Running npm install..."
Push-Location $jacksonPath
npm install --silent
Pop-Location
Write-Host "      Done." -ForegroundColor Green

# ── 4. Write rules.json (Wiley Strat) ────────────────────────────────────────
Write-Host ""
Write-Host "[4/6] Writing Wiley Strat rules.json..." -ForegroundColor Yellow
$rulesJson = @'
{
  "watchlist": [
    "QQQ", "SPY", "IWM",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "PLTR",
    "NU", "FCEL", "CRWV", "HIMS", "SOFI", "CIFR", "AAL", "CCL", "CLSK", "RIOT",
    "WULF", "MARA", "RKT", "OPEN", "KMI", "DAL", "LUNR", "RDW", "JOBY",
    "SOUN", "BBAI", "QBTS", "IONQ", "HIVE", "RIVN", "NIO", "ASTS", "RKLB",
    "QLD", "SSO", "QID", "SDS", "UWM", "TWM", "NVDL",
    "BOTZ", "ARKQ", "SMH", "SOXX", "KWEB"
  ],
  "default_timeframe": "5",
  "timeframes": {
    "zone_map": "30",
    "day_type_confirmation": "15",
    "primary_signal": "5",
    "execution_trigger": "2"
  },
  "strategy": {
    "name": "Wiley Strat — Casey Options + Shares Scanner",
    "description": "Two separate systems. Casey system is OPTIONS ONLY on SPY/QQQ/IWM. Wiley Shares is the $10-50 scanner universe.",
    "systems": {
      "casey_options": {
        "instruments": ["SPY", "QQQ", "IWM"],
        "secondary": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "PLTR"],
        "default_dte": 2,
        "position_size_usd": 50
      },
      "wiley_shares": {
        "universe": "$10-50 price range, HH/HL uptrend confirmed 3-5 days minimum",
        "position_size_usd": 50,
        "profit_target_pct": 5,
        "stop_loss_pct": 5,
        "max_trades_per_day": 3
      }
    }
  },
  "weekly_rotation": {
    "monday":    "Full universe — scanner + QQQ + SPY + IWM (weekend research drives picks)",
    "tuesday":   "QQQ only — QLD (bull) or QID (bear), fracs, direction by day type",
    "wednesday": "SPY only — SSO (bull) or SDS (bear), fracs, direction by day type",
    "thursday":  "IWM only — UWM (bull), TWM (bear), shares/fracs or 2DTE options",
    "friday":    "Full universe — all four plays if setups confirm"
  },
  "four_major_levels": {
    "description": "Mark every morning before 9:30am ET from the previous session",
    "PDH": "Previous Day High — Zone 1 breakout point",
    "PDL": "Previous Day Low — support/breakdown level",
    "PMH": "Pre-Market High — first bullish sign when broken by 15min body close",
    "PML": "Pre-Market Low — first bearish sign when broken by 15min body close",
    "zone_draw_rule": "Draw zones from WICK TIP to BODY of following candle"
  },
  "index_timing_rule": {
    "real_move_starts": "9:45am ET",
    "move_deadline": "12:00pm ET",
    "window": "9:45am to 12:00pm ET = the move zone"
  },
  "day_type_classification": {
    "types": {
      "STRONGEST_BULL":  "PDH + PMH both broken → full size calls",
      "BULL_TREND":      "PDH broken only → favor calls",
      "BREAKOUT_WATCH":  "PMH broken only → first bullish sign",
      "CHOP_ZONE":       "Between PML and PMH → avoid",
      "BREAKDOWN_WATCH": "PML broken only → first bearish sign",
      "BEAR_TREND":      "PDL broken only → favor puts",
      "BALANCED":        "Holds all 4 levels → cautious, small size"
    }
  },
  "a_plus_checklist": {
    "minimum_score": 7,
    "scoring": {
      "ema_fan": "+2 — aligned and spacing out",
      "body_close": "+2 — 15min body close above PMH (calls) or below PML (puts)",
      "zone_structure": "+2 — zone play confirmed + HH/HL or LH/LL match",
      "candle_pattern": "+1 — flag, wedge, or rejection candle at zone",
      "ema_pullback": "+1 — 13 EMA pullback entry on 2min",
      "rvol": "+1 — RVOL >2x on setup candle",
      "vwap": "+1 — VWAP agrees with direction"
    },
    "size_guide": {
      "8-10": "A+ SETUP — full size",
      "7":    "HIGH — full size",
      "5-6":  "B SETUP — half size or wait",
      "<5":   "NO TRADE"
    }
  },
  "ema_fan": {
    "periods": [13, 48, 200],
    "bullish": "All three EMAs aligned upward, spacing out, price above all",
    "bearish": "All three EMAs aligned downward, spacing out, price below all",
    "bunched": "EMAs compressed = chop zone = avoid"
  },
  "exit_rules": {
    "priority": "PROFIT TARGET FIRST — sell the instant target is hit intraday",
    "hard_rules": [
      "Hit profit target → SELL IMMEDIATELY",
      "Hit stop loss → SELL IMMEDIATELY",
      "3:45pm ET → FORCE CLOSE all 0DTE positions",
      "NEVER enter after 3:45pm ET on 0DTE"
    ]
  },
  "risk_rules": {
    "max_per_trade": 50,
    "max_trades_per_day": 3,
    "no_entries_after": "3:45pm ET (0DTE)",
    "no_chop_zone": "No trades when price between PML and PMH"
  },
  "account": {
    "number": "666042577",
    "type": "Agentic, option_level_2",
    "rule": "Always review_option_order BEFORE place_option_order"
  }
}
'@
Set-Content -Path "$jacksonPath\rules.json" -Value $rulesJson -Encoding UTF8
Write-Host "      Written to $jacksonPath\rules.json" -ForegroundColor Green

# ── 5. Write .mcp.json for Claude Code ───────────────────────────────────────
Write-Host ""
Write-Host "[5/6] Writing Claude Code MCP config..." -ForegroundColor Yellow
if (-not (Test-Path $claudeDir)) {
    New-Item -ItemType Directory -Path $claudeDir | Out-Null
}
$tvArg      = "$tvMcpPath\src\server.js"   -replace '\\', '\\'
$jacksonArg = "$jacksonPath\src\server.js" -replace '\\', '\\'
$mcpConfig = "{
  `"mcpServers`": {
    `"tradingview`": {
      `"command`": `"node`",
      `"args`": [`"$tvArg`"]
    },
    `"tradingview-rules`": {
      `"command`": `"node`",
      `"args`": [`"$jacksonArg`"]
    }
  }
}"
Set-Content -Path $mcpJson -Value $mcpConfig -Encoding UTF8
Write-Host "      Written to $mcpJson" -ForegroundColor Green

# ── 6. Launch TradingView with debug port ─────────────────────────────────────
Write-Host ""
Write-Host "[6/6] Launching TradingView with debug port 9222..." -ForegroundColor Yellow
$batPath = "$tvMcpPath\scripts\launch_tv_debug.bat"
if (Test-Path $batPath) {
    Start-Process "cmd.exe" -ArgumentList "/c `"$batPath`"" -WindowStyle Normal
    Write-Host "      TradingView launching — log in if prompted." -ForegroundColor Green
} else {
    Write-Host "      launch_tv_debug.bat not found. Launch TradingView manually with:" -ForegroundColor Yellow
    Write-Host "      TradingView.exe --remote-debugging-port=9222"
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!                    " -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Log in to TradingView if the window opened" -ForegroundColor White
Write-Host "  2. Restart Claude Code completely" -ForegroundColor White
Write-Host "  3. TradingView MCP tools will appear automatically" -ForegroundColor White
Write-Host ""
