#!/usr/bin/env python3
"""
Script di avvio rapido per il LabTrade Trading Desk.
"""
import sys
import os

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.dashboard.trading_desk import TradingDesk

if __name__ == "__main__":
    print("🚀 Avvio LabTrade Trading Desk...")
    desk = TradingDesk(
        log_file="logs/paper_trading.log",
        trades_dir="logs"
    )
    desk.run(refresh_rate=1)
