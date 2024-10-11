import os
import requests
from influxdb import InfluxDBClient
import pandas as pd
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging to record events and errors
logging.basicConfig(
    filename='influxdb_monitor.log',  # Log file location
    level=logging.INFO,  # Log level set to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log message format
    datefmt='%Y-%m-%d %H:%M:%S'  # Date format in logs
)

# InfluxDB connection parameters
INFLUXDB_HOST = os.getenv('INFLUXDB_HOST')  # IP address of the InfluxDB server
INFLUXDB_PORT = int(os.getenv('INFLUXDB_PORT', 8086))  # Port where InfluxDB is listening, default to 8086
INFLUXDB_DATABASE = os.getenv('INFLUXDB_DATABASE')  # Name of the InfluxDB database
INFLUXDB_MEASUREMENT = os.getenv('INFLUXDB_MEASUREMENT')  # Measurement/table within the database

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # Telegram bot token for authentication
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')  # Telegram chat ID to send alerts
TELEGRAM_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'  # Telegram API URL for sending messages

# Device name mapping
device_name_map = {
    'pilotdevice'  : 'ED0',
    'pilotdevice01': 'ED1',
    'pilotdevice02': 'ED2',
    'pilotdevice03': 'ED3',
    'pilotdevice04': 'ED4',
    'pilotdevice05': 'ED5'
}

def send_telegram_alert(message: str):
    """
    Sends an alert message to a Telegram chat.
    """
    params = {'chat_id': CHAT_ID, 'text': message}
    try:
        response = requests.post(TELEGRAM_URL, data=params)
        response.raise_for_status()
        logging.info(f"Telegram alert sent: {message}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Telegram alert. Error: {e}")

def query_unique_device_ids(client: InfluxDBClient) -> set:
    """
    Queries InfluxDB to get the unique device IDs from the data.
    """
    try:
        query = f'SELECT DISTINCT("end_device_ids_device_id") FROM {INFLUXDB_MEASUREMENT}'
        result = client.query(query)
        device_ids = {point['distinct'] for point in result.get_points()}
        return device_ids
    except Exception as e:
        logging.error(f"Error querying unique device IDs: {e}")
        return set()

def query_influxdb_for_device(client: InfluxDBClient, device_id: str) -> pd.DataFrame:
    """
    Queries InfluxDB to get the last logged data point for a specific device.
    """
    try:
        query = (
            f'SELECT time, end_device_ids_device_id '
            f'FROM {INFLUXDB_MEASUREMENT} '
            f'WHERE "end_device_ids_device_id" = \'{device_id}\' '
            f'ORDER BY time DESC LIMIT 1'
        )
        result = client.query(query)
        points = list(result.get_points())
        return pd.DataFrame(points)
    except Exception as e:
        logging.error(f"Error querying data for device '{device_id}': {e}")
        return pd.DataFrame()

def check_and_alert_for_device(client: InfluxDBClient, device_id: str):
    """
    Checks the last log time for a device and sends an alert if it exceeds 5 minutes.
    """
    df = query_influxdb_for_device(client, device_id)
    if not df.empty:
        last_time_utc = pd.to_datetime(df['time'].iloc[0])
        last_time_berlin = last_time_utc.tz_convert('Europe/Berlin')

        # Calculate the time difference
        time_diff = datetime.now(last_time_berlin.tzinfo) - last_time_berlin

        # Check if the time difference is more than 5 minutes
        if time_diff > timedelta(minutes=10):
            # Calculate the exact time difference in hours and minutes
            total_seconds = int(time_diff.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes = (remainder // 60) % 60

            # Map the device ID to the desired name
            mapped_device_id = device_name_map.get(device_id, device_id)

            # Prepare the alert message with the exact time difference in hours and minutes
            alert_message = (
                f"ALERT: Device '{mapped_device_id}' has not logged data for over 10 minutes! "
                f"Last log at: {last_time_berlin}. It has been "
                f"{hours} hours and {minutes} minutes since the last log."
            )
            send_telegram_alert(alert_message)
            logging.warning(alert_message)
    else:
        # Map the device ID to the desired name
        mapped_device_id = device_name_map.get(device_id, device_id)
        logging.warning(f"No data found for Device ID '{mapped_device_id}'.")

def fetch_last_logged_time():
    """
    Fetches the last logged time of data for each unique device from InfluxDB.
    """
    try:
        client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT)
        client.switch_database(INFLUXDB_DATABASE)

        # Get the unique device IDs dynamically from the data
        unique_device_ids = query_unique_device_ids(client)
        if not unique_device_ids:
            logging.error("No unique device IDs found.")
            return

        for device_id in unique_device_ids:
            check_and_alert_for_device(client, device_id)

    except Exception as e:
        logging.error(f"Error fetching last logged time from InfluxDB: {e}")
        send_telegram_alert("ALERT: Error occurred while fetching data from InfluxDB.")

def main():
    """
    Main function to run the InfluxDB monitor.
    """
    logging.info("Starting InfluxDB monitor.")
    fetch_last_logged_time()
    logging.info("InfluxDB monitor run completed.")

if __name__ == "__main__":
    main()
