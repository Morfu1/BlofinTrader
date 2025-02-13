import os
import logging
from twilio.rest import Client
from typing import Optional

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        """Initialize Twilio client for notifications."""
        self.enabled = False
        try:
            self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
            self.to_number = os.getenv('NOTIFICATION_PHONE_NUMBER')
            
            if all([self.account_sid, self.auth_token, self.from_number, self.to_number]):
                self.client = Client(self.account_sid, self.auth_token)
                self.enabled = True
                logger.info("SMS notifications enabled")
            else:
                logger.warning("SMS notifications disabled: missing configuration")
        
        except Exception as e:
            logger.error(f"Failed to initialize notification service: {str(e)}")
            self.enabled = False

    def send_notification(self, message: str) -> bool:
        """Send SMS notification."""
        if not self.enabled:
            logger.warning("Notification service is not enabled")
            return False

        try:
            self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=self.to_number
            )
            logger.info(f"SMS notification sent: {message}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send SMS notification: {str(e)}")
            return False

    def notify_signal(self, symbol: str, signal: str, price: float, 
                     tp_price: Optional[float] = None, 
                     sl_price: Optional[float] = None) -> bool:
        """Send notification for trading signal."""
        message = f"Trading Signal: {signal.upper()} {symbol} @ ${price:.2f}"
        if tp_price:
            message += f"\nTake Profit: ${tp_price:.2f}"
        if sl_price:
            message += f"\nStop Loss: ${sl_price:.2f}"
        return self.send_notification(message)

    def notify_position_closed(self, symbol: str, side: str, 
                             entry_price: float, exit_price: float, 
                             pnl: float) -> bool:
        """Send notification for position closure."""
        message = (
            f"Position Closed: {side.upper()} {symbol}\n"
            f"Entry: ${entry_price:.2f}\n"
            f"Exit: ${exit_price:.2f}\n"
            f"PnL: ${pnl:.2f} ({(pnl/entry_price)*100:.2f}%)"
        )
        return self.send_notification(message)
