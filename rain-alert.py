#!/usr/bin/env python3

# Script to run on schedule and check if there is rain predicted in a specific
# location for the next hour. Send a push notification with the details.

import argparse
from datetime import datetime
import logging
import os
import requests
import sys

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Rain alert',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--lat', type=float, required=True, help='Latitude')
    parser.add_argument('--lon', type=float, required=True, help='Longitude')
    parser.add_argument('--icon-cache-dir',
                        default=os.path.expanduser('~/.cache/weather-icons'),
                        help='Icon cache directory')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                        level=log_level)

    if not os.path.exists(args.icon_cache_dir):
        os.makedirs(args.icon_cache_dir)

    # API key for OpenWeatherMap
    openweather_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
    if not openweather_api_key:
        logging.error('OPENWEATHERMAP_API_KEY not found')
        sys.exit(1)

    # API keys for Pushover
    pushover_api_key = os.getenv('PUSHOVER_API_KEY')
    if not pushover_api_key:
        logging.error('PUSHOVER_API_KEY not found')
        sys.exit(1)
    pushover_user_key = os.getenv('PUSHOVER_USER_KEY')
    if not pushover_user_key:
        logging.error('PUSHOVER_USER_KEY not found')
        sys.exit(1)

    URL = (
        "https://api.openweathermap.org/data/3.0/onecall?"
        "lat={LAT}&lon={LON}&exclude=current,minutely,daily,alerts"
        "&appid={API_KEY}"
    ).format(LAT=args.lat, LON=args.lon, API_KEY=openweather_api_key)

    # Get the weather data
    response = requests.get(URL)
    response.raise_for_status()

    # Get next hour's weather
    # If current time more than 15 minutes past the hour, get the next hour's
    # weather also
    forecast_range = 2 if datetime.now().minute > 10 else 1
    next_hour = response.json()["hourly"][:forecast_range]

    # Check if it will rain in the next hour
    for hour in next_hour:
        weather = hour.get("weather", [{}])[0]
        logging.debug(weather)
        if "rain" in weather.get("main", "").lower():
            message = f"Rain alert: {weather['description']} in the next hour"
            icon = weather.get("icon")
            break
    else:
        message = "No rain in the next hour"
        icon = next_hour[0].get("weather", [{}])[0].get("icon")

    logging.info("Message: %s, icon: %s", message, icon)

    # Download icon if not already present in cache
    icon_path = os.path.join(args.icon_cache_dir, f"{icon}.png")
    if not os.path.exists(icon_path):
        icon_url = f"http://openweathermap.org/img/wn/{icon}@2x.png"
        response = requests.get(icon_url)
        if response.status_code != 200:
            logging.error("Failed to download icon: %s", response.text)
            icon_path = None
        else:
            with open(icon_path, "wb") as f:
                f.write(response.content)

    # Send push notification
    pushover_data = {
        "token": pushover_api_key,
        "user": pushover_user_key,
        "message": message,
    }

    files = {}
    if icon_path:
        f = open(icon_path, "rb")
        files["attachment"] = ("image.png", f, "image/png")
        pushover_data["attachment_type"] = "image/png"

    response = requests.post("https://api.pushover.net/1/messages.json",
                             data=pushover_data,
                             files=files)
    response.raise_for_status()
