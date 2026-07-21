#!/usr/bin/env python3
"""
Script di avvio rapido per il LabTrade Trading Desk.
"""
import sys
import os
import glob

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.dashboard.trading_desk import TradingDesk

if __name__ == "__main__":
    print("🚀 Avvio LabTrade Trading Desk...")
    
    # Trova automaticamente l'ultimo file di trade generato
    trades_files = glob.glob("logs/trades_*.csv")
    if trades_files:
        latest_trades_file = max(trades_files, key=os.path.getctime)
    else:
        latest_trades_file = "logs/trades_current.csv"
        
    print(f"📂 Lettura trade da: {latest_trades_file}")
    
    desk = TradingDesk(
        log_file="logs/paper_trading.log",
        trades_file=latest_trades_file
    )
    desk.run(refresh_rate=1)
