import logging

from typing import Tuple

class PositionCalculator:
    # Minimum amounts for different trading pairs
    MIN_AMOUNTS = {
        'BTC-USDT': 0.1,
        'ETH-USDT': 1.0,  # Blofin minimum requirement
        'DEFAULT': 1.0  # Conservative default
    }

    @staticmethod
    def get_minimum_amount(symbol: str) -> float:
        """Get minimum position size for a trading pair"""
        return PositionCalculator.MIN_AMOUNTS.get(symbol, PositionCalculator.MIN_AMOUNTS['DEFAULT'])

    @staticmethod
    def calculate_position_size(
        price: float,
        usd_size: float,
        leverage: int,
        symbol: str = 'BTC-USDT'
    ) -> float:
        """Calculate position size in coins based on USD amount"""
        position_size = (usd_size * leverage) / price
        min_amount = PositionCalculator.get_minimum_amount(symbol)

        # Round to 4 decimal places for comparison
        position_size = round(position_size, 4)

        if position_size < min_amount:
            # Adjust position size to minimum required
            position_size = min_amount
            logging.warning(f"Adjusted position size to minimum required amount ({min_amount}) for {symbol}")

        return round(position_size, 8)

    @staticmethod
    def calculate_tp_sl(
        entry_price: float,
        is_long: bool,
        tp_percentage: float,
        sl_percentage: float
    ) -> Tuple[float, float]:
        """Calculate take profit and stop loss prices"""
        if is_long:
            tp_price = entry_price * (1 + tp_percentage / 100)
            sl_price = entry_price * (1 - sl_percentage / 100)
        else:
            tp_price = entry_price * (1 - tp_percentage / 100)
            sl_price = entry_price * (1 + sl_percentage / 100)

        return round(tp_price, 8), round(sl_price, 8)