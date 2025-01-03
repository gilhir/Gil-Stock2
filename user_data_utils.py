import json
import os

USER_DATA_FILE = 'user_data.json'

def load_user_data(user_id):
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as file:
            try:
                user_data = json.load(file)
                if user_id not in user_data:
                    user_data[user_id] = {"default_tickers": "", "default_watch_list": ""}
            except json.decoder.JSONDecodeError as e:
                user_data = {user_id: {"default_tickers": "", "default_watch_list": ""}}
    else:
        user_data = {user_id: {"default_tickers": "", "default_watch_list": ""}}
    return user_data

def save_user_data(user_id, data):
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as file:
                user_data = json.load(file)
        else:
            user_data = {}
        user_data[user_id] = data
        with open(USER_DATA_FILE, 'w') as file:
            json.dump(user_data, file, indent=4)
    except TypeError as e:
        print(f"Error saving user data: {e}")

def get_all_user_ids():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as file:
            try:
                user_data = json.load(file)
                return list(user_data.keys())
            except json.decoder.JSONDecodeError as e:
                return []
    return []