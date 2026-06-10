import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
        self.BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', 'test_key')
        self.BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', 'test_secret')
        self.INITIAL_CAPITAL = float(os.getenv('INITIAL_CAPITAL', 10000))
        self.RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', 0.02))

config = Config()
