import os
import datetime
import yfinance as yf
import pandas as pd
import gzip
import pandas_market_calendars as mcal
import json
import pytz


def save_compressed(data, filename):
    """Save data to a compressed JSON file."""
    with gzip.open(filename, "wt", encoding="utf-8") as f:
        json.dump(data, f)


def load_compressed(filename):
    """Load data from a compressed JSON file."""
    if not os.path.exists(filename):
        return {"global_last_updated": None, "historical_data": {}}
    with gzip.open(filename, "rt", encoding="utf-8") as f:
        return json.load(f)
    
def market_is_open_now(date, tz='America/New_York'):
    ny_tz = pytz.timezone(tz)
    now = datetime.datetime.now(ny_tz)
    result = mcal.get_calendar("NYSE").schedule(start_date=now.date(), end_date=date)

    if result.empty:
        return False

    market_open = result.iloc[0]['market_open'].tz_convert(ny_tz).time()
    market_close = result.iloc[0]['market_close'].tz_convert(ny_tz).time()
    current_time = now.time()

    return market_open <= current_time < market_close


def market_is_open(date):
    result = mcal.get_calendar("NYSE").schedule(start_date=date, end_date=date)
    return not result.empty

def next_market_open():
    nyse = mcal.get_calendar("NYSE")
    current_daten = datetime.datetime.now()
    current_date = datetime.datetime.now().date()
    if not market_is_open_now(current_daten):
        current_date += datetime.timedelta(days=1)
    while not market_is_open(current_date.strftime("%Y-%m-%d")):
        current_date += datetime.timedelta(days=1)
    next_open = nyse.schedule(start_date=current_date.strftime("%Y-%m-%d"), end_date=current_date.strftime("%Y-%m-%d"))
    return next_open.iloc[0].market_open.strftime("%Y-%m-%d %H:%M:%S")

current_task = None

def get_current_price(tickers):
    try:
        global current_task
        if current_task == 'fetch_and_store_stock_data':
            return {}
        current_task = 'get_current_prices'
        tickers_yahoo = yf.Tickers(tickers)
        history = tickers_yahoo.history(period="1d")
        if not history.empty:
            # Round the closing prices to two decimal places and format as requested
            prices = history["Close"].iloc[-1].to_dict()
            formatted_prices = { ticker: {"current_price": f"{round(price, 2):.2f}"} for ticker, price in prices.items() if not pd.isna(price) }
            current_task = None
            return formatted_prices
        else:
            current_task = None
            return {ticker: {"current_price": "nan"} for ticker in tickers}
    except Exception as e:
        current_task = None
        print(f"Error fetching prices: {e}")
        return {ticker: {"current_price": "nan"} for ticker in tickers}

def validate_json_structure(data):
    required_keys = {"historical_data", "global_last_updated"}
    if not all(key in data for key in required_keys):
        raise ValueError("Invalid JSON structure: Missing required keys")

def process_ticker_data(ticker, new_data, data, start_date, end_date):
    try:
        validate_json_structure(data)
    except ValueError as e:
        print(e)
        return
    
    stored_data = data["historical_data"].get(ticker, {"prices": [], "last_updated": None})

    if new_data is None or new_data.empty:
        return

    if "Close" not in new_data.columns:
        return

    existing_dates = set(date_str for date_str, _ in stored_data["prices"])

    def find_insert_position(prices, date_str):
        """Find the insert position for a new date using binary search."""
        date_strs = [price[0] for price in prices]
        index = bisect_left(date_strs, date_str)
        return index

    new_prices = [
        (date.strftime("%Y%m%d"), round(row["Close"], 2))
        for date, row in new_data.iterrows()
        if date.strftime("%Y%m%d") not in existing_dates and not pd.isna(row["Close"])
    ]
    
    for new_date_str, new_price in new_prices:
        insert_position = find_insert_position(stored_data["prices"], new_date_str)
        stored_data["prices"].insert(insert_position, (new_date_str, new_price))
    
    stored_data["prices"] = stored_data["prices"][-700:]
    stored_data["last_updated"] = end_date.strftime("%Y-%m-%d")

    data["historical_data"][ticker] = stored_data
    data = sort_historical_data(data)
    save_compressed(data, "optimized_data.json.gz")



def sort_historical_data(data):
    sorted_data = {}
    for ticker in sorted(data.get("historical_data", {})):
        sorted_data[ticker] = data["historical_data"][ticker]
    data["historical_data"] = sorted_data
    return data


from concurrent.futures import ThreadPoolExecutor

from bisect import bisect_left

def find_closest_date(prices, target_date):
    """Find the closest date in a sorted list of prices using binary search."""
    date_strs = [price[0] for price in prices]
    index = bisect_left(date_strs, target_date.strftime("%Y%m%d"))
    if index < len(date_strs) and date_strs[index] == target_date.strftime("%Y%m%d"):
        return index
    elif index > 0:
        return index - 1
    else:
        return -1


