import json
import user_data_utils
import datetime
import stock_utils

def load_heatmap_data(user_id):
    try:
        with open(f'heatmap_data_{user_id}.json', 'r') as f:
            heatmap_data = json.load(f)
        return heatmap_data
    except FileNotFoundError:
        print(f"DEBUG: Heatmap data file for user {user_id} not found.")
        return {}
    
def dailytracker():
    user_ids = user_data_utils.get_all_user_ids()
    for user_id in user_ids:
        # Create an entry dictionary
        entry = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "value": 0
        }

        total_value = 0

        heatmap_data = load_heatmap_data(user_id)
        if not heatmap_data:
            continue
        ticker_data = heatmap_data.get('ticker_data', {})
        user_cashflow = float(heatmap_data.get('cash_flow', 0))
        tickers = ticker_data.keys()

        current_prices = stock_utils.get_current_price(list(tickers))

        for ticker, stock_list in ticker_data.items():
            for stock in stock_list:
                number_of_stocks = stock['number_of_stocks']
                current_price = float(current_prices.get(ticker, {}).get('current_price', 0))  # Get the actual price as a float
                total_value += number_of_stocks * current_price

        total_value += user_cashflow

        entry['value'] = total_value

        # JSON file path based on user_id
        json_file_path = f'heatmap_data_{user_id}.json'

        # Read existing entries from the JSON file
        try:
            with open(json_file_path, 'r') as file:
                data = json.load(file)
                if not isinstance(data, dict):
                    data = {"history": []}  # Initialize as an empty history list if data is not a dictionary
        except FileNotFoundError:
            data = {"history": []}

        # Replace the entry for today if it exists, otherwise append it
        history = data.setdefault('history', [])
        for i, existing_entry in enumerate(history):
            if existing_entry['date'] == entry['date']:
                history[i] = entry
                break
        else:
            history.append(entry)

        # Write updated data back to the JSON file
        with open(json_file_path, 'w') as file:
            json.dump(data, file, indent=4)

    return
dailytracker()