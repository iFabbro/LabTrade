import glob
import os

def main():
    print("\n📝 LOG RECENTI (Ultime 15 righe)")
    print("=" * 60)
    
    # Trova il file di log modificato più di recente
    log_files = glob.glob('logs/*.log')
    if not log_files:
        print("❌ Nessun file di log trovato.")
        return
        
    latest_log = max(log_files, key=os.path.getmtime)
    
    with open(latest_log, 'r') as f:
        lines = f.readlines()
        
    # Prendi le ultime 15 righe
    recent_lines = lines[-15:]
    
    for line in recent_lines:
        line = line.strip()
        if not line: 
            continue
        
        # Colori ANSI per il terminale
        if 'ERROR' in line or '❌' in line:
            color = "\033[91m" # Rosso
        elif 'WARNING' in line or '⚠️' in line:
            color = "\033[93m" # Giallo
        elif 'DRY-RUN' in line:
            color = "\033[95m" # Magenta
        else:
            color = "\033[96m" # Ciano
            
        reset = "\033[0m"
        print(f"{color}{line}{reset}")
        
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
