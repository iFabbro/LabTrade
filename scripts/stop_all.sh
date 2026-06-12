#!/bin/bash
# LabTrade Stop All - Termina tutti i processi
echo "🛑 Arresto LabTrade Command Center in corso..."

# Termina i processi Python di LabTrade
pkill -f "run_paper_trading.py" 2>/dev/null
pkill -f "run_dashboard.py" 2>/dev/null
pkill -f "run_mission_control.py" 2>/dev/null

# Termina il monitor dei log
pkill -f "tail -f logs/paper_trading.log" 2>/dev/null

# Attendi un secondo per la propagazione
sleep 1

# Verifica se ci sono processi residui
if pgrep -f "LabTrade" > /dev/null || pgrep -f "run_paper_trading" > /dev/null; then
    echo "⚠️  Alcuni processi potrebbero essere ancora in chiusura..."
else
    echo "✅ Tutti i processi LabTrade sono stati terminati con successo."
fi
