import pandas as pd
import numpy as np
from typing import Dict, List

class Backtester:
    """
    Motore di backtesting per simulare l'esecuzione di strategie di trading.
    """
    
    def __init__(self, initial_capital=10000, commission=0.001, slippage=0.0005):
        """
        Args:
            initial_capital: Capitale iniziale in USD
            commission: Commissione per trade (0.1% = 0.001)
            slippage: Slippage stimato (0.05% = 0.0005)
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        
    def run_backtest(self, df_signals: pd.DataFrame) -> Dict:
        """
        Esegue il backtest sui segnali di trading.
        
        Args:
            df_signals: DataFrame con colonna 'signal' (1=BUY, -1=SELL, 0=HOLD)
        
        Returns:
            Dizionario con risultati del backtest
        """
        capital = self.initial_capital
        position = 0  # 0 = no position, 1 = long
        entry_price = 0
        
        trades = []
        equity_curve = []
        
        for idx, row in df_signals.iterrows():
            current_price = row['close']
            signal = row['signal']
            
            # Apri posizione LONG
            if signal == 1 and position == 0:
                # Applica slippage (compri leggermente più alto)
                entry_price = current_price * (1 + self.slippage)
                # Calcola quantità acquistabile
                quantity = capital / entry_price
                # Applica commissione
                commission_cost = capital * self.commission
                capital -= commission_cost
                position = 1
                
                trades.append({
                    'date': row['timestamp'],
                    'type': 'BUY',
                    'price': entry_price,
                    'quantity': quantity,
                    'commission': commission_cost
                })
            
            # Chiudi posizione LONG
            elif signal == -1 and position == 1:
                # Applica slippage (vendi leggermente più basso)
                exit_price = current_price * (1 - self.slippage)
                # Calcola profitto/perdita
                pnl = (exit_price - entry_price) * quantity
                # Applica commissione
                commission_cost = (quantity * exit_price) * self.commission
                capital += pnl - commission_cost
                position = 0
                
                trades.append({
                    'date': row['timestamp'],
                    'type': 'SELL',
                    'price': exit_price,
                    'quantity': quantity,
                    'pnl': pnl,
                    'commission': commission_cost
                })
            
            # Calcola equity corrente
            if position == 1:
                equity = capital + (current_price * quantity)
            else:
                equity = capital
            
            equity_curve.append({
                'date': row['timestamp'],
                'equity': equity,
                'price': current_price
            })
        
        # Calcola metriche finali
        df_equity = pd.DataFrame(equity_curve)
        df_trades = pd.DataFrame(trades)
        
        final_capital = df_equity['equity'].iloc[-1] if len(df_equity) > 0 else self.initial_capital
        total_return = (final_capital - self.initial_capital) / self.initial_capital
        
        # Calcola drawdown
        df_equity['peak'] = df_equity['equity'].cummax()
        df_equity['drawdown'] = (df_equity['peak'] - df_equity['equity']) / df_equity['peak']
        max_drawdown = df_equity['drawdown'].max()
        
        # Calcola win rate
        if len(df_trades) > 0:
            sell_trades = df_trades[df_trades['type'] == 'SELL']
            if len(sell_trades) > 0:
                winning_trades = len(sell_trades[sell_trades['pnl'] > 0])
                win_rate = winning_trades / len(sell_trades)
            else:
                win_rate = 0
        else:
            win_rate = 0
        
        results = {
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'total_trades': len(df_trades[df_trades['type'] == 'SELL']) if len(df_trades) > 0 else 0,
            'win_rate': win_rate,
            'win_rate_pct': win_rate * 100,
            'equity_curve': df_equity,
            'trades': df_trades
        }
        
        return results
