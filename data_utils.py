import json
import os

DATA_FILE = 'data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            try:
                data = json.load(file)
                if "historical_data" not in data:
                    data["historical_data"] = {}
                if "last_updated" not in data:
                    data["last_updated"] = None
            except json.decoder.JSONDecodeError as e:
                data = {"default_tickers": "", "default_watch_list": "", "historical_data": {}, "last_updated": None}
    else:
        data = {"default_tickers": "", "default_watch_list": "", "historical_data": {}, "last_updated": None}
    return data

def save_data(data):
    try:
        with open(DATA_FILE, 'w') as file:
            json.dump(data, file, indent=4, default=str)
    except TypeError as e:
        print(f"Error saving data: {e}")
