from binance.client import Client
import pandas as pd
from datetime import datetime

class BinanceDataClient:
    def __init__(self):
        # Client pubblico per dati storici (non servono API keys)
        self.client = Client()
    
    def get_historical_klines(self, symbol, interval, start_str, end_str=None):
        """
        Scarica dati storici OHLCV da Binance
        
        Args:
            symbol: Coppia di trading (es. 'BTCUSDT')
            interval: Timeframe (es. '1h', '4h', '1d')
            start_str: Data inizio (es. '1 Jan 2020')
            end_str: Data fine (opzionale)
        
        Returns:
            DataFrame pandas con colonne: timestamp, open, high, low, close, volume
        """
        klines = self.client.get_historical_klines(
            symbol, 
            interval, 
            start_str,
            end_str
        )
        
        # Converti in DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        # Converti timestamp in datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Converti colonne numeriche
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].astype(float)
        
        # Mantieni solo le colonne essenziali
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        return df

# Istanza globale
binance_client = BinanceDataClient()
