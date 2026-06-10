import pandas as pd
import pandas_ta as ta

class SMACrossoverStrategy:
    """
    Strategia basata sul crossover di Medie Mobili Semplici (SMA).
    
    Regole:
    - BUY: Quando SMA veloce incrocia al rialzo SMA lenta
    - SELL: Quando SMA veloce incrocia al ribasso SMA lenta
    """
    
    def __init__(self, fast_period=20, slow_period=50):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.name = f"SMA_Crossover_{fast_period}_{slow_period}"
    
    def generate_signals(self, df):
        """
        Genera segnali di trading basati sul crossover SMA.
        
        Args:
            df: DataFrame con colonne ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
        Returns:
            DataFrame con colonna aggiuntiva 'signal' (1=BUY, -1=SELL, 0=HOLD)
        """
        # Crea una copia per non modificare l'originale
        df_signals = df.copy()
        
        # Calcola le SMA usando pandas_ta
        df_signals['sma_fast'] = ta.sma(df_signals['close'], length=self.fast_period)
        df_signals['sma_slow'] = ta.sma(df_signals['close'], length=self.slow_period)
        
        # Rimuovi i NaN iniziali (dove le SMA non sono ancora calcolate)
        df_signals = df_signals.dropna()
        
        # Genera segnali
        # 1 = BUY (SMA veloce > SMA lenta)
        # -1 = SELL (SMA veloce < SMA lenta)
        # 0 = HOLD (nessun cambiamento)
        df_signals['signal'] = 0
        df_signals.loc[df_signals['sma_fast'] > df_signals['sma_slow'], 'signal'] = 1
        df_signals.loc[df_signals['sma_fast'] < df_signals['sma_slow'], 'signal'] = -1
        
        # Identifica i crossover (cambiamenti di segnale)
        df_signals['position'] = df_signals['signal'].diff()
        
        return df_signals
    
    def get_crossover_points(self, df_signals):
        """
        Estrae i punti esatti di crossover (entry/exit).
        
        Returns:
            Tuple di (buy_signals, sell_signals) come DataFrame
        """
        buy_signals = df_signals[df_signals['position'] == 2].copy()  # Da -1 a 1
        sell_signals = df_signals[df_signals['position'] == -2].copy()  # Da 1 a -1
        
        return buy_signals, sell_signals
