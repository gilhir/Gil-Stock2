import os
import datetime
import yfinance as yf
import pandas as pd
import gzip
import pandas_market_calendars as mcal
import json


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
    
def market_is_open_now(date):
    now = datetime.datetime.now()
    result = mcal.get_calendar("NYSE").schedule(start_date=now.date(), end_date=date)
    if result.empty:
        return False
    market_open = result.iloc[0]['market_open'].time()
    market_close = result.iloc[0]['market_close'].time()
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
            print("fetch_and_store_stock_data is currently running. Skipping get_current_prices.")
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
            return {ticker: {"current_price": "nan"} for ticker in tickers.split()}
    except Exception as e:
        current_task = None
        print(f"Error fetching prices: {e}")
        return {ticker: {"current_price": "nan"} for ticker in tickers.split()}

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
    last_updated = stored_data.get("last_updated")
    last_updated_date = (
        datetime.datetime.strptime(last_updated, "%Y-%m-%d").date() if last_updated else None
    )
    if last_updated_date == end_date:
        return

    if new_data is None or new_data.empty:
        print(f"Warning: No valid data fetched for ticker {ticker}")
        return

    if "Close" not in new_data.columns:
        print(f"Error: Missing 'Close' column for ticker {ticker}")
        return

    existing_dates = {entry[0] for entry in stored_data["prices"]}
    for date, row in new_data.iterrows():
        date_str = date.strftime("%Y%m%d")
        if date_str not in existing_dates and not pd.isna(row["Close"]):
            stored_data["prices"].append([date_str, round(row["Close"], 2)])

    stored_data["last_updated"] = end_date.strftime("%Y-%m-%d")

    stored_data["prices"] = [
        entry for entry in stored_data["prices"]
        if datetime.datetime.strptime(entry[0], "%Y%m%d").date() >= start_date
    ]

    stored_data["prices"] = stored_data["prices"][-700:]

    data["historical_data"][ticker] = stored_data

def fetch_and_store_stock_data(tickers, period, data_file="optimized_data.json.gz"):
    try:
        data = load_compressed(data_file)
        validate_json_structure(data)  # Validate JSON structure
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error loading data file: {e}")
        os.remove(data_file)  # Delete the invalid file
        return

    end_date = datetime.datetime.now().date()
    start_date = end_date - datetime.timedelta(days=period + 150)

    batch_size = 100
    tickers_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]

    global_last_updated = data.get("global_last_updated", None)
    global_last_updated_date = (
        datetime.datetime.strptime(global_last_updated, "%Y-%m-%d").date()
        if global_last_updated else None
    )

    if global_last_updated_date == end_date:
        print("Global data is up-to-date. Checking for missing tickers...")
    print(tickers)
    missing_tickers = [ticker for ticker in tickers if ticker not in data["historical_data"]]
    print(end_date)
    outdated_tickers = []
    for ticker in tickers:
        if ticker in data["historical_data"]:
            prices = data["historical_data"][ticker]["prices"]
            if prices:
                last_date = prices[-1][0]
                last_date = datetime.datetime.strptime(last_date, "%Y%m%d").date()
                if last_date != end_date:
                    outdated_tickers.append(ticker)
            else:
                missing_tickers.append(ticker)

    print(f'outdated{outdated_tickers}')
    print(f'missing:{missing_tickers}')

    oldest_date = datetime.datetime.now().date()
    for ticker in outdated_tickers:
        last_date_str = data["historical_data"][ticker]["prices"][-1][0]
        last_updated = datetime.datetime.strptime(last_date_str, "%Y%m%d").date()
        if last_updated < oldest_date:
            oldest_date = last_updated

    outdated_start_date = oldest_date + datetime.timedelta(days=1)

    for tickers_batch in tickers_batches:
        tickers_batch_to_process = [ticker for ticker in tickers_batch if ticker in missing_tickers]
        if tickers_batch_to_process:
            ticker_data = fetch_data(tickers_batch_to_process, start_date, end_date)
            print(tickers_batch_to_process,ticker_data)
            if ticker_data is not None:
                for ticker in tickers_batch_to_process:
                    if ticker in ticker_data:
                        process_ticker_data(ticker, ticker_data[ticker], data, start_date, end_date)
        tickers_batch_to_process = [ticker for ticker in tickers_batch if ticker in outdated_tickers]
        if tickers_batch_to_process:
            ticker_data = fetch_data(tickers_batch_to_process, outdated_start_date, end_date)
            if ticker_data is not None:
                for ticker in tickers_batch_to_process:
                    if ticker in ticker_data:
                        process_ticker_data(ticker, ticker_data[ticker], data, outdated_start_date, end_date)
        

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
            
    current_task = None
    return results

def fetch_data(tickers_batch, start_date, end_date):
        global current_task
        current_task = 'fetch_and_store_stock_data'
        if current_task == 'get_current_prices':
            print("get_current_prices is currently running. Skipping process_ticker_data.")
            return
        tickers_string = " ".join(tickers_batch)
        try:
            data = yf.download(tickers=tickers_string, start=start_date, end=end_date, group_by='ticker')
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

