import os
import requests
import pandas as pd
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging to record events and errors
logging.basicConfig(
    filename='influxdb_reachability.log',  # Log file location
    level=logging.INFO,  # Log level set to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log message format
    datefmt='%Y-%m-%d %H:%M:%S'  # Date format in logs
)

# InfluxDB connection parameters
INFLUXDB_HOST = os.getenv('INFLUXDB_HOST')  # IP address of the InfluxDB server
INFLUXDB_PORT = int(os.getenv('INFLUXDB_PORT', 8086))  # Port where InfluxDB is listening, default to 8086

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # Telegram bot token for authentication
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')  # Telegram chat ID to send alerts
TELEGRAM_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'  # Telegram API URL for sending messages

def send_telegram_alert(message: str):
    """
    Sends an alert message to a specified Telegram chat using the bot.

    Parameters:
    - message (str): The alert message to be sent.
    """
    params = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        response = requests.post(TELEGRAM_URL, data=params, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        logging.info(f"Telegram alert sent: {message}")  # Log successful alert
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Telegram alert. Error: {e}")  # Log any errors during alert sending

def check_influx_reachability() -> bool:
    """
    Verifies if the InfluxDB server is reachable by pinging its /ping endpoint.
    Sends an alert if the server is not reachable.

    Returns:
    - bool: True if InfluxDB is reachable, False otherwise.
    """
    try:
        # Send a GET request to the /ping endpoint of InfluxDB
        response = requests.get(f'http://{INFLUXDB_HOST}:{INFLUXDB_PORT}/ping', timeout=5)
        if response.status_code != 204:
            # If the status code is not 204 (No Content), consider it a failure
            raise Exception(f"InfluxDB ping failed with status code: {response.status_code}")
        logging.info("✅ InfluxDB is reachable.")  # Log successful reachability
        return True  # InfluxDB is reachable
    except Exception as e:
        # Handle any exceptions during the ping request
        logging.error(f"❌ InfluxDB is not reachable: {e}")
        # Get current time in Berlin timezone without timezone abbreviation
        current_time_berlin = pd.Timestamp.now(tz='Europe/Berlin').strftime('%Y-%m-%d %H:%M:%S %Z')
        alert_message = (
            f"🚨 ALERT: InfluxDB is NOT reachable as of {current_time_berlin}."
        )
        send_telegram_alert(alert_message)  # Send the alert via Telegram
        return False  # InfluxDB is not reachable

def main():
    """
    Main function to run the InfluxDB reachability monitor.
    """
    logging.info("Starting InfluxDB reachability monitor.")
    if check_influx_reachability():
        logging.info("InfluxDB is operational.")
    else:
        logging.info("InfluxDB is not reachable. Alert has been sent.")
    logging.info("InfluxDB reachability monitor run completed.")

if __name__ == "__main__":
    main()
