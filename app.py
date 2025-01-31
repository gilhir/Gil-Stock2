from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
import os
import pandas as pd
import stock_utils
import json
import user_data_utils
import git
import numpy as np
import datetime
from flask_apscheduler import APScheduler
import dailyjob
import pytz


app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_secret_key_here'  # Required for flash messages
scheduler = APScheduler()

def clean_list(input_string):
    return list(dict.fromkeys([item.strip() for item in input_string.split(',') if item.strip()]))

def get_user_data_or_redirect():
    user_id = session.get('user_id')
    if not user_id:
        return None ,None, redirect(url_for('home'))
    return user_data_utils.load_user_data(user_id), user_id, None

@app.route('/')
def home():
    user_id = session.get('user_id')
    if(user_id is not None):
        return redirect(url_for('results'))
    else:
        return render_template('index.html', default_tickers='', default_watch_list='')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/results', methods=['GET','POST'])
def results():
    try:
        user_id = session.get('user_id')
        if request.method == 'POST':
            user_id = request.form.get('user_id')
            session['user_id'] = user_id
            user_data = {
                "default_tickers": request.form.get('tickers', ''),
                "default_watch_list": request.form.get('watch_list', ''),
                "analysis_period": request.form.get('period', ''),
                "watch_list_trend_days": request.form.get('watch_list_trend_days', '')
            }
            user_data_utils.save_user_data(user_id, user_data)
            return render_template('results.html', results=results, missing_tickers=results["missing"], user_id=user_id)
        if request.method == 'GET':
            user_id = session.get('user_id')
            if user_id is not None:
                return render_template('results.html', user_id=user_id)
        else:
            return redirect(url_for('home'))
    except Exception as e:
        print(f"DEBUG: Error processing request: {e}")
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('home'))

    
def clean_json(data):
    if isinstance(data, dict):
        return {k: clean_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json(i) for i in data]
    elif isinstance(data, float) and np.isnan(data):
        return None
    return data

def clean_list(stocklist):
    stocklist = stocklist.split(',')
    ticker= list(set([ticker.strip() for ticker in stocklist]))
    return ticker

from concurrent.futures import ThreadPoolExecutor

@app.route('/fetch_stocks/<int:period>', methods=['GET'])
def fetch_stocks(period):
    try:
        user_data, user_id, redirect_response = get_user_data_or_redirect()
        if redirect_response:
            return redirect_response
        
        tickers = clean_list(user_data[user_id].get("default_tickers", ''))
        watch_list = clean_list(user_data[user_id].get("default_watch_list", ''))
        analysis_period = int(user_data[user_id].get("analysis_period", ''))
        watch_list_trend_days = int(user_data[user_id].get("watch_list_trend_days", ''))

        # Use ThreadPoolExecutor to fetch and process data in parallel
        with ThreadPoolExecutor() as executor:
            tickers_data_future = executor.submit(stock_utils.fetch_and_store_stock_data, tickers + watch_list, period + 150)
            tickers_data = tickers_data_future.result()
            results = {"portfolio": [], "watch_list": [], "missing": []}

            futures = []
            for ticker in set(tickers + watch_list):
                if ticker in tickers:
                    future = executor.submit(stock_utils.process_ticker, ticker, tickers_data, results["portfolio"], period, missing_list=results["missing"])
                    futures.append(future)
                if ticker in watch_list:
                    future = executor.submit(stock_utils.process_ticker, ticker, tickers_data, results["watch_list"], period, watch_list_trend_days, results["missing"])
                    futures.append(future)
            
            for future in futures:
                future.result()

        clean_results = clean_json(results)
        response = json.dumps({"results": clean_results, "missing_tickers": results["missing"], "user_id": user_id})
        return app.response_class(response, content_type='application/json')

    except Exception as e:
        print(f"DEBUG: Error processing request: {e}")
        return app.response_class(json.dumps({"error": str(e)}), content_type='application/json', status=400)

last_nan_detection_time = None

