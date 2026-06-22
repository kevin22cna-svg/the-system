#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  KEVIN'S TRADING SYSTEM — ONE-COMMAND INSTALLER
#  Works on Termux (Android) and Linux/Mac/WSL (PC)
#  Run with:  bash setup.sh
# ═══════════════════════════════════════════════════════════

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   KEVIN'S TRADING SYSTEM — SETUP                ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Detect environment
if command -v pkg &> /dev/null; then
    echo "📱 Termux detected (Android)"
    ENV="termux"
    pkg install -y python nodejs git 2>/dev/null
else
    echo "💻 PC/Linux/Mac detected"
    ENV="pc"
fi

# Install Python dependencies
echo ""
echo "📦 Installing Python packages..."
PIP_FLAG=""
if [ "$ENV" = "pc" ]; then PIP_FLAG="--break-system-packages"; fi
pip install anthropic pytz $PIP_FLAG 2>/dev/null || pip3 install anthropic pytz 2>/dev/null

# Check for API key
echo ""
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  ANTHROPIC_API_KEY not set."
    echo "   Add it now (paste your key, or press Enter to skip):"
    read -r APIKEY
    if [ -n "$APIKEY" ]; then
        echo "export ANTHROPIC_API_KEY=$APIKEY" >> ~/.bashrc
        export ANTHROPIC_API_KEY=$APIKEY
        echo "✅ API key saved to ~/.bashrc"
    fi
else
    echo "✅ ANTHROPIC_API_KEY already set"
fi

# Optional Reddit setup
echo ""
echo "📱 Reddit/WSB feed setup (optional)"
echo "   The WSB feed works WITHOUT login via public API."
echo "   For richer data (comments, higher limits), register a free"
echo "   app at https://reddit.com/prefs/apps and enter creds below."
echo "   Press Enter to skip and use the free public feed:"
read -r -p "   Reddit Client ID (or Enter to skip): " RID
if [ -n "$RID" ]; then
    read -r -p "   Reddit Client Secret: " RSECRET
    # Patch config.py with the creds
    sed -i "s|\"reddit_client_id\": \"\"|\"reddit_client_id\": \"$RID\"|" config.py
    sed -i "s|\"reddit_client_secret\": \"\"|\"reddit_client_secret\": \"$RSECRET\"|" config.py
    echo "✅ Reddit credentials saved to config.py"
else
    echo "✅ Using free public WSB feed (no login needed)"
fi

# Verify all files
echo ""
echo "🔍 Verifying files..."
for f in config.py explosion_scanner.py kevin_0dte_system.py \
         live_combined_scanner.py profit_monitor.py eod_lead_scanner.py; do
    if [ -f "$f" ]; then
        python3 -c "import ast; ast.parse(open('$f').read())" 2>/dev/null && echo "  ✅ $f" || echo "  ❌ $f (syntax error)"
    else
        echo "  ⚠️  $f missing"
    fi
done

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   SETUP COMPLETE                                 ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Commands you can run now:"
echo "  python3 config.py                    # view/check your settings"
echo "  python3 explosion_scanner.py         # scan stocks (shares)"
echo "  python3 live_combined_scanner.py     # continuous scan, Big 3"
echo "  python3 kevin_0dte_system.py         # options analysis"
echo "  python3 profit_monitor.py --auto     # auto take-profit (dry run)"
echo "  python3 eod_lead_scanner.py          # end-of-day next-day leads"
echo ""
echo "To run continuously in background (Termux), use tmux:"
echo "  pkg install tmux"
echo "  tmux new -s trading"
echo "  python3 live_combined_scanner.py --trade"
echo "  (Ctrl+B then D to detach, it keeps running)"
echo ""
echo "⚙️  Edit config.py to change ANY setting across the whole system."
echo ""
