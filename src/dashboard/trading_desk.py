"""
LabTrade Trading Desk - Dashboard Live per Paper Trading
Mostra in tempo reale lo stato del sistema di trading nel terminale.
"""
import os
import sys
import time
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from rich.live import Live
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.align import Align

console = Console()

class TradingDesk:
    """Dashboard terminale live per monitoraggio paper trading."""
    
    def __init__(self, log_file="logs/paper_trading.log", trades_dir="logs"):
        self.log_file = Path(log_file)
        self.trades_dir = Path(trades_dir)
        self.start_time = datetime.now()
        self.last_log_lines = []
        self.trades_history = []
        
    def get_latest_logs(self, n_lines=8):
        """Legge le ultime N righe del log."""
        if not self.log_file.exists():
            return ["[dim]Nessun log disponibile[/dim]"]
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                return [l.strip() for l in lines[-n_lines:]]
        except Exception as e:
            return [f"[red]Errore lettura log: {e}[/red]"]
    
    def get_trades_summary(self):
        """Legge tutti i trade dai file CSV e calcola statistiche."""
        trades = []
        if not self.trades_dir.exists():
            return trades
        
        for csv_file in self.trades_dir.glob("trades_*.csv"):
            try:
                with open(csv_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        trades.append(row)
            except Exception:
                continue
        return trades
    
    def calculate_metrics(self, trades):
        """Calcola metriche di performance dai trade."""
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
            }
        
        pnls = []
        for t in trades:
            try:
                pnl = float(t.get('pnl', 0) or 0)
                pnls.append(pnl)
            except (ValueError, TypeError):
                continue
        
        if not pnls:
            return {
                'total_trades': len(trades),
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
            }
        
        winning = sum(1 for p in pnls if p > 0)
        losing = sum(1 for p in pnls if p < 0)
        
        return {
            'total_trades': len(pnls),
            'winning_trades': winning,
            'losing_trades': losing,
            'win_rate': (winning / len(pnls)) * 100 if pnls else 0,
            'total_pnl': sum(pnls),
            'avg_pnl': sum(pnls) / len(pnls),
            'best_trade': max(pnls),
            'worst_trade': min(pnls),
        }
    
    def extract_current_state(self, logs):
        """Estrae lo stato corrente dai log (ultimo segnale, prezzo, ecc.)."""
        state = {
            'last_candle': 'N/A',
            'sma_fast': 'N/A',
            'sma_slow': 'N/A',
            'atr': 'N/A',
            'signal': 'WAITING',
            'position': 'FLAT',
            'last_price': 'N/A',
        }
        
        for line in reversed(logs):
            line_lower = line.lower()
            
            # Estrai ultima candela
            if 'candela' in line_lower or 'candle' in line_lower:
                try:
                    state['last_candle'] = line.split(' - ')[-1][:25]
                except:
                    pass
            
            # Estrai SMA
            if 'sma' in line_lower:
                try:
                    state['sma_info'] = line.split(' - ')[-1][:50]
                except:
                    pass
            
            # Estrai segnale
            if 'segnale' in line_lower or 'signal' in line_lower:
                if 'buy' in line_lower:
                    state['signal'] = '🟢 BUY'
                elif 'sell' in line_lower:
                    state['signal'] = '🔴 SELL'
                elif 'hold' in line_lower:
                    state['signal'] = '⚪ HOLD'
            
            # Estrai ordine eseguito
            if 'ordine' in line_lower or 'order' in line_lower:
                if 'buy' in line_lower:
                    state['position'] = '🟢 LONG'
                elif 'sell' in line_lower or 'close' in line_lower:
                    state['position'] = '⚪ FLAT'
        
        return state
    
    def create_header(self):
        """Crea l'header del dashboard."""
        elapsed = datetime.now() - self.start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        header_text = Text()
        header_text.append("🚀 LABTRADE TRADING DESK", style="bold cyan")
        header_text.append(f"  |  Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}", style="dim")
        header_text.append(f"  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
        
        return Panel(
            Align.center(header_text),
            style="bold cyan",
            border_style="cyan"
        )
    
    def create_status_panel(self, state):
        """Crea il pannello stato sistema."""
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold")
        grid.add_column()
        
        grid.add_row("🟢 Stato:", "ATTIVO")
        grid.add_row("📊 Simbolo:", "BTCUSDT")
        grid.add_row("⏱️  Timeframe:", "1h")
        grid.add_row("📅 Ultima candela:", str(state.get('last_candle', 'N/A')))
        grid.add_row("🎯 Segnale:", state.get('signal', 'WAITING'))
        grid.add_row("💼 Posizione:", state.get('position', 'FLAT'))
        
        return Panel(grid, title="[bold]STATO SISTEMA[/bold]", border_style="green")
    
    def create_indicators_panel(self, state):
        """Crea il pannello indicatori tecnici."""
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold")
        grid.add_column()
        
        grid.add_row("SMA Fast (25):", str(state.get('sma_fast', 'N/A')))
        grid.add_row("SMA Slow (30):", str(state.get('sma_slow', 'N/A')))
        grid.add_row("ATR (14):", str(state.get('atr', 'N/A')))
        
        if 'sma_info' in state:
            grid.add_row("", "")
            grid.add_row("[dim]Info:[/dim]", f"[dim]{state['sma_info']}[/dim]")
        
        return Panel(grid, title="[bold]INDICATORI[/bold]", border_style="yellow")
    
    def create_performance_panel(self, metrics):
        """Crea il pannello performance."""
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold")
        grid.add_column(justify="right")
        
        # PnL colorato
        pnl = metrics['total_pnl']
        pnl_style = "green" if pnl >= 0 else "red"
        pnl_symbol = "+" if pnl >= 0 else ""
        
        grid.add_row("Trade Totali:", f"{metrics['total_trades']}")
        grid.add_row("Vinti:", f"[green]{metrics['winning_trades']}[/green]")
        grid.add_row("Persi:", f"[red]{metrics['losing_trades']}[/red]")
        grid.add_row("Win Rate:", f"{metrics['win_rate']:.1f}%")
        grid.add_row("", "")
        grid.add_row("PnL Totale:", f"[{pnl_style}]{pnl_symbol}${pnl:.2f}[/{pnl_style}]")
        grid.add_row("PnL Medio:", f"${metrics['avg_pnl']:+.2f}")
        grid.add_row("Miglior Trade:", f"[green]+${metrics['best_trade']:.2f}[/green]")
        grid.add_row("Peggior Trade:", f"[red]${metrics['worst_trade']:.2f}[/red]")
        
        return Panel(grid, title="[bold]PERFORMANCE[/bold]", border_style="magenta")
    
    def create_logs_panel(self, logs):
        """Crea il pannello log recenti."""
        log_text = Text()
        for line in logs[-8:]:
            # Colora in base al livello
            if 'ERROR' in line:
                style = "red"
            elif 'WARNING' in line:
                style = "yellow"
            elif 'INFO' in line:
                style = "cyan"
            else:
                style = "dim"
            log_text.append(line + "\n", style=style)
        
        return Panel(log_text, title="[bold]LOG RECENTI[/bold]", border_style="blue")
    
    def create_layout(self):
        """Crea il layout completo del dashboard."""
        logs = self.get_latest_logs(10)
        trades = self.get_trades_summary()
        metrics = self.calculate_metrics(trades)
        state = self.extract_current_state(logs)
        
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="logs", size=12)
        )
        
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        layout["left"].split_column(
            Layout(self.create_status_panel(state)),
            Layout(self.create_indicators_panel(state))
        )
        
        layout["right"].update(self.create_performance_panel(metrics))
        layout["logs"].update(self.create_logs_panel(logs))
        layout["header"].update(self.create_header())
        
        return layout
    
    def run(self, refresh_rate=2):
        """Avvia il dashboard live."""
        console.clear()
        console.print("[bold cyan]🚀 Avvio LabTrade Trading Desk...[/bold cyan]")
        time.sleep(1)
        
        with Live(self.create_layout(), refresh_per_second=refresh_rate, console=console) as live:
            try:
                while True:
                    live.update(self.create_layout())
                    time.sleep(1 / refresh_rate)
            except KeyboardInterrupt:
                console.print("\n[yellow]👋 Dashboard chiuso.[/yellow]")


if __name__ == "__main__":
    desk = TradingDesk()
    desk.run(refresh_rate=1)