@app.route('/latest_prices', methods=['GET'])
def latest_prices():
    global last_nan_detection_time
    try:
        user_data, user_id, redirect_response = get_user_data_or_redirect()
        if redirect_response:
            return json.dumps({'error': 'User ID is required'}), 400

        current_date = datetime.datetime.now()
        market_open = stock_utils.market_is_open_now(current_date)

        default_tickers = clean_list(user_data[user_id].get("default_tickers", ''))
        default_watch_list = clean_list(user_data[user_id].get("default_watch_list", ''))
        tickers = default_tickers + default_watch_list
        latest_prices = {}
        # Print to check if last NaN detection time is within the last minute
        if last_nan_detection_time and (datetime.datetime.now() - last_nan_detection_time).total_seconds() < 240:
            print("Skipping fetch due to API overwhelmed.")
            return json.dumps({'market_status': 'open', 'error': 'NaN values detected previously, skipping fetch'}), 200

        latest_prices = stock_utils.get_current_price(tickers)
        
        # Check for NaN values in latest_prices
        if any(price['current_price'] == 'nan' for price in latest_prices.values()):
            last_nan_detection_time = datetime.datetime.now()
            return json.dumps({'market_status': 'open', 'error': 'NaN values detected'}), 200

        if not market_open:
            next_open = stock_utils.next_market_open()
            return json.dumps({'market_status': 'closed', 'next_open': next_open, 'latest_prices': latest_prices}), 200
        else:
            return json.dumps({'market_status': 'open', 'latest_prices': latest_prices}), 200
    except Exception as e:
        return json.dumps({'error': str(e)}), 500


@app.route('/new_user', methods=['GET', 'POST'])
def new_user():
    if request.method == 'POST':
        try:
            # Extract form data
            user_id = request.form.get('user_id', '').strip()
            if not user_id:
                flash("User ID is required!", "danger")
                return redirect(url_for('new_user'))

            # Optional: Add default data for the new user
            default_tickers = request.form.get('default_tickers', '')
            default_watch_list = request.form.get('default_watch_list', '')

            user_data = {
                "default_tickers": default_tickers,
                "default_watch_list": default_watch_list
            }

            # Save new user data
            user_data_utils.save_user_data(user_id, user_data)
            flash(f"User '{user_id}' created successfully!", "success")
            return redirect(url_for('home'))

        except Exception as e:
            print(f"DEBUG: Error creating new user: {e}")
            flash(f"An error occurred: {e}", "danger")
            return redirect(url_for('new_user'))

    # Handle GET request
    return render_template('new_user.html')

@app.route('/edit')
def edit():
    try:
        user_id = request.args.get('user_id', 'default_user')
        user_data = get_user_data_or_redirect()
        return render_template('index.html', default_tickers=user_data[user_id]['default_tickers'], default_watch_list=user_data[user_id]['default_watch_list'])
    except Exception as e:
        print(f"DEBUG: Error loading user data: {e}")
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('home'))

@app.route('/user_data.json')
def user_data():
    return send_from_directory('.', 'user_data.json')

@app.route('/update_server', methods=['POST'])
def webhook():
            current_dir = os.getcwd()
            repo = git.Repo(current_dir)
            origin = repo.remotes.origin
            repo.create_head('main',origin.refs.main).set_tracking_branch(origin.refs.main).checkout()
            origin.pull()
            return 'Updated PythonAnywhere successfully', 200


@app.route('/user_tickers/<user_id>', methods=['GET'])
def user_tickers(user_id):
    try:
        user_data = user_data_utils.load_user_data(user_id)
        if not user_data or user_id not in user_data:
            return json.dumps({'tickers': []}), 404

        tickers = user_data[user_id].get("default_tickers", "").split(",")
        tickers = [ticker.strip() for ticker in tickers if ticker.strip()]
        return json.dumps({'tickers': tickers})

    except Exception as e:
        print(f"DEBUG: Error fetching user tickers: {e}")
        return json.dumps({'tickers': []}), 500

