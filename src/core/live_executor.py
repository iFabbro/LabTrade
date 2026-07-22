import requests
"""
Live Strategy Executor - FIXED VERSION
Esegue strategia in loop continuo con dati reali da Binance Testnet
"""
import time
import json
import logging
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

from src.utils.binance_testnet import BinanceTestnetClient
from src.utils.trade_logger import TradeLogger
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.risk.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class LiveExecutor:
    """Esecutore live strategia con dati reali"""
    
    def __init__(self, symbol: str = "BTCUSDT", timeframe: str = "1h", 
                 hours: int = 24, dry_run: bool = True):
        """
        Inizializza esecutore live
        
        Args:
            symbol: Simbolo trading
            timeframe: Timeframe candele (1h, 4h, 1d)
            hours: Ore di esecuzione
            dry_run: Se True, non invia ordini reali
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.hours = hours
        self.dry_run = dry_run
        
        # Inizializza componenti
        self.client = BinanceTestnetClient()
        self.logger = TradeLogger()
        self.strategy = SMACrossoverStrategy(fast_period=25, slow_period=30)
        self.risk_manager = RiskManager(
            risk_per_trade=0.02,
            atr_period=14,
            atr_sl_multiplier=1.5,
            rr_ratio=2.0
        )
        
        # Buffer candele storiche (ultime 50 per calcolare SMA 30)
        self.candle_buffer: List[Dict] = []
        self.max_buffer_size = 50
        
        # Stato posizione
        self.position_open = False
        self.position_side = None
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.position_quantity = 0.0
        
        # Timing
        self.start_time = None
        self.last_candle_time = None

        # State persistence
        self.state_file = Path("state/position_state.json")
        self.state_file.parent.mkdir(exist_ok=True)
        self.load_state()
        
        logger.info(f"Live Executor inizializzato: {symbol} {timeframe}, {hours}h, Dry-run={dry_run}")
    
    def get_balance(self) -> float:
        """Ottieni saldo account"""
        if self.dry_run:
            return 10000.0  # Saldo simulato
        
        try:
            balances = self.client.get_account_balance()
            return balances.get("USDT", 0.0)
        except Exception as e:
            logger.error(f"Errore recupero saldo: {e}")
            return 10000.0
    
    def fetch_historical_candles(self, limit: int = 50) -> List[Dict]:
        """
        Scarica candele storiche da Binance Testnet
        
        Args:
            limit: Numero di candele da scaricare
        
        Returns:
            Lista di dict con OHLCV
        """
        try:
            logger.info(f"📥 Download {limit} candele storiche...")
            klines = self.client.get_historical_klines(
                symbol=self.symbol,
                interval=self.timeframe,
                limit=limit
            )
            
            candles = []
            for k in klines:
                candles.append({
                    'timestamp': datetime.fromtimestamp(k[0] / 1000),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                })
            
            logger.info(f"✓ Scaricate {len(candles)} candele")
            return candles
            
        except Exception as e:
            logger.error(f"❌ Errore download candele: {e}")
            return []
    
    def fetch_latest_candle(self) -> Optional[Dict]:
        """
        Scarica ultima candela chiusa
        
        Returns:
            Dict con OHLCV o None
        """
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=self.timeframe,
                limit=1
            )
            
            if not klines:
                return None
            
            k = klines[0]
            return {
                'timestamp': datetime.fromtimestamp(k[0] / 1000),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            }
            
        except Exception as e:
            logger.error(f"❌ Errore download ultima candela: {e}")
            return None
    
    def initialize_buffer(self):
        """Inizializza buffer con candele storiche"""
        logger.info("🔄 Inizializzazione buffer candele...")
        self.candle_buffer = self.fetch_historical_candles(limit=self.max_buffer_size)
        
        if len(self.candle_buffer) < 30:
            logger.warning(f"⚠️  Buffer insufficiente: {len(self.candle_buffer)} candele (minimo 30)")
        else:
            logger.info(f"✓ Buffer inizializzato con {len(self.candle_buffer)} candele")
    
    def create_dataframe(self) -> pd.DataFrame:
        """Crea DataFrame dal buffer candele"""
        if not self.candle_buffer:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.candle_buffer)
        df = df.sort_values('timestamp').reset_index(drop=True)
        return df
    

    def _check_position_only(self, current_price: float):
        """
        Controllo veloce posizione aperta (ogni 60 secondi).
        Controlla solo SL/TP/ladder senza calcolare indicatori.
        """
        if not self.position_open:
            return
        
        # Controlla prima il ladder TP
        ladder_closed = self._check_ladder_take_profits(current_price)
        if ladder_closed:
            return
        
        # Poi controlla SL e TP finale
        if self.position_side == "LONG":
            if current_price <= self.stop_loss:
                logger.info(f"🔴 STOP LOSS toccato! Prezzo: ${current_price:.2f} <= SL: ${self.stop_loss:.2f}")
                self._close_position(current_price, "STOP_LOSS")
            elif current_price >= self.take_profit:
                logger.info(f"🟢 TAKE PROFIT toccato! Prezzo: ${current_price:.2f} >= TP: ${self.take_profit:.2f}")
                self._close_position(current_price, "TAKE_PROFIT")
        else:  # SHORT
            if current_price >= self.stop_loss:
                logger.info(f"🔴 STOP LOSS toccato! Prezzo: ${current_price:.2f} >= SL: ${self.stop_loss:.2f}")
                self._close_position(current_price, "STOP_LOSS")
            elif current_price <= self.take_profit:
                logger.info(f"🟢 TAKE PROFIT toccato! Prezzo: ${current_price:.2f} <= TP: ${self.take_profit:.2f}")
                self._close_position(current_price, "TAKE_PROFIT")

    def execute_strategy(self):
        """Esegui un ciclo della strategia con Filtri Soft (Punteggio)"""
        latest_candle = self.fetch_latest_candle()
        if not latest_candle:
            logger.warning("⚠️  Impossibile scaricare ultima candela, skip ciclo")
            return
        
        if not self.candle_buffer or latest_candle['timestamp'] > self.candle_buffer[-1]['timestamp']:
            self.candle_buffer.append(latest_candle)
            if len(self.candle_buffer) > self.max_buffer_size:
                self.candle_buffer.pop(0)
        
        df = self.create_dataframe()
        if len(df) < 30:
            logger.warning(f"⚠️  Dati insufficienti: {len(df)} candele (minimo 30)")
            return
        
        current_price = df.iloc[-1]['close']
        current_volume = df.iloc[-2].get('volume', 0) if len(df) >= 2 else df.iloc[-1].get('volume', 0)
        logger.info(f"📊 Prezzo corrente: ${current_price:.2f}")
        
        df['sma_fast'] = ta.sma(df['close'], length=25)
        df['sma_slow'] = ta.sma(df['close'], length=30)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['adx'] = ta.adx(df['high'], df['low'], df['close'], length=14).iloc[:, 0]
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        
        df = df.dropna()
        if len(df) == 0:
            logger.warning("⚠️  DataFrame vuoto dopo rimozione NaN")
            return
        
        df['signal'] = 0
        df.loc[df['sma_fast'] > df['sma_slow'], 'signal'] = 1
        df.loc[df['sma_fast'] < df['sma_slow'], 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        last_row = df.iloc[-1]
        signal_value = last_row['signal']
        
        sma_fast = last_row['sma_fast']
        sma_slow = last_row['sma_slow']
        atr = last_row['atr']
        adx = last_row['adx']
        volume_sma = last_row['volume_sma']
        
        logger.info(f"📈 SMA25: ${sma_fast:.2f}, SMA30: ${sma_slow:.2f}, ATR: ${atr:.2f}, ADX: {adx:.1f}")
        
        adx_confirmed = adx >= 25
        volume_confirmed = current_volume > (volume_sma * 1.2)
        higher_tf_trend = "NEUTRAL"  # MTF disabilitato temporaneamente per problemi API
        mtf_aligned = (higher_tf_trend == "UP" if signal_value == 1 else 
                       higher_tf_trend == "DOWN" if signal_value == -1 else True)
        
        if self.position_open:
            self._check_position(current_price)
            if self.position_side == "LONG" and signal_value == -1:
                logger.info("🔴 Chiusura LONG per inversione trend!")
                self._close_position(current_price, "TREND_REVERSAL")
            elif self.position_side == "SHORT" and signal_value == 1:
                logger.info("🟢 Chiusura SHORT per inversione trend!")
                self._close_position(current_price, "TREND_REVERSAL")
        else:
            if signal_value == 1 and not self.position_open:
                close_prices = [c['close'] for c in self.candle_buffer]
                rsi = self.strategy.calculate_rsi(close_prices, period=14)
                logger.info(f"📊 RSI: {rsi:.1f}, ADX: {adx:.1f}, Vol: {current_volume:.0f}/{volume_sma:.0f}, 4H: {higher_tf_trend}")
                
                score = 0
                checks = []
                if rsi < 70:
                    score += 1; checks.append(f"✓ RSI {rsi:.1f} < 70")
                else:
                    checks.append(f"✗ RSI {rsi:.1f} >= 70")
                
                if adx_confirmed:
                    score += 1; checks.append(f"✓ ADX {adx:.1f} >= 25")
                else:
                    checks.append(f"✗ ADX {adx:.1f} < 25")
                
                if volume_confirmed:
                    score += 1; checks.append(f"✓ Volume {current_volume:.0f} > {volume_sma*1.2:.0f}")
                else:
                    checks.append(f"✗ Volume {current_volume:.0f} < {volume_sma*1.2:.0f}")
                
                if mtf_aligned:
                    score += 1; checks.append(f"✓ Trend 4h: {higher_tf_trend}")
                else:
                    checks.append(f"✗ Trend 4h: {higher_tf_trend} (contrario)")
                
                if score >= 3:
                    logger.info(f"🟢 BUY CONFERMATO (punteggio: {score}/4)!")
                    for check in checks: logger.info(f"   {check}")
                    self._open_position("LONG", current_price, atr)
                else:
                    logger.info(f"⚠️ BUY rifiutato (punteggio: {score}/4). Servono almeno 3/4 filtri.")
                    for check in checks: logger.info(f"   {check}")
                    
            elif signal_value == -1 and not self.position_open:
                close_prices = [c['close'] for c in self.candle_buffer]
                rsi = self.strategy.calculate_rsi(close_prices, period=14)
                logger.info(f"📊 RSI: {rsi:.1f}, ADX: {adx:.1f}, Vol: {current_volume:.0f}/{volume_sma:.0f}, 4H: {higher_tf_trend}")
                
                score = 0
                checks = []
                if rsi > 30:
                    score += 1; checks.append(f"✓ RSI {rsi:.1f} > 30")
                else:
                    checks.append(f"✗ RSI {rsi:.1f} <= 30")
                
                if adx_confirmed:
                    score += 1; checks.append(f"✓ ADX {adx:.1f} >= 25")
                else:
                    checks.append(f"✗ ADX {adx:.1f} < 25")
                
                if volume_confirmed:
                    score += 1; checks.append(f"✓ Volume {current_volume:.0f} > {volume_sma*1.2:.0f}")
                else:
                    checks.append(f"✗ Volume {current_volume:.0f} < {volume_sma*1.2:.0f}")
                
                if mtf_aligned:
                    score += 1; checks.append(f"✓ Trend 4h: {higher_tf_trend}")
                else:
                    checks.append(f"✗ Trend 4h: {higher_tf_trend} (contrario)")
                
                if score >= 3:
                    logger.info(f"🔴 SELL CONFERMATO (punteggio: {score}/4)!")
                    for check in checks: logger.info(f"   {check}")
                    self._open_position("SHORT", current_price, atr)
                else:
                    logger.info(f"⚠️ SELL rifiutato (punteggio: {score}/4). Servono almeno 3/4 filtri.")
                    for check in checks: logger.info(f"   {check}")
            else:
                logger.info("⚪ Nessun segnale di ingresso")

    def _check_higher_timeframe_trend(self) -> str:
        """
        Controlla trend su timeframe superiore (4h) per conferma Multi-Timeframe
        
        Returns:
            "UP", "DOWN", o "NEUTRAL"
        """
        try:
            # Scarica candele 4h (50 candele = ~8 giorni)
            candles_4h = self.client.get_klines(self.symbol, "4h", limit=50)
            
            if not candles_4h or len(candles_4h) < 30:
                return "NEUTRAL"
            
            # Converti in DataFrame
            df_4h = pd.DataFrame(candles_4h, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            df_4h['close'] = df_4h['close'].astype(float)
            df_4h['sma_fast'] = df_4h['close'].rolling(window=25).mean()
            df_4h['sma_slow'] = df_4h['close'].rolling(window=30).mean()
            df_4h = df_4h.dropna()
            
            if len(df_4h) == 0:
                return "NEUTRAL"
            
            last_4h = df_4h.iloc[-1]
            
            if last_4h['sma_fast'] > last_4h['sma_slow']:
                return "UP"
            elif last_4h['sma_fast'] < last_4h['sma_slow']:
                return "DOWN"
            else:
                return "NEUTRAL"
        
        except Exception as e:
            logger.warning(f"⚠️ Errore controllo trend 4h: {e}")
            return "NEUTRAL"

    def save_state(self):
        """Salva stato posizione su JSON con scrittura atomica (previene corruzione su crash)."""
        state = {
            "position_open": self.position_open,
            "position_side": self.position_side,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_quantity": self.position_quantity,
            "tp1": getattr(self, 'tp1', self.take_profit),
            "tp2": getattr(self, 'tp2', self.take_profit),
            "tp3": getattr(self, 'tp3', self.take_profit),
            "tp1_hit": getattr(self, 'tp1_hit', False),
            "tp2_hit": getattr(self, 'tp2_hit', False),
            "tp3_hit": getattr(self, 'tp3_hit', False),
            "remaining_quantity": getattr(self, 'remaining_quantity', self.position_quantity)
        }
        # Scrittura atomica: scrive su file temporaneo, poi rinomina. 
        # Il rename è atomico a livello di OS: il file è integro o non esiste.
        import os
        temp_file = self.state_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(state, f)
        os.replace(temp_file, self.state_file)

    def load_state(self):
        """Carica stato posizione da JSON. Gestisce file corrotti per evitare crash all'avvio."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                self.position_open = state.get("position_open", False)
                self.position_side = state.get("position_side")
                self.entry_price = state.get("entry_price", 0.0)
                self.stop_loss = state.get("stop_loss", 0.0)
                self.take_profit = state.get("take_profit", 0.0)
                self.position_quantity = state.get("position_quantity", 0.0)
                self.tp1 = state.get("tp1", self.take_profit)
                self.tp2 = state.get("tp2", self.take_profit)
                self.tp3 = state.get("tp3", self.take_profit)
                self.tp1_hit = state.get("tp1_hit", False)
                self.tp2_hit = state.get("tp2_hit", False)
                self.tp3_hit = state.get("tp3_hit", False)
                self.remaining_quantity = state.get("remaining_quantity", self.position_quantity)
                
                if self.position_open:
                    logger.info(f"🔄 Stato posizione ripristinato: {self.position_side} @ {self.entry_price}")
                    logger.info(f"   Ladder TP: TP1=${self.tp1:.2f}, TP2=${self.tp2:.2f}, TP3=${self.tp3:.2f}")
                    
            except (json.JSONDecodeError, Exception) as e:
                logger.critical(f"🚨 ERRORE CRITICO: File di stato corrotto ({e}).")
                logger.critical("⚠️  Avvio in modalità sicura: nessuna posizione aperta. Controllo manuale richiesto.")
                # Reset allo stato di default per permettere al bot di avviarsi
                self.position_open = False
                self.position_side = None
                self.entry_price = 0.0
                self.stop_loss = 0.0
                self.take_profit = 0.0
                self.position_quantity = 0.0
                self.remaining_quantity = 0.0

    def _open_position(self, side: str, price: float, atr: float):
        """Apri posizione con Ladder TP automatico"""
        balance = self.get_balance()
        
        # Calcola stop loss e take profit usando ATR
        if side == "LONG":
            self.stop_loss = price - (self.risk_manager.atr_sl_multiplier * atr)
            self.take_profit = price + (4.0 * atr)  # RR 1:2
        else:  # SHORT
            self.stop_loss = price + (self.risk_manager.atr_sl_multiplier * atr)
            self.take_profit = price - (4.0 * atr)
        
        # Calcola i 3 TP scalati (TP3 = TP originale)
        ladder_tp = self.risk_manager.calculate_ladder_take_profits(price, atr, side, self.take_profit)
        self.tp1 = ladder_tp['tp1']
        self.tp2 = ladder_tp['tp2']
        self.tp3 = ladder_tp['tp3']
        
        # Resetta flag TP
        self.tp1_hit = False
        self.tp2_hit = False
        self.tp3_hit = False
        
        # Calcola position size
        risk_amount = balance * 0.02  # 2% rischio
        stop_distance = abs(price - self.stop_loss)
        
        import math
        if stop_distance == 0 or math.isnan(stop_distance) or math.isinf(stop_distance):
            logger.error(f"❌ Stop distance invalida ({stop_distance}), impossibile calcolare position size. Skip ciclo.")
            return
        
        quantity = risk_amount / stop_distance
        
        # 🛡️ FIX: Limita la Position Size (Leva Max 1x)
        # Evita di esporre più del balance totale quando la volatilità è bassa
        max_leverage = 1.0 
        max_quantity = (balance * max_leverage) / price
        
        if quantity > max_quantity:
            logger.warning(f"⚠️ Position size ridotta per limite leva: {quantity:.4f} -> {max_quantity:.4f} BTC")
            quantity = max_quantity
        
        # Arrotonda a 3 decimali (precisione richiesta da Binance per BTCUSDT)
        quantity = round(quantity, 3)
        
        # Verifica quantità minima (0.001 BTC per Binance Futures)
        if quantity < 0.001:
            logger.warning(f"⚠️  Quantità troppo piccola: {quantity:.6f} BTC (minimo 0.001)")
            return
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Apertura posizione {side}: {quantity:.6f} {self.symbol} @ ${price:.2f}")
            logger.info(f"   SL: ${self.stop_loss:.2f}, TP: ${self.take_profit:.2f}")
            logger.info(f"   Ladder TP: TP1=${self.tp1:.2f}, TP2=${self.tp2:.2f}, TP3=${self.tp3:.2f}")
            order_result = {"orderId": "DRY_RUN", "status": "FILLED"}
        else:
            try:
                order_result = self.client.place_order(
                    self.symbol, 
                    "BUY" if side == "LONG" else "SELL", 
                    "MARKET", 
                    quantity
                )
                logger.info(f"✓ Ordine inviato: {order_result}")
                logger.info(f"   Ladder TP: TP1=${self.tp1:.2f}, TP2=${self.tp2:.2f}, TP3=${self.tp3:.2f}")
            except Exception as e:
                logger.error(f"❌ Errore invio ordine: {e}")
                return
        
        # Aggiorna stato
        self.position_open = True
        self.position_side = side
        self.entry_price = price
        self.position_quantity = quantity
        self.remaining_quantity = quantity
        
        # Salva stato su disco (include tp1, tp2, tp3 e flags)
        self.save_state()

        # Logga trade
        self.logger.log_trade(
            symbol=self.symbol,
            action=f"OPEN_{side}",
            side="BUY" if side == "LONG" else "SELL",
            price=price,
            quantity=quantity,
            balance=balance,
            notes=f"SL=${self.stop_loss:.2f}, TP=${self.take_profit:.2f}"
        )
    
    def _check_ladder_take_profits(self, current_price: float) -> bool:
        """
        Controlla e gestisce i 3 Take Profit scalati.
        Regola: dopo ogni TP, sposta SL al TP raggiunto.
        Ritorna True se la posizione è stata completamente chiusa.
        """
        if not self.position_open:
            return False
        
        side = self.position_side
        entry = self.entry_price
        
        # TP1: Chiude 33% e sposta SL a Break Even
        if not self.tp1_hit:
            if side == "LONG" and current_price >= self.tp1:
                self.tp1_hit = True
                close_qty = self.position_quantity * 0.33
                pnl = (current_price - entry) * close_qty
                
                logger.info(f"🎯 TP1 RAGGIUNTO! Chiudo 33% ({close_qty:.3f} BTC) con PnL: ${pnl:.2f}")
                self.logger.log_trade(
                    symbol=self.symbol, action="CLOSE_LONG", side="SELL",
                    price=current_price, quantity=close_qty, pnl=pnl,
                    balance=self.get_balance() + pnl, notes="TP1 triggered (33% closed)"
                )
                
                self.remaining_quantity -= close_qty
                self.stop_loss = entry  # SL a Break Even
                self.save_state()
                logger.info(f"   SL spostato a Break Even: ${self.stop_loss:.2f}")
                return False
                
            elif side == "SHORT" and current_price <= self.tp1:
                self.tp1_hit = True
                close_qty = self.position_quantity * 0.33
                pnl = (entry - current_price) * close_qty
                
                logger.info(f"🎯 TP1 RAGGIUNTO! Chiudo 33% ({close_qty:.3f} BTC) con PnL: ${pnl:.2f}")
                self.logger.log_trade(
                    symbol=self.symbol, action="CLOSE_SHORT", side="BUY",
                    price=current_price, quantity=close_qty, pnl=pnl,
                    balance=self.get_balance() + pnl, notes="TP1 triggered (33% closed)"
                )
                
                self.remaining_quantity -= close_qty
                self.stop_loss = entry
                self.save_state()
                logger.info(f"   SL spostato a Break Even: ${self.stop_loss:.2f}")
                return False
        
        # TP2: Chiude 33% e sposta SL a TP1
        if self.tp1_hit and not self.tp2_hit:
            if side == "LONG" and current_price >= self.tp2:
                self.tp2_hit = True
                close_qty = self.position_quantity * 0.33
                pnl = (current_price - entry) * close_qty
                
                logger.info(f"🎯 TP2 RAGGIUNTO! Chiudo 33% ({close_qty:.3f} BTC) con PnL: ${pnl:.2f}")
                self.logger.log_trade(
                    symbol=self.symbol, action="CLOSE_LONG", side="SELL",
                    price=current_price, quantity=close_qty, pnl=pnl,
                    balance=self.get_balance() + pnl, notes="TP2 triggered (33% closed)"
                )
                
                self.remaining_quantity -= close_qty
                self.stop_loss = self.tp2  # SL a TP2
                self.save_state()
                logger.info(f"   SL spostato a TP2: ${self.stop_loss:.2f}")
                return False
                
            elif side == "SHORT" and current_price <= self.tp2:
                self.tp2_hit = True
                close_qty = self.position_quantity * 0.33
                pnl = (entry - current_price) * close_qty
                
                logger.info(f"🎯 TP2 RAGGIUNTO! Chiudo 33% ({close_qty:.3f} BTC) con PnL: ${pnl:.2f}")
                self.logger.log_trade(
                    symbol=self.symbol, action="CLOSE_SHORT", side="BUY",
                    price=current_price, quantity=close_qty, pnl=pnl,
                    balance=self.get_balance() + pnl, notes="TP2 triggered (33% closed)"
                )
                
                self.remaining_quantity -= close_qty
                self.stop_loss = self.tp2  # SL a TP2
                self.save_state()
                logger.info(f"   SL spostato a TP2: ${self.stop_loss:.2f}")
                return False
        
        # TP3: Chiude il rimanente 34%
        if self.tp2_hit and not self.tp3_hit:
            if side == "LONG" and current_price >= self.tp3:
                self.tp3_hit = True
                close_qty = self.remaining_quantity
                pnl = (current_price - entry) * close_qty
                
                logger.info(f"🎯 TP3 RAGGIUNTO! Chiudo restante 34% ({close_qty:.3f} BTC) con PnL: ${pnl:.2f}")
                self.logger.log_trade(
                    symbol=self.symbol, action="CLOSE_LONG", side="SELL",
                    price=current_price, quantity=close_qty, pnl=pnl,
                    balance=self.get_balance() + pnl, notes="TP3 triggered (34% closed - POSITION CLOSED)"
                )
                
                self._close_position(current_price, "TP3 triggered")
                return True
                
            elif side == "SHORT" and current_price <= self.tp3:
                self.tp3_hit = True
                close_qty = self.remaining_quantity
                pnl = (entry - current_price) * close_qty
                
                logger.info(f"🎯 TP3 RAGGIUNTO! Chiudo restante 34% ({close_qty:.3f} BTC) con PnL: ${pnl:.2f}")
                self.logger.log_trade(
                    symbol=self.symbol, action="CLOSE_SHORT", side="BUY",
                    price=current_price, quantity=close_qty, pnl=pnl,
                    balance=self.get_balance() + pnl, notes="TP3 triggered (34% closed - POSITION CLOSED)"
                )
                
                self._close_position(current_price, "TP3 triggered")
                return True
        
        return False

    def _check_position(self, current_price: float):
        """Controlla posizione aperta con Ladder TP"""
        # Prima controlla i TP scalati
        ladder_closed = self._check_ladder_take_profits(current_price)
        if ladder_closed:
            return  # Posizione già chiusa dal ladder
        
        # Poi controlla SL e TP finale
        if self.position_side == "LONG":
            if current_price <= self.stop_loss:
                self._close_position(current_price, "STOP_LOSS")
            elif current_price >= self.take_profit:
                self._close_position(current_price, "TAKE_PROFIT")
        else:  # SHORT
            if current_price >= self.stop_loss:
                self._close_position(current_price, "STOP_LOSS")
            elif current_price <= self.take_profit:
                self._close_position(current_price, "TAKE_PROFIT")
    
    def _close_position(self, current_price: float, reason: str, quantity_to_close: float = None):
        """Chiudi posizione (parziale o totale)"""
        # Determina quantità da chiudere
        if quantity_to_close is None:
            quantity_to_close = self.remaining_quantity
        
        # Verifica che ci sia quantità rimanente
        if quantity_to_close <= 0:
            logger.warning(f"⚠️  Nessuna quantità rimanente da chiudere")
            return
        
        # Calcola PnL sulla quantità chiusa
        if self.position_side == "LONG":
            pnl = (current_price - self.entry_price) * quantity_to_close
        else:  # SHORT
            pnl = (self.entry_price - current_price) * quantity_to_close
        
        balance = self.get_balance()
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Chiusura {quantity_to_close:.5f} BTC {self.position_side}: PnL=${pnl:.2f} ({reason})")
            order_result = {"orderId": "DRY_RUN", "status": "FILLED"}
        else:
            try:
                close_side = "SELL" if self.position_side == "LONG" else "BUY"
                order_result = self.client.close_position(self.symbol, close_side, quantity_to_close)
                logger.info(f"✓ Posizione chiusa: {order_result}")
            except Exception as e:
                logger.error(f"❌ Errore chiusura posizione: {e}")
        
        # Salva stato su disco
        self.save_state()

        # Logga trade con quantità reale
        close_qty = self.remaining_quantity if self.remaining_quantity > 0 else self.position_quantity
        self.logger.log_trade(
            symbol=self.symbol,
            action=f"CLOSE_{self.position_side}",
            side="SELL" if self.position_side == "LONG" else "BUY",
            price=current_price,
            quantity=close_qty,
            pnl=pnl,
            balance=balance + pnl,
            notes=f"{reason} triggered"
        )
        
        # Reset stato
        self.position_open = False
        self.save_state()
        self.position_side = None
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.position_quantity = 0.0
    
    def run(self):
        """Esegui loop principale con controllo veloce ogni 60s"""
        logger.info(f"🚀 Avvio Live Executor per {self.hours} ore")
        
        self.start_time = datetime.utcnow()
        end_time = self.start_time + timedelta(hours=self.hours)
        
        # Inizializza buffer con dati storici
        self.initialize_buffer()
        
        # Intervalli
        strategy_interval = 3600 if self.timeframe == "1h" else 14400 if self.timeframe == "4h" else 86400
        fast_check_interval = 30  # Controllo veloce ogni 30 secondi
        
        last_strategy_time = 0
        last_fast_check_time = 0
        
        try:
            while datetime.utcnow() < end_time:
                now = time.time()
                
                # Controllo veloce ogni 60 secondi (solo se posizione aperta)
                if self.position_open and (now - last_fast_check_time) >= fast_check_interval:
                    try:
                        # Ottieni prezzo corrente da Binance con retry
                        current_price = None
                        for attempt in range(3):
                            try:
                                response = requests.get(
                                    "https://testnet.binancefuture.com/fapi/v1/ticker/price",
                                    params={"symbol": self.symbol},
                                    timeout=5  # Aumentato da 2 a 5 secondi
                                )
                                if response.status_code == 200:
                                    current_price = float(response.json()["price"])
                                    break
                            except Exception:
                                if attempt < 2:
                                    time.sleep(1)  # Attendi 1 secondo prima del retry
                                continue
                        
                        if current_price:
                            self._check_position_only(current_price)
                        else:
                            logger.debug("⚠️  Controllo veloce: impossibile ottenere prezzo dopo 3 tentativi")
                    except Exception as e:
                        logger.debug(f"⚠️  Errore controllo veloce: {e}")
                    
                    last_fast_check_time = now
                
                # Strategia completa ogni intervallo (1h, 4h, 1d)
                if (now - last_strategy_time) >= strategy_interval:
                    self.execute_strategy()
                    last_strategy_time = now
                    
                    # Attendi prossimo ciclo strategia
                    logger.info(f"⏳ Attendo {strategy_interval}s per prossima candela...")
                
                # Dormi 1 secondo per non sovraccaricare la CPU
                time.sleep(1)
        
        except KeyboardInterrupt:
            logger.info("⚠️  Interruzione manuale rilevata")
            self._graceful_shutdown()
        
        finally:
            self._print_summary()
    
    def _graceful_shutdown(self):
        """Shutdown graceful - SALVA posizioni aperte, NON chiuderle"""
        if self.position_open:
            logger.info("💾 Salvataggio stato posizioni (NON chiudo posizioni aperte)...")
            logger.info(f"✓ Posizione {self.position_side} salvata. Al riavvio continuerà ad essere monitorata.")
            self.save_state()
        else:
            logger.info("✓ Nessuna posizione aperta da salvare.")
    
    def _print_summary(self):
        """Stampa summary finale"""
        duration = datetime.utcnow() - self.start_time
        logger.info(f"✅ Esecuzione completata in {duration}")
        self.logger.print_summary()
