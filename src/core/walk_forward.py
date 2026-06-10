import pandas as pd
import numpy as np
from typing import Dict, Any, List
from src.core.backtester import Backtester

class WalkForwardValidator:
    def __init__(self, data: pd.DataFrame, n_windows: int = 5, is_ratio: float = 0.70):
        self.data = data.copy()
        if 'timestamp' not in self.data.columns and self.data.index.name == 'timestamp':
            self.data = self.data.reset_index()
        self.data = self.data.dropna().sort_values('timestamp').reset_index(drop=True)
        self.n_windows = n_windows
        self.is_ratio = is_ratio
        self.window_results = []

    def _run_backtest(self, df, strategy, risk_manager):
        """Helper per eseguire un backtest e restituire le metriche."""
        df_signals = strategy.generate_signals(df)
        backtester = Backtester(
            initial_capital=10000,
            commission=0.001,
            slippage=0.0005,
            risk_manager=risk_manager
        )
        return backtester.run_backtest(df_signals)

    def _calculate_degradation(self, is_val, oos_val, threshold=5.0):
        """
        Calcola il degrado in modo robusto.
        Se IS < threshold, il degrado non è significativo (torna 0).
        Valori negativi indicano che OOS è migliore di IS (buon segno).
        """
        if abs(is_val) < threshold:
            return 0.0
        return ((is_val - oos_val) / abs(is_val) * 100)

    def run(self, strategy_class, strategy_params: Dict, risk_manager_class, risk_params: Dict) -> Dict[str, Any]:
        total_rows = len(self.data)
        rows_per_window = total_rows // self.n_windows
        
        print("=" * 60)
        print("WALK-FORWARD VALIDATION - SMA Crossover (25/30)")
        print("=" * 60)

        for i in range(self.n_windows):
            start_idx = i * rows_per_window
            end_idx = (i + 1) * rows_per_window if i < self.n_windows - 1 else total_rows
            
            window_data = self.data.iloc[start_idx:end_idx]
            is_split_idx = int(len(window_data) * self.is_ratio)
            
            is_data = window_data.iloc[:is_split_idx].copy()
            oos_data = window_data.iloc[is_split_idx:].copy()
            
            strategy_is = strategy_class(**strategy_params)
            risk_manager_is = risk_manager_class(**risk_params)
            metrics_is = self._run_backtest(is_data, strategy_is, risk_manager_is)
            
            strategy_oos = strategy_class(**strategy_params)
            risk_manager_oos = risk_manager_class(**risk_params)
            metrics_oos = self._run_backtest(oos_data, strategy_oos, risk_manager_oos)
            
            ret_is = metrics_is.get('total_return', 0) * 100
            ret_oos = metrics_oos.get('total_return', 0) * 100
            ret_deg = self._calculate_degradation(ret_is, ret_oos)
            
            dd_is = metrics_is.get('max_drawdown', 0) * 100
            dd_oos = metrics_oos.get('max_drawdown', 0) * 100
            dd_deg = self._calculate_degradation(dd_is, dd_oos)
            
            wr_is = metrics_is.get('win_rate', 0) * 100
            wr_oos = metrics_oos.get('win_rate', 0) * 100
            wr_deg = self._calculate_degradation(wr_is, wr_oos)
            
            is_start = is_data['timestamp'].iloc[0].strftime('%Y-%m-%d')
            is_end = is_data['timestamp'].iloc[-1].strftime('%Y-%m-%d')
            oos_start = oos_data['timestamp'].iloc[0].strftime('%Y-%m-%d')
            oos_end = oos_data['timestamp'].iloc[-1].strftime('%Y-%m-%d')
            win_start = self.data['timestamp'].iloc[start_idx].strftime('%Y-%m-%d')
            win_end = self.data['timestamp'].iloc[end_idx-1].strftime('%Y-%m-%d')
            
            self.window_results.append({
                'window': i + 1,
                'is_start': is_start,
                'is_end': is_end,
                'oos_start': oos_start,
                'oos_end': oos_end,
                'is_return': ret_is,
                'is_dd': dd_is,
                'is_wr': wr_is,
                'is_sharpe': metrics_is.get('sharpe_ratio', 0.0),
                'oos_return': ret_oos,
                'oos_dd': dd_oos,
                'oos_wr': wr_oos,
                'oos_sharpe': metrics_oos.get('sharpe_ratio', 0.0),
                'ret_deg': ret_deg,
                'dd_deg': dd_deg,
                'wr_deg': wr_deg
            })
            
            print(f"\nFinestra {i+1}/{self.n_windows}: {win_start} → {win_end}")
            print(f"  In-Sample (70%):      {is_start} → {is_end} | Return: {ret_is:+.2f}% | DD: {dd_is:.2f}%")
            print(f"  Out-of-Sample (30%):  {oos_start} → {oos_end} | Return: {ret_oos:+.2f}% | DD: {dd_oos:.2f}%")
            print(f"  Degrado Rendimento:   {ret_deg:.1f}%")

        avg_is_ret = np.mean([r['is_return'] for r in self.window_results])
        avg_is_dd = np.mean([r['is_dd'] for r in self.window_results])
        avg_is_wr = np.mean([r['is_wr'] for r in self.window_results])
        avg_is_sharpe = np.mean([r['is_sharpe'] for r in self.window_results])
        
        avg_oos_ret = np.mean([r['oos_return'] for r in self.window_results])
        avg_oos_dd = np.mean([r['oos_dd'] for r in self.window_results])
        avg_oos_wr = np.mean([r['oos_wr'] for r in self.window_results])
        avg_oos_sharpe = np.mean([r['oos_sharpe'] for r in self.window_results])
        
        avg_ret_deg = np.mean([r['ret_deg'] for r in self.window_results])
        avg_dd_deg = np.mean([r['dd_deg'] for r in self.window_results])
        avg_wr_deg = np.mean([r['wr_deg'] for r in self.window_results])
        
        # Logica overfitting più intelligente:
        # Overfitting solo se MULTIPLE metriche chiave degradano significativamente
        # Se OOS Sharpe > IS Sharpe, forte indicatore di NON-overfitting
        sharpe_improved = avg_oos_sharpe > avg_is_sharpe
        
        # Overfitting severo: rendimento degrada > 50%
        severe_degradation = avg_ret_deg > 50
        
        # Overfitting moderato: rendimento degrada > 30% E win rate degrada > 30%
        moderate_degradation = (avg_ret_deg > 30) and (avg_wr_deg > 30)
        
        is_overfitted = severe_degradation or moderate_degradation
        
        print("\n" + "=" * 60)
        print("RISULTATI AGGREGATI")
        print("=" * 60)
        print("Performance In-Sample (media):")
        print(f"  - Rendimento:   {avg_is_ret:+.2f}%")
        print(f"  - Max Drawdown: {avg_is_dd:.2f}%")
        print(f"  - Win Rate:     {avg_is_wr:.1f}%")
        print(f"  - Sharpe Ratio: {avg_is_sharpe:.2f}")
        print("\nPerformance Out-of-Sample (media):")
        print(f"  - Rendimento:   {avg_oos_ret:+.2f}%")
        print(f"  - Max Drawdown: {avg_oos_dd:.2f}%")
        print(f"  - Win Rate:     {avg_oos_wr:.1f}%")
        print(f"  - Sharpe Ratio: {avg_oos_sharpe:.2f}")
        print("\nDegrado Performance (IS → OOS):")
        print(f"  - Rendimento:   {avg_ret_deg:.1f}%")
        print(f"  - Max Drawdown: {avg_dd_deg:.1f}%")
        print(f"  - Win Rate:     {avg_wr_deg:.1f}%")
        print("=" * 60)
        
        if not is_overfitted:
            print("✓ Strategia NON Overfittata")
            if sharpe_improved:
                print("✓ OOS Sharpe Ratio migliore di IS (strategia robusta)")
            if avg_oos_dd < avg_is_dd:
                print("✓ OOS Drawdown minore di IS (risk management efficace)")
        else:
            print("⚠ Strategia Overfittata")
            if severe_degradation:
                print("  - Degrado rendimento severo (> 50%)")
            if moderate_degradation:
                print("  - Degrado rendimento e win rate moderato (> 30%)")
        print("=" * 60)
        
        return {
            'is_overfitted': is_overfitted,
            'window_results': self.window_results,
            'aggregate': {
                'is': {'return': avg_is_ret, 'dd': avg_is_dd, 'wr': avg_is_wr, 'sharpe': avg_is_sharpe},
                'oos': {'return': avg_oos_ret, 'dd': avg_oos_dd, 'wr': avg_oos_wr, 'sharpe': avg_oos_sharpe},
                'degradation': {'return': avg_ret_deg, 'dd': avg_dd_deg, 'wr': avg_wr_deg}
            }
        }