@app.route('/heatmap')
def heatmap():
    user_ids = user_data_utils.get_all_user_ids()
    return render_template('heatmap.html', user_ids=user_ids)

@app.route('/heatmap_data/<user_id>', methods=['POST'])
def update_heatmap_data(user_id):
    try:
        data = request.get_json()  # Get the JSON data from the request
        ticker_data = data.get("ticker_data", {})
        cash_flow = data.get("cash_flow", 0)  # Separate cash flow

        tickers = list(ticker_data.keys())
        tickers_data = stock_utils.get_current_price(tickers)  # Fetch current stock prices
        # Combine entries for the same stock and get current prices
        combined_ticker_data = {}
        for ticker, entries in ticker_data.items():
            current_price = float(tickers_data.get(ticker, {}).get('current_price', 0))
            total_number_of_stocks = sum(entry['number_of_stocks'] for entry in entries)
            total_cash_in_market = total_number_of_stocks * current_price  # Calculate total_cash_in_market based on current_price
            percentage_diffs = [((current_price - entry['purchase_price']) / entry['purchase_price']) * 100 if entry['purchase_price'] != 0 else 0 for entry in entries]

            combined_ticker_data[ticker] = {
                'number_of_stocks': total_number_of_stocks,
                'total_cash_in_market': total_cash_in_market,
                'current_price': current_price,
                'percentage_diff': sum(percentage_diffs) / len(percentage_diffs) if percentage_diffs else 0,
                'entries': entries  # Keep the original entries for reference
            }

        # Calculate total cash in market for the portfolio based on current prices
        total_cash = sum(data['total_cash_in_market'] for data in combined_ticker_data.values())

        # Calculate weight for each ticker based on aggregated total_cash_in_market
        for ticker, data in combined_ticker_data.items():
            data['weight'] = data['total_cash_in_market'] / total_cash if total_cash > 0 else 0

        # Reconstruct the original ticker_data with the combined fields
        for ticker, data in ticker_data.items():
            for entry in data:
                entry['current_price'] = combined_ticker_data[ticker]['current_price']
                entry['total_cash_in_market'] = combined_ticker_data[ticker]['total_cash_in_market']
                entry['percentage_diff'] = combined_ticker_data[ticker]['percentage_diff']
                entry['weight'] = combined_ticker_data[ticker]['weight']

        # Read existing data from the JSON file to preserve history
        json_file_path = f'heatmap_data_{user_id}.json'
        try:
            with open(json_file_path, 'r') as f:
                existing_data = json.load(f)
        except FileNotFoundError:
            existing_data = {}

        # Preserve existing history and add new data
        history = existing_data.get('history', [])
        existing_data['ticker_data'] = ticker_data
        existing_data['cash_flow'] = cash_flow
        existing_data['history'] = history  # Preserve history

        # Save the updated data back to the JSON file
        with open(json_file_path, 'w') as f:
            json.dump(existing_data, f, indent=4)

        return json.dumps({"message": "Data updated successfully"}), 200

    except Exception as e:
        print(f"DEBUG: Error saving heatmap data: {e}")
        return json.dumps({"error": str(e)}), 500


@app.route('/heatmap_data/<user_id>/<ticker>', methods=['GET'])
def get_heatmap_data(user_id, ticker):
    try:
        file_path = f'heatmap_data_{user_id}.json'
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                ticker_data = json.load(f)
                ticker_data = ticker_data.get('ticker_data',{})
                return json.dumps(ticker_data.get(ticker, []))
        return json.dumps([])
    except Exception as e:
        print(f"DEBUG: Error fetching heatmap data for {user_id} and {ticker}: {e}")
        return json.dumps([]), 500

