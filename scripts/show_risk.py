import csv
import glob
import json
from pathlib import Path

def get_complete_trades():
    trades = []
    for f in sorted(glob.glob('logs/trades_*.csv')):
        with open(f, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('action') in ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE_LONG', 'CLOSE_SHORT']:
                    trades.append(row)
    
    closed = []
    i = 0
    while i < len(trades):
        trade = trades[i]
        action = trade.get('action', '')
        if action in ['OPEN_LONG', 'OPEN_SHORT']:
            side = 'LONG' if action == 'OPEN_LONG' else 'SHORT'
            entry_price = float(trade.get('price', 0))
            total_quantity = float(trade.get('quantity', 0))
            total_pnl = 0.0
            has_closes = False
            
            j = i + 1
            while j < len(trades):
                close_trade = trades[j]
                close_action = close_trade.get('action', '')
                if close_action in ['OPEN_LONG', 'OPEN_SHORT']:
                    break
                if close_action == f'CLOSE_{side}':
                    total_pnl += float(close_trade.get('pnl', 0))
                    has_closes = True
                j += 1
            
            if has_closes:
                closed.append({'side': side, 'entry': entry_price, 'quantity': total_quantity, 'pnl': total_pnl})
            i = j
        else:
            i += 1
    return closed

def get_equity_curve():
    balances = [10000.0] # Balance iniziale di default
    for f in sorted(glob.glob('logs/trades_*.csv')):
        with open(f, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get('action', '').startswith('CLOSE') and row.get('balance'):
                    try:
                        balances.append(float(row.get('balance')))
                    except ValueError:
                        pass
    return balances

def main():
    print("\n🛡️ RISK MANAGEMENT DASHBOARD")
    print("=" * 45)
    
    # 1. Esposizione Attuale
    state_file = Path('state/position_state.json')
    exposure = 0.0
    if state_file.exists():
        with open(state_file, 'r') as f:
            state = json.load(f)
        if state.get('position_open'):
            qty = state.get('remaining_quantity', state.get('position_quantity'))
            entry = state.get('entry_price')
            exposure = qty * entry
            
    print("💰 ESPOSIZIONE ATTUALE")
    if exposure > 0:
        leverage = exposure / 10000.0
        print(f"   Valore Posizione: ${exposure:,.2f}")
        print(f"   Leva Implicita:   {leverage:.2f}x {'⚠️' if leverage > 1.0 else '✅'}")
    else:
        print("   Nessuna posizione aperta (Cash: $10,000)")
        
    # 2. Statistiche Strategia
    trades = get_complete_trades()
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    print("\n📊 PERFORMANCE STATISTICA")
    print(f"   Trade Totali:   {len(trades)}")
    print(f"   Win Rate:       {len(wins)/len(trades)*100:.1f}% ({len(wins)}W / {len(losses)}L)")
    print(f"   Profit Factor:  {profit_factor:.2f}")
    
    if wins: print(f"   Avg Win:        ${gross_profit/len(wins):,.2f}")
    if losses: print(f"   Avg Loss:       -${gross_loss/len(losses):,.2f}")
    
    # 3. Drawdown
    balances = get_equity_curve()
    peak = balances[0]
    max_dd = 0.0
    max_dd_val = 0.0
    
    for b in balances:
        if b > peak: peak = b
        dd = (peak - b)
        dd_pct = dd / peak
        if dd_pct > max_dd:
            max_dd = dd_pct
            max_dd_val = dd
            
    print("\n📉 DRAWDOWN & CAPITALE")
    print(f"   Balance Attuale: ${balances[-1]:,.2f}")
    print(f"   Max Drawdown:    ${max_dd_val:,.2f} ({max_dd*100:.2f}%)")
    print("=" * 45 + "\n")

if __name__ == "__main__":
    main()
