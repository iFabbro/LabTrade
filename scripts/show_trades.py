import csv
import glob

def main():
    trades = []
    for f in sorted(glob.glob('logs/trades_*.csv')):
        with open(f, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('action') in ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE_LONG', 'CLOSE_SHORT']:
                    trades.append(row)
    
    closed_trades = []
    i = 0
    while i < len(trades):
        trade = trades[i]
        action = trade.get('action', '')
        if action in ['OPEN_LONG', 'OPEN_SHORT']:
            side = 'LONG' if action == 'OPEN_LONG' else 'SHORT'
            entry_price = float(trade.get('price', 0))
            total_quantity = float(trade.get('quantity', 0))
            total_pnl = 0.0
            last_exit_price = entry_price
            has_closes = False
            
            j = i + 1
            while j < len(trades):
                close_trade = trades[j]
                close_action = close_trade.get('action', '')
                if close_action in ['OPEN_LONG', 'OPEN_SHORT']:
                    break
                if close_action == f'CLOSE_{side}':
                    total_pnl += float(close_trade.get('pnl', 0))
                    last_exit_price = float(close_trade.get('price', 0))
                    has_closes = True
                j += 1
            
            if has_closes:
                closed_trades.append({
                    'side': side, 'entry': entry_price, 'exit': last_exit_price,
                    'quantity': total_quantity, 'pnl': total_pnl
                })
            i = j
        else:
            i += 1

    print(f"\n{'#':<4} {'Side':<6} {'Entry':<12} {'Exit':<12} {'Qty':<8} {'PnL':<10}")
    print("-" * 55)
    total_pnl = 0
    wins = 0
    for idx, t in enumerate(closed_trades, 1):
        pnl = t['pnl']
        total_pnl += pnl
        if pnl > 0: wins += 1
        pnl_str = f"${pnl:+.2f}"
        print(f"{idx:<4} {t['side']:<6} ${t['entry']:<11.2f} ${t['exit']:<11.2f} {t['quantity']:<7.3f} {pnl_str:<10}")
    
    print("-" * 55)
    total = len(closed_trades)
    win_rate = (wins/total*100) if total > 0 else 0
    print(f"Trade Totali: {total} | Win Rate: {win_rate:.1f}% | PnL Totale: ${total_pnl:+.2f}\n")

if __name__ == "__main__":
    main()
