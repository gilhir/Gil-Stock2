import os
import datetime
import yfinance as yf
import pandas as pd
import gzip
import pandas_market_calendars as mcal
import json
import pytz
import threading

current_task = None

# Add a lock for thread-safe data modifications

def save_compressed(data, filename):
    """Save data to a compressed Parquet file."""
    df = pd.DataFrame({
        'ticker': [t for t in data['historical_data'] for _ in data['historical_data'][t]['prices']],
        'date': pd.to_datetime([d[0] for t in data['historical_data'] for d in data['historical_data'][t]['prices']]), 
        'price': [d[1] for t in data['historical_data'] for d in data['historical_data'][t]['prices']]
    })
    df.to_parquet(filename, compression='gzip')

def load_compressed(filename):
    """Load data from a compressed Parquet file."""
    if not os.path.exists(filename):
        return {"global_last_updated": None, "historical_data": {}}
    df = pd.read_parquet(filename)
    data = {"global_last_updated": None, "historical_data": {}}
    if not df.empty:
        grouped = df.groupby('ticker')
        for ticker, group in grouped:
            prices = list(zip(group['date'].dt.strftime('%Y%m%d'), group['price']))
            data['historical_data'][ticker] = {
                "prices": sorted(prices, key=lambda x: x[0]),
                "last_updated": group['date'].max().strftime('%Y-%m-%d')
            }
    return data
    
def market_is_open_now(date):
    nyse = mcal.get_calendar("NYSE")
    current_date_ny = date.astimezone(pytz.timezone('America/New_York'))
    schedule = nyse.schedule(start_date=current_date_ny.date(), end_date=current_date_ny.date())
    if schedule.empty:
        return False
    market_open = schedule.iloc[0]['market_open'].astimezone(pytz.timezone('America/New_York')).time()
    market_close = schedule.iloc[0]['market_close'].astimezone(pytz.timezone('America/New_York')).time()
    current_time = current_date_ny.time()
    return market_open <= current_time <= market_close

def market_is_open(date):
    result = mcal.get_calendar("NYSE").schedule(start_date=date, end_date=date)
    return not result.empty

def next_market_open():
    nyse = mcal.get_calendar("NYSE")
    current_daten = datetime.datetime.now(pytz.timezone('America/New_York'))
    if market_is_open_now(current_daten):
        return current_daten.strftime("%Y-%m-%d %H:%M:%S")
    current_date_ny = current_daten.date()
    # Check if market is already closed today
    schedule = nyse.schedule(start_date=current_date_ny.strftime("%Y-%m-%d"), end_date=current_date_ny.strftime("%Y-%m-%d"))
    if not schedule.empty:
        market_close = schedule.iloc[0]['market_close'].astimezone(pytz.timezone('America/New_York')).time()
        if current_daten.time() > market_close:
            current_date_ny += datetime.timedelta(days=1)
    while not market_is_open(current_date_ny.strftime("%Y-%m-%d")):
        current_date_ny += datetime.timedelta(days=1)
    next_open = nyse.schedule(start_date=current_date_ny.strftime("%Y-%m-%d"), end_date=current_date_ny.strftime("%Y-%m-%d"))
    market_open_time = next_open.iloc[0]['market_open'].astimezone(pytz.timezone('America/New_York'))
    return market_open_time.strftime("%Y-%m-%d %H:%M:%S")

def get_last_market_open_date():
    nyse = mcal.get_calendar("NYSE")
    ny_tz = pytz.timezone('America/New_York')
    current_date = datetime.datetime.now(ny_tz)
    
    # Check if market is open now
    if market_is_open_now(current_date):
        return current_date.date()
    
    # Get last market open day
    lookback_days = 7
    start_date = current_date.date() - datetime.timedelta(days=lookback_days)
    schedule = nyse.schedule(start_date=start_date, end_date=current_date.date())
    if not schedule.empty:
        return schedule.iloc[-1]['market_close'].date()
    return current_date.date() - datetime.timedelta(days=1)

from typing import Dict, List, Optional, Any

# Usage in fetch_and_store_stock_data:
def get_current_price(tickers: List[str]) -> Dict[str, Dict[str, str]]:
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
    data_lock = threading.Lock()
    try:
        with data_lock:
            print('data is locked')
            data = load_compressed(data_file)
            validate_json_structure(data)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error loading data file: {e}")
        os.remove(data_file)
        return

    # Ensure 'historical_data' key exists in data
    if "historical_data" not in data:
        data["historical_data"] = {}

    ny_tz = pytz.timezone('America/New_York')
    current_time_ny = datetime.datetime.now(ny_tz)
    if market_is_open_now(current_time_ny):
        # Find the last closed market date
        nyse = mcal.get_calendar("NYSE")
        start_date = current_time_ny.date() - datetime.timedelta(days=7)
        end_date_search = current_time_ny.date() - datetime.timedelta(days=1)
        schedule = nyse.schedule(start_date=start_date, end_date=end_date_search)
        if schedule.empty:
            end_date = end_date_search  # Fallback to yesterday even if not a trading day
        else:
            end_date = schedule.iloc[-1]['market_close'].date()
    else:
        end_date = current_time_ny.date()
    
    start_date = end_date - datetime.timedelta(days=period + 150)

    batch_size = 100
    tickers_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]

    global_last_updated = data.get("global_last_updated", None)
    global_last_updated_date = (
        datetime.datetime.strptime(global_last_updated, "%Y-%m-%d").date()
        if global_last_updated else None
    )
    oldest_date = get_last_market_open_date()


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
                    with data_lock:
                        print('data is locked')
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
            outdated_tickers_batch_to_process = [ticker for ticker in tickers_batch if ticker in outdated_tickers]
            if outdated_tickers_batch_to_process:
                future = executor.submit(process_ticker_batch, outdated_tickers_batch_to_process, start_date, end_date)
                futures.append(future)
            missing_tickers_batch_to_process = [ticker for ticker in tickers_batch if ticker in missing_tickers]
            if missing_tickers_batch_to_process:
                missing_start_date = datetime.datetime.now().date() - datetime.timedelta(days=period + 150)
                print(end_date)
                future = executor.submit(process_ticker_batch, missing_tickers_batch_to_process, missing_start_date, end_date)
                futures.append(future)

        for future in futures:
            future.result()

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

import time

def fetch_data(tickers_batch, start_date, end_date):
    global current_task
    current_task = 'fetch_and_store_stock_data'
    max_retries = 3
    retry_delay = 6  # seconds between retries
    end_date += datetime.timedelta(days=1)
    for attempt in range(max_retries):
        try:
            data = yf.download(
                tickers=" ".join(tickers_batch),
                start=start_date,
                end=end_date,
                group_by='ticker',
                progress=False,
                # Add these parameters to speed up:
                threads=True,  # Parallelize downloads
                timeout=10,    # Fail faster instead of waiting indefinitely
                ignore_tz=True # Skip timezone alignment overhead
            )
            if not data.empty:
                current_task = None
                return data
            print(f"Empty data for {tickers_batch} (attempt {attempt+1})")
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    current_task = None
    print(f"All retries failed for {tickers_batch}")
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

