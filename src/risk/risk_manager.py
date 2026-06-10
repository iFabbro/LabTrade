import pandas as pd
import pandas_ta as ta

class RiskManager:
    def __init__(self, risk_per_trade: float = 0.02, atr_period: int = 14, atr_sl_multiplier: float = 2.0, rr_ratio: float = 2.0):
        """
        Args:
            risk_per_trade: Percentuale del capitale da rischiare per trade (es. 0.02 = 2%)
            atr_period: Periodo per il calcolo dell'ATR
            atr_sl_multiplier: Moltiplicatore dell'ATR per lo Stop Loss (es. 2.0)
            rr_ratio: Risk/Reward ratio per il Take Profit (es. 2.0 per 1:2)
        """
        self.risk_per_trade = risk_per_trade
        self.atr_period = atr_period
        self.atr_sl_multiplier = atr_sl_multiplier
        self.rr_ratio = rr_ratio

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcola l'ATR e lo shifta di 1 periodo per evitare lookahead bias.
        Assume che il DataFrame abbia colonne 'high', 'low', 'close'.
        """
        df = df.copy()
        df['atr'] = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=self.atr_period)
        # Shift di 1: usiamo l'ATR calcolato alla chiusura del giorno precedente
        # per decidere il rischio all'apertura del giorno corrente.
        df['atr'] = df['atr'].shift(1)
        return df

    def calculate_position_size(self, capital: float, entry_price: float, atr: float) -> float:
        """
        Calcola la quantità di asset da acquistare (Fixed Fractional).
        """
        if pd.isna(atr) or atr <= 0:
            return 0.0
        
        risk_amount = capital * self.risk_per_trade
        risk_per_share = self.atr_sl_multiplier * atr
        
        if risk_per_share <= 0:
            return 0.0
            
        quantity = risk_amount / risk_per_share
        return quantity

    def get_stop_loss(self, entry_price: float, atr: float) -> float:
        """Calcola il prezzo di Stop Loss."""
        return entry_price - (self.atr_sl_multiplier * atr)

    def get_take_profit(self, entry_price: float, atr: float) -> float:
        """Calcola il prezzo di Take Profit basato sul Risk/Reward ratio."""
        risk = self.atr_sl_multiplier * atr
        return entry_price + (self.rr_ratio * risk)
