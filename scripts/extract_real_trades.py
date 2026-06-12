import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.binance_client import binance_client
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.risk.risk_manager import RiskManager
from src.core.backtester import Backtester

def extract_real_trade_returns():
    """Estrae la lista reale dei rendimenti percentuali dai trade della strategia ottimizzata"""
    print("\n" + "="*60)
    print("ESTRAZIONE DATI REALI - SMA 25/30 + Risk Manager")
    print("="*60)
    
    # 1. Scarica dati
    print("\n[1/3] Download dati BTC/USDT...")
    df = binance_client.get_historical_klines(
        symbol='BTCUSDT',
        interval='1d',
        start_str='1 Jan 2023',
        end_str='10 Apr 2024'
    )
    print(f"Scaricati {len(df)} giorni")
    
    # 2. Applica strategia con parametri ottimizzati (Thread 01)
    print("\n[2/3] Applicazione strategia SMA 25/30...")
    strategy = SMACrossoverStrategy(fast_period=25, slow_period=30)
    df_signals = strategy.generate_signals(df)
    
    # Calcola ATR necessario per il Risk Manager
    import pandas_ta as ta
    df_signals["atr"] = ta.atr(df_signals["high"], df_signals["low"], df_signals["close"], length=14)
    
    # 3. Esegui backtest con Risk Manager (Thread 02)
    print("\n[3/3] Esecuzione backtest con Risk Manager...")
    risk_manager = RiskManager(
        risk_per_trade=0.02,
        atr_period=14,
        atr_sl_multiplier=2.0,
    )
    backtester = Backtester(
        initial_capital=10000,
        commission=0.001,
        slippage=0.0005,
        risk_manager=risk_manager
    )
    results = backtester.run_backtest(df_signals)
    
    # 4. Estrai PnL percentuali dei trade chiusi
    df_trades = results['trades']
    sell_trades = df_trades[df_trades['type'] == 'SELL'].copy()
    
    if len(sell_trades) == 0:
        print("\nERRORE: Nessun trade chiuso trovato!")
        return
    
    # Calcola pnl_pct per ogni trade
    pnl_pct_list = []
    for idx, trade in sell_trades.iterrows():
        # PnL percentuale rispetto al capitale investito
        invested = trade['quantity'] * trade['price']
        pnl_pct = (trade['pnl'] / invested) * 100 if invested > 0 else 0
        pnl_pct_list.append(round(pnl_pct, 4))
    
    print(f"\n{'='*60}")
    print(f"TOTALE TRADE CHIUSI: {len(pnl_pct_list)}")
    print(f"{'='*60}")
    print(f"\nLista PnL Percentuali (da copiare in test_monte_carlo.py):")
    print("-"*60)
    print(pnl_pct_list)
    print("-"*60)
    
    # Statistiche rapide
    import numpy as np
    arr = np.array(pnl_pct_list)
    print(f"\nStatistiche:")
    print(f"  Media PnL:      {arr.mean():+.3f}%")
    print(f"  Mediana PnL:    {np.median(arr):+.3f}%")
    print(f"  Std Dev:        {arr.std():.3f}%")
    print(f"  Trade Vincenti: {np.sum(arr > 0)} ({np.sum(arr > 0)/len(arr)*100:.1f}%)")
    print(f"  Trade Perdenti: {np.sum(arr < 0)} ({np.sum(arr < 0)/len(arr)*100:.1f}%)")
    print(f"  Miglior Trade:  {arr.max():+.3f}%")
    print(f"  Peggior Trade:  {arr.min():+.3f}%")
    print("="*60 + "\n")

if __name__ == "__main__":
    extract_real_trade_returns()
