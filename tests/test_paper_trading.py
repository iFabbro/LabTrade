"""
Test Paper Trading Automation
Test completi per il sistema di paper trading
"""
import pytest
import pandas as pd
import os
from pathlib import Path
from datetime import datetime

from src.utils.binance_testnet import BinanceTestnetClient
from src.utils.trade_logger import TradeLogger
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.risk.risk_manager import RiskManager
from src.core.live_executor import LiveExecutor


def test_binance_testnet_client_init():
    """Test inizializzazione client Binance Testnet"""
    client = BinanceTestnetClient(api_key="test", api_secret="test")
    assert client.api_key == "test"
    assert client.api_secret == "test"
    assert client.BASE_URL == "https://testnet.binancefuture.com"


def test_trade_logger_creation():
    """Test creazione trade logger"""
    logger = TradeLogger(log_dir="logs/test")
    assert logger.log_dir.exists()
    assert logger.trades_file.exists()
    
    # Pulisci
    import shutil
    shutil.rmtree("logs/test")


def test_trade_logger_log_trade():
    """Test logging trade"""
    logger = TradeLogger(log_dir="logs/test")
    
    logger.log_trade(
        symbol="BTCUSDT",
        action="OPEN_LONG",
        side="BUY",
        price=50000.0,
        quantity=0.1,
        balance=10000.0,
        notes="Test trade"
    )
    
    assert len(logger.trades) == 1
    assert logger.trades[0]["symbol"] == "BTCUSDT"
    assert logger.trades[0]["action"] == "OPEN_LONG"
    
    # Pulisci
    import shutil
    shutil.rmtree("logs/test")


def test_trade_logger_statistics():
    """Test calcolo statistiche"""
    logger = TradeLogger(log_dir="logs/test")
    
    # Simula alcuni trade
    logger.log_trade("BTCUSDT", "OPEN_LONG", "BUY", 50000, 0.1, balance=10000)
    logger.log_trade("BTCUSDT", "CLOSE_LONG", "SELL", 51000, 0.1, pnl=100, balance=10100)
    logger.log_trade("BTCUSDT", "OPEN_SHORT", "SELL", 51000, 0.1, balance=10100)
    logger.log_trade("BTCUSDT", "CLOSE_SHORT", "BUY", 50500, 0.1, pnl=50, balance=10150)
    
    stats = logger.get_statistics()
    
    assert stats["total_trades"] == 2
    assert stats["winning_trades"] == 2
    assert stats["losing_trades"] == 0
    assert stats["win_rate"] == 100.0
    assert stats["total_pnl"] == 150
    
    # Pulisci
    import shutil
    shutil.rmtree("logs/test")


def test_sma_strategy_live():
    """Test strategia SMA per uso live"""
    strategy = SMACrossoverStrategy(fast_period=5, slow_period=10)
    
    # Aggiungi prezzi
    for i in range(15):
        strategy.add_price(100 + i)
    
    # Genera segnale
    signal = strategy.generate_signal()
    assert signal in ["BUY", "SELL", "HOLD"]
    
    # Test indicatori
    indicators = strategy.get_indicators()
    assert "sma_fast" in indicators
    assert "sma_slow" in indicators
    assert indicators["prices_count"] == 15


def test_sma_strategy_backtest():
    """Test strategia SMA per backtest"""
    strategy = SMACrossoverStrategy(fast_period=5, slow_period=10)
    
    # Crea DataFrame di test
    df = pd.DataFrame({
        "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]
    })
    
    # Genera segnali
    df_signals = strategy.generate_signals(df)
    
    assert "sma_fast" in df_signals.columns
    assert "sma_slow" in df_signals.columns
    assert "signal" in df_signals.columns
    assert len(df_signals) == len(df)


def test_risk_manager_init():
    """Test inizializzazione risk manager"""
    rm = RiskManager(
        risk_per_trade=0.02,
        atr_period=14,
        atr_sl_multiplier=2.0,
        rr_ratio=2.0
    )
    
    assert rm.risk_per_trade == 0.02
    assert rm.atr_period == 14
    assert rm.atr_sl_multiplier == 2.0
    assert rm.rr_ratio == 2.0


