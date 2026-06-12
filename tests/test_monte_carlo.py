import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import numpy as np
from src.utils.binance_client import binance_client
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.risk.risk_manager import RiskManager
from src.core.backtester import Backtester
from src.risk.monte_carlo import run_monte_carlo
import pandas_ta as ta

def test_monte_carlo_with_real_data():
    """Test Monte Carlo con dati reali dalla strategia SMA 25/30 + Risk Manager"""
    print("\n" + "="*60)
    print("MONTE CARLO SIMULATION - Dati Reali")
    print("="*60)
    
    # 1. Scarica dati reali
    print("\n[1/4] Download dati reali BTC/USDT...")
    df = binance_client.get_historical_klines(
        symbol='BTCUSDT',
        interval='1d',
        start_str='1 Jan 2023',
        end_str='10 Apr 2024'
    )
    print(f"Scaricati {len(df)} giorni")
    
    # 2. Applica strategia
    print("\n[2/4] Applicazione strategia SMA 25/30...")
    strategy = SMACrossoverStrategy(fast_period=25, slow_period=30)
    df_signals = strategy.generate_signals(df)
    
    # Calcola ATR per Risk Manager
    df_signals['atr'] = ta.atr(df_signals['high'], df_signals['low'], df_signals['close'], length=14)
    
    # 3. Esegui backtest con Risk Manager
    print("\n[3/4] Esecuzione backtest con Risk Manager...")
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
    results = backtester.run_backtest(df_signals)
    
    # Estrai rendimenti reali
    df_trades = results['trades']
    sell_trades = df_trades[df_trades['type'].str.startswith('SELL')]
    
    if len(sell_trades) == 0:
        pytest.fail("Nessun trade chiuso trovato nel backtest!")
    
    # Calcola PnL percentuali in formato decimale (es. 0.02 per 2%)
    trade_returns_decimal = []
    for idx, trade in sell_trades.iterrows():
        invested = trade['quantity'] * trade['price']
        if invested > 0:
            pnl_pct = (trade['pnl'] / invested)
            trade_returns_decimal.append(pnl_pct)
    
    print(f"Estratti {len(trade_returns_decimal)} rendimenti reali")
    print(f"Media PnL: {np.mean(trade_returns_decimal)*100:+.2f}%")
    print(f"Win Rate: {sum(1 for r in trade_returns_decimal if r > 0) / len(trade_returns_decimal) * 100:.1f}%")
    
    # 4. Esegui Monte Carlo
    print("\n[4/4] Esecuzione simulazione Monte Carlo (1000 iterazioni)...")
    results_mc = run_monte_carlo(
        trade_returns=trade_returns_decimal,
        initial_capital=10000.0,
        n_simulations=1000,
        block_size=3,
        seed=42
    )
    
    # Output risultati
    print("\n" + "="*60)
    print("RISULTATI MONTE CARLO")
    print("="*60)
    print(f"Strategia: SMA 25/30 + Risk Manager")
    print(f"Periodo: 2023-01-01 → 2024-04-10")
    print(f"Trade Storici: {len(trade_returns_decimal)}")
    print(f"Simulazioni: 1000")
    print("-"*60)
    
    print("\nDistribuzione Rendimento Finale:")
    print(f"  Worst Case (5° percentile):  {results_mc['percentile_5_return']:+.2f}%")
    print(f"  Mediana (50° percentile):    {results_mc['percentile_50_return']:+.2f}%")
    print(f"  Best Case (95° percentile):  {results_mc['percentile_95_return']:+.2f}%")
    
    print("\nDistribuzione Max Drawdown:")
    print(f"  Worst Case (5° percentile):  {results_mc['percentile_5_dd']:.2f}%")
    print(f"  Mediana (50° percentile):    {results_mc['percentile_50_dd']:.2f}%")
    print(f"  Best Case (95° percentile):  {results_mc['percentile_95_dd']:.2f}%")
    
    print("\nAnalisi Rischio:")
    print(f"  Probabilità di Perdita:      {results_mc['prob_loss_pct']:.1f}%")
    print(f"  Probabilità DD > 20%:        {results_mc['prob_dd_20_pct']:.1f}%")
    
    # Classificazione robustezza
    if results_mc['prob_loss_pct'] < 20 and results_mc['percentile_5_dd'] < 30:
        print("\n✅ Strategia ROBUSTA")
    else:
        print("\n⚠️  Strategia FRAGILE")
    
    print("="*60 + "\n")
    
    # Verifiche
    assert results_mc['prob_loss_pct'] >= 0
    assert results_mc['prob_loss_pct'] <= 100
    assert len(results_mc['final_returns_pct']) == 1000
