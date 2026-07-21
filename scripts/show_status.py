import json
import urllib.request
from pathlib import Path

def get_btc_price():
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            return float(data['price'])
    except Exception:
        return None

def main():
    state_file = Path('state/position_state.json')
    print("\n LABTRADE STATUS")
    print("=" * 40)
    
    # 1. Prezzo Live
    price = get_btc_price()
    price_str = f"${price:,.2f}" if price else "N/D"
    print(f"💰 BTC/USDT: {price_str}")
    
    # 2. Stato Posizione
    if state_file.exists():
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        if state.get('position_open'):
            side = state.get('position_side')
            entry = state.get('entry_price')
            qty = state.get('remaining_quantity', state.get('position_quantity'))
            sl = state.get('stop_loss')
            tp1 = state.get('tp1')
            tp2 = state.get('tp2')
            tp3 = state.get('tp3')
            
            print(f"\n📊 POSIZIONE APERTA: {side}")
            print(f"   Entry: ${entry:,.2f} | Qty: {qty:.3f} BTC")
            print(f"   SL:    ${sl:,.2f}")
            print(f"   TP1:   ${tp1:,.2f} {'✅' if state.get('tp1_hit') else '⏳'}")
            print(f"   TP2:   ${tp2:,.2f} {'✅' if state.get('tp2_hit') else '⏳'}")
            print(f"   TP3:   ${tp3:,.2f} {'✅' if state.get('tp3_hit') else '⏳'}")
            
            if price:
                diff = (price - entry) if side == 'LONG' else (entry - price)
                pnl = diff * qty
                color = "🟢" if pnl >= 0 else "🔴"
                print(f"\n{color} PnL Live: ${pnl:+,.2f}")
        else:
            print("\n😴 Nessuna posizione aperta (FLAT)")
    else:
        print("\n⚠️ File di stato non trovato.")
    
    print("=" * 40 + "\n")

if __name__ == "__main__":
    main()
