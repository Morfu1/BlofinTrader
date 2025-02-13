import os
import logging
import pandas as pd
from blofin_api import BlofinAPI
import json
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {str(e)}")
        raise

def calculate_bands(df):
    """Calculate SMA 21 and EMA 34 bands"""
    try:
        logger.info("Calculating bands...")
        df['EMA34'] = df['close'].ewm(span=34, adjust=False).mean()
        df['SMA21'] = df['close'].rolling(window=21).mean()

        # Log band calculation details for verification
        last_row = df.iloc[-1]
        logger.info(f"Latest calculations:")
        logger.info(f"Close price: ${last_row['close']:.4f}")
        logger.info(f"EMA34: ${last_row['EMA34']:.4f}")
        logger.info(f"SMA21: ${last_row['SMA21']:.4f}")

        return df
    except Exception as e:
        logger.error(f"Failed to calculate bands: {str(e)}")
        raise

def analyze_market_conditions(df):
    """Analyze current market conditions based on band positions"""
    try:
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        upper_band = max(latest['EMA34'], latest['SMA21'])
        lower_band = min(latest['EMA34'], latest['SMA21'])
        current_price = latest['close']

        # Determine market condition
        if current_price > upper_band:
            condition = "ABOVE_BANDS"
        elif current_price < lower_band:
            condition = "BELOW_BANDS"
        else:
            condition = "BETWEEN_BANDS"

        # Check for crossovers
        prev_upper = max(prev['EMA34'], prev['SMA21'])
        prev_lower = min(prev['EMA34'], prev['SMA21'])
        prev_price = prev['close']

        crossover = None
        if prev_price <= prev_upper and current_price > upper_band:
            crossover = "BULLISH_CROSSOVER"
        elif prev_price >= prev_lower and current_price < lower_band:
            crossover = "BEARISH_CROSSOVER"

        return {
            'current_price': current_price,
            'upper_band': upper_band,
            'lower_band': lower_band,
            'condition': condition,
            'crossover': crossover,
            'band_distance': upper_band - lower_band,
            'price_to_upper': upper_band - current_price,
            'price_to_lower': current_price - lower_band
        }
    except Exception as e:
        logger.error(f"Failed to analyze market conditions: {str(e)}")
        raise

def main():
    try:
        # Load configuration
        config = load_config()
        logger.info("Configuration loaded successfully")

        # Log API credentials status (without exposing values)
        api_key = os.getenv('BLOFIN_API_KEY')
        api_secret = os.getenv('BLOFIN_SECRET_KEY')
        api_passphrase = os.getenv('BLOFIN_API_PASSPHRASE')

        logger.debug("Checking API credentials...")
        logger.debug(f"API Key present: {bool(api_key)}")
        logger.debug(f"API Secret present: {bool(api_secret)}")
        logger.debug(f"API Passphrase present: {bool(api_passphrase)}")

        if not all([api_key, api_secret, api_passphrase]):
            logger.error("Missing API credentials")
            return

        logger.debug(f"Using base URL: {config['base_url']}")
        api = BlofinAPI(
            api_key=api_key,
            api_secret=api_secret,
            password=api_passphrase,
            base_url=config['base_url']
        )

        # Fetch OHLCV data for XRP-USDT
        symbol = "XRP-USDT"  # Changed from BTC-USDT to XRP-USDT
        logger.info(f"Fetching OHLCV data for {symbol}")

        try:
            response = api._request(
                'GET',
                '/api/v1/market/candles',
                params={
                    'instId': symbol,
                    'bar': '5m',  # Changed from '1m' to '5m' for 5-minute timeframe
                    'limit': '300'
                }
            )
            logger.debug(f"API Response Status: {bool(response)}")
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return

        if not response or 'data' not in response:
            logger.error(f"Invalid API response format: {response}")
            return

        # Convert to DataFrame with proper timestamp handling
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'vol', 'volCurrency', 'volCurrencyQuote', 'confirm']
        df = pd.DataFrame(response['data'], columns=columns)

        # Convert timestamp to datetime and set as index
        df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)

        # Convert price columns to numeric
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col])

        logger.info(f"Successfully loaded {len(df)} candles")

        # Calculate bands
        df = calculate_bands(df)

        # Print the last few candles with bands (showing more recent ones)
        last_rows = df.tail(10)  # Show last 10 candles instead of 5
        logger.info("\nLast 10 candles with bands:")
        for idx, row in last_rows.iterrows():
            logger.info(
                f"Time: {idx.strftime('%Y-%m-%d %H:%M:%S')}, "  # Include seconds in timestamp
                f"Close: ${row['close']:.4f}, "
                f"EMA34: ${row['EMA34']:.4f}, "
                f"SMA21: ${row['SMA21']:.4f}"
            )

        # Analyze market conditions
        analysis = analyze_market_conditions(df)

        logger.info("\nCurrent Market Analysis:")
        logger.info(f"Time: {df.index[-1].strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Price: ${analysis['current_price']:.4f}")
        logger.info(f"Upper band: ${analysis['upper_band']:.4f}")
        logger.info(f"Lower band: ${analysis['lower_band']:.4f}")
        logger.info(f"Band distance: ${analysis['band_distance']:.4f}")
        logger.info(f"Distance to upper: ${analysis['price_to_upper']:.4f}")
        logger.info(f"Distance to lower: ${analysis['price_to_lower']:.4f}")
        logger.info(f"Market condition: {analysis['condition']}")
        if analysis['crossover']:
            logger.info(f"Signal: {analysis['crossover']}")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()