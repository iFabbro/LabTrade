import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.binance_client import binance_client

def test_download_btc_data():
    """Testa il download di dati storici di Bitcoin"""
    # Scarica solo 10 giorni di dati per velocità
    df = binance_client.get_historical_klines(
        symbol='BTCUSDT',
        interval='1d',
        start_str='1 Jan 2024',
        end_str='10 Jan 2024'
    )
    
    # Verifica che il DataFrame non sia vuoto
    assert not df.empty, "DataFrame è vuoto"
    
    # Verifica le colonne
    expected_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    assert list(df.columns) == expected_cols, f"Colonne errate: {df.columns}"
    
    # Verifica che i dati siano numerici
    assert df['close'].dtype == float, "Prezzo close non è float"
    assert df['volume'].dtype == float, "Volume non è float"
    
    # Verifica che ci siano dati
    assert len(df) > 0, "Nessun dato scaricato"
    
    print(f"\n✓ Scaricati {len(df)} giorni di dati BTC")
    print(f"✓ Primo prezzo: ${df['close'].iloc[0]:,.2f}")
    print(f"✓ Ultimo prezzo: ${df['close'].iloc[-1]:,.2f}")
