"""
Binance Testnet Client
Gestisce connessione e operazioni su Binance Testnet
"""
import os
import time
from collections import deque
import hmac
import hashlib
import requests
from typing import Dict, List, Optional
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)


class BinanceTestnetClient:
    """Client per Binance Testnet Futures"""
    
    BASE_URL = "https://testnet.binancefuture.com"
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        """
        Inizializza client con API keys
        
        Args:
            api_key: API key (se None, legge da .env)
            api_secret: API secret (se None, legge da .env)
        """
        self.api_key = api_key or os.getenv("BINANCE_TESTNET_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_TESTNET_API_SECRET")
        
        if not self.api_key or not self.api_secret:
            logger.warning("API keys non trovate. Modalità dry-run attiva.")
        
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key or ""
        })
        
        # Rate limiting: max 10 richieste/secondo
        self.request_times = deque(maxlen=10)
        
        # Rate limiting: max 10 richieste/secondo
        self.request_times = deque(maxlen=10)
        
    def _generate_signature(self, query_string: str) -> str:
        """Genera firma HMAC SHA256"""
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        """
        Effettua richiesta HTTP con retry automatico
        
        Args:
            method: HTTP method (GET/POST/DELETE)
            endpoint: Endpoint API
            params: Parametri query
            signed: Se richiesta firmata
            
        Returns:
            Response JSON
        """
        # Rate limiting: aspetta se necessario
        current_time = time.time()
        if len(self.request_times) == 10:
            oldest_request = self.request_times[0]
            elapsed = current_time - oldest_request
            if elapsed < 1.0:
                sleep_time = 1.0 - elapsed
                logger.debug(f"⏳ Rate limiting: sleep {sleep_time:.2f}s")
                time.sleep(sleep_time)
        self.request_times.append(time.time())
        
        # Rate limiting: aspetta se necessario
        current_time = time.time()
        if len(self.request_times) == 10:
            oldest_request = self.request_times[0]
            elapsed = current_time - oldest_request
            if elapsed < 1.0:
                sleep_time = 1.0 - elapsed
                logger.debug(f"⏳ Rate limiting: sleep {sleep_time:.2f}s")
                time.sleep(sleep_time)
        self.request_times.append(time.time())
        
        if params is None:
            params = {}
        
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            query_string = urlencode(params)
            params["signature"] = self._generate_signature(query_string)
        
        url = f"{self.BASE_URL}{endpoint}"
        
        # Retry logic con backoff esponenziale
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if method == "GET":
                    response = self.session.get(url, params=params, timeout=10)
                elif method == "POST":
                    response = self.session.post(url, params=params, timeout=10)
                elif method == "DELETE":
                    response = self.session.delete(url, params=params, timeout=10)
                else:
                    raise ValueError(f"Method {method} non supportato")
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Errore richiesta (tentativo {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff esponenziale
                else:
                    raise
    
    def get_account_balance(self) -> Dict:
        """
        Ottieni saldo account
        
        Returns:
            Dict con saldo disponibile
        """
        try:
            response = self._make_request("GET", "/fapi/v2/balance", signed=True)
            # Filtra solo asset con saldo > 0
            balances = {item["asset"]: float(item["balance"]) for item in response if float(item["balance"]) > 0}
            return balances
        except Exception as e:
            logger.error(f"Errore ottenimento saldo: {e}")
            return {}
    
    def get_open_positions(self, symbol: str = None) -> List[Dict]:
        """
        Ottieni posizioni aperte
        
        Args:
            symbol: Se specificato, filtra per simbolo
            
        Returns:
            Lista posizioni aperte
        """
        try:
            response = self._make_request("GET", "/fapi/v2/positionRisk", signed=True)
            positions = []
            for pos in response:
                if float(pos["positionAmt"]) != 0:
                    if symbol is None or pos["symbol"] == symbol:
                        positions.append({
                            "symbol": pos["symbol"],
                            "side": "LONG" if float(pos["positionAmt"]) > 0 else "SHORT",
                            "amount": abs(float(pos["positionAmt"])),
                            "entry_price": float(pos["entryPrice"]),
                            "mark_price": float(pos["markPrice"]),
                            "unrealized_pnl": float(pos["unRealizedProfit"])
                        })
            return positions
        except Exception as e:
            logger.error(f"Errore ottenimento posizioni: {e}")
            return []
    
    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, 
                    price: float = None, stop_price: float = None) -> Dict:
        """
        Invia ordine
        
        Args:
            symbol: Simbolo trading (es. BTCUSDT)
            side: BUY o SELL
            order_type: MARKET, LIMIT, STOP_MARKET, TAKE_PROFIT_MARKET
            quantity: Quantità
            price: Prezzo (per LIMIT)
            stop_price: Stop price (per STOP_MARKET, TAKE_PROFIT_MARKET)
            
        Returns:
            Response ordine
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity
        }
        
        if price:
            params["price"] = price
        if stop_price:
            params["stopPrice"] = stop_price
        
        try:
            response = self._make_request("POST", "/fapi/v1/order", params=params, signed=True)
            
            # Verifica stato ordine
            status = response.get("status", "UNKNOWN")
            if status in ["NEW", "PARTIALLY_FILLED"]:
                logger.info(f"⏳ Ordine {order_type} in stato {status}: {side} {quantity} {symbol}")
            elif status == "FILLED":
                logger.info(f"✅ Ordine eseguito: {side} {quantity} {symbol} @ {order_type}")
            elif status in ["CANCELED", "REJECTED", "EXPIRED"]:
                logger.error(f"❌ Ordine {status}: {side} {quantity} {symbol}")
                return {"error": f"Ordine {status}", "response": response}
            
            return response
        except Exception as e:
            logger.error(f"Errore invio ordine: {e}")
            return {"error": str(e)}
    
    def close_position(self, symbol: str, side: str, quantity: float) -> Dict:
        """
        Chiudi posizione
        
        Args:
            symbol: Simbolo
            side: BUY (per chiudere SHORT) o SELL (per chiudere LONG)
            quantity: Quantità da chiudere
            
        Returns:
            Response chiusura
        """
        return self.place_order(symbol, side, "MARKET", quantity)
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """
        Cancella tutti gli ordini per un simbolo
        
        Args:
            symbol: Simbolo
            
        Returns:
            Response cancellazione
        """
        try:
            response = self._make_request("DELETE", "/fapi/v1/allOpenOrders", params={"symbol": symbol}, signed=True)
            logger.info(f"Tutti gli ordini cancellati per {symbol}")
            return response
        except Exception as e:
            logger.error(f"Errore cancellazione ordini: {e}")
            return {"error": str(e)}
    
    def get_ticker_price(self, symbol: str) -> float:
        """
        Ottieni prezzo attuale
        
        Args:
            symbol: Simbolo
            
        Returns:
            Prezzo attuale
        """
        try:
            response = self._make_request("GET", "/fapi/v1/ticker/price", params={"symbol": symbol})
            return float(response["price"])
        except Exception as e:
            logger.error(f"Errore ottenimento prezzo: {e}")
            return 0.0
    
    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> List[List]:
        """
        Scarica candele (klines) da Binance Futures
        
        Args:
            symbol: Simbolo (es. BTCUSDT)
            interval: Intervallo tempo (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
            limit: Numero di candele (max 1500)
            
        Returns:
            Lista di klines: [[open_time, open, high, low, close, volume, close_time, ...], ...]
        """
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        try:
            response = self._make_request("GET", "/fapi/v1/klines", params=params)
            return response
        except Exception as e:
            logger.error(f"Errore download klines: {e}")
            return []
    
    def get_historical_klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> List[List]:
        """
        Alias per get_klines - scarica candele storiche
        
        Args:
            symbol: Simbolo
            interval: Intervallo tempo
            limit: Numero di candele
            
        Returns:
            Lista di klines
        """
        return self.get_klines(symbol, interval, limit)
