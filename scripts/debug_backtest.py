import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.binance_client import binance_client
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.risk.risk_manager import RiskManager
from src.core.backtester import Backtester
import pandas_ta as ta
import pandas as pd

print("\n" + "="*60)
print("DEBUG BACKTEST - Analisi Dati")
print("="*60)

# 1. Scarica dati
print("\n[1/5] Download dati...")
df = binance_client.get_historical_klines(
    symbol='BTCUSDT',
    interval='1d',
    start_str='1 Jan 2023',
    end_str='10 Apr 2024'
)
print(f"✓ Scaricati {len(df)} giorni")
print(f"✓ Colonne iniziali: {list(df.columns)}")

# 2. Applica strategia
print("\n[2/5] Applicazione strategia...")
strategy = SMACrossoverStrategy(fast_period=25, slow_period=30)
df_signals = strategy.generate_signals(df)
print(f"✓ Colonne dopo strategia: {list(df_signals.columns)}")
print(f"✓ Valori unici in 'signal': {df_signals['signal'].unique()}")
print(f"✓ Numero di segnali BUY (1): {(df_signals['signal'] == 1).sum()}")
print(f"✓ Numero di segnali SELL (-1): {(df_signals['signal'] == -1).sum()}")

# 3. Calcola ATR
print("\n[3/5] Calcolo ATR...")
df_signals['atr'] = ta.atr(df_signals['high'], df_signals['low'], df_signals['close'], length=14)
print(f"✓ Colonne dopo ATR: {list(df_signals.columns)}")
print(f"✓ NaN in colonna 'atr': {df_signals['atr'].isna().sum()}")
print(f"✓ Prime 5 righe dopo ATR:")
print(df_signals.head())

# 4. Rimuovi NaN
print("\n[4/5] Rimozione NaN...")
df_clean = df_signals.dropna().reset_index(drop=True)
print(f"✓ Righe dopo dropna: {len(df_clean)}")
print(f"✓ Colonne finali: {list(df_clean.columns)}")

# 5. Test backtest
print("\n[5/5] Test Backtester...")
risk_manager = RiskManager(
    risk_per_trade=0.02,
    atr_period=14,
    atr_sl_multiplier=2.0,
    rr_ratio=2.0
)
backtester = Backtester(
    initial_capital=10000,
    commission=0.001,
    slippage=0.0005,
    risk_manager=risk_manager
)

print("✓ Esecuzione backtest...")
results = backtester.run_backtest(df_clean)

print(f"\n✓ Risultati:")
print(f"  - Capitale finale: ${results['final_capital']:.2f}")
print(f"  - Rendimento: {results['total_return_pct']:+.2f}%")
print(f"  - Trade totali: {results['total_trades']}")
print(f"  - Max Drawdown: {results['max_drawdown_pct']:.2f}%")

df_trades = results['trades']
print(f"\n✓ DataFrame trades:")
print(f"  - Righe totali: {len(df_trades)}")
if len(df_trades) > 0:
    print(f"  - Colonne: {list(df_trades.columns)}")
    print(f"  - Tipi di trade: {df_trades['type'].value_counts().to_dict()}")
    print(f"\n✓ Prime 10 trade:")
    print(df_trades.head(10))
else:
    print("  ⚠️  NESSUN TRADE!")

print("="*60 + "\n")
