#!/usr/bin/env python3
"""
Script di avvio rapido per il LabTrade Mission Control.
"""
import sys
import os

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.dashboard.mission_control import MissionControl

if __name__ == "__main__":
    print("🚀 Avvio LabTrade Mission Control...")
    control = MissionControl(
        log_file="logs/paper_trading.log"
    )
    control.run(refresh_rate=1)
