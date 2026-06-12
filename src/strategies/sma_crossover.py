"""
SMA Crossover Strategy
Strategia basata su incrocio SMA 25/30
"""
import numpy as np
import pandas as pd
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)


class SMACrossoverStrategy:
    """Strategia SMA Crossover"""
    
    def __init__(self, fast_period: int = 25, slow_period: int = 30):
        """
        Inizializza strategia
        
        Args:
            fast_period: Periodo SMA veloce (default 25)
            slow_period: Periodo SMA lento (default 30)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.prices: List[float] = []
        self.name = f"SMA_Crossover_{fast_period}_{slow_period}"
        
        logger.info(f"Strategia SMA inizializzata: Fast={fast_period}, Slow={slow_period}")
    
    def add_price(self, price: float):
        """
        Aggiungi prezzo al buffer
        
        Args:
            price: Prezzo attuale
        """
        self.prices.append(price)
        
        # Mantieni solo ultimi 100 prezzi per efficienza
        if len(self.prices) > 100:
            self.prices = self.prices[-100:]
    
    def calculate_sma(self, period: int) -> float:
        """
        Calcola Simple Moving Average
        
        Args:
            period: Periodo SMA
            
        Returns:
            Valore SMA
        """
        if len(self.prices) < period:
            return 0.0
        
        return np.mean(self.prices[-period:])
    
    def generate_signal(self) -> str:
        """
        Genera segnale di trading (per uso live)
        
        Returns:
            BUY, SELL, o HOLD
        """
        if len(self.prices) < self.slow_period:
            logger.debug(f"Buffer insufficiente: {len(self.prices)}/{self.slow_period}")
            return "HOLD"
        
        sma_fast = self.calculate_sma(self.fast_period)
        sma_slow = self.calculate_sma(self.slow_period)
        
        # Calcola SMA precedenti per rilevare incrocio
        prices_prev = self.prices[:-1]
        if len(prices_prev) < self.slow_period:
            return "HOLD"
        
        sma_fast_prev = np.mean(prices_prev[-self.fast_period:])
        sma_slow_prev = np.mean(prices_prev[-self.slow_period:])
        
        # Golden Cross: SMA veloce attraversa sopra SMA lenta
        if sma_fast_prev <= sma_slow_prev and sma_fast > sma_slow:
            logger.info(f"🟢 GOLDEN CROSS: SMA{self.fast_period}={sma_fast:.2f} > SMA{self.slow_period}={sma_slow:.2f}")
            return "BUY"
        
        # Death Cross: SMA veloce attraversa sotto SMA lenta
        elif sma_fast_prev >= sma_slow_prev and sma_fast < sma_slow:
            logger.info(f"🔴 DEATH CROSS: SMA{self.fast_period}={sma_fast:.2f} < SMA{self.slow_period}={sma_slow:.2f}")
            return "SELL"
        
        return "HOLD"
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Genera segnali per backtest su DataFrame
        
        Args:
            df: DataFrame con colonne 'close'
            
        Returns:
            DataFrame con colonne aggiuntive: sma_fast, sma_slow, signal, position
        """
        df = df.copy()
        
        # Calcola SMA
        df['sma_fast'] = df['close'].rolling(window=self.fast_period).mean()
        df['sma_slow'] = df['close'].rolling(window=self.slow_period).mean()
        
        # Genera segnali
        # 1 = BUY (Golden Cross), -1 = SELL (Death Cross), 0 = HOLD
        df['signal'] = 0
        
        for i in range(1, len(df)):
            if pd.isna(df['sma_fast'].iloc[i]) or pd.isna(df['sma_slow'].iloc[i]):
                continue
            
            sma_fast_prev = df['sma_fast'].iloc[i-1]
            sma_slow_prev = df['sma_slow'].iloc[i-1]
            sma_fast_curr = df['sma_fast'].iloc[i]
            sma_slow_curr = df['sma_slow'].iloc[i]
            
            # Golden Cross
            if sma_fast_prev <= sma_slow_prev and sma_fast_curr > sma_slow_curr:
                df.loc[df.index[i], 'signal'] = 1
            # Death Cross
            elif sma_fast_prev >= sma_slow_prev and sma_fast_curr < sma_slow_curr:
                df.loc[df.index[i], 'signal'] = -1
        
        # Aggiungi colonna position (1 se in posizione long, 0 se flat, -1 se short)
        # Per ora implementiamo solo long positions
        df['position'] = 0
        in_position = False
        
        for i in range(len(df)):
            if df['signal'].iloc[i] == 1:  # BUY signal
                in_position = True
            elif df['signal'].iloc[i] == -1:  # SELL signal
                in_position = False
            
            df.loc[df.index[i], 'position'] = 1 if in_position else 0
        
        return df
    
    def get_crossover_points(self, df: pd.DataFrame) -> Tuple[List[int], List[int]]:
        """
        Ottieni punti di incrocio per visualizzazione
        
        Args:
            df: DataFrame con segnali
            
        Returns:
            Tuple (buy_indices, sell_indices)
        """
        buy_indices = df[df['signal'] == 1].index.tolist()
        sell_indices = df[df['signal'] == -1].index.tolist()
        return buy_indices, sell_indices
    
    def get_indicators(self) -> dict:
        """
        Ottieni valori indicatori attuali
        
        Returns:
            Dict con SMA25, SMA30
        """
        return {
            "sma_fast": self.calculate_sma(self.fast_period),
            "sma_slow": self.calculate_sma(self.slow_period),
            "prices_count": len(self.prices)
        }
