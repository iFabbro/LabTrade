"""
LabTrade Mission Control - Visualizzazione Team in Azione
Mostra come tutti i moduli collaborano in tempo reale.
"""
import time
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.table import Table
from rich import box

console = Console()

# Mapping tra nomi nei log e nomi visualizzati
LOG_TO_MODULE = {
    'binance': ['binance', 'testnet', 'api'],
    'strategy': ['strategy', 'sma', 'crossover', 'sma_crossover'],
    'risk': ['risk', 'manager', 'risk_manager'],
    'executor': ['executor', 'live', 'order'],
    'logger': ['logger', 'log', 'csv', 'trade_logger'],
    'main': ['main', '__main__'],
}

class ModuleMonitor:
    """Monitora lo stato di un singolo modulo."""
    
    def __init__(self, name, icon, keywords):
        self.name = name
        self.icon = icon
        self.keywords = keywords  # Lista di keywords per identificare questo modulo nei log
        self.status = "INIZIALIZZAZIONE"
        self.last_action = "In attesa..."
        self.actions_count = 0
        self.errors = 0
        self.last_update = datetime.now()
        self.is_active = False
        
    def update_from_log(self, log_line):
        """Aggiorna lo stato del modulo basandosi sul log."""
        log_lower = log_line.lower()
        
        # Controlla se questo modulo è menzionato nel log usando le keywords
        if not any(keyword in log_lower for keyword in self.keywords):
            return False
        
        self.last_update = datetime.now()
        self.actions_count += 1
        self.is_active = True
        
        # Determina stato e azione
        if "error" in log_lower:
            self.status = "ERRORE"
            self.errors += 1
        elif "ordine" in log_lower or "order" in log_lower or "buy" in log_lower or "sell" in log_lower:
            self.status = "ESECUZIONE"
        elif "calcolo" in log_lower or "calculating" in log_lower or "sma" in log_lower or "atr" in log_lower:
            self.status = "CALCOLO"
        elif "attendo" in log_lower or "waiting" in log_lower or "attesa" in log_lower:
            self.status = "ATTESA"
        elif "ricevuto" in log_lower or "received" in log_lower or "download" in log_lower:
            self.status = "RICEZIONE DATI"
        elif "inizializzat" in log_lower or "initialized" in log_lower:
            self.status = "ATTIVO"
        else:
            self.status = "ATTIVO"
        
        # Estrai l'azione (ultima parte del log)
        try:
            self.last_action = log_line.split(" - ")[-1][:50]
        except:
            self.last_action = log_line[:50]
        
        return True
    
    def get_status_color(self):
        """Restituisce il colore in base allo stato."""
        if "ERRORE" in self.status:
            return "red"
        elif "ATTIVO" in self.status or "ESECUZIONE" in self.status:
            return "green"
        elif "CALCOLO" in self.status:
            return "yellow"
        elif "ATTESA" in self.status:
            return "dim"
        else:
            return "cyan"
    
    def create_panel(self):
        """Crea il pannello del modulo."""
        elapsed = (datetime.now() - self.last_update).total_seconds()
        
        # Icona stato
        if elapsed < 60:
            status_icon = "🟢"
        elif elapsed < 300:
            status_icon = "🟡"
        else:
            status_icon = "🔴"
        
        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="bold")
        grid.add_column()
        
        grid.add_row("Stato:", f"[{self.get_status_color()}]{self.status}[/{self.get_status_color()}]")
        grid.add_row("Ultima azione:", f"[dim]{self.last_action}[/dim]")
        grid.add_row("Attività:", f"{self.actions_count} operazioni")
        if self.errors > 0:
            grid.add_row("Errori:", f"[red]{self.errors}[/red]")
        
        return Panel(
            grid,
            title=f"{status_icon} {self.icon} {self.name}",
            border_style=self.get_status_color(),
            box=box.ROUNDED
        )


