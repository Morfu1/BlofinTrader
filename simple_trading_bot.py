import ccxt
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def place_simple_order(symbol='XRP-USDT', tp_percentage=2.0, sl_percentage=1.0):
    try:
        # Initialize exchange with explicit hedge mode configuration
        exchange = ccxt.blofin({
            'apiKey': os.getenv('BLOFIN_API_KEY'),
            'secret': os.getenv('BLOFIN_API_SECRET'),
            'password': os.getenv('BLOFIN_PASSWORD'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'defaultMarginMode': 'isolated',
                'position_mode': 'net'  # Use one-way mode instead of hedge mode
            }
        })
        exchange.set_sandbox_mode(True)  # Use demo account

        # First, get market data to ensure the exchange is properly initialized
        exchange.load_markets()
        symbol_ccxt = f"{symbol.split('-')[0]}/USDT:USDT"
        market_info = exchange.market(symbol_ccxt)
        logger.info(f"Market info: {market_info}")

        # Get current price
        ticker = exchange.fetch_ticker(symbol_ccxt)
        current_price = float(ticker['last'])
        logger.info(f"Current {symbol} price: ${current_price}")

        # Calculate required position size
        target_position_value = 300  # $300 USD (3x leverage on $100 margin)
        asset_amount = target_position_value / current_price  # How much XRP we need
        contract_size = market_info['contractSize']  # Contract size in XRP
        num_contracts = round(asset_amount / contract_size)  # Number of contracts needed

        # Calculate TP and SL prices (for short position)
        tp_price = current_price * (1 - tp_percentage/100)
        sl_price = current_price * (1 + sl_percentage/100)

        logger.info(f"Calculated position details:")
        logger.info(f"- Target position value: ${target_position_value}")
        logger.info(f"- {symbol.split('-')[0]} amount needed: {asset_amount:.4f}")
        logger.info(f"- Contract size: {contract_size} {symbol.split('-')[0]}")
        logger.info(f"- Number of contracts: {num_contracts}")
        logger.info(f"- Take Profit price: ${tp_price:.2f} ({tp_percentage}%)")
        logger.info(f"- Stop Loss price: ${sl_price:.2f} ({sl_percentage}%)")

        # Prepare order parameters
        params = {
            'instId': symbol,
            'marginMode': "isolated",
            'side': "sell",
            'size': str(num_contracts),
            'clientOrderId': "",
            'orderType': "market",
            'tdMode': 'isolated',
            'tpTriggerPrice': str(tp_price),
            'tpOrderPrice': "-1",  # Market price for TP execution
            'slTriggerPrice': str(sl_price),
            'slOrderPrice': "-1"   # Market price for SL execution
        }

        logger.info(f"Placing order with parameters: {params}")

        # Place the order
        order = exchange.privatePostTradeOrder(params)
        logger.info(f"Order placed successfully: {order}")

        # Fetch the actual position to verify the size
        positions = exchange.fetch_positions([symbol_ccxt])
        logger.info(f"Current positions after order: {positions}")

        return order

    except Exception as e:
        logger.error(f"Error placing order: {str(e)}")
        raise

if __name__ == "__main__":
    place_simple_order(symbol='XRP-USDT', tp_percentage=2.0, sl_percentage=1.0)