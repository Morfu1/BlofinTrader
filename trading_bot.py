import os
import logging
import time
from typing import Dict, Optional
import pandas as pd
from datetime import datetime
from strategy import BandStrategy
from blofin_api import BlofinAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_bot.log')
    ]
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self,
                 symbol: str = "BTC-USDT",
                 position_size_usd: float = 100,
                 leverage: int = 3,
                 tp_multiplier: float = 2.0,
                 sl_multiplier: float = 1.0):
        """Initialize the trading bot with configuration."""
        logger.info(f"Initializing trading bot for {symbol}")
        self.symbol = symbol
        self.api = BlofinAPI(
            api_key=os.getenv('BLOFIN_API_KEY'),
            api_secret=os.getenv('BLOFIN_SECRET_KEY'),
            password=os.getenv('BLOFIN_API_PASSPHRASE'),
            base_url="https://demo-trading-openapi.blofin.com"
        )
        self.strategy = BandStrategy(
            position_size_usd=position_size_usd,
            leverage=leverage,
            tp_multiplier=tp_multiplier,
            sl_multiplier=sl_multiplier
        )
        self.running = False
        logger.info("Trading bot initialized successfully")

    def fetch_ohlcv(self) -> pd.DataFrame:
        """Fetch recent OHLCV data for analysis."""
        try:
            logger.debug(f"Fetching OHLCV data for {self.symbol}")
            response = self.api._request(
                'GET',
                '/api/v1/market/candles',
                params={
                    'instId': self.symbol,
                    'bar': '5m',  # 5-minute timeframe
                    'limit': '300'
                }
            )

            if not response or 'data' not in response:
                logger.error("Invalid API response format")
                return pd.DataFrame()

            # Convert to DataFrame
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'vol', 'volCurrency', 'volCurrencyQuote', 'confirm']
            df = pd.DataFrame(response['data'], columns=columns)

            # Convert timestamp to datetime and set as index
            df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)

            # Convert price columns to numeric
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col])

            logger.debug(f"Retrieved {len(df)} candles")

            # Calculate indicators and bands
            df = self.strategy.calculate_indicators(df)

            # Log the last few candles with band information
            last_candles = df.tail(3)
            logger.info("\nLast 3 candles:")
            for idx, row in last_candles.iterrows():
                logger.info(
                    f"Time: {idx.strftime('%Y-%m-%d %H:%M:%S')}, "
                    f"Close: ${row['close']:.4f}, "
                    f"Upper: ${row['upper_band']:.4f}, "
                    f"Lower: ${row['lower_band']:.4f}"
                )

            return df

        except Exception as e:
            logger.error(f"Error fetching OHLCV data: {str(e)}")
            return pd.DataFrame()

    def execute_trade(self, signal: str, current_price: float) -> bool:
        """Execute a trade based on the signal."""
        try:
            logger.info(f"Executing {signal} trade at ${current_price:.4f}")
            logger.info(f"Signal was generated at {self.strategy.last_signal_candle}")

            # Calculate band levels for TP/SL
            df = self.fetch_ohlcv()
            if df.empty:
                logger.error("Cannot execute trade: No OHLCV data available")
                return False

            # Get the latest band levels
            latest = df.iloc[-1]
            bands = {
                'upper': latest['upper_band'],
                'lower': latest['lower_band']
            }

            # Calculate TP/SL levels
            is_long = signal == 'long'
            tp_price, sl_price = self.strategy.calculate_entry_levels(
                current_price,
                bands,
                is_long
            )

            # Set order parameters
            side = "buy" if is_long else "sell"
            size = self.strategy.position_size_usd / current_price

            logger.info(f"Placing {side} order:")
            logger.info(f"Entry Price: ${current_price:.4f}")
            logger.info(f"Band Distance: ${abs(bands['upper'] - bands['lower']):.4f}")
            logger.info(f"Size: {size:.4f}")
            logger.info(f"Take Profit: ${tp_price:.4f}")
            logger.info(f"Stop Loss: ${sl_price:.4f}")

            # Place the order using BlofinAPI
            order_result = self.api.place_order(
                symbol=self.symbol,
                side=side,
                size=size,
                take_profit=tp_price,
                stop_loss=sl_price,
                leverage=self.strategy.leverage
            )

            logger.info(f"Order placed successfully: {order_result}")
            return True

        except Exception as e:
            logger.error(f"Failed to execute trade: {str(e)}")
            return False

    def check_and_close_position(self) -> bool:
        """Check if current position should be closed."""
        try:
            # For now, we'll rely on the TP/SL orders set during position opening
            # Future enhancement: Implement manual position closing based on strategy signals
            return False

        except Exception as e:
            logger.error(f"Error checking position: {str(e)}")
            return False

    def run(self):
        """Run the trading bot."""
        self.running = True
        logger.info(f"Starting trading bot for {self.symbol}")
        logger.info("Strategy configuration:")
        logger.info(f"Position size: ${self.strategy.position_size_usd}")
        logger.info(f"Leverage: {self.strategy.leverage}x")
        logger.info(f"TP multiplier: {self.strategy.tp_multiplier}")
        logger.info(f"SL multiplier: {self.strategy.sl_multiplier}")

        try:
            while self.running:
                try:
                    start_time = time.time()

                    # Calculate time until next 5-minute candle
                    current_minute = start_time // 60
                    next_candle = ((current_minute // 5) + 1) * 5 * 60
                    wait_time = next_candle - start_time

                    if wait_time > 0:
                        logger.info(f"Waiting {wait_time:.1f} seconds for next candle")
                        time.sleep(wait_time)

                    # Fetch latest data
                    df = self.fetch_ohlcv()
                    if df.empty:
                        logger.warning("No data available, waiting for next iteration")
                        time.sleep(10)
                        continue

                    # Get current price and time
                    current_price = float(df['close'].iloc[-1])
                    current_time = df.index[-1]
                    logger.info(f"\nCurrent time: {current_time}")
                    logger.info(f"Current price: ${current_price:.4f}")

                    # Get signal and execute if conditions are met
                    signal = self.strategy.get_signal(df)
                    if signal:
                        logger.info(f"Executing {signal} signal immediately")

                        if self.execute_trade(signal, current_price):
                            logger.info(f"Trade executed successfully at ${current_price:.4f}")
                        else:
                            logger.warning("Trade execution failed")

                    # Sleep until just before the next candle
                    sleep_time = max(1, 300 - (time.time() % 300) - 2)  # Wake up 2 seconds before next candle
                    logger.info(f"Next candle check in {sleep_time:.1f} seconds")
                    time.sleep(sleep_time)

                except Exception as e:
                    logger.error(f"Error in main loop: {str(e)}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    time.sleep(60)

        except KeyboardInterrupt:
            logger.info("Stopping trading bot...")
            self.running = False

def main():
    """Main entry point for the trading bot."""
    import argparse

    parser = argparse.ArgumentParser(description='Band Strategy Trading Bot')
    parser.add_argument('--symbol', type=str, default='BTC-USDT',
                      help='Trading pair symbol')
    parser.add_argument('--size', type=float, default=100,
                      help='Position size in USD')
    parser.add_argument('--leverage', type=int, default=3,
                      help='Trading leverage')
    parser.add_argument('--tp-mult', type=float, default=2.0,
                      help='Take profit multiplier')
    parser.add_argument('--sl-mult', type=float, default=1.0,
                      help='Stop loss multiplier')

    args = parser.parse_args()

    bot = TradingBot(
        symbol=args.symbol,
        position_size_usd=args.size,
        leverage=args.leverage,
        tp_multiplier=args.tp_mult,
        sl_multiplier=args.sl_mult
    )

    bot.run()

if __name__ == "__main__":
    main()