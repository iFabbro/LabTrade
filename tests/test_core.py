import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.config import config

def test_config_loads_defaults():
    assert config.INITIAL_CAPITAL == 10000.0
    assert config.RISK_PER_TRADE == 0.02
    assert config.BINANCE_API_KEY == 'test_key'

def test_core_imports():
    import pandas as pd
    import numpy as np
    import pandas_ta as ta
    from binance.client import Client
    assert pd.__version__ is not None
    assert np.__version__ is not None
