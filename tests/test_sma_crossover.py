import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.binance_client import binance_client
from src.strategies.sma_crossover import SMACrossoverStrategy

def test_sma_crossover_strategy():
    """Testa la strategia SMA Crossover su dati reali di Bitcoin"""
    # Scarica 100 giorni di dati (necessari per SMA a 50 periodi)
    df = binance_client.get_historical_klines(
        symbol='BTCUSDT',
        interval='1d',
        start_str='1 Jan 2023',
        end_str='10 Apr 2024'
    )
    
    # Inizializza la strategia
    strategy = SMACrossoverStrategy(fast_period=20, slow_period=50)
    
    # Genera i segnali
    df_signals = strategy.generate_signals(df)
    
    # Verifica che il DataFrame non sia vuoto
    assert not df_signals.empty, "DataFrame segnali è vuoto"
    
    # Verifica che le colonne SMA siano state aggiunte
    assert 'sma_fast' in df_signals.columns, "Colonna sma_fast mancante"
    assert 'sma_slow' in df_signals.columns, "Colonna sma_slow mancante"
    assert 'signal' in df_signals.columns, "Colonna signal mancante"
    assert 'position' in df_signals.columns, "Colonna position mancante"
    
    # Verifica che ci siano segnali (1, -1, o 0)
    assert df_signals['signal'].isin([-1, 0, 1]).all(), "Valori signal non validi"
    
    # Ottieni i punti di crossover
    buy_signals, sell_signals = strategy.get_crossover_points(df_signals)
    
    print(f"\n✓ Strategia: {strategy.name}")
    print(f"✓ Dati analizzati: {len(df_signals)} giorni")
    print(f"✓ Segnali BUY generati: {len(buy_signals)}")
    print(f"✓ Segnali SELL generati: {len(sell_signals)}")
    
    if len(buy_signals) > 0:
        print(f"✓ Primo BUY: {buy_signals.iloc[0]['timestamp'].strftime('%Y-%m-%d')} a ${buy_signals.iloc[0]['close']:,.2f}")
    
    if len(sell_signals) > 0:
        print(f"✓ Primo SELL: {sell_signals.iloc[0]['timestamp'].strftime('%Y-%m-%d')} a ${sell_signals.iloc[0]['close']:,.2f}")
    
    # Verifica che ci sia almeno un segnale (dopo 100 giorni dovrebbe esserci)
    assert len(buy_signals) + len(sell_signals) > 0, "Nessun segnale di crossover generato"
