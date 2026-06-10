import pytest
from src.utils.binance_client import BinanceDataClient
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.risk.risk_manager import RiskManager
from src.core.walk_forward import WalkForwardValidator

def test_walk_forward_validation():
    # 1. Scaricamento Dati (Estesi al 2022 per avere più finestre)
    client = BinanceDataClient()
    data = client.get_historical_klines(
        symbol='BTCUSDT', 
        interval='1d', 
        start_str='1 Jan 2022', 
        end_str='10 Apr 2024'
    )
    
    # Imposta timestamp come indice
    data.set_index('timestamp', inplace=True)
    
    # 2. Inizializzazione Validator
    validator = WalkForwardValidator(data=data, n_windows=5, is_ratio=0.70)
    
    # 3. Parametri Strategia e Risk Manager
    strategy_params = {
        'fast_period': 25,
        'slow_period': 30
    }
    risk_manager_params = {
        'risk_per_trade': 0.02,
        'atr_period': 14,
        'atr_sl_multiplier': 2.0,
        'rr_ratio': 2.0
    }
    
    # 4. Esecuzione Walk-Forward
    results = validator.run(
        strategy_class=SMACrossoverStrategy,
        strategy_params=strategy_params,
        risk_manager_class=RiskManager,
        risk_params=risk_manager_params
    )
    
    # 5. Verifica Criteri di Successo
    assert not results['is_overfitted'], "Strategia Overfittata!"
    assert results['aggregate']['oos']['return'] > 0, "Strategia in perdita Out-of-Sample"
