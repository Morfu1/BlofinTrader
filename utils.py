import logging
from typing import Dict
import json

def setup_logging(level: str = "INFO") -> None:
    """Configure logging"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def load_config(config_path: str = "config.json") -> Dict:
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        raise
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in configuration file: {config_path}")
        raise

def validate_input(
    symbol: str,
    position_size: float,
    leverage: int,
    tp_percentage: float,
    sl_percentage: float
) -> None:
    """Validate user input parameters"""
    if position_size <= 0:
        raise ValueError("Position size must be positive")
    
    if leverage < 1:
        raise ValueError("Leverage must be at least 1")
    
    if tp_percentage <= 0 or sl_percentage <= 0:
        raise ValueError("TP and SL percentages must be positive")
    
    if not symbol.endswith("-USDT"):
        raise ValueError("Symbol must be in format XXX-USDT")
