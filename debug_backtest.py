"""
Debug script per capire perché il backtester non esegue trade
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.binance_client import BinanceDataClient
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.core.backtester import Backtester

# 1. Scarica dati
print("Download dati...")
client = BinanceDataClient()
df = client.get_historical_klines('BTCUSDT', '1d', '1 Jan 2023', '10 Apr 2024')
print(f"Scaricati {len(df)} giorni\n")

# 2. Genera segnali
print("Generazione segnali...")
strategy = SMACrossoverStrategy(fast_period=20, slow_period=50)
df_signals = strategy.generate_signals(df)

# 3. Conta segnali
buy_signals = df_signals[df_signals['signal'] == 1]
sell_signals = df_signals[df_signals['signal'] == -1]

print(f"Segnali BUY: {len(buy_signals)}")
print(f"Segnali SELL: {len(sell_signals)}\n")

if len(buy_signals) > 0:
    print("Primi 3 segnali BUY:")
    for idx, row in buy_signals.head(3).iterrows():
        print(f"  Index {idx}: {row['timestamp']} - Close: ${row['close']:.2f} - Signal: {row['signal']}\n")

# 4. Esegui backtest con debug
print("\n" + "="*60)
print("Esecuzione backtest con debug...")
print("="*60 + "\n")

class DebugBacktester(Backtester):
    def run_backtest(self, df_signals):
        df = df_signals.copy()
        
        capital = self.initial_capital
        position = 0
        entry_price = 0.0
        quantity = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        
        trades = []
        signal_count = 0
        
        for idx, row in df.iterrows():
            current_price = row['close']
            signal = row['signal']
            
            if signal != 0:
                signal_count += 1
                print(f"[{signal_count}] Segnale trovato a index {idx}: signal={signal}, position={position}, price=${current_price:.2f}")
            
            # Logica BUY
            if signal == 1 and position == 0:
                entry_price = current_price * (1 + self.slippage)
                quantity = capital / entry_price
                cost = quantity * entry_price
                commission_cost = cost * self.commission
                
                print(f"  → BUY signal! Entry: ${entry_price:.2f}, Qty: {quantity:.6f}, Cost: ${cost:.2f}, Commission: ${commission_cost:.2f}")
                print(f"  → Capital: ${capital:.2f}, Can afford: {cost + commission_cost <= capital}")
                
                if cost + commission_cost <= capital and quantity > 0:
                    capital -= (cost + commission_cost)
                    position = 1
                    print(f"  ✅ Posizione aperta! Nuovo capital: ${capital:.2f}")
                else:
                    print(f"  ❌ Impossibile aprire posizione!")
            
            # Logica SELL
            elif signal == -1 and position == 1:
                exit_price = current_price * (1 - self.slippage)
                pnl = (exit_price - entry_price) * quantity
                print(f"  → SELL signal! Exit: ${exit_price:.2f}, PnL: ${pnl:.2f}")
                
                commission_cost = (quantity * exit_price) * self.commission
                capital += (quantity * exit_price) - commission_cost
                position = 0
                print(f"  ✅ Posizione chiusa! Nuovo capital: ${capital:.2f}")
        
        print(f"\nRisultato finale:")
        print(f"  Capital: ${capital:.2f}")
        print(f"  Position: {position}")
        print(f"  Total signals processed: {signal_count}")

backtester = DebugBacktester(initial_capital=10000, commission=0.001, slippage=0.0005)
backtester.run_backtest(df_signals)
