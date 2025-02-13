import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BandStrategy:
    def __init__(self, 
                 position_size_usd: float = 100,
                 leverage: int = 3,
                 tp_multiplier: float = 2.0,
                 sl_multiplier: float = 1.0):
        """Initialize the band strategy with configurable parameters."""
        self.position_size_usd = position_size_usd
        self.leverage = leverage
        self.tp_multiplier = tp_multiplier
        self.sl_multiplier = sl_multiplier
        self.active_position = None
        self.last_signal_candle = None
        self.pending_signal = None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate SMA 21 and EMA 34 indicators."""
        if df.empty:
            return df

        df['EMA34'] = df['close'].ewm(span=34, adjust=False).mean()
        df['SMA21'] = df['close'].rolling(window=21).mean()

        # Calculate upper and lower bands
        df['upper_band'] = df[['EMA34', 'SMA21']].max(axis=1)
        df['lower_band'] = df[['EMA34', 'SMA21']].min(axis=1)

        return df.dropna()

    def get_signal(self, df: pd.DataFrame) -> Optional[str]:
        """
        Generate trading signal based on price position relative to bands.
        Signal is generated when price closes outside the bands and executed on next candle.
        """
        if len(df) < 2:  # Need at least previous and current candle
            return None

        # Get the last two candles
        current = df.iloc[-1]
        prev = df.iloc[-2]

        # Enhanced logging for signal analysis
        logger.info("\n=== Signal Analysis ===")
        logger.info(f"Previous Candle Time: {prev.name}")
        logger.info(f"Previous Close: ${prev['close']:.4f}")
        logger.info(f"Previous Upper Band: ${prev['upper_band']:.4f}")
        logger.info(f"Previous Lower Band: ${prev['lower_band']:.4f}")
        logger.info(f"Distance from Upper: ${(prev['upper_band'] - prev['close']):.4f}")
        logger.info(f"Distance from Lower: ${(prev['close'] - prev['lower_band']):.4f}")
        logger.info(f"Outside Bands: {'Above' if prev['close'] > prev['upper_band'] else 'Below' if prev['close'] < prev['lower_band'] else 'No'}")

        logger.info(f"\nCurrent Candle Time: {current.name}")
        logger.info(f"Has Pending Signal: {self.pending_signal is not None}")
        if self.last_signal_candle:
            logger.info(f"Last Signal Time: {self.last_signal_candle}")

        # Check if current candle is exactly the next one after signal
        if self.pending_signal and self.last_signal_candle:
            expected_next_candle = self.last_signal_candle + timedelta(minutes=5)  # 5-minute timeframe
            current_time = current.name.to_pydatetime()

            logger.info(f"\n=== Execution Check ===")
            logger.info(f"Current candle time: {current_time}")
            logger.info(f"Expected next candle: {expected_next_candle}")

            if current_time == expected_next_candle:
                logger.info(f">>> EXECUTING {self.pending_signal.upper()} signal now!")
                signal = self.pending_signal
                self.pending_signal = None
                self.last_signal_candle = None
                return signal
            elif current_time > expected_next_candle:
                logger.info("Missed execution window, discarding signal")
                self.pending_signal = None
                self.last_signal_candle = None
            return None

        # Check if the previous candle closed outside the bands
        prev_above_bands = prev['close'] > prev['upper_band']
        prev_below_bands = prev['close'] < prev['lower_band']

        # Generate new signal if previous candle closed outside bands
        if prev_above_bands or prev_below_bands:
            self.pending_signal = 'long' if prev_above_bands else 'short'
            self.last_signal_candle = prev.name.to_pydatetime()
            logger.info(f"\n!!! New {self.pending_signal.upper()} signal generated !!!")
            logger.info(f"Signal Time: {self.last_signal_candle}")
            logger.info(f"Signal Price: ${prev['close']:.4f}")
            logger.info(f"Band Distance: ${abs(prev['upper_band'] - prev['lower_band']):.4f}")
            logger.info(f"Will execute at the start of {self.last_signal_candle + timedelta(minutes=5)}")

        return None

    def calculate_entry_levels(self, 
                             current_price: float, 
                             bands: Dict[str, float], 
                             is_long: bool) -> Tuple[float, float]:
        """Calculate take profit and stop loss levels based on band position."""
        band_distance = abs(bands['upper'] - bands['lower'])

        if is_long:
            tp_distance = band_distance * self.tp_multiplier
            sl_distance = band_distance * self.sl_multiplier
            tp_price = current_price + tp_distance
            sl_price = current_price - sl_distance
        else:
            tp_distance = band_distance * self.tp_multiplier
            sl_distance = band_distance * self.sl_multiplier
            tp_price = current_price - tp_distance
            sl_price = current_price + sl_distance

        return round(tp_price, 4), round(sl_price, 4)

    def calculate_position_size(self, 
                              current_price: float,
                              market_info: Dict) -> float:
        """
        Calculate the position size in contracts based on USD size and leverage.
        """
        contract_value = float(market_info['contractValue'])
        min_size = float(market_info['minSize'])
        
        # Calculate the number of contracts needed
        contracts = (self.position_size_usd * self.leverage) / (current_price * contract_value)
        
        # Round down to the minimum contract size
        contracts = max(min_size, round(contracts / min_size) * min_size)
        
        return contracts
    
    def should_close_position(self, 
                            df: pd.DataFrame, 
                            position: Dict) -> bool:
        """
        Check if the current position should be closed based on band crossover.
        """
        if not position:
            return False
        
        latest = df.iloc[-1]
        is_long = position['side'] == 'buy'
        
        # Close long if price crosses below bands
        if is_long and latest['close'] < min(latest['EMA34'], latest['SMA21']):
            return True
        
        # Close short if price crosses above bands
        if not is_long and latest['close'] > max(latest['EMA34'], latest['SMA21']):
            return True
        
        return False