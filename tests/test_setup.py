import os
from dotenv import load_dotenv

def test_environment_loads():
    load_dotenv()
    assert os.getenv('LABTRADE_ENV') == 'test'

def test_basic_math():
    assert 1 + 1 == 2