class MissionControl:
    """Visualizza tutti i moduli che collaborano."""
    
    def __init__(self, log_file="logs/paper_trading.log"):
        self.log_file = Path(log_file)
        self.start_time = datetime.now()
        
        # Inizializza monitor per ogni modulo con le relative keywords
        self.modules = {
            'binance': ModuleMonitor("Binance Client", "🔌", LOG_TO_MODULE['binance']),
            'strategy': ModuleMonitor("Strategy Engine", "🧠", LOG_TO_MODULE['strategy']),
            'risk': ModuleMonitor("Risk Manager", "🛡️", LOG_TO_MODULE['risk']),
            'executor': ModuleMonitor("Live Executor", "⚡", LOG_TO_MODULE['executor']),
            'logger': ModuleMonitor("Trade Logger", "", LOG_TO_MODULE['logger']),
            'main': ModuleMonitor("Main Controller", "🎛️", LOG_TO_MODULE['main']),
        }
        
        self.data_flow = []
        self.last_log_position = 0
        
    def parse_logs(self):
        """Legge i nuovi log e aggiorna i moduli."""
        if not self.log_file.exists():
            return
        
        try:
            with open(self.log_file, 'r') as f:
                f.seek(self.last_log_position)
                new_lines = f.readlines()
                self.last_log_position = f.tell()
            
            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Estrai il nome del modulo dal log
                for module_key, module in self.modules.items():
                    if module.update_from_log(line):
                        # Registra nel data flow
                        self.data_flow.append({
                            'time': datetime.now(),
                            'module': module.name,
                            'action': line.split(" - ")[-1][:40]
                        })
                        # Mantieni solo ultimi 10 eventi
                        if len(self.data_flow) > 10:
                            self.data_flow.pop(0)
                        break
                        
        except Exception as e:
            console.print(f"[red]Errore lettura log: {e}[/red]")
    
    def create_system_overview(self):
        """Crea la panoramica del sistema."""
        active_modules = sum(1 for m in self.modules.values() if m.is_active)
        total_actions = sum(m.actions_count for m in self.modules.values())
        total_errors = sum(m.errors for m in self.modules.values())
        
        elapsed = datetime.now() - self.start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold cyan")
        grid.add_column()
        
        grid.add_row("️  Uptime:", f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        grid.add_row("🟢 Moduli attivi:", f"{active_modules}/{len(self.modules)}")
        grid.add_row("⚡ Operazioni totali:", str(total_actions))
        grid.add_row("🔴 Errori:", f"[red]{total_errors}[/red]" if total_errors > 0 else "[green]0[/green]")
        
        return Panel(
            grid,
            title="[bold]🌐 SYSTEM OVERVIEW[/bold]",
            border_style="cyan",
            box=box.DOUBLE
        )
    
    def create_modules_grid(self):
        """Crea la griglia con tutti i moduli."""
        panels = [module.create_panel() for module in self.modules.values()]
        return Columns(panels, equal=True, expand=True)
    
    def create_data_flow_panel(self):
        """Crea il pannello del flusso dati."""
        if not self.data_flow:
            return Panel(
                "[dim]In attesa di attività...[/dim]",
                title="[bold]📡 DATA FLOW[/bold]",
                border_style="blue"
            )
        
        flow_text = Text()
        for event in reversed(self.data_flow[-8:]):
            time_str = event['time'].strftime("%H:%M:%S")
            flow_text.append(f"[dim]{time_str}[/dim] ")
            flow_text.append(f"[cyan]{event['module']}[/cyan] ")
            flow_text.append(f"→ [yellow]{event['action']}[/yellow]\n")
        
        return Panel(
            flow_text,
            title="[bold]📡 DATA FLOW (Real-time)[/bold]",
            border_style="blue",
            box=box.ROUNDED
        )
    
    def create_architecture_diagram(self):
        """Crea un diagramma dell'architettura con stato."""
        arch_text = Text()
        
        # Binance API
        binance_status = "🟢" if self.modules['binance'].is_active else "⚪"
        arch_text.append(f"{binance_status} Binance Testnet API\n", style="bold")
        arch_text.append("   ↓\n", style="dim")
        
        # Main Controller
        main_status = "🟢" if self.modules['main'].is_active else ""
        arch_text.append(f"{main_status} Main Controller\n", style="bold cyan")
        arch_text.append("   ↓\n", style="dim")
        
        # Strategy Engine
        strat_status = "🟢" if self.modules['strategy'].is_active else "⚪"
        arch_text.append(f"{strat_status} Strategy Engine (SMA 25/30)\n", style="bold yellow")
        arch_text.append("   ↓\n", style="dim")
        
        # Risk Manager
        risk_status = "🟢" if self.modules['risk'].is_active else "⚪"
        arch_text.append(f"{risk_status} Risk Manager (ATR SL/TP)\n", style="bold magenta")
        arch_text.append("   ↓\n", style="dim")
        
        # Executor
        exec_status = "🟢" if self.modules['executor'].is_active else "⚪"
        arch_text.append(f"{exec_status} Order Executor\n", style="bold green")
        arch_text.append("   ↓\n", style="dim")
        
        # Logger
        log_status = "🟢" if self.modules['logger'].is_active else "⚪"
        arch_text.append(f"{log_status} Trade Logger (CSV)\n", style="bold blue")
        
        return Panel(
            arch_text,
            title="[bold]🏗️ SYSTEM ARCHITECTURE[/bold]",
            border_style="white",
            box=box.ROUNDED
        )
    
    def run(self, refresh_rate=1):
        """Avvia il Mission Control."""
        console.clear()
        console.print("[bold cyan]🚀 Avvio LabTrade Mission Control...[/bold cyan]\n")
        time.sleep(1)
        
        with Live(console=console, refresh_per_second=refresh_rate) as live:
            try:
                while True:
                    # Aggiorna dai log
                    self.parse_logs()
                    
                    # Crea layout
                    overview = self.create_system_overview()
                    modules = self.create_modules_grid()
                    architecture = self.create_architecture_diagram()
                    data_flow = self.create_data_flow_panel()
                    
                    # Combina tutto
                    from rich.layout import Layout
                    layout = Layout()
                    layout.split_column(
                        Layout(overview, size=7),
                        Layout(modules, size=12),
                        Layout(architecture, size=13),
                        Layout(data_flow, size=12)
                    )
                    
                    live.update(layout)
                    time.sleep(1 / refresh_rate)
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]👋 Mission Control chiuso.[/yellow]")


if __name__ == "__main__":
    control = MissionControl()
    control.run()
