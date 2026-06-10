import pandas as pd
import numpy as np
from typing import List, Dict
from src.strategies.sma_crossover import SMACrossoverStrategy
from src.core.backtester import Backtester

class ParameterOptimizer:
    def __init__(self, df_data: pd.DataFrame, fast_periods: List[int], slow_periods: List[int]):
        self.df_data = df_data
        self.fast_periods = fast_periods
        self.slow_periods = slow_periods
        self.backtester = Backtester(initial_capital=10000, commission=0.001, slippage=0.0005)
        
    def calculate_sharpe_ratio(self, equity_curve: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
        """Calcola lo Sharpe Ratio annualizzato"""
        if len(equity_curve) < 2:
            return 0.0
        
        equity_curve = equity_curve.copy()
        equity_curve['daily_return'] = equity_curve['equity'].pct_change()
        equity_curve = equity_curve.dropna()
        
        if len(equity_curve) == 0 or equity_curve['daily_return'].std() == 0:
            return 0.0
            
        mean_daily_return = equity_curve['daily_return'].mean()
        std_daily_return = equity_curve['daily_return'].std()
        
        # Annualizzazione (365 giorni per crypto)
        sharpe_ratio = np.sqrt(365) * (mean_daily_return - risk_free_rate) / std_daily_return
        return float(sharpe_ratio)

    def run(self) -> List[Dict]:
        results = []
        
        for fast in self.fast_periods:
            for slow in self.slow_periods:
                if fast >= slow:
                    continue  # La SMA veloce deve essere inferiore alla lenta
                
                strategy = SMACrossoverStrategy(fast_period=fast, slow_period=slow)
                df_signals = strategy.generate_signals(self.df_data)
                
                if len(df_signals) == 0:
                    continue
                    
                backtest_result = self.backtester.run_backtest(df_signals)
                sharpe = self.calculate_sharpe_ratio(backtest_result['equity_curve'])
                
                results.append({
                    'fast_period': fast,
                    'slow_period': slow,
                    'total_return_pct': backtest_result['total_return_pct'],
                    'max_drawdown_pct': backtest_result['max_drawdown_pct'],
                    'sharpe_ratio': sharpe,
                    'win_rate_pct': backtest_result['win_rate_pct'],
                    'total_trades': backtest_result['total_trades']
                })
                
        def sort_key(res):
            # Priorità 1: Drawdown < 30% (penalità 0 se rispettato, 100 se violato)
            dd_penalty = 0 if res['max_drawdown_pct'] < 30.0 else 100.0
            # Priorità 3: Rendimento positivo (penalità 0 se > 0, 100 se <= 0)
            return_penalty = 0 if res['total_return_pct'] > 0.0 else 100.0
            
            # Ordinamento: minimizza dd_penalty, massimizza sharpe (quindi -sharpe), 
            # minimizza return_penalty, massimizza return (quindi -return)
            return (
                dd_penalty,
                -res['sharpe_ratio'],
                return_penalty,
                -res['total_return_pct']
            )
            
        results.sort(key=sort_key)
        return results
