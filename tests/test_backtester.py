import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.binance_client import binance_client
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.core.backtester import Backtester

def test_backtest_sma_crossover():
    """Test completo: scarica dati, applica strategia, esegue backtest"""
    print("\n" + "="*60)
    print("BACKTEST COMPLETO - SMA Crossover su Bitcoin")
    print("="*60)
    
    # 1. Scarica dati storici
    print("\n[1/4] Download dati storici BTC/USDT...")
    df = binance_client.get_historical_klines(
        symbol='BTCUSDT',
        interval='1d',
        start_str='1 Jan 2023',
        end_str='10 Apr 2024'
    )
    print(f"✓ Scaricati {len(df)} giorni di dati")
    print(f"✓ Periodo: {df['timestamp'].iloc[0].strftime('%Y-%m-%d')} → {df['timestamp'].iloc[-1].strftime('%Y-%m-%d')}")
    
    # 2. Applica strategia
    print("\n[2/4] Applicazione strategia SMA Crossover (20/50)...")
    strategy = SMACrossoverStrategy(fast_period=20, slow_period=50)
    df_signals = strategy.generate_signals(df)
    buy_signals, sell_signals = strategy.get_crossover_points(df_signals)
    print(f"✓ Segnali BUY: {len(buy_signals)}")
    print(f"✓ Segnali SELL: {len(sell_signals)}")
    
    # 3. Esegui backtest
    print("\n[3/4] Esecuzione backtest...")
    backtester = Backtester(
        initial_capital=10000,
        commission=0.001,  # 0.1%
        slippage=0.0005    # 0.05%
    )
    results = backtester.run_backtest(df_signals)
    
    # 4. Mostra risultati
    print("\n[4/4] Risultati Backtest:")
    print("-" * 60)
    print(f"Capitale Iniziale:     ${results['initial_capital']:,.2f}")
    print(f"Capitale Finale:       ${results['final_capital']:,.2f}")
    print(f"Rendimento Totale:     {results['total_return_pct']:+.2f}%")
    print(f"Max Drawdown:          {results['max_drawdown_pct']:.2f}%")
    print(f"Numero Trade:          {results['total_trades']}")
    print(f"Win Rate:              {results['win_rate_pct']:.1f}%")
    print("-" * 60)
    
    # Verifiche
    assert results['final_capital'] > 0, "Capitale finale deve essere > 0"
    assert results['total_trades'] > 0, "Deve esserci almeno un trade completato"
    assert results['max_drawdown'] >= 0, "Drawdown deve essere >= 0"
    assert 0 <= results['win_rate'] <= 1, "Win rate deve essere tra 0 e 1"
    
    # Mostra dettaglio trade
    if len(results['trades']) > 0:
        print("\nDettaglio Trade:")
        print("-" * 60)
        for idx, trade in results['trades'].iterrows():
            if trade['type'] == 'BUY':
                print(f"BUY  {trade['date'].strftime('%Y-%m-%d')} @ ${trade['price']:,.2f}")
            else:
                pnl_pct = (trade['pnl'] / (trade['quantity'] * trade['price'])) * 100
                emoji = "✓" if trade['pnl'] > 0 else "✗"
                print(f"{emoji} SELL {trade['date'].strftime('%Y-%m-%d')} @ ${trade['price']:,.2f} | PnL: ${trade['pnl']:+,.2f} ({pnl_pct:+.2f}%)")
        print("-" * 60)
    
    print("\n✓ Backtest completato con successo!")
    print("="*60 + "\n")
