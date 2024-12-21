import json
import os

USER_DATA_FILE = 'user_data.json'

def load_user_data(user_id):
    """
    Load user data from the JSON file. If the user_id does not exist in the file, it initializes the user with default values.
    """
    user_data = {}
    try:
        # Check if the user data file exists
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as file:
                user_data = json.load(file)
        # Initialize user if not present
        if user_id not in user_data:
            user_data[user_id] = {"default_tickers": "", "default_watch_list": ""}
    except json.decoder.JSONDecodeError:
        print("Error: Corrupt JSON file. Reinitializing data.")
        user_data = {user_id: {"default_tickers": "", "default_watch_list": ""}}
    except Exception as e:
        print(f"Error loading user data: {e}")
    return user_data

def save_user_data(user_id, data):
    """
    Save user data to the JSON file. If the file does not exist, it creates one.
    """
    try:
        user_data = {}
        # Load existing data if file exists
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as file:
                user_data = json.load(file)
        # Update or add the user data
        user_data[user_id] = data
        # Save the updated data
        with open(USER_DATA_FILE, 'w') as file:
            json.dump(user_data, file, indent=4)
    except json.decoder.JSONDecodeError:
        print("Error: Corrupt JSON file. Unable to save data.")
    except Exception as e:
        print(f"Error saving user data: {e}")
