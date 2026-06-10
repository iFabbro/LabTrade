import sys
import os
import pandas as pd
import numpy as np

# Aggiungi il percorso del progetto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.backtester import Backtester
from src.risk.risk_manager import RiskManager

def generate_synthetic_data():
    """
    Genera dati sintetici che mimano un trend rialzista con drawdown profondi,
    simile al comportamento osservato nella strategia SMA 25/30.
    """
    np.random.seed(42)
    periods = 1000
    dates = pd.date_range(end='2023-12-31', periods=periods, freq='D')
    
    # Trend rialzista forte con volatilità e drawdown
    trend = np.linspace(0, 1.5, periods)
    noise = np.cumsum(np.random.normal(0, 0.015, periods))
    price = 100 * np.exp(trend + noise)
    
    high = price * (1 + np.abs(np.random.normal(0, 0.02, periods)))
    low = price * (1 - np.abs(np.random.normal(0, 0.02, periods)))
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': price,
        'high': high,
        'low': low,
        'close': price
    })
    
    # Calcolo SMA 25 e 30
    df['sma_fast'] = df['close'].rolling(25).mean()
    df['sma_slow'] = df['close'].rolling(30).mean()
    
    # Genera segnali: 1 quando fast > slow, -1 quando fast < slow
    df['signal'] = 0
    df.loc[df['sma_fast'] > df['sma_slow'], 'signal'] = 1
    df.loc[df['sma_fast'] < df['sma_slow'], 'signal'] = -1
    
    # Rimuovi i primi 30 giorni dove le SMA sono NaN
    df = df.dropna().reset_index(drop=True)
    return df

def test_risk_management():
    df = generate_synthetic_data()
    
    # 1. Backtest SENZA Risk Management (All-in, no SL)
    bt_no_rm = Backtester(initial_capital=10000, commission=0.001, slippage=0.0005)
    results_no_rm = bt_no_rm.run_backtest(df)
    
    # 2. Backtest CON Risk Manager
    rm = RiskManager(risk_per_trade=0.02, atr_period=14, atr_sl_multiplier=2.0, rr_ratio=2.0)
    bt_with_rm = Backtester(initial_capital=10000, commission=0.001, slippage=0.0005, risk_manager=rm)
    results_with_rm = bt_with_rm.run_backtest(df)
    
    # Output richiesto
    print("\n" + "="*60)
    print("RISK MANAGEMENT - SMA Crossover (25/30)")
    print("="*60)
    print("\n[PRIMA] Senza Risk Management:")
    print(f"- Rendimento: {results_no_rm['total_return_pct']:+.2f}%")
    print(f"- Max Drawdown: {results_no_rm['max_drawdown_pct']:.2f}%")
    
    print("\n[DOPO] Con Risk Manager (Risk 2%, ATR SL 2x):")
    print(f"- Rendimento: {results_with_rm['total_return_pct']:+.2f}%")
    print(f"- Max Drawdown: {results_with_rm['max_drawdown_pct']:.2f}%")
    print(f"- Sharpe Ratio: {results_with_rm['sharpe_ratio']:.2f}")
    print(f"- Numero Trade: {results_with_rm['total_trades']}")
    print("-" * 60)
    
    target_dd = 25.0
    achieved = results_with_rm['max_drawdown_pct'] < target_dd
    status = "RAGGIUNTO" if achieved else "NON RAGGIUNTO"
    print(f"✓ Obiettivo Drawdown < {target_dd}%: [{status}]")
    print("="*60 + "\n")
    
    # Assert per validazione automatica
    assert results_with_rm['total_trades'] > 0, "Nessun trade eseguito"
    assert 'sharpe_ratio' in results_with_rm, "Sharpe Ratio mancante"
    print("✅ Test passato con successo!")

if __name__ == "__main__":
    test_risk_management()
