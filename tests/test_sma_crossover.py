"""
Test SMA Crossover Strategy
"""
import pytest
import pandas as pd
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.utils.binance_client import BinanceDataClient


@pytest.fixture
def binance_client():
    return BinanceDataClient()


def test_sma_crossover_strategy():
    """Testa la strategia SMA Crossover su dati reali di Bitcoin"""
    # Scarica 100 giorni di dati (necessari per SMA a 50 periodi)
    client = BinanceDataClient()
    df = client.get_historical_klines(
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
    buy_indices, sell_indices = strategy.get_crossover_points(df_signals)
    
    print(f"\n✓ Strategia: {strategy.name}")
    print(f"✓ Dati analizzati: {len(df_signals)} giorni")
    print(f"✓ Segnali BUY generati: {len(buy_indices)}")
    print(f"✓ Segnali SELL generati: {len(sell_indices)}")
    
    if len(buy_indices) > 0:
        first_buy_idx = buy_indices[0]
        first_buy_row = df_signals.iloc[first_buy_idx]
        print(f"✓ Primo BUY: {first_buy_row['timestamp'].strftime('%Y-%m-%d')} a ${first_buy_row['close']:,.2f}")
    
    if len(sell_indices) > 0:
        first_sell_idx = sell_indices[0]
        first_sell_row = df_signals.iloc[first_sell_idx]
        print(f"✓ Primo SELL: {first_sell_row['timestamp'].strftime('%Y-%m-%d')} a ${first_sell_row['close']:,.2f}")
    
    # Verifica che ci siano almeno alcuni segnali
    assert len(buy_indices) > 0 or len(sell_indices) > 0, "La strategia non ha generato nessun segnale"
