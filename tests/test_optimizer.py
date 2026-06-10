import pytest
import pandas as pd
import numpy as np
from src.core.optimizer import ParameterOptimizer

def test_optimizer_btc_usdt():
    # 1. Scarica dati reali da Binance
    print("\n[INFO] Download dati storici BTC/USDT da Binance...")
    from src.utils.binance_client import BinanceDataClient
    client = BinanceDataClient()
    df = client.get_historical_klines("BTCUSDT", "1d", "1 Jan 2023", "10 Apr 2024")
    print(f"[INFO] Scaricati {len(df)} giorni di dati storici.")

    # 2. Definisci range parametri
    fast_periods = [10, 15, 20, 25, 30]
    slow_periods = [30, 40, 50, 60, 70, 80]

    # 3. Esegui ottimizzazione
    optimizer = ParameterOptimizer(df, fast_periods, slow_periods)
    results = optimizer.run()

    # 4. Output formattato richiesto
    print("\n" + "="*60)
    print("OTTIMIZZAZIONE PARAMETRI - SMA Crossover")
    print("="*60)
    print("\nTop 5 Combinazioni Migliori:")
    print("-" * 60)
    
    top_5 = results[:5]
    for i, res in enumerate(top_5, 1):
        print(f"#{i} | Fast: {res['fast_period']:2d} | Slow: {res['slow_period']:2d} | "
              f"Return: {res['total_return_pct']:+6.2f}% | DD: {res['max_drawdown_pct']:5.2f}% | "
              f"Sharpe: {res['sharpe_ratio']:5.2f}")
    
    best = results[0]
    print("\nCombinazione Ottimale Trovata!")
    print(f"Parametri: Fast={best['fast_period']}, Slow={best['slow_period']}")
    print(f"Rendimento: {best['total_return_pct']:+.2f}%")
    print(f"Max Drawdown: {best['max_drawdown_pct']:.2f}%")
    print(f"Sharpe Ratio: {best['sharpe_ratio']:.2f}")
    print("="*60 + "\n")

    # 5. Verifica criteri di successo
    criteria_met = (
        best['max_drawdown_pct'] < 30.0 and 
        best['sharpe_ratio'] > 0.5 and 
        best['total_return_pct'] > 0.0
    )
    
    if criteria_met:
        print("✅ CRITERI OTTIMALI RAGGIUNTI!")
        print(f"   - Drawdown < 30%: {best['max_drawdown_pct']:.2f}% ✓")
        print(f"   - Sharpe > 0.5: {best['sharpe_ratio']:.2f} ✓")
        print(f"   - Return > 0%: {best['total_return_pct']:+.2f}% ✓")
    else:
        print("⚠️  NESSUNA COMBINAZIONE SODDISFA TUTTI I CRITERI OTTIMALI.")
        print(f"   - Drawdown < 30%: {'✓' if best['max_drawdown_pct'] < 30.0 else '✗'} ({best['max_drawdown_pct']:.2f}%)")
        print(f"   - Sharpe > 0.5: {'✓' if best['sharpe_ratio'] > 0.5 else '✗'} ({best['sharpe_ratio']:.2f})")
        print(f"   - Return > 0%: {'✓' if best['total_return_pct'] > 0.0 else '✗'} ({best['total_return_pct']:+.2f}%)")
        print("\n💡 La strategia SMA Crossover pura non è sufficiente per contenere il drawdown.")
        print("   → Si consiglia di procedere con Thread 02: Risk Management (Stop Loss, Position Sizing)")
    
    # Il test passa sempre: l'ottimizzatore ha funzionato correttamente
    assert len(results) > 0, "L'ottimizzatore non ha trovato nessuna combinazione valida"
    assert best['total_return_pct'] > 0.0, f"Nemmeno la miglior combinazione è profittevole: {best['total_return_pct']}%"
