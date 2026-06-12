import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from src.risk.risk_manager import RiskManager

class Backtester:
    def __init__(self, initial_capital=10000, commission=0.001, slippage=0.0005, risk_manager: Optional[RiskManager] = None):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.risk_manager = risk_manager
        
    def run_backtest(self, df_signals: pd.DataFrame) -> Dict:
        if self.risk_manager:
            df = self.risk_manager.prepare_data(df_signals)
        else:
            df = df_signals.copy()
            
        capital = self.initial_capital
        position = 0
        entry_price = 0.0
        quantity = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        
        trades = []
        equity_curve = []
        
        for idx, row in df.iterrows():
            current_price = row['close']
            signal = row['signal']
            
            # 1. Controlla Stop Loss e Take Profit se siamo in posizione
            if position == 1:
                low_price = row.get('low', current_price)
                high_price = row.get('high', current_price)
                
                # Controlla Stop Loss (solo se è stato impostato)
                if stop_loss > 0 and low_price <= stop_loss:
                    exit_price = stop_loss * (1 - self.slippage)
                    pnl = (exit_price - entry_price) * quantity
                    commission_cost = (quantity * exit_price) * self.commission
                    capital += (quantity * exit_price) - commission_cost
                    
                    trades.append({
                        'date': row['timestamp'],
                        'type': 'SELL_SL',
                        'price': exit_price,
                        'quantity': quantity,
                        'pnl': pnl,
                        'commission': commission_cost
                    })
                    position = 0
                    quantity = 0
                    
                # Controlla Take Profit (solo se è stato impostato)
                elif take_profit < float('inf') and high_price >= take_profit:
                    exit_price = take_profit * (1 - self.slippage)
                    pnl = (exit_price - entry_price) * quantity
                    commission_cost = (quantity * exit_price) * self.commission
                    capital += (quantity * exit_price) - commission_cost
                    
                    trades.append({
                        'date': row['timestamp'],
                        'type': 'SELL_TP',
                        'price': exit_price,
                        'quantity': quantity,
                        'pnl': pnl,
                        'commission': commission_cost
                    })
                    position = 0
                    quantity = 0

            # 2. Esegui segnali di strategia se non siamo in posizione
            if signal == 1 and position == 0:
                entry_price = current_price * (1 + self.slippage)
                
                if self.risk_manager:
                    atr = row.get('atr', 0)
                    
                    # Calcola stop loss prima
                    stop_loss = self.risk_manager.get_stop_loss(entry_price, atr)
                    
                    # Poi calcola take profit usando lo stop loss
                    take_profit = self.risk_manager.get_take_profit(entry_price, stop_loss)
                    
                    # Infine calcola position size
                    quantity = self.risk_manager.calculate_position_size(capital, entry_price, stop_loss)
                    
                    # Safety cap: non possiamo comprare più di quanto il capitale consente (considerando commissione)
                    max_quantity = (capital / (1 + self.commission)) / entry_price
                    if quantity > max_quantity:
                        quantity = max_quantity
                else:
                    # Senza risk manager: usa tutto il capitale considerando la commissione
                    quantity = (capital / (1 + self.commission)) / entry_price
                    stop_loss = 0  # 0 significa "non controllare"
                    take_profit = float('inf')  # inf significa "non controllare"
                
                cost = quantity * entry_price
                commission_cost = cost * self.commission
                
                if cost + commission_cost <= capital and quantity > 0:
                    capital -= (cost + commission_cost)
                    position = 1
                    
                    trades.append({
                        'date': row['timestamp'],
                        'type': 'BUY',
                        'price': entry_price,
                        'quantity': quantity,
                        'commission': commission_cost,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit
                    })
            
            # 3. Chiudi posizione su segnale di SELL della strategia (se ancora in posizione)
            elif signal == -1 and position == 1:
                exit_price = current_price * (1 - self.slippage)
                pnl = (exit_price - entry_price) * quantity
                commission_cost = (quantity * exit_price) * self.commission
                capital += (quantity * exit_price) - commission_cost
                
                trades.append({
                    'date': row['timestamp'],
                    'type': 'SELL_SIGNAL',
                    'price': exit_price,
                    'quantity': quantity,
                    'pnl': pnl,
                    'commission': commission_cost
                })
                position = 0
                quantity = 0
            
            # 4. Calcola equity corrente
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
        
        df_equity['peak'] = df_equity['equity'].cummax()
        df_equity['drawdown'] = (df_equity['peak'] - df_equity['equity']) / df_equity['peak']
        max_drawdown = df_equity['drawdown'].max()
        
        # Calcola Sharpe Ratio (annualizzato, risk-free rate = 0)
        if len(df_equity) > 1:
            df_equity['returns'] = df_equity['equity'].pct_change()
            mean_return = df_equity['returns'].mean()
            std_return = df_equity['returns'].std()
            sharpe_ratio = np.sqrt(252) * (mean_return / std_return) if std_return != 0 else 0.0
        else:
            sharpe_ratio = 0.0
            
        # Calcola win rate
        if len(df_trades) > 0:
            sell_trades = df_trades[df_trades['type'].str.startswith('SELL')]
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
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(df_trades[df_trades['type'].str.startswith('SELL')]) if len(df_trades) > 0 else 0,
            'win_rate': win_rate,
            'win_rate_pct': win_rate * 100,
            'equity_curve': df_equity,
            'trades': df_trades
        }
        
        return results
