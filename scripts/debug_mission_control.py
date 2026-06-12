#!/usr/bin/env python3
"""
Debug script per testare il parsing dei log del Mission Control.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.dashboard.mission_control import MissionControl, LOG_TO_MODULE

def test_log_parsing():
    print("="*60)
    print("DEBUG: Test Parsing Log Mission Control")
    print("="*60)
    
    # Crea istanza Mission Control
    mc = MissionControl(log_file="logs/paper_trading.log")
    
    # Leggi il file di log
    print("\n[1] Lettura file di log...")
    with open("logs/paper_trading.log", 'r') as f:
        lines = f.readlines()
    
    print(f"✓ Totale righe nel log: {len(lines)}")
    
    # Testa il parsing di ogni riga
    print("\n[2] Test parsing righe...")
    parsed_count = 0
    
    for i, line in enumerate(lines[:20]):  # Testa prime 20 righe
        line = line.strip()
        if not line:
            continue
        
        print(f"\nRiga {i+1}: {line[:80]}...")
        
        # Controlla quale modulo viene identificato
        for module_key, module in mc.modules.items():
            keywords = LOG_TO_MODULE.get(module_key, [])
            log_lower = line.lower()
            
            if any(keyword in log_lower for keyword in keywords):
                print(f"  → Modulo identificato: {module.name}")
                print(f"  → Keywords trovate: {[k for k in keywords if k in log_lower]}")
                
                # Testa update_from_log
                result = module.update_from_log(line)
                print(f"  → update_from_log() risultato: {result}")
                print(f"  → Stato modulo: {module.status}")
                print(f"  → Azione: {module.last_action}")
                parsed_count += 1
                break
        else:
            print(f"  → ️  Nessun modulo identificato!")
    
    print(f"\n{'='*60}")
    print(f"Righe parse correttamente: {parsed_count}/20")
    print(f"{'='*60}")
    
    # Mostra stato finale dei moduli
    print("\n[3] Stato finale moduli:")
    for key, module in mc.modules.items():
        print(f"  {module.icon} {module.name}: {module.status} ({module.actions_count} azioni)")

if __name__ == "__main__":
    test_log_parsing()