@app.route('/heatmap_data/<user_id>/<ticker>', methods=['POST'])
def update_single_ticker_data(user_id, ticker):
    try:
        data = request.get_json()  # Get the JSON data from the request
        file_path = f'heatmap_data_{user_id}.json'
        
        # Read existing data if the file exists, otherwise start with an empty dict
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                ticker_data = json.load(f)
        else:
            ticker_data = {}

        # Ensure the data for the ticker is a list
        ticker_data["ticker_data"][ticker] = data  # Directly assign the list

        # Save the updated data back to the file
        with open(file_path, 'w') as f:
            json.dump(ticker_data, f, indent=4)

        return json.dumps({'success': True}), 200

    except Exception as e:
        print(f"DEBUG: Error updating heatmap data for {user_id} and {ticker}: {e}")
        return json.dumps({'success': False}), 500


@app.route('/heatmap_data/<user_id>', methods=['GET'])
def get_all_heatmap_data(user_id):
    try:
        file_path = f'heatmap_data_{user_id}.json'
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                ticker_data = json.load(f)
                return json.dumps(ticker_data)
        return json.dumps({})
    except Exception as e:
        print(f"DEBUG: Error fetching all heatmap data for {user_id}: {e}")
        return json.dumps({}), 500

@app.route('/visualization/')
def visualization():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('home'))  # Redirect to home if user_id is not in session
        
        file_path = f'heatmap_data_{user_id}.json'
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                ticker_data = json.load(f)
        else:
            ticker_data = {}

        return render_template('visualization.html', ticker_data=ticker_data, user_id=user_id)

    except Exception as e:
        print(f"DEBUG: Error fetching visualization data for {user_id}: {e}")
        return json.dumps({"error": str(e)}), 500

# List of market holidays for 2025, 2026, and 2027
market_holidays = [
    datetime.date(2025, 1, 1),  # New Year's Day
    datetime.date(2025, 1, 9),  # Jimmy Carter NDoM
    datetime.date(2025, 1, 20),  # Martin Luther King, Jr. Day
    datetime.date(2025, 2, 17),  # Washington's Birthday
    datetime.date(2025, 4, 18),  # Good Friday
    datetime.date(2025, 5, 26),  # Memorial Day
    datetime.date(2025, 6, 19),  # Juneteenth National Independence Day
    datetime.date(2025, 7, 4),   # Independence Day
    datetime.date(2025, 9, 1),   # Labor Day
    datetime.date(2025, 11, 27), # Thanksgiving Day
    datetime.date(2025, 12, 25), # Christmas Day

    datetime.date(2026, 1, 1),   # New Year's Day
    datetime.date(2026, 1, 19),  # Martin Luther King, Jr. Day
    datetime.date(2026, 2, 16),  # Washington's Birthday
    datetime.date(2026, 4, 3),   # Good Friday
    datetime.date(2026, 5, 25),  # Memorial Day
    datetime.date(2026, 6, 19),  # Juneteenth National Independence Day
    datetime.date(2026, 7, 3),   # Independence Day observed
    datetime.date(2026, 9, 7),   # Labor Day
    datetime.date(2026, 11, 26), # Thanksgiving Day
    datetime.date(2026, 12, 25), # Christmas Day

    datetime.date(2027, 1, 1),   # New Year's Day
    datetime.date(2027, 1, 18),  # Martin Luther King, Jr. Day
    datetime.date(2027, 2, 15),  # Washington's Birthday
    datetime.date(2027, 3, 26),  # Good Friday
    datetime.date(2027, 5, 31),  # Memorial Day
    datetime.date(2027, 6, 18),  # Juneteenth National Independence Day observed
    datetime.date(2027, 7, 5),   # Independence Day observed
    datetime.date(2027, 9, 6),   # Labor Day
    datetime.date(2027, 11, 25), # Thanksgiving Day
    datetime.date(2027, 12, 24), # Christmas Day observed
]

def days_passed_since_start_of_year():
    today = datetime.date.today()
    start_of_year = datetime.date(today.year, 1, 1)
    days_passed = 0

    for single_date in (start_of_year + datetime.timedelta(n) for n in range((today - start_of_year).days + 1)):
        if single_date.weekday() < 5 and single_date not in market_holidays:  # Weekdays are 0 (Monday) to 4 (Friday)
            days_passed += 1

    return days_passed

from concurrent.futures import ThreadPoolExecutor

