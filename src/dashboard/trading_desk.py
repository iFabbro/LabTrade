import re
"""
LabTrade Trading Desk - Dashboard Professionale
Mostra posizione aperta, trade storici e performance in tempo reale.
"""
import time
import requests
import json
import csv
import logging
from datetime import datetime
from pathlib import Path
from rich.console import Console

logger = logging.getLogger(__name__)
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich import box

console = Console()


class TradingDesk:
    """Dashboard professionale per monitoraggio trading."""
    
    def __init__(self, log_file="logs/paper_trading.log", trades_file="logs/trades_20260613.csv"):
        self.log_file = Path(log_file)
        self.trades_file = Path(trades_file)
        self.start_time = datetime.now()
        self.last_logs = []
        self.price_cache = None
        self.price_cache_time = 0
        
    def read_logs(self, num_lines=15):
        """Legge le ultime righe del log."""
        if not self.log_file.exists():
            return []
        
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                return lines[-num_lines:]
        except:
            return []
    
    def read_trades(self):
        """Legge i trade da tutti i file CSV nella cartella logs con caching."""
        # Cache: se i file non sono cambiati, ritorna la cache
        logs_dir = Path("logs")
        if not logs_dir.exists():
            return []
        
        trades_files = sorted(logs_dir.glob("trades_*.csv"))
        if not trades_files:
            return []
        
        # Controlla se i file sono cambiati (mtime + size)
        current_signature = [(f.name, f.stat().st_mtime, f.stat().st_size) for f in trades_files]
        
        if hasattr(self, '_trades_cache') and hasattr(self, '_trades_signature'):
            if self._trades_signature == current_signature:
                return self._trades_cache  # Cache hit!
        
        # Cache miss: leggi tutti i file
        trades = []
        for trades_file in trades_files:
            try:
                with open(trades_file, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Filtra solo le righe valide
                        action = row.get('action', '')
                        if action in ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE_LONG', 'CLOSE_SHORT']:
                            # Validazione base
                            try:
                                float(row.get('price', 0))
                                float(row.get('quantity', 0))
                                trades.append(row)
                            except (ValueError, TypeError):
                                logger.warning(f"⚠️ Riga CSV invalida in {trades_file.name}: {row}")
            except csv.Error as e:
                logger.error(f"❌ Errore CSV in {trades_file.name}: {e}")
            except Exception as e:
                logger.error(f"❌ Errore lettura {trades_file.name}: {e}")
        
        # Aggiorna cache
        self._trades_cache = trades
        self._trades_signature = current_signature
        
        return trades
    
    def get_current_position(self, trades):
        """Determina la posizione aperta attuale leggendo dal file di stato."""
        state_file = Path("state/position_state.json")
        
        # Priorità: leggi dal file di stato JSON
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                
                if state.get('position_open', False):
                    # Estrai SL e TP dal file di stato
                    sl = state.get('stop_loss', 0)
                    tp = state.get('take_profit', 0)
                    tp1 = state.get('tp1', 0)
                    tp2 = state.get('tp2', 0)
                    tp3 = state.get('tp3', 0)
                    
                    notes = f"SL=${sl:.2f}, TP=${tp:.2f}"
                    
                    return {
                        'side': state.get('position_side', 'LONG'),
                        'entry_price': state.get('entry_price', 0),
                        'quantity': state.get('position_quantity', 0),
                        'remaining_quantity': state.get('remaining_quantity', state.get('position_quantity', 0)),
                        'timestamp': state.get('entry_time', ''),
                        'notes': notes,
                        'stop_loss': sl,
                        'take_profit': tp,
                        'tp1': tp1,
                        'tp2': tp2,
                        'tp3': tp3,
                        'tp1_hit': state.get('tp1_hit', False),
                        'tp2_hit': state.get('tp2_hit', False),
                        'tp3_hit': state.get('tp3_hit', False)
                    }
            except json.JSONDecodeError as e:
                logger.error(f"❌ File di stato corrotto: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Errore lettura file di stato: {e}")
        
        # Fallback: ricostruisci dal CSV (per retrocompatibilità)
        open_position = None
        for trade in trades:
            action = trade.get('action', '')
            if action in ['OPEN_LONG', 'OPEN_SHORT']:
                open_position = {
                    'side': 'LONG' if action == 'OPEN_LONG' else 'SHORT',
                    'entry_price': float(trade.get('price', 0)),
                    'quantity': float(trade.get('quantity', 0)),
                    'remaining_quantity': float(trade.get('quantity', 0)),
                    'timestamp': trade.get('timestamp', ''),
                    'notes': trade.get('notes', ''),
                    'tp1_hit': False,
                    'tp2_hit': False,
                    'tp3_hit': False
                }
            elif action in ['CLOSE_LONG', 'CLOSE_SHORT']:
                # Controlla se è chiusura completa o parziale
                notes = trade.get('notes', '')
                if 'POSITION CLOSED' in notes or 'STOP_LOSS' in notes:
                    open_position = None  # Chiusura completa
                elif open_position:
                    # Chiusura parziale (TP1 o TP2) - riduci remaining_quantity
                    close_qty = float(trade.get('quantity', 0))
                    open_position['remaining_quantity'] = max(0, open_position.get('remaining_quantity', 0) - close_qty)
                    if 'TP1' in notes:
                        open_position['tp1_hit'] = True
                    elif 'TP2' in notes:
                        open_position['tp2_hit'] = True
        
        return open_position
    
    def get_closed_trades(self, trades):
        """Ottiene le trade complete (aggrega chiusure parziali ladder TP)."""
        closed = []
        
        i = 0
        while i < len(trades):
            trade = trades[i]
            action = trade.get('action', '')
            
            if action in ['OPEN_LONG', 'OPEN_SHORT']:
                # Inizio di una nuova trade
                side = 'LONG' if action == 'OPEN_LONG' else 'SHORT'
                entry_price = float(trade.get('price', 0))
                entry_time = trade.get('timestamp', '')
                total_quantity = float(trade.get('quantity', 0))
                total_pnl = 0.0
                last_exit_time = entry_time
                has_closes = False
                
                # Per calcolare il prezzo medio di uscita
                total_exit_value = 0.0  # Somma di (prezzo × qty) per ogni chiusura
                total_closed_qty = 0.0
                
                # Cerca tutte le chiusure parziali successive
                j = i + 1
                seen_closes = set()  # Evita duplicati
                
                while j < len(trades):
                    close_trade = trades[j]
                    close_action = close_trade.get('action', '')
                    
                    # Se troviamo un altro OPEN, la trade precedente è completa
                    if close_action in ['OPEN_LONG', 'OPEN_SHORT']:
                        break
                    
                    # Se è una chiusura dello stesso lato, aggrega
                    if close_action == f'CLOSE_{side}':
                        # Evita duplicati (stesso timestamp + price + quantity)
                        close_key = (
                            close_trade.get('timestamp', '')[:19],
                            close_trade.get('price', ''),
                            close_trade.get('quantity', '')
                        )
                        
                        if close_key not in seen_closes:
                            seen_closes.add(close_key)
                            total_pnl += float(close_trade.get('pnl', 0))
                            close_price = float(close_trade.get('price', 0))
                            close_qty = float(close_trade.get('quantity', 0))
                            
                            total_exit_value += close_price * close_qty
                            total_closed_qty += close_qty
                            
                            last_exit_time = close_trade.get('timestamp', '')
                            has_closes = True
                    
                    j += 1
                
                # Calcola il prezzo medio ponderato di uscita
                avg_exit_price = total_exit_value / total_closed_qty if total_closed_qty > 0 else entry_price
                
                # Aggiungi solo se ci sono state chiusure (trade completata)
                if has_closes:
                    closed.append({
                        'side': side,
                        'entry': entry_price,
                        'exit': avg_exit_price,  # Prezzo medio ponderato
                        'quantity': total_quantity,
                        'pnl': total_pnl,
                        'entry_time': entry_time,
                        'exit_time': last_exit_time
                    })
                
                # Salta alla prossima trade
                i = j
            else:
                i += 1
        
        return closed
    
    def calculate_performance(self, closed_trades):
        """Calcola metriche di performance complete."""
        if not closed_trades:
            return {
                'total_trades': 0,
                'winning': 0,
                'losing': 0,
                'break_even': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
                'max_drawdown': 0.0
            }
        
        # Validazione input
        try:
            pnls = [float(t['pnl']) for t in closed_trades]
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Errore validazione PnL: {e}")
            return {'total_trades': 0, 'winning': 0, 'losing': 0, 'break_even': 0}
        
        total = len(pnls)
        winning = sum(1 for p in pnls if p > 0)
        losing = sum(1 for p in pnls if p < 0)
        break_even = sum(1 for p in pnls if p == 0)
        
        total_pnl = sum(pnls)
        
        # Calcola medie separate
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        
        # Profit Factor
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy
        win_rate = winning / total if total > 0 else 0
        loss_rate = losing / total if total > 0 else 0
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
        
        # Max Drawdown (semplificato: basato sulla sequenza di PnL)
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            cumulative += p
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        
        return {
            'total_trades': total,
            'winning': winning,
            'losing': losing,
            'break_even': break_even,
            'win_rate': (winning / total * 100) if total > 0 else 0,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / total if total > 0 else 0,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'best_trade': max(pnls) if pnls else 0,
            'worst_trade': min(pnls) if pnls else 0,
            'max_drawdown': max_dd
        }
    

    def get_current_price(self):
        """Ottiene prezzo corrente BTC da Binance (con cache di 5 secondi)."""
        now = time.time()
        if self.price_cache and (now - self.price_cache_time) < 5:
            return self.price_cache
            
        try:
            response = requests.get(
                "https://testnet.binancefuture.com/fapi/v1/ticker/price",
                params={"symbol": "BTCUSDT"},
                timeout=2
            )
            if response.status_code == 200:
                price = float(response.json()["price"])
                self.price_cache = price
                self.price_cache_time = now
                return price
        except requests.RequestException as e:
            logger.debug(f"⚠️ Errore rete prezzo: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Errore imprevisto prezzo: {e}")
        
        # Ritorna l'ultimo prezzo noto se la rete fallisce
        if self.price_cache is None:
            logger.error("❌ Nessun prezzo cache disponibile")
        return self.price_cache
    
    def calculate_live_pnl(self, position):
        """Calcola PnL live della posizione aperta considerando chiusure parziali."""
        if not position:
            return None
        
        current_price = self.get_current_price()
        if not current_price or current_price <= 0:
            return None
        
        entry = position.get('entry_price', 0)
        qty = position.get('quantity', 0)
        side = position.get('side', '')
        
        # Validazione input
        if entry <= 0 or qty <= 0:
            logger.warning(f"⚠️ Input invalidi: entry={entry}, qty={qty}")
            return None
        
        # Usa remaining_quantity se disponibile (considera chiusure parziali)
        remaining_qty = position.get('remaining_quantity', qty)
        if remaining_qty > 0 and remaining_qty < qty:
            qty = remaining_qty  # Usa quantity ridotta dopo TP1/TP2
        
        if side == 'LONG':
            pnl = (current_price - entry) * qty
        else:
            pnl = (entry - current_price) * qty
        
        # Distanza da SL e TP
        notes = position.get('notes', '')
        sl_match = re.search(r'SL=\$?([\d.]+)', notes)
        tp_match = re.search(r'TP=\$?([\d.]+)', notes)
        
        sl = float(sl_match.group(1)) if sl_match else None
        tp = float(tp_match.group(1)) if tp_match else None
        
        sl_dist = ((current_price - sl) / sl * 100) if sl else None
        tp_dist = ((tp - current_price) / current_price * 100) if tp else None
        
        # Leggi TP1, TP2, TP3 dal file di stato
        tp1, tp2, tp3 = tp, tp, tp
        state_file = Path("state/position_state.json")
        if state_file.exists():
            try:
                import json
                with open(state_file, 'r') as sf:
                    state = json.load(sf)
                tp1 = state.get('tp1', tp)
                tp2 = state.get('tp2', tp)
                tp3 = state.get('tp3', tp)
            except:
                pass

        # Leggi stato TP raggiunti dallo state file
        tp1_hit = False
        tp2_hit = False
        tp3_hit = False
        state_file = Path("state/position_state.json")
        if state_file.exists():
            try:
                import json
                with open(state_file, 'r') as sf:
                    state = json.load(sf)
                tp1_hit = state.get('tp1_hit', False)
                tp2_hit = state.get('tp2_hit', False)
                tp3_hit = state.get('tp3_hit', False)
            except:
                pass

        return {
            'current_price': current_price,
            'pnl': pnl,
            'pnl_pct': (pnl / (entry * qty) * 100),
            'sl_dist_pct': sl_dist,
            'tp_dist_pct': tp_dist,
            'sl': sl,
            'tp': tp,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'tp1_hit': tp1_hit,
            'tp2_hit': tp2_hit,
            'tp3_hit': tp3_hit,
            'qty': qty
        }

    def create_header(self):
        """Crea header con uptime e ora."""
        elapsed = datetime.now() - self.start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        header_table = Table.grid(expand=True)
        header_table.add_column(justify="left")
        header_table.add_column(justify="center")
        header_table.add_column(justify="right")
        
        header_table.add_row(
            "[bold cyan]🚀 LABTRADE TRADING DESK[/bold cyan]",
            f"[dim]Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}[/dim]",
            f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        )
        
        return Panel(header_table, border_style="cyan", box=box.DOUBLE)
    
    def create_system_status(self, position):
        """Crea pannello stato sistema."""
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()
        
        # Prezzo corrente sempre visibile
        current_price = self.get_current_price()
        if current_price:
            table.add_row("BTC/USDT:", f"[bold yellow]${current_price:,.2f}[/bold yellow]")
        else:
            table.add_row("BTC/USDT:", "[dim]N/A[/dim]")
        
        table.add_row("Stato:", "[green]ATTIVO[/green]")
        table.add_row("Simbolo:", "BTCUSDT")
        table.add_row("Timeframe:", "1h")
        
        if position:
            table.add_row("", "")
            position_side = position['side']
            position_color = "bold green" if position_side == "LONG" else "bold red" if position_side == "SHORT" else "bold yellow"
            table.add_row("Posizione:", f"[{position_color}]{position_side}[/{position_color}]")
            table.add_row("Entry:", f"${position['entry_price']:.2f}")
            table.add_row("Quantità:", f"{position['quantity']:.3f} BTC")
            
            # PnL live
            live_data = self.calculate_live_pnl(position)
            if live_data:
                pnl_color = "green" if live_data['pnl'] >= 0 else "red"
                pnl_sign = "+" if live_data['pnl'] >= 0 else ""
                table.add_row("", "")
                table.add_row("PnL Live:", f"[bold {pnl_color}]{pnl_sign}${live_data['pnl']:.2f} ({pnl_sign}{live_data['pnl_pct']:.2f}%)[/bold {pnl_color}]")
                
                if live_data and live_data.get('sl') is not None and current_price is not None:
                    sl = live_data['sl']
                    qty = live_data['qty']
                    entry = position['entry_price']
                    
                    sl_dist_pct = abs(current_price - sl) / current_price * 100
                    sl_pnl = (sl - entry) * qty
                    
                    table.add_row("Stop Loss:", f"[red]${sl:,.2f} (-{sl_dist_pct:.2f}% / ${sl_pnl:,.2f})[/red]")
                    
                    # Mostra i 3 TP scalati
                    tp1 = live_data.get('tp1', live_data.get('tp'))
                    tp2 = live_data.get('tp2', live_data.get('tp'))
                    tp3 = live_data.get('tp3', live_data.get('tp'))
                    
                    side = position['side']
                    
                    # Leggi stato TP raggiunti
                    tp1_hit = live_data.get('tp1_hit', False)
                    tp2_hit = live_data.get('tp2_hit', False)
                    tp3_hit = live_data.get('tp3_hit', False)
                    
                    if tp1:
                        tp1_dist = abs(tp1 - entry) / entry * 100
                        if side == "LONG":
                            tp1_pnl = (tp1 - entry) * (qty * 0.33)
                        else:
                            tp1_pnl = (entry - tp1) * (qty * 0.33)
                        
                        if tp1_hit:
                            table.add_row("TP1 (33%):", f"[bold green]✅ ${tp1:,.2f} RAGGIUNTO (+${tp1_pnl:,.2f})[/bold green]")
                        else:
                            table.add_row("TP1 (33%):", f"[green]${tp1:,.2f} (+{tp1_dist:.2f}% / +${tp1_pnl:,.2f})[/green]")
                    
                    if tp2:
                        tp2_dist = abs(tp2 - entry) / entry * 100
                        if side == "LONG":
                            tp2_pnl = (tp2 - entry) * (qty * 0.33)
                        else:
                            tp2_pnl = (entry - tp2) * (qty * 0.33)
                        
                        if tp2_hit:
                            table.add_row("TP2 (33%):", f"[bold green]✅ ${tp2:,.2f} RAGGIUNTO (+${tp2_pnl:,.2f})[/bold green]")
                        else:
                            table.add_row("TP2 (33%):", f"[green]${tp2:,.2f} (+{tp2_dist:.2f}% / +${tp2_pnl:,.2f})[/green]")
                    
                    if tp3:
                        tp3_dist = abs(tp3 - entry) / entry * 100
                        if side == "LONG":
                            tp3_pnl = (tp3 - entry) * (qty * 0.34)
                        else:
                            tp3_pnl = (entry - tp3) * (qty * 0.34)
                        
                        if tp3_hit:
                            table.add_row("TP3 (34%):", f"[bold green]✅ ${tp3:,.2f} RAGGIUNTO (+${tp3_pnl:,.2f})[/bold green]")
                        else:
                            table.add_row("TP3 (34%):", f"[green]${tp3:,.2f} (+{tp3_dist:.2f}% / +${tp3_pnl:,.2f})[/green]")
                        
                elif live_data and live_data.get('sl') is not None:
                    sl = live_data['sl']
                    table.add_row("Stop Loss:", f"[red]${sl:,.2f} (N/A)[/red]")
            else:
                table.add_row("Note:", f"[dim]{position['notes']}[/dim]")
        else:
            table.add_row("", "")
            table.add_row("Posizione:", "[dim]FLAT (in attesa)[/dim]")
        
        return Panel(
            table,
            title="[bold]📊 STATO SISTEMA[/bold]",
            border_style="green",
            box=box.ROUNDED
        )
    
    def create_performance_panel(self, perf):
        """Crea pannello performance."""
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()
        
        table.add_row("Trade Totali:", str(perf['total_trades']))
        table.add_row("Vinti:", f"[green]{perf['winning']}[/green]")
        table.add_row("Persi:", f"[red]{perf['losing']}[/red]")
        table.add_row("Win Rate:", f"{perf['win_rate']:.1f}%")
        table.add_row("", "")
        
        pnl_color = "green" if perf['total_pnl'] >= 0 else "red"
        table.add_row("PnL Totale:", f"[{pnl_color}]${perf['total_pnl']:.2f}[/{pnl_color}]")
        table.add_row("PnL Medio:", f"${perf['avg_pnl']:.2f}")
        table.add_row("Miglior Trade:", f"[green]${perf['best_trade']:.2f}[/green]")
        table.add_row("Peggior Trade:", f"[red]${perf['worst_trade']:.2f}[/red]")
        
        return Panel(
            table,
            title="[bold]📈 PERFORMANCE[/bold]",
            border_style="yellow",
            box=box.ROUNDED
        )
    

    def create_wallet_panel(self, initial_balance: float, realized_pnl: float, unrealized_pnl: float, 
                           max_drawdown: float, closed_trades: list, position: dict):
        """Crea pannello portafoglio avanzato con metriche complete."""
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()
        
        current_balance = initial_balance + realized_pnl + unrealized_pnl
        total_pnl = realized_pnl + unrealized_pnl
        pnl_pct = (total_pnl / initial_balance * 100) if initial_balance > 0 else 0
        
        # Calcola capitale impegnato nella posizione aperta
        capital_committed = 0.0
        if position:
            current_price = self.get_current_price()
            if current_price:
                entry = position.get('entry_price', 0)
                qty = position.get('remaining_quantity', position.get('quantity', 0))
                capital_committed = entry * qty
        
        capital_committed_pct = (capital_committed / current_balance * 100) if current_balance > 0 else 0
        capital_available = current_balance - capital_committed
        
        # Calcola Profit Factor
        gross_profit = 0.0
        gross_loss = 0.0
        for trade in closed_trades:
            pnl = trade.get('pnl', 0)
            if pnl > 0:
                gross_profit += pnl
            elif pnl < 0:
                gross_loss += abs(pnl)
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calcola Expectancy
        total_trades = len(closed_trades)
        expectancy = realized_pnl / total_trades if total_trades > 0 else 0.0
        
        # Saldo Iniziale
        table.add_row("💰 Saldo Iniziale:", f"${initial_balance:,.2f}")
        table.add_row("", "")
        
        # PnL Realizzato
        realized_color = "green" if realized_pnl >= 0 else "red"
        table.add_row("📊 PnL Realizzato:", f"[{realized_color}]${realized_pnl:,.2f}[/{realized_color}]")
        
        # PnL Non Realizzato
        unrealized_color = "green" if unrealized_pnl >= 0 else "red"
        table.add_row("📈 PnL Non Realizzato:", f"[{unrealized_color}]${unrealized_pnl:,.2f}[/{unrealized_color}]")
        table.add_row("", "")
        
        # Saldo Attuale
        balance_color = "green" if current_balance >= initial_balance else "red"
        table.add_row("💵 Saldo Attuale:", f"[{balance_color}]${current_balance:,.2f}[/{balance_color}]")
        
        # Variazione %
        pnl_pct_color = "green" if pnl_pct >= 0 else "red"
        table.add_row("📉 Variazione:", f"[{pnl_pct_color}]{pnl_pct:+.2f}%[/{pnl_pct_color}]")
        table.add_row("", "")
        
        # Capitale Impegnato
        table.add_row("💵 Capitale Impegnato:", f"${capital_committed:,.2f} ({capital_committed_pct:.1f}%)")
        
        # Capitale Disponibile
        available_color = "green" if capital_available > 0 else "red"
        table.add_row("💸 Capitale Disponibile:", f"[{available_color}]${capital_available:,.2f}[/{available_color}]")
        table.add_row("", "")
        
        # Metriche avanzate
        table.add_row("📊 Trade Chiuse:", str(total_trades))
        table.add_row("📈 Profit Factor:", f"{profit_factor:.2f}" if profit_factor != float('inf') else "∞")
        table.add_row("📉 Expectancy:", f"${expectancy:.2f}/trade")
        table.add_row("", "")
        
        # Max Drawdown
        table.add_row("⚠️ Max Drawdown:", f"${max_drawdown:,.2f}")
        
        # Ultimo aggiornamento
        table.add_row("🕐 Ultimo Aggiornamento:", datetime.now().strftime("%H:%M:%S"))
        
        return Panel(
            table,
            title="[bold]💰 PORTAFOGLIO[/bold]",
            border_style="magenta",
            box=box.ROUNDED
        )

    def create_closed_trades_panel(self, closed_trades):
        """Crea pannello trade chiusi."""
        if not closed_trades:
            return Panel(
                "[dim]Nessun trade chiuso ancora[/dim]",
                title="[bold]📜 TRADE CHIUSI[/bold]",
                border_style="blue",
                box=box.ROUNDED
            )
        
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Side", width=6)
        table.add_column("Entry", justify="right", width=10)
        table.add_column("Exit", justify="right", width=10)
        table.add_column("Qty", justify="right", width=8)
        table.add_column("PnL", justify="right", width=10)
        
        for i, trade in enumerate(closed_trades[-10:], 1):  # Ultimi 10 trade
            pnl_color = "green" if trade['pnl'] >= 0 else "red"
            side_color = "green" if trade['side'] == 'LONG' else "red"
            
            table.add_row(
                str(i),
                f"[{side_color}]{trade['side']}[/{side_color}]",
                f"${trade['entry']:.2f}",
                f"${trade['exit']:.2f}",
                f"{trade['quantity']:.3f}",
                f"[{pnl_color}]${trade['pnl']:.2f}[/{pnl_color}]"
            )
        
        return Panel(
            table,
            title="[bold]📜 TRADE CHIUSI (Ultimi 10)[/bold]",
            border_style="blue",
            box=box.ROUNDED
        )
    
    def create_logs_panel(self, logs):
        """Crea pannello log recenti."""
        if not logs:
            return Panel(
                "[dim]Nessun log disponibile[/dim]",
                title="[bold]📝 LOG RECENTI[/bold]",
                border_style="magenta",
                box=box.ROUNDED
            )
        
        log_text = ""
        for line in logs[-12:]:
            line = line.strip()
            if "ERROR" in line:
                log_text += f"[red]{line}[/red]\n"
            elif "WARNING" in line:
                log_text += f"[yellow]{line}[/yellow]\n"
            elif "BUY" in line or "LONG" in line:
                log_text += f"[green]{line}[/green]\n"
            elif "SELL" in line or "SHORT" in line:
                log_text += f"[red]{line}[/red]\n"
            else:
                log_text += f"[cyan]{line}[/cyan]\n"
        
        return Panel(
            log_text,
            title="[bold]📝 LOG RECENTI[/bold]",
            border_style="magenta",
            box=box.ROUNDED
        )
    
    def run(self, refresh_rate=1):
        """Avvia il Trading Desk."""
        console.clear()
        console.print("[bold cyan]🚀 Avvio LabTrade Trading Desk...[/bold cyan]\n")
        time.sleep(1)
        
        with Live(console=console, refresh_per_second=refresh_rate) as live:
            try:
                while True:
                    # Leggi dati
                    logs = self.read_logs()
                    trades = self.read_trades()
                    position = self.get_current_position(trades)
                    closed_trades = self.get_closed_trades(trades)
                    perf = self.calculate_performance(closed_trades)
                    
                    # Calcola dati wallet
                    initial_balance = 10000.0  # Saldo iniziale
                    realized_pnl = perf['total_pnl']  # PnL dalle trade chiuse
                    
                    # PnL non realizzato dalla posizione aperta
                    unrealized_pnl = 0.0
                    if position:
                        current_price = self.get_current_price()
                        if current_price:
                            entry = position.get('entry_price', 0)
                            qty = position.get('remaining_quantity', position.get('quantity', 0))
                            side = position.get('side', 'LONG')
                            if side == 'LONG':
                                unrealized_pnl = (current_price - entry) * qty
                            else:
                                unrealized_pnl = (entry - current_price) * qty
                    
                    max_drawdown = perf.get('max_drawdown', 0.0)
                    
                    # Crea layout
                    header = self.create_header()
                    status = self.create_system_status(position)
                    performance = self.create_performance_panel(perf)
                    wallet = self.create_wallet_panel(initial_balance, realized_pnl, unrealized_pnl, 
                                                       max_drawdown, closed_trades, position)
                    closed = self.create_closed_trades_panel(closed_trades)
                    logs_panel = self.create_logs_panel(logs)
                    
                    # Combina tutto
                    layout = Layout()
                    layout.split_column(
                        Layout(header, size=3),
                        Layout(name="middle"),
                        Layout(name="bottom"),
                        Layout(logs_panel, size=15)
                    )
                    
                    layout["middle"].split_row(
                        Layout(status, size=40),
                        Layout(performance, size=40),
                        Layout(wallet, size=40)
                    )
                    
                    layout["bottom"].split_row(
                        Layout(closed)
                    )
                    
                    live.update(layout)
                    time.sleep(1 / refresh_rate)
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]👋 Trading Desk chiuso.[/yellow]")


if __name__ == "__main__":
    desk = TradingDesk()
    desk.run()
