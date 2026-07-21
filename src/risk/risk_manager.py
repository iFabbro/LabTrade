"""
Risk Manager
Gestione rischio con Fixed Fractional e ATR
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """Gestore rischio"""
    
    def __init__(self, risk_per_trade: float = 0.02, atr_period: int = 14, 
                 atr_sl_multiplier: float = 1.5, rr_ratio: float = 2.0):
        """
        Inizializza risk manager
        
        Args:
            risk_per_trade: Rischio per trade (default 2%)
            atr_period: Periodo ATR (default 14)
            atr_sl_multiplier: Moltiplicatore ATR per Stop Loss (default 2.0)
            rr_ratio: Risk/Reward ratio (default 2.0)
        """
        self.risk_per_trade = risk_per_trade
        self.atr_period = atr_period
        self.atr_sl_multiplier = atr_sl_multiplier
        self.rr_ratio = rr_ratio
        
        self.high_prices: list = []
        self.low_prices: list = []
        self.close_prices: list = []
        
        logger.info(f"Risk Manager inizializzato: Risk={risk_per_trade*100}%, ATR={atr_period}, SL={atr_sl_multiplier}x, RR={rr_ratio}")
    
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara dati per backtest con risk management
        
        Args:
            df: DataFrame con OHLCV e signal
            
        Returns:
            DataFrame con colonne aggiuntive per risk management
        """
        df = df.copy()
        
        # Calcola ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=self.atr_period).mean()
        
        # Inizializza colonne per position tracking
        df['position'] = 0
        df['entry_price'] = np.nan
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan
        df['position_size'] = 0.0
        
        return df
    
    def add_candle(self, high: float, low: float, close: float):
        """
        Aggiungi candela per calcolo ATR
        
        Args:
            high: Prezzo massimo
            low: Prezzo minimo
            close: Prezzo chiusura
        """
        self.high_prices.append(high)
        self.low_prices.append(low)
        self.close_prices.append(close)
        
        # Mantieni solo ultimi 50 candele
        if len(self.high_prices) > 50:
            self.high_prices = self.high_prices[-50:]
            self.low_prices = self.low_prices[-50:]
            self.close_prices = self.close_prices[-50:]
    
    def calculate_atr(self) -> float:
        """
        Calcola Average True Range
        
        Returns:
            Valore ATR
        """
        if len(self.high_prices) < self.atr_period + 1:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(self.high_prices)):
            high = self.high_prices[i]
            low = self.low_prices[i]
            prev_close = self.close_prices[i-1]
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        # ATR = media degli ultimi 'atr_period' True Range
        return np.mean(true_ranges[-self.atr_period:])
    
    def calculate_position_size(self, balance: float, entry_price: float, stop_loss: float) -> float:
        """
        Calcola dimensione posizione con Fixed Fractional
        
        Args:
            balance: Saldo account
            entry_price: Prezzo entrata
            stop_loss: Prezzo stop loss
            
        Returns:
            Quantità da tradare
        """
        risk_amount = balance * self.risk_per_trade
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            logger.warning("Price risk è 0, posizione minima")
            return 0.001
        
        quantity = risk_amount / price_risk
        
        logger.info(f"Position size: {quantity:.4f} (Risk: ${risk_amount:.2f}, Price Risk: ${price_risk:.2f})")
        return quantity
    
    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """
        Calcola Stop Loss basato su ATR
        
        Args:
            entry_price: Prezzo entrata
            side: LONG o SHORT
            
        Returns:
            Prezzo Stop Loss
        """
        atr = self.calculate_atr()
        
        if atr == 0:
            logger.warning("ATR non disponibile, uso stop loss default 2%")
            atr = entry_price * 0.02
        
        sl_distance = atr * self.atr_sl_multiplier
        
        if side == "LONG":
            stop_loss = entry_price - sl_distance
        else:
            stop_loss = entry_price + sl_distance
        
        logger.info(f"Stop Loss calcolato: {stop_loss:.2f} (ATR: {atr:.2f}, Distance: {sl_distance:.2f})")
        return stop_loss
    
    def get_stop_loss(self, entry_price: float, atr: float) -> float:
        """
        Calcola Stop Loss basato su ATR (versione semplificata per backtest)
        
        Args:
            entry_price: Prezzo entrata
            atr: Valore ATR
            
        Returns:
            Prezzo Stop Loss
        """
        if atr == 0 or pd.isna(atr):
            logger.warning("ATR non disponibile, uso stop loss default 2%")
            atr = entry_price * 0.02
        
        sl_distance = atr * self.atr_sl_multiplier
        stop_loss = entry_price - sl_distance
        
        return stop_loss
    
    def get_take_profit(self, entry_price: float, stop_loss: float) -> float:
        """
        Calcola Take Profit basato su Risk/Reward ratio (versione semplificata per backtest)
        
        Args:
            entry_price: Prezzo entrata
            stop_loss: Prezzo stop loss
            
        Returns:
            Prezzo Take Profit
        """
        risk_distance = abs(entry_price - stop_loss)
        reward_distance = risk_distance * self.rr_ratio
        take_profit = entry_price + reward_distance
        
        return take_profit
    
    def calculate_take_profit(self, entry_price: float, stop_loss: float, side: str) -> float:
        """
        Calcola Take Profit basato su Risk/Reward ratio
        
        Args:
            entry_price: Prezzo entrata
            stop_loss: Prezzo stop loss
            side: LONG o SHORT
            
        Returns:
            Prezzo Take Profit
        """
        risk_distance = abs(entry_price - stop_loss)
        reward_distance = risk_distance * self.rr_ratio
        
        if side == "LONG":
            take_profit = entry_price + reward_distance
        else:
            take_profit = entry_price - reward_distance
        
        logger.info(f"Take Profit calcolato: {take_profit:.2f} (RR: {self.rr_ratio}, Distance: {reward_distance:.2f})")
        return take_profit
    

    def calculate_ladder_take_profits(self, entry_price: float, atr: float, side: str = "LONG", original_tp: float = None) -> dict:
        """
        Calcola 3 Take Profit scalati con R:R >= 2.0 garantito.
        
        Best practices per swing trading crypto:
        - TP1: 2× SL distance (R:R 1:2) - Chiude 33% posizione
        - TP2: 3× SL distance (R:R 1:3) - Chiude 33% posizione
        - TP3: 4× SL distance (R:R 1:4) - Chiude 34% posizione
        
        Args:
            entry_price: Prezzo di entry
            atr: ATR corrente
            side: LONG o SHORT
            original_tp: TP originale (non usato, calcolato automaticamente)
            
        Returns:
            Dizionario con tp1, tp2, tp3
        """
        # Validazione input
        if atr <= 0 or entry_price <= 0:
            logger.error(f"❌ Input invalidi: atr={atr}, entry_price={entry_price}")
            return {'tp1': entry_price, 'tp2': entry_price, 'tp3': entry_price}
        
        # Calcola SL distance e TP multipli
        sl_distance = atr * self.atr_sl_multiplier  # 1.5 × ATR
        
        if side == "LONG":
            tp1 = entry_price + (sl_distance * 2)  # 2× SL distance = 3× ATR
            tp2 = entry_price + (sl_distance * 3)  # 3× SL distance = 4.5× ATR
            tp3 = entry_price + (sl_distance * 4)  # 4× SL distance = 6× ATR
        else:  # SHORT
            tp1 = entry_price - (sl_distance * 2)
            tp2 = entry_price - (sl_distance * 3)
            tp3 = entry_price - (sl_distance * 4)
        
        # Calcola R:R complessivo
        risk_per_unit = sl_distance
        reward_tp1 = (tp1 - entry_price) * 0.33 if side == "LONG" else (entry_price - tp1) * 0.33
        reward_tp2 = (tp2 - entry_price) * 0.33 if side == "LONG" else (entry_price - tp2) * 0.33
        reward_tp3 = (tp3 - entry_price) * 0.34 if side == "LONG" else (entry_price - tp3) * 0.34
        total_reward = reward_tp1 + reward_tp2 + reward_tp3
        rr_ratio = total_reward / risk_per_unit if risk_per_unit > 0 else 0
        
        logger.info(f"Ladder TP calcolati: TP1={tp1:.2f}, TP2={tp2:.2f}, TP3={tp3:.2f} (R:R={rr_ratio:.2f})")
        
        return {
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'tp1_distance': sl_distance * 2,
            'tp2_distance': sl_distance * 3,
            'tp3_distance': sl_distance * 4,
            'rr_ratio': rr_ratio
        }

    def check_stop_loss_take_profit(self, position_side: str, entry_price: float, 
                                     stop_loss: float, take_profit: float, 
                                     current_price: float) -> Tuple[bool, str]:
        """
        Controlla se SL o TP sono stati toccati
        
        Args:
            position_side: LONG o SHORT
            entry_price: Prezzo entrata
            stop_loss: Prezzo stop loss
            take_profit: Prezzo take profit
            current_price: Prezzo attuale
            
        Returns:
            Tuple (triggered, reason): triggered=True se SL/TP toccato, reason="SL" o "TP"
        """
        if position_side == "LONG":
            if current_price <= stop_loss:
                return True, "SL"
            elif current_price >= take_profit:
                return True, "TP"
        else:  # SHORT
            if current_price >= stop_loss:
                return True, "SL"
            elif current_price <= take_profit:
                return True, "TP"
        
        return False, ""
    
    def calculate_pnl(self, entry_price: float, exit_price: float, quantity: float, side: str) -> float:
        """
        Calcola Profit/Loss
        
        Args:
            entry_price: Prezzo entrata
            exit_price: Prezzo uscita
            quantity: Quantità
            side: LONG o SHORT
            
        Returns:
            PnL
        """
        if side == "LONG":
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
        
        return pnl