def fetch_and_store_stock_data(tickers, period, data_file="optimized_data.json.gz"):
    try:
        data = load_compressed(data_file)
        validate_json_structure(data)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error loading data file: {e}")
        os.remove(data_file)
        return

    # Ensure 'historical_data' key exists in data
    if "historical_data" not in data:
        data["historical_data"] = {}

    end_date = datetime.datetime.now().date()
    start_date = datetime.datetime.now().date() - datetime.timedelta(days=period + 150)

    batch_size = 100
    tickers_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]

    global_last_updated = data.get("global_last_updated", None)
    global_last_updated_date = (
        datetime.datetime.strptime(global_last_updated, "%Y-%m-%d").date()
        if global_last_updated else None
    )

    ny_tz = pytz.timezone('America/New_York')
    ny_time = datetime.datetime.now(ny_tz)
    if ny_time.hour < 16:
        oldest_date = (ny_time - datetime.timedelta(days=1)).date()
    else:
        oldest_date = ny_time.date()


    def binary_search_ticker(tickers, target):
        """Binary search to find the position of the target ticker."""
        lo, hi = 0, len(tickers) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if tickers[mid] < target:
                lo = mid + 1
            elif tickers[mid] > target:
                hi = mid - 1
            else:
                return mid
        return -1

    def preprocess_historical_data(data):
        processed_data = {}
        tickers = list(data["historical_data"].keys())  # Assume tickers are already sorted

        def process_ticker_batch(tickers_batch):
            local_processed_data = {}
            for ticker in tickers_batch:
                index = binary_search_ticker(tickers, ticker)
                if index != -1:
                    ticker_data = data["historical_data"][tickers[index]]
                    prices = ticker_data.get("prices", [])
                    if prices:
                        last_date_str = prices[-1][0]
                        last_date = datetime.datetime.strptime(last_date_str, "%Y%m%d").date()
                        local_processed_data[ticker] = (prices, last_date)
            return local_processed_data

        batch_size = 100  # Adjust as necessary
        ticker_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_ticker_batch, batch) for batch in ticker_batches]
            for future in futures:
                batch_result = future.result()
                processed_data.update(batch_result)
        
        return processed_data


    processed_data = preprocess_historical_data(data)

    def identify_missing_outdated_tickers(tickers, processed_data, period, oldest_date):
        missing_tickers = []
        outdated_tickers = []

        sorted_tickers = sorted(processed_data.keys())

        def check_ticker(ticker):
            index = binary_search_ticker(sorted_tickers, ticker)
            if index == -1:
                return 'missing', ticker, None
            prices, last_date = processed_data[sorted_tickers[index]]
            if len(prices) < period:
                return 'missing', ticker, None
            closest_date_index = find_closest_date(prices, oldest_date)
            if closest_date_index == -1 or datetime.datetime.strptime(prices[closest_date_index][0], "%Y%m%d").date() < oldest_date:
                return 'outdated', ticker, last_date
            return None, None, None

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(check_ticker, ticker) for ticker in tickers]
            for future in futures:
                result_type, ticker, last_date = future.result()
                if result_type == 'missing':
                    missing_tickers.append(ticker)
                elif result_type == 'outdated':
                    outdated_tickers.append(ticker)
                    if last_date and last_date < oldest_date:
                        oldest_date = last_date

        return missing_tickers, outdated_tickers, oldest_date


    missing_tickers, outdated_tickers, oldest_date = identify_missing_outdated_tickers(tickers, processed_data, period, oldest_date)

    def process_ticker_batch(tickers_batch, start_date, end_date):
        batch_results = {}
        ticker_data = fetch_data(tickers_batch, start_date, end_date)
        if ticker_data is not None:
            for ticker in tickers_batch:
                if ticker in ticker_data:
                    process_ticker_data(ticker, ticker_data[ticker], data, start_date, end_date)
                    batch_results[ticker] = ticker_data[ticker]
        return batch_results

    def identify_missing_outdated_tickers_in_batches(tickers, processed_data, period, oldest_date):
        missing_tickers = []
        outdated_tickers = []

        sorted_tickers = sorted(processed_data.keys())

        def check_ticker_batch(tickers_batch):
            for ticker in tickers_batch:
                index = binary_search_ticker(sorted_tickers, ticker)
                if index == -1:
                    missing_tickers.append(ticker)
                else:
                    prices, last_date = processed_data[sorted_tickers[index]]
                    if len(prices) < period:
                        missing_tickers.append(ticker)
                    closest_date_index = find_closest_date(prices, oldest_date)
                    if closest_date_index == -1 or datetime.datetime.strptime(prices[closest_date_index][0], "%Y%m%d").date() < oldest_date:
                        outdated_tickers.append(ticker)
                        if last_date and last_date < oldest_date:
                            oldest_date = last_date

        batch_size = 100  # Adjust as necessary
        ticker_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(check_ticker_batch, batch) for batch in ticker_batches]
            for future in futures:
                future.result()

        return missing_tickers, outdated_tickers, oldest_date


    with ThreadPoolExecutor() as executor:
        futures = []
        for tickers_batch in tickers_batches:
            tickers_batch_to_process = [ticker for ticker in tickers_batch if ticker in missing_tickers or ticker in outdated_tickers]
            if tickers_batch_to_process:
                future = executor.submit(process_ticker_batch, tickers_batch_to_process, start_date, end_date)
                futures.append(future)

        for future in futures:
            future.result()

    data["global_last_updated"] = end_date.strftime("%Y-%m-%d")
    save_compressed(data, data_file)

    results = {}
    for ticker in tickers:
        if ticker in data["historical_data"] and data["historical_data"][ticker]["prices"]:
            prices = pd.Series(
                {entry[0]: entry[1] for entry in data["historical_data"][ticker]["prices"]},
                name=ticker
            )
            prices.index = pd.to_datetime(prices.index, format="%Y%m%d")
            results[ticker] = prices

    return results

