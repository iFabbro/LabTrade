"""
Trade Logger
Logger operazioni di trading su file CSV con statistiche real-time
"""
import csv
import os
from datetime import datetime
from typing import Dict, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class TradeLogger:
    """Logger operazioni di trading"""
    
    def __init__(self, log_dir: str = "logs"):
        """
        Inizializza logger
        
        Args:
            log_dir: Directory per file log
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.trades_file = self.log_dir / f"trades_{datetime.now().strftime('%Y%m%d')}.csv"
        self.trades: List[Dict] = []
        
        # Inizializza file CSV con header se non esiste
        if not self.trades_file.exists():
            self._write_header()
    
    def _write_header(self):
        """Scrivi header CSV"""
        with open(self.trades_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "symbol", "action", "side", "price", 
                "quantity", "pnl", "commission", "balance", "notes"
            ])
    
    def log_trade(self, symbol: str, action: str, side: str, price: float, 
                  quantity: float, pnl: float = 0.0, commission: float = 0.0, 
                  balance: float = 0.0, notes: str = ""):
        """
        Registra operazione
        
        Args:
            symbol: Simbolo trading
            action: OPEN_LONG, OPEN_SHORT, CLOSE_LONG, CLOSE_SHORT
            side: BUY o SELL
            price: Prezzo esecuzione
            quantity: Quantità
            pnl: Profit/Loss (per chiusure)
            commission: Commissione
            balance: Saldo dopo operazione
            notes: Note aggiuntive
        """
        trade = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "action": action,
            "side": side,
            "price": price,
            "quantity": quantity,
            "pnl": pnl,
            "commission": commission,
            "balance": balance,
            "notes": notes
        }
        
        self.trades.append(trade)
        
        # Scrivi su CSV
        with open(self.trades_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                trade["timestamp"], trade["symbol"], trade["action"], trade["side"],
                trade["price"], trade["quantity"], trade["pnl"], trade["commission"],
                trade["balance"], trade["notes"]
            ])
        
        logger.info(f"Trade loggato: {action} {side} {quantity} {symbol} @ {price}")
    
    def get_statistics(self) -> Dict:
        """
        Calcola statistiche trading
        
        Returns:
            Dict con statistiche
        """
        if not self.trades:
            return {"total_trades": 0}
        
        # Filtra solo chiusure per calcolare PnL
        closing_trades = [t for t in self.trades if t["action"] in ["CLOSE_LONG", "CLOSE_SHORT"]]
        
        total_trades = len(closing_trades)
        winning_trades = sum(1 for t in closing_trades if t["pnl"] > 0)
        losing_trades = sum(1 for t in closing_trades if t["pnl"] < 0)
        
        total_pnl = sum(t["pnl"] for t in closing_trades)
        total_commission = sum(t["commission"] for t in self.trades)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Calcola ROI se abbiamo saldo iniziale
        initial_balance = self.trades[0]["balance"] if self.trades else 0
        final_balance = self.trades[-1]["balance"] if self.trades else 0
        roi = ((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_commission": total_commission,
            "net_pnl": total_pnl - total_commission,
            "roi": roi,
            "initial_balance": initial_balance,
            "final_balance": final_balance
        }
    
    def print_summary(self):
        """Stampa summary statistiche"""
        stats = self.get_statistics()
        
        print("\n" + "="*60)
        print("📊 TRADING SUMMARY")
        print("="*60)
        print(f"Totale Trade: {stats['total_trades']}")
        print(f"Trade Vincenti: {stats['winning_trades']}")
        print(f"Trade Perdenti: {stats['losing_trades']}")
        print(f"Win Rate: {stats['win_rate']:.2f}%")
        print(f"PnL Totale: ${stats['total_pnl']:.2f}")
        print(f"Commissioni: ${stats['total_commission']:.2f}")
        print(f"PnL Netto: ${stats['net_pnl']:.2f}")
        print(f"ROI: {stats['roi']:.2f}%")
        print(f"Saldo Iniziale: ${stats['initial_balance']:.2f}")
        print(f"Saldo Finale: ${stats['final_balance']:.2f}")
        print("="*60 + "\n")
