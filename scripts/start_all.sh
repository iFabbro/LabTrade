#!/bin/bash
# LabTrade Start All - Avvia motore e monitoraggio (versione minimal)
PROJECT_DIR="/Users/jumpman/Desktop/LabTrade"

echo "🚀 Avvio LabTrade Command Center..."

# 1. Avvia il motore di Paper Trading (se non è già attivo)
if pgrep -f "run_paper_trading.py" > /dev/null; then
    echo "⚙️  Paper Trading Engine è già attivo."
else
    echo "⚙️  Avvio Paper Trading Engine (DRY-RUN)..."
    osascript -e "tell application \"Terminal\"
        set newWindow to do script \"cd $PROJECT_DIR && source venv/bin/activate && python3 scripts/run_paper_trading.py --hours 24 --dry-run\"
        set custom title of newWindow to \"⚙️  Paper Trading Engine\"
    end tell" > /dev/null
    sleep 2
fi

# 2. Apri Trading Desk
osascript -e "tell application \"Terminal\"
    set newWindow to do script \"cd $PROJECT_DIR && source venv/bin/activate && python3 scripts/run_dashboard.py\"
    set custom title of newWindow to \"📊 Trading Desk\"
end tell" > /dev/null
sleep 1

# 3. Apri Mission Control
osascript -e "tell application \"Terminal\"
    set newWindow to do script \"cd $PROJECT_DIR && source venv/bin/activate && python3 scripts/run_mission_control.py\"
    set custom title of newWindow to \"🛰️  Mission Control\"
end tell" > /dev/null

echo ""
echo "✅ Command Center avviato!"
echo " 3 finestre: Engine (nascosta/minimizzata), Trading Desk, Mission Control."
