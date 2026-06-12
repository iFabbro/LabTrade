#!/usr/bin/env python3
"""
Paper Trading Runner
Script principale per eseguire paper trading su Binance Testnet
"""
import argparse
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Aggiungi root directory al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.live_executor import LiveExecutor

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/paper_trading.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Funzione principale"""
    # Carica variabili d'ambiente
    load_dotenv()
    
    # Parser argomenti
    parser = argparse.ArgumentParser(description="Paper Trading su Binance Testnet")
    parser.add_argument("--symbol", default="BTCUSDT", help="Simbolo trading (default: BTCUSDT)")
    parser.add_argument("--timeframe", default="1h", choices=["1h", "4h", "1d"], help="Timeframe (default: 1h)")
    parser.add_argument("--hours", type=int, default=24, help="Ore di esecuzione (default: 24)")
    parser.add_argument("--dry-run", action="store_true", help="Modalità dry-run (no ordini reali)")
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("🚀 LABTRADE - PAPER TRADING SYSTEM")
    logger.info("="*60)
    logger.info(f"Symbol: {args.symbol}")
    logger.info(f"Timeframe: {args.timeframe}")
    logger.info(f"Duration: {args.hours} hours")
    logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE (Testnet)'}")
    logger.info("="*60)
    
    # Crea ed esegui executor
    executor = LiveExecutor(
        symbol=args.symbol,
        timeframe=args.timeframe,
        hours=args.hours,
        dry_run=args.dry_run
    )
    
    try:
        executor.run()
    except Exception as e:
        logger.error(f"❌ Errore fatale: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("✅ Paper trading completato con successo")


if __name__ == "__main__":
    main()
