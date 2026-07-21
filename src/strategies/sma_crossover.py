"""
SMA Crossover Strategy - Triple Confirmation
Strategia basata su incrocio SMA 25/30 con filtri ADX, Volume e Multi-Timeframe
"""
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict
import logging

logger = logging.getLogger(__name__)


class SMACrossoverStrategy:
    """Strategia SMA Crossover con Triple Confirmation"""
    
    def __init__(self, fast_period: int = 25, slow_period: int = 30, 
                 adx_period: int = 14, adx_threshold: int = 25,
                 volume_multiplier: float = 1.5):
        """
        Inizializza strategia con filtri avanzati
        
        Args:
            fast_period: Periodo SMA veloce (default 25)
            slow_period: Periodo SMA lento (default 30)
            adx_period: Periodo ADX (default 14)
            adx_threshold: Soglia ADX per trend forte (default 25)
            volume_multiplier: Moltiplicatore volume medio (default 1.5)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.volume_multiplier = volume_multiplier
        self.prices: List[float] = []
        self.volumes: List[float] = []
        self.name = f"SMA_Crossover_{fast_period}_{slow_period}_TripleConf"
        
        logger.info(f"Strategia Triple Confirmation inizializzata:")
        logger.info(f"  SMA: Fast={fast_period}, Slow={slow_period}")
        logger.info(f"  ADX: Period={adx_period}, Threshold={adx_threshold}")
        logger.info(f"  Volume: Multiplier={volume_multiplier}x")
    
    def add_price(self, price: float, volume: float = None):
        """
        Aggiungi prezzo e volume al buffer
        
        Args:
            price: Prezzo attuale
            volume: Volume attuale (opzionale)
        """
        self.prices.append(price)
        
        if volume is not None:
            self.volumes.append(volume)
        
        # Mantieni solo ultimi 100 valori per efficienza
        if len(self.prices) > 100:
            self.prices = self.prices[-100:]
        
        if len(self.volumes) > 100:
            self.volumes = self.volumes[-100:]
    
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
    

    def calculate_adx(self, high: List[float], low: List[float], close: List[float], period: int = 14) -> float:
        """
        Calcola ADX (Average Directional Index) - misura forza del trend
        
        Args:
            high: Lista prezzi high
            low: Lista prezzi low
            close: Lista prezzi close
            period: Periodo ADX (default 14)
            
        Returns:
            Valore ADX (0-100), oppure 0.0 se dati insufficienti
        """
        if len(high) < period + 1:
            return 0.0
        
        # Calcola True Range, +DM, -DM
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []
        
        for i in range(1, len(high)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
            tr_list.append(tr)
            
            up_move = high[i] - high[i-1]
            down_move = low[i-1] - low[i]
            
            plus_dm = up_move if up_move > down_move and up_move > 0 else 0
            minus_dm = down_move if down_move > up_move and down_move > 0 else 0
            
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
        
        # Calcola smoothed averages (Wilder's smoothing)
        atr = sum(tr_list[:period]) / period
        plus_dm_smooth = sum(plus_dm_list[:period]) / period
        minus_dm_smooth = sum(minus_dm_list[:period]) / period
        
        # Applica smoothing per il resto
        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period
            plus_dm_smooth = (plus_dm_smooth * (period - 1) + plus_dm_list[i]) / period
            minus_dm_smooth = (minus_dm_smooth * (period - 1) + minus_dm_list[i]) / period
        
        # Calcola +DI, -DI, DX
        if atr == 0:
            return 0.0
        
        plus_di = (plus_dm_smooth / atr) * 100
        minus_di = (minus_dm_smooth / atr) * 100
        
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 0.0
        
        dx = (abs(plus_di - minus_di) / di_sum) * 100
        
        # ADX è la media di DX (semplificato: usiamo l'ultimo DX come approssimazione)
        # Per ADX completo servirebbe calcolare la media di più DX
        return dx
    
    def calculate_volume_average(self, period: int = 20) -> float:
        """
        Calcola media volume degli ultimi N periodi
        
        Args:
            period: Periodo media (default 20)
            
        Returns:
            Media volume, oppure 0.0 se dati insufficienti
        """
        if len(self.volumes) < period:
            return 0.0
        
        return np.mean(self.volumes[-period:])

    def generate_signal(self, high: List[float] = None, low: List[float] = None, 
                        current_volume: float = None, higher_tf_trend: str = None) -> str:
        """
        Genera segnale di trading con Triple Confirmation
        
        Args:
            high: Lista prezzi high (per ADX)
            low: Lista prezzi low (per ADX)
            current_volume: Volume attuale (per conferma volume)
            higher_tf_trend: Trend timeframe superiore ("UP", "DOWN", o None)
            
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
        
        # FIX: Calcola RSI correttamente
        rsi = self.calculate_rsi(self.prices, 14)
        
        # Calcola ADX se disponibili high/low
        adx = 0.0
        if high and low and len(high) >= self.adx_period + 1:
            adx = self.calculate_adx(high, low, self.prices, self.adx_period)
        
        # Verifica conferma volume
        volume_confirmed = True
        if current_volume is not None:
            avg_volume = self.calculate_volume_average(20)
            if avg_volume > 0:
                volume_confirmed = current_volume > (avg_volume * self.volume_multiplier)
        
        # Verifica conferma multi-timeframe
        mtf_confirmed = True
        if higher_tf_trend is not None:
            # Per BUY, trend superiore deve essere UP
            # Per SELL, trend superiore deve essere DOWN
            pass  # MTF check verrà fatto dopo
        
        # === FILTRI TRIPLE CONFIRMATION ===
        
        # Golden Cross: SMA veloce attraversa sopra SMA lenta
        if sma_fast_prev <= sma_slow_prev and sma_fast > sma_slow:
            # Filtro 1: RSI non ipercomprato
            if rsi >= 70:
                logger.info(f"⚠️ BUY rifiutato: RSI {rsi:.1f} >= 70 (ipercomprato)")
                return "HOLD"
            
            # Filtro 2: ADX conferma trend forte
            if adx > 0 and adx < self.adx_threshold:
                logger.info(f"⚠️ BUY rifiutato: ADX {adx:.1f} < {self.adx_threshold} (trend debole)")
                return "HOLD"
            
            # Filtro 3: Volume conferma movimento
            if not volume_confirmed:
                logger.info(f"⚠️ BUY rifiutato: Volume insufficiente")
                return "HOLD"
            
            # Filtro 4: Multi-Timeframe conferma trend
            if higher_tf_trend == "DOWN":
                logger.info(f"⚠️ BUY rifiutato: Trend superiore DOWN")
                return "HOLD"
            
            logger.info(f"🟢 BUY CONFERMATO (Triple Conf):")
            logger.info(f"   SMA Cross: {sma_fast_prev:.2f} → {sma_fast:.2f}")
            logger.info(f"   RSI: {rsi:.1f}, ADX: {adx:.1f}, Volume: {'✓' if volume_confirmed else '✗'}")
            return "BUY"
        
        # Death Cross: SMA veloce attraversa sotto SMA lenta
        elif sma_fast_prev >= sma_slow_prev and sma_fast < sma_slow:
            # Filtro 1: RSI non ipervenduto
            if rsi <= 30:
                logger.info(f"⚠️ SELL rifiutato: RSI {rsi:.1f} <= 30 (ipervenduto)")
                return "HOLD"
            
            # Filtro 2: ADX conferma trend forte
            if adx > 0 and adx < self.adx_threshold:
                logger.info(f"⚠️ SELL rifiutato: ADX {adx:.1f} < {self.adx_threshold} (trend debole)")
                return "HOLD"
            
            # Filtro 3: Volume conferma movimento
            if not volume_confirmed:
                logger.info(f"⚠️ SELL rifiutato: Volume insufficiente")
                return "HOLD"
            
            # Filtro 4: Multi-Timeframe conferma trend
            if higher_tf_trend == "UP":
                logger.info(f"⚠️ SELL rifiutato: Trend superiore UP")
                return "HOLD"
            
            logger.info(f"🔴 SELL CONFERMATO (Triple Conf):")
            logger.info(f"   SMA Cross: {sma_fast_prev:.2f} → {sma_fast:.2f}")
            logger.info(f"   RSI: {rsi:.1f}, ADX: {adx:.1f}, Volume: {'✓' if volume_confirmed else '✗'}")
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

    def calculate_rsi(self, prices: list, period: int = 14) -> float:
        """
        Calcola RSI (Relative Strength Index) usando EMA di Wilder (standard).
        
        Args:
            prices: Lista di prezzi (minimo period+1 elementi)
            period: Periodo per il calcolo (default: 14)
        
        Returns:
            Valore RSI tra 0 e 100, oppure 50.0 se dati insufficienti
        """
        if len(prices) < period + 1:
            return 50.0
        
        # ✅ FIX: Implementa RSI Wilder EMA
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Calcola prime medie (SMA iniziale)
        gains = [d if d > 0 else 0 for d in deltas[:period]]
        losses = [-d if d < 0 else 0 for d in deltas[:period]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        # Applica smoothing EMA per il resto
        for i in range(period, len(deltas)):
            gain = deltas[i] if deltas[i] > 0 else 0
            loss = -deltas[i] if deltas[i] < 0 else 0
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
        
        if avg_loss == 0:
            return 100.0
        
        return 100 - (100 / (1 + avg_gain / avg_loss))
