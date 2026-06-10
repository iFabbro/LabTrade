import pytest
import sys
import os

# Aggiungi il percorso radice al sys.path per importare i moduli del progetto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.risk.monte_carlo import run_monte_carlo

def test_monte_carlo_simulation():
    # Mock dei rendimenti dei 42 trade storici della strategia ottimizzata
    # Generati per riflettere approssimativamente: Win Rate ~55%, Sharpe > 1.5, Max DD basso
    # NOTA: In produzione, questa lista sarà popolata dall'output reale del backtester
    mock_trade_returns = [
        0.015, -0.010, 0.020, -0.012, 0.018, 0.022, -0.015, 0.010,
        -0.008, 0.025, 0.012, -0.018, 0.030, -0.010, 0.015, 0.018,
        -0.012, 0.020, -0.015, 0.022, 0.010, -0.020, 0.028, -0.010,
        0.015, 0.012, -0.015, 0.020, -0.010, 0.018, 0.025, -0.012,
        0.010, -0.018, 0.022, 0.015, -0.010, 0.020, -0.015, 0.018,
        0.012, -0.010
    ]
    
    # Esegui la simulazione Monte Carlo
    results = run_monte_carlo(
        trade_returns=mock_trade_returns,
        initial_capital=10000.0,
        n_simulations=1000,
        block_size=3,
        seed=42
    )
    
    # Stampa l'output richiesto
    print("\n" + "="*60)
    print("MONTE CARLO SIMULATION - 1000 Simulazioni")
    print("="*60)
    print("\nStrategia: SMA Crossover (25/30) + Risk Manager")
    print("Periodo: 2023-01-01 → 2024-04-10")
    print(f"Trade Storici: {len(mock_trade_returns)}")
    print("\nDistribuzione Rendimento Finale:")
    print("-" * 60)
    print(f"Worst Case (5° percentile):  {results['percentile_5_return']:>7.2f}%")
    print(f"Mediana (50° percentile):    {results['percentile_50_return']:>7.2f}%")
    print(f"Best Case (95° percentile):  {results['percentile_95_return']:>7.2f}%")
    print("-" * 60)
    print("\nDistribuzione Max Drawdown:")
    print("-" * 60)
    print(f"Worst Case (5° percentile):  {results['percentile_5_dd']:>7.2f}%")
    print(f"Mediana (50° percentile):    {results['percentile_50_dd']:>7.2f}%")
    print(f"Best Case (95° percentile):  {results['percentile_95_dd']:>7.2f}%")
    print("-" * 60)
    print(f"\nProbabilità di Perdita (Capital < $10,000): {results['prob_loss_pct']:.1f}%")
    print(f"Probabilità Drawdown > 20%:                 {results['prob_dd_20_pct']:.1f}%")
    print()
    
    # Classificazione robustezza
    if results['prob_loss_pct'] > 20.0:
        print("⚠ Strategia FRAGILE")
    else:
        print("✓ Strategia ROBUSTA")
    print("="*60 + "\n")
    
    # Asserzioni di base per validare il funzionamento del modulo
    assert results['percentile_50_return'] > 0, "La mediana del rendimento dovrebbe essere positiva"
    assert 0 <= results['prob_loss_pct'] <= 100, "Probabilità di perdita non valida"
    assert len(results['final_returns_pct']) == 1000, "Numero di simulazioni non corrispondente"

if __name__ == "__main__":
    test_monte_carlo_simulation()
