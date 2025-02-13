import hmac
import hashlib
import time
import requests
import json
import logging
from typing import Dict, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket

class BlofinAPI:
    def __init__(self, api_key: str, api_secret: str, base_url: str, password: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.password = password
        self.base_url = base_url.rstrip('/')  # Remove trailing slash if present
        self.session = self._create_session()
        self.logger = logging.getLogger(__name__)

    def _create_session(self):
        """Create session with custom retry strategy"""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[408, 429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"],
            raise_on_status=True
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """Generate signature for API request"""
        message = str(timestamp) + method.upper() + request_path
        if body:
            message += body

        mac = hmac.new(
            bytes(self.api_secret, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod='sha256'
        )
        return mac.hexdigest()

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """Make API request with authentication and improved error handling"""
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        url = f"{self.base_url}{endpoint}"
        timestamp = str(int(time.time() * 1000))

        headers = {
            'BF-API-KEY': self.api_key,
            'BF-API-TIMESTAMP': timestamp,
            'BF-API-SIGN': '',
            'Content-Type': 'application/json',
            'BF-API-PASSPHRASE': self.password
        }

        body = ''
        if data:
            body = json.dumps(data)

        try:
            signature = self._generate_signature(timestamp, method, endpoint, body)
            headers['BF-API-SIGN'] = signature

            self.logger.debug(f"Making {method} request to {url}")
            self.logger.debug(f"Headers: {headers}")
            self.logger.debug(f"Params: {params}")
            self.logger.debug(f"Body: {body}")

            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data if data else None,
                timeout=30
            )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError as e:
            if isinstance(e.args[0], socket.gaierror):
                self.logger.error(f"DNS resolution failed for {url}: {str(e)}")
                raise ValueError(f"Could not connect to Blofin API. Please check your internet connection and try again.")
            raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response text: {e.response.text}")
            raise

    def place_order(self, symbol: str, side: str, size: float, 
                   take_profit: Optional[float] = None, 
                   stop_loss: Optional[float] = None,
                   leverage: int = 1) -> Dict:
        """Place a new order with optional TP/SL"""
        try:
            # First, set the leverage
            self.set_leverage(symbol, leverage)

            endpoint = "/trade/order"

            # Base order data
            data = {
                "instId": symbol,
                "tdMode": "isolated",  # Use isolated margin mode
                "side": side,
                "ordType": "market",
                "sz": str(size)
            }

            # Add take profit and stop loss if provided
            if take_profit is not None:
                data.update({
                    "tpTriggerPrice": str(take_profit),
                    "tpOrderPrice": "-1"  # Market price execution for TP
                })

            if stop_loss is not None:
                data.update({
                    "slTriggerPrice": str(stop_loss),
                    "slOrderPrice": "-1"  # Market price execution for SL
                })

            self.logger.info(f"Placing order with data: {data}")
            return self._request('POST', endpoint, data=data)

        except Exception as e:
            self.logger.error(f"Failed to place order for {symbol}: {str(e)}")
            raise

    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for a symbol"""
        try:
            endpoint = "/account/set-leverage"
            data = {
                "instId": symbol,
                "lever": str(leverage)
            }
            return self._request('POST', endpoint, data=data)
        except Exception as e:
            self.logger.error(f"Failed to set leverage for {symbol}: {str(e)}")
            raise

    def get_ticker_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            endpoint = "/market/ticker"
            params = {"instId": symbol}
            response = self._request('GET', endpoint, params=params)

            if not response or 'data' not in response:
                raise ValueError(f"Invalid response format from API: {response}")

            data = response['data']
            if not isinstance(data, list) or len(data) == 0:
                raise ValueError(f"No ticker data received for {symbol}")

            ticker_data = data[0]
            price = ticker_data.get('last')
            if not price:
                raise ValueError(f"No price data found for {symbol}")

            return float(price)

        except Exception as e:
            self.logger.error(f"Failed to get ticker price for {symbol}: {str(e)}")
            raise