def test_risk_manager_prepare_data():
    """Test preparazione dati per backtest"""
    rm = RiskManager()
    
    df = pd.DataFrame({
        "high": [105, 106, 107, 108, 109],
        "low": [95, 96, 97, 98, 99],
        "close": [100, 101, 102, 103, 104],
        "signal": [0, 1, 0, -1, 0]
    })
    
    df_prepared = rm.prepare_data(df)
    
    assert "atr" in df_prepared.columns
    assert "position" in df_prepared.columns
    assert "entry_price" in df_prepared.columns
    assert "stop_loss" in df_prepared.columns
    assert "take_profit" in df_prepared.columns


def test_risk_manager_atr_calculation():
    """Test calcolo ATR"""
    rm = RiskManager(atr_period=3)
    
    # Aggiungi candele
    for i in range(10):
        rm.add_candle(high=100+i+5, low=100+i-5, close=100+i)
    
    atr = rm.calculate_atr()
    assert atr > 0


def test_risk_manager_position_size():
    """Test calcolo position size"""
    rm = RiskManager(risk_per_trade=0.02)
    
    quantity = rm.calculate_position_size(
        balance=10000,
        entry_price=100,
        stop_loss=95
    )
    
    # Risk = 10000 * 0.02 = 200
    # Price risk = 100 - 95 = 5
    # Quantity = 200 / 5 = 40
    assert quantity == 40.0


def test_risk_manager_stop_loss():
    """Test calcolo stop loss"""
    rm = RiskManager(atr_sl_multiplier=2.0)
    rm.add_candle(110, 90, 100)  # TR = 20
    
    sl_long = rm.calculate_stop_loss(100, "LONG")
    sl_short = rm.calculate_stop_loss(100, "SHORT")
    
    # ATR ≈ 20, SL distance = 20 * 2 = 40
    assert sl_long < 100
    assert sl_short > 100


def test_risk_manager_take_profit():
    """Test calcolo take profit"""
    rm = RiskManager(rr_ratio=2.0)
    
    tp_long = rm.calculate_take_profit(100, 90, "LONG")
    tp_short = rm.calculate_take_profit(100, 110, "SHORT")
    
    # Risk = 10, Reward = 10 * 2 = 20
    assert tp_long == 120
    assert tp_short == 80


def test_live_executor_init():
    """Test inizializzazione live executor"""
    executor = LiveExecutor(
        symbol="BTCUSDT",
        timeframe="1h",
        hours=1,
        dry_run=True
    )
    
    assert executor.symbol == "BTCUSDT"
    assert executor.timeframe == "1h"
    assert executor.hours == 1
    assert executor.dry_run is True
    assert executor.position_open is False


def test_live_executor_dry_run():
    """Test esecuzione dry-run"""
    executor = LiveExecutor(dry_run=True)
    
    # Test get_balance
    balance = executor.get_balance()
    assert balance == 10000.0
    
    # Test fetch_candle_data
    candle = executor.fetch_candle_data()
    assert "close" in candle
    assert "high" in candle
    assert "low" in candle


def test_integration_full_cycle():
    """Test integrazione ciclo completo"""
    # Crea componenti
    strategy = SMACrossoverStrategy(fast_period=5, slow_period=10)
    rm = RiskManager(risk_per_trade=0.02)
    logger = TradeLogger(log_dir="logs/test")
    
    # Simula ciclo
    for i in range(20):
        price = 100 + i
        strategy.add_price(price)
        rm.add_candle(price+5, price-5, price)
        
        signal = strategy.generate_signal()
        
        if signal == "BUY":
            logger.log_trade("BTCUSDT", "OPEN_LONG", "BUY", price, 0.1, balance=10000)
        elif signal == "SELL":
            logger.log_trade("BTCUSDT", "CLOSE_LONG", "SELL", price, 0.1, pnl=10, balance=10010)
    
    # Verifica statistiche
    stats = logger.get_statistics()
    assert stats["total_trades"] >= 0
    
    # Pulisci
    import shutil
    shutil.rmtree("logs/test")