def fetch_data(tickers_batch, start_date, end_date):
    global current_task
    current_task = 'fetch_and_store_stock_data'
    if current_task == 'get_current_prices':
        return
    tickers_string = " ".join(tickers_batch)
    try:
        data = yf.download(tickers=tickers_string, start=start_date, end=end_date, group_by='ticker')
        # Remove rows with NaN prices
        data = data.dropna()
        if data.empty:
            print(f"Warning: No data fetched for batch {tickers_batch}")
            current_task = None
            return None
        current_task = None
        return data
    except Exception as e:
        print(f"Error fetching data for batch {tickers_batch}: {e}")
        current_task = None
        return None


def check_upward_trend(data, trend_days):
    rolling_average = data.rolling(window=150).mean()
    trend_period_data = rolling_average[-trend_days:]
    return all(x < y for x, y in zip(trend_period_data, trend_period_data[1:]))

# Helper function to process each ticker for both portfolio and watch list
def process_ticker(ticker, tickers_data, result_list, period, watch_list_trend_days=None, missing_list=None):
    if ticker not in tickers_data or tickers_data[ticker].empty:
        if missing_list is not None:
            missing_list.append(ticker)
        return
    close_prices = tickers_data[ticker]
    dates = close_prices.index[-period:].strftime('%Y-%m-%d').tolist()
    period_closes = close_prices[-period:].tolist()
    period_ma = close_prices.rolling(window=150).mean().iloc[-period:].tolist()
    period_closes = [round(price, 2) for price in period_closes]
    period_ma = [round(price, 2) for price in period_ma]

    rolling_avg = (
        close_prices.rolling(window=150).mean().iloc[-1]
        if len(close_prices) >= 150
        else None
    )
    current_price = close_prices.iloc[-1] if not close_prices.empty else None

    if rolling_avg is not None and not pd.isna(rolling_avg):
        percentage_diff = ((current_price - rolling_avg) / rolling_avg) * 100
        action = "Sell" if percentage_diff < 0 else ""
    else:
        percentage_diff = None
        action = "Insufficient Data"

    result = {
        'ticker': ticker,
        'current_price': f"${current_price:.2f}" if current_price else "N/A",
        'average_price': f"${rolling_avg:.2f}" if rolling_avg else "N/A",
        'percentage_diff': f"{percentage_diff:.2f}%" if percentage_diff else "N/A",
        'action': action,
        'period_closes': period_closes,
        'period_ma': period_ma,
        'dates': dates
    }

    if watch_list_trend_days:
        rolling_average = close_prices.rolling(window=150).mean()
        trend_period_data = rolling_average[-watch_list_trend_days:]
        trend = all(x < y for x, y in zip(trend_period_data, trend_period_data[1:]))
        trend_status = "Upward" if trend else "Not upward"
        action = determine_watchlist_action(trend_status, percentage_diff, current_price, rolling_avg)
        
        result['action'] = action
        result['trend_status'] = trend_status

    result_list.append(result)


def determine_watchlist_action(trend_status, percentage_diff, current_price, rolling_avg):
    if trend_status == "Not upward":
        return "Stay Away"
    
    if trend_status == "Upward":
        if percentage_diff is not None and -1.5 < percentage_diff < 1.5 and current_price > rolling_avg:
            return "Buy"
        elif percentage_diff is not None and -2 < percentage_diff < 2 and current_price < rolling_avg:
            return "Get Ready"
        elif percentage_diff is not None and percentage_diff > 1.5 and current_price > rolling_avg:
            return "Next Time"
        else:
            return "Non relevant"

    return "Non relevant"