@app.route('/stock_performance/<user_id>', methods=['GET'])
def stock_performance(user_id):
    try:
        days_passed = days_passed_since_start_of_year() + 1
        period = request.args.get('period')
        period_mapping = {
            '1day': 1,
            '2day': 2,
            '1week': 7,
            '5days': 5,
            '1month': 30,
            '3months': 90,
            '6months': 180,
            '1year': 365,
            'YTD': int(days_passed),
            '3years': 1095,
            'alltime': 10000,  # Arbitrary large number for all time
        }

        if period in ['from_beginning', 'since_bought']:
            days = 0
        else:
            days = period_mapping.get(period, 10000)
        
        if days == 1:
            current_daten = datetime.datetime.now(pytz.timezone('America/New_York'))
            print(current_daten)
            print(stock_utils.market_is_open_now(current_daten))
            days = 1
            if not stock_utils.market_is_open_now(current_daten):
                current_date = datetime.datetime.now().date()
                while not stock_utils.market_is_open(current_date):
                    print('not open',current_date)
                    current_date += datetime.timedelta(days=-1)
                    days += 1

        print(days)
        user_data = user_data_utils.load_user_data(user_id)
        if not user_data or user_id not in user_data:
            return json.dumps({'error': 'User ID not found'}), 404

        tickers = [ticker.strip() for ticker in user_data[user_id].get("default_tickers", "").split(",") if ticker.strip()]
        
        # Utilize ThreadPoolExecutor to fetch data in parallel
        with ThreadPoolExecutor() as executor:
            stock_data_future = executor.submit(stock_utils.fetch_and_store_stock_data, tickers, days)
            current_prices_future = executor.submit(stock_utils.get_current_price, tickers)
            heatmap_data_future = executor.submit(load_heatmap_data, user_id)

        stock_data = stock_data_future.result()
        current_prices = current_prices_future.result()        
        # Load weight data from heatmap data
        heatmap_data = heatmap_data_future.result().get('ticker_data', {})
        
        # Calculate performance and prepare the JSON response
        performance_data = {}
        for ticker in tickers:
            purchase_data = heatmap_data.get(ticker, [{}])[0]

            if period in ['from_beginning', 'since_bought']:
                old_price = purchase_data.get('purchase_price', 0)
            else:
                if ticker in stock_data:
                    dates = sorted(stock_data[ticker].keys())
                    today = datetime.datetime.now().strftime('%Y-%m-%d')
                    today_timestamp = pd.Timestamp(today)
                    dates = [date for date in dates if date != today_timestamp]
                    dates = [date for date in dates if date != today]
                    date_days_ago = dates[-days] if len(dates) >= days else dates[0]
                    old_price = stock_data[ticker].get(date_days_ago, 0)
                else:
                    old_price = 0

            new_price = float(current_prices.get(ticker, {}).get('current_price', 0))
            percentage_change = ((new_price - old_price) / old_price) * 100 if old_price else 0

            weight_data = purchase_data.get('weight', 0)
            percentage_diff = purchase_data.get('percentage_diff', 0)

            performance_data[ticker] = {
                'percentage_change': percentage_change,
                'weight': weight_data,
                'percentage_diff': percentage_diff
            }

        return json.dumps(performance_data)
    except Exception as e:
        print(f"DEBUG: Error fetching stock performance data: {e}")
        return json.dumps({'error': str(e)}), 500



def load_heatmap_data(user_id):
    try:
        with open(f'heatmap_data_{user_id}.json', 'r') as f:
            heatmap_data = json.load(f)
        return heatmap_data
    except FileNotFoundError:
        print(f"DEBUG: Heatmap data file for user {user_id} not found.")
        return {}

dailyjob.dailytracker()

scheduler.add_job(func=dailyjob.dailytracker, trigger='cron', hour=23, minute=55, id='dailytracker')

# Schedule the dailytracker function to run every day at 23:50

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    scheduler.init_app(app)
    scheduler.start()
    app.run(host="0.0.0.0", port=port)
