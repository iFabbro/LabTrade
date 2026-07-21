import re
import glob
from pathlib import Path

def main():
    print("\n INDICATORI ATTUALI")
    print("=" * 40)
    
    log_files = sorted(glob.glob('logs/paper_trading.log'))
    if not log_files:
        print(" Nessun file di log trovato.")
        return

    log_file = log_files[0]
    sma_line = None
    rsi_line = None

    with open(log_file, 'r') as f:
        lines = f.readlines()
        for line in reversed(lines):
            if 'SMA25:' in line and not sma_line:
                sma_line = line.strip()
            if 'RSI:' in line and not rsi_line:
                rsi_line = line.strip()
            if sma_line and rsi_line:
                break

    if sma_line:
        # Regex che cattura numeri e virgole, poi le rimuoviamo con .replace()
        sma25 = re.search(r'SMA25: \$([0-9.,]+)', sma_line)
        sma30 = re.search(r'SMA30: \$([0-9.,]+)', sma_line)
        atr = re.search(r'ATR: \$([0-9.,]+)', sma_line)
        
        print("📈 Medie Mobili & Volatilità:")
        if sma25: print(f"   SMA25: ${float(sma25.group(1).replace(',', '')):,.2f}")
        if sma30: print(f"   SMA30: ${float(sma30.group(1).replace(',', '')):,.2f}")
        if atr: print(f"   ATR:   ${float(atr.group(1).replace(',', '')):,.2f}")
    else:
        print("⚠️ Dati SMA/ATR non ancora disponibili.")

    if rsi_line:
        rsi = re.search(r'RSI: ([0-9.,]+)', rsi_line)
        print("\n📉 Momentum:")
        if rsi: 
            rsi_val = float(rsi.group(1).replace(',', ''))
            status = "🔴 Ipercomprato" if rsi_val > 70 else ("🟢 Ipervenduto" if rsi_val < 30 else "⚪ Neutro")
            print(f"   RSI:   {rsi_val:.1f} ({status})")
    else:
        print("⚠️ Dati RSI non ancora disponibili.")

    print("=" * 40 + "\n")

if __name__ == "__main__":
    main()
