import numpy as np
from typing import List, Dict, Any

def run_monte_carlo(
    trade_returns: List[float],
    initial_capital: float = 10000.0,
    n_simulations: int = 1000,
    block_size: int = 3,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Esegue una simulazione Monte Carlo con Block Bootstrap sui rendimenti dei trade.
    
    Args:
        trade_returns: Lista dei rendimenti percentuali in decimale (es. 0.02 per 2%)
        initial_capital: Capitale iniziale
        n_simulations: Numero di simulazioni da eseguire
        block_size: Dimensione del blocco per il bootstrap (preserva autocorrelazione)
        seed: Seed per la riproducibilità
        
    Returns:
        Dizionario con le statistiche aggregate della simulazione
    """
    np.random.seed(seed)
    
    n_trades = len(trade_returns)
    if n_trades == 0:
        raise ValueError("trade_returns non può essere vuoto")
        
    # Crea blocchi di trade consecutivi per preservare l'autocorrelazione temporale
    blocks = [trade_returns[i:i + block_size] for i in range(0, n_trades, block_size)]
    n_blocks = len(blocks)
    
    final_returns = np.zeros(n_simulations)
    max_drawdowns = np.zeros(n_simulations)
    sharpe_ratios = np.zeros(n_simulations)
    
    for i in range(n_simulations):
        # Campiona blocchi con ripetizione
        sampled_indices = np.random.randint(0, n_blocks, size=n_blocks)
        sampled_trades = []
        for idx in sampled_indices:
            sampled_trades.extend(blocks[idx])
        
        # Taglia alla lunghezza originale esatta
        sampled_trades = np.array(sampled_trades[:n_trades])
        
        # Calcola la curva di equity (capitalizzazione composta)
        equity_curve = initial_capital * np.cumprod(1 + sampled_trades)
        equity_curve = np.insert(equity_curve, 0, initial_capital)
        
        # Calcola Max Drawdown
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = (running_max - equity_curve) / running_max
        max_dd = np.max(drawdowns)
        
        # Calcola Rendimento Finale
        final_eq = equity_curve[-1]
        final_ret = (final_eq - initial_capital) / initial_capital
        
        # Calcola Sharpe Ratio (proxy annualizzato a livello di trade)
        mean_ret = np.mean(sampled_trades)
        std_ret = np.std(sampled_trades)
        sharpe = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0
        
        final_returns[i] = final_ret
        max_drawdowns[i] = max_dd
        sharpe_ratios[i] = sharpe
        
    # Statistiche aggregate
    results = {
        'final_returns_pct': final_returns * 100,
        'max_drawdowns_pct': max_drawdowns * 100,
        'sharpe_ratios': sharpe_ratios,
        'prob_loss_pct': np.mean(final_returns < 0) * 100,
        'prob_dd_20_pct': np.mean(max_drawdowns > 0.20) * 100,
        'percentile_5_return': np.percentile(final_returns, 5) * 100,
        'percentile_50_return': np.percentile(final_returns, 50) * 100,
        'percentile_95_return': np.percentile(final_returns, 95) * 100,
        'percentile_5_dd': np.percentile(max_drawdowns, 5) * 100,
        'percentile_50_dd': np.percentile(max_drawdowns, 50) * 100,
        'percentile_95_dd': np.percentile(max_drawdowns, 95) * 100,
    }
    
    return results
