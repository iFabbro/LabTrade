"""
Live Strategy Executor - FIXED VERSION
Esegue strategia in loop continuo con dati reali da Binance Testnet
"""
import time
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
            atr_sl_multiplier=2.0,
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
    
    def execute_strategy(self):
        """Esegui un ciclo della strategia"""
        # Scarica ultima candela
        latest_candle = self.fetch_latest_candle()
        
        if not latest_candle:
            logger.warning("⚠️  Impossibile scaricare ultima candela, skip ciclo")
            return
        
        # Aggiungi al buffer (evita duplicati)
        if not self.candle_buffer or latest_candle['timestamp'] > self.candle_buffer[-1]['timestamp']:
            self.candle_buffer.append(latest_candle)
            
            # Mantieni buffer alla dimensione massima
            if len(self.candle_buffer) > self.max_buffer_size:
                self.candle_buffer.pop(0)
        
        # Crea DataFrame
        df = self.create_dataframe()
        
        if len(df) < 30:
            logger.warning(f"⚠️  Dati insufficienti: {len(df)} candele (minimo 30)")
            return
        
        current_price = df.iloc[-1]['close']
        logger.info(f"📊 Prezzo corrente: ${current_price:.2f}")
        
        # Calcola indicatori
        df['sma_fast'] = ta.sma(df['close'], length=25)
        df['sma_slow'] = ta.sma(df['close'], length=30)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        # Rimuovi NaN
        df = df.dropna()
        
        if len(df) == 0:
            logger.warning("⚠️  DataFrame vuoto dopo rimozione NaN")
            return
        
        # Genera segnali
        df['signal'] = 0
        df.loc[df['sma_fast'] > df['sma_slow'], 'signal'] = 1
        df.loc[df['sma_fast'] < df['sma_slow'], 'signal'] = -1
        df['position'] = df['signal'].diff()
        
        # Ultimo segnale
        last_row = df.iloc[-1]
        signal_value = last_row['signal']
        position_change = last_row['position']
        
        sma_fast = last_row['sma_fast']
        sma_slow = last_row['sma_slow']
        atr = last_row['atr']
        
        logger.info(f"📈 SMA25: ${sma_fast:.2f}, SMA30: ${sma_slow:.2f}, ATR: ${atr:.2f}")
        
        # Controlla posizione aperta
        if self.position_open:
            self._check_position(current_price)
        else:
            # Genera segnale di ingresso
            if position_change == 2:  # Crossover rialzista
                logger.info("🟢 Segnale BUY rilevato!")
                self._open_position("LONG", current_price, atr)
            elif position_change == -2:  # Crossover ribassista
                logger.info("🔴 Segnale SELL rilevato!")
                self._open_position("SHORT", current_price, atr)
            else:
                logger.info("⚪ Nessun segnale di ingresso")
    
    def _open_position(self, side: str, price: float, atr: float):
        """Apri posizione"""
        balance = self.get_balance()
        
        # Calcola stop loss e take profit usando ATR
        if side == "LONG":
            self.stop_loss = price - (2.0 * atr)
            self.take_profit = price + (4.0 * atr)  # RR 1:2
        else:  # SHORT
            self.stop_loss = price + (2.0 * atr)
            self.take_profit = price - (4.0 * atr)
        
        # Calcola position size
        risk_amount = balance * 0.02  # 2% rischio
        stop_distance = abs(price - self.stop_loss)
        
        if stop_distance == 0:
            logger.error("❌ Stop distance zero, impossibile calcolare position size")
            return
        
        quantity = risk_amount / stop_distance
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Apertura posizione {side}: {quantity:.6f} {self.symbol} @ ${price:.2f}")
            logger.info(f"   SL: ${self.stop_loss:.2f}, TP: ${self.take_profit:.2f}")
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
            except Exception as e:
                logger.error(f"❌ Errore invio ordine: {e}")
                return
        
        # Aggiorna stato
        self.position_open = True
        self.position_side = side
        self.entry_price = price
        self.position_quantity = quantity
        
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
    
    def _check_position(self, current_price: float):
        """Controlla posizione aperta"""
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
    
    def _close_position(self, current_price: float, reason: str):
        """Chiudi posizione"""
        # Calcola PnL
        if self.position_side == "LONG":
            pnl = (current_price - self.entry_price) * self.position_quantity
        else:  # SHORT
            pnl = (self.entry_price - current_price) * self.position_quantity
        
        balance = self.get_balance()
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Chiusura posizione {self.position_side}: PnL=${pnl:.2f} ({reason})")
            order_result = {"orderId": "DRY_RUN", "status": "FILLED"}
        else:
            try:
                close_side = "SELL" if self.position_side == "LONG" else "BUY"
                order_result = self.client.close_position(self.symbol, close_side, self.position_quantity)
                logger.info(f"✓ Posizione chiusa: {order_result}")
            except Exception as e:
                logger.error(f"❌ Errore chiusura posizione: {e}")
        
        # Logga trade
        self.logger.log_trade(
            symbol=self.symbol,
            action=f"CLOSE_{self.position_side}",
            side="SELL" if self.position_side == "LONG" else "BUY",
            price=current_price,
            quantity=self.position_quantity,
            pnl=pnl,
            balance=balance + pnl,
            notes=f"{reason} triggered"
        )
        
        # Reset stato
        self.position_open = False
        self.position_side = None
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.position_quantity = 0.0
    
    def run(self):
        """Esegui loop principale"""
        logger.info(f"🚀 Avvio Live Executor per {self.hours} ore")
        
        self.start_time = datetime.utcnow()
        end_time = self.start_time + timedelta(hours=self.hours)
        
        # Inizializza buffer con dati storici
        self.initialize_buffer()
        
        # Intervallo tra cicli
        interval = 3600 if self.timeframe == "1h" else 14400 if self.timeframe == "4h" else 86400
        
        try:
            while datetime.utcnow() < end_time:
                self.execute_strategy()
                
                # Attendi prossimo ciclo
                logger.info(f"⏳ Attendo {interval}s per prossima candela...")
                time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("⚠️  Interruzione manuale rilevata")
            self._graceful_shutdown()
        
        finally:
            self._print_summary()
    
    def _graceful_shutdown(self):
        """Shutdown graceful - chiudi posizioni aperte"""
        if self.position_open:
            logger.info("🔄 Chiusura posizione aperta prima dello shutdown...")
            latest_candle = self.fetch_latest_candle()
            if latest_candle:
                self._close_position(latest_candle['close'], "MANUAL_SHUTDOWN")
    
    def _print_summary(self):
        """Stampa summary finale"""
        duration = datetime.utcnow() - self.start_time
        logger.info(f"✅ Esecuzione completata in {duration}")
        self.logger.print_summary()
