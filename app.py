from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
import os
import pandas as pd
import stock_utils
import json
import user_data_utils
import git
import numpy as np
import datetime

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_secret_key_here'  # Required for flash messages

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
            tickers = [ticker.strip() for ticker in request.form.get('tickers', '').split(',')]
            watch_list = [ticker.strip() for ticker in request.form.get('watch_list', '').split(',')]
            tickers = list(dict.fromkeys(tickers))
            watch_list = list(dict.fromkeys(watch_list))
            period = int(request.form.get('period', 150))
            watch_list_trend_days = int(request.form.get('watch_list_trend_days', 30))
            user_data = {
                "default_tickers": request.form.get('tickers', ''),
                "default_watch_list": request.form.get('watch_list', ''),
                "analysis_period": request.form.get('period', ''),
                "watch_list_trend_days": request.form.get('watch_list_trend_days', '')
            }
            user_data_utils.save_user_data(user_id, user_data)
            session['user_id'] = user_id
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

@app.route('/fetch_stocks/<period>', methods=['GET'])
def fetcher(period):
    try:
            period = int(period)
            user_id = session.get('user_id')
            if user_id:
                user_data = user_data_utils.load_user_data(user_id)
                tickers = [ticker.strip() for ticker in user_data[user_id].get('default_tickers', '').split(',')]
                watch_list = [ticker.strip() for ticker in user_data[user_id].get('default_watch_list', '').split(',')]
                tickers = list(set(tickers))
                watch_list = list(set(watch_list))
                analysis_period = int(user_data_utils.get_user_analysis_period(user_data, user_id))
                watch_list_trend_days = int(user_data_utils.get_user_watch_list_trend_days(user_data,user_id))
                print(watch_list_trend_days)
                tickers_data = stock_utils.fetch_and_store_stock_data(tickers + watch_list, period + 150)
                results = {"portfolio": [], "watch_list": [], "missing": []}

                for ticker in set(tickers + watch_list):
                    if ticker in tickers:
                        process_ticker(ticker, tickers_data, results["portfolio"], period, missing_list=results["missing"])
                    if ticker in watch_list:
                        process_ticker(ticker, tickers_data, results["watch_list"], period, watch_list_trend_days, missing_list=results["missing"])

                user_data["results"] = results
                clean_results = clean_json(results)
                response = json.dumps({"results": clean_results, "missing_tickers": results["missing"], "user_id": user_id})
                return app.response_class(response, content_type='application/json')


            return redirect(url_for('home'))

    except Exception as e:
        print(f"DEBUG: Error processing request: {e}")
        return app.response_class(json.dumps({"error": str(e)}), content_type='application/json', status=400)

# Helper function to process each ticker for both portfolio and watch list
def process_ticker(ticker, tickers_data, result_list, period, watch_list_trend_days=None, missing_list=None):
    if ticker in tickers_data and not tickers_data[ticker].empty:
        close_prices = tickers_data[ticker]
        dates = close_prices.index[-period:].strftime('%Y-%m-%d').tolist()
        last_50_closes = close_prices[-period:].tolist()
        last_50_ma = close_prices.rolling(window=150).mean().iloc[-period:].tolist()

        if len(close_prices) < 150:
            rolling_avg = None
            percentage_diff = None
            current_price = close_prices.iloc[-1] if len(close_prices) > 0 else None
        else:
            rolling_avg = close_prices.rolling(window=150).mean().iloc[-1]
            current_price = close_prices.iloc[-1]

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
            'external_link': f"https://finance.yahoo.com/quote/{ticker}/chart",
            'last_50_closes': last_50_closes,
            'last_50_ma': last_50_ma,
            'dates': dates
        }

        # For watch list, check the trend status
        if watch_list_trend_days:
            trend = stock_utils.check_upward_trend(close_prices, watch_list_trend_days)
            trend_status = "Upward" if trend else "Not upward"

            if trend_status == "Not upward":
                action = "Stay Away"
            elif trend_status == "Upward":
                if percentage_diff is not None and (-1.5 < percentage_diff < 1.5) and current_price > rolling_avg:
                    action = "Buy"
                elif percentage_diff is not None and -2 < percentage_diff < 2 and current_price < rolling_avg:
                    action = "Get Ready"
                elif percentage_diff is not None and percentage_diff > 1.5 and current_price > rolling_avg:
                    action = "Next Time"
                else:
                    action = "Non relevant"
            else:
                action = "Non relevant"

            result['action'] = action
            result['trend_status'] = trend_status

        result_list.append(result)
    else:
        if missing_list is not None:
            missing_list.append(ticker)

    

@app.route('/latest_prices', methods=['GET'])
def latest_prices():
    try:
        user_id = session.get('user_id')
        if not user_id:
            flash("User ID is required to fetch the latest prices.", "warning")
            return json.dumps({'error': 'User ID is required'}), 400

        user_data = user_data_utils.load_user_data(user_id)
        if not user_data or user_id not in user_data:
            flash(f"No data found for User ID '{user_id}'.", "warning")
            return json.dumps({'error': f"No data found for User ID '{user_id}'"}), 404
        
        current_date = datetime.datetime.now()
        market_open = stock_utils.market_is_open_now(current_date)

        # Extract tickers from default_tickers and default_watch_list
        default_tickers = user_data[user_id].get("default_tickers", "")
        default_watch_list = user_data[user_id].get("default_watch_list", "")
        tickers = default_tickers.split(",") + default_watch_list.split(",")
        tickers = [ticker.strip() for ticker in tickers if ticker.strip()]  # Clean up any empty strings or whitespace
        latest_prices = {}
        for ticker in tickers:
            current_price = stock_utils.get_current_price(ticker)
            if not current_price != current_price:
                try:
                    formatted_price = f"{current_price:.2f}"
                    latest_prices[ticker] = {'current_price': formatted_price}
                except ValueError:
                    print(f"Invalid price for ticker {ticker}: {current_price}")
        
        if not market_open:
            next_open = stock_utils.next_market_open()
            return json.dumps({'market_status': 'closed', 'next_open': next_open, 'latest_prices': latest_prices}), 200
        else:
            return json.dumps({'market_status': 'open', 'latest_prices': latest_prices}), 200
        
    except Exception as e:
        print(f"DEBUG: Error fetching latest prices: {e}")
        flash(f"An error occurred while fetching prices: {e}", "danger")
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
        user_data = user_data_utils.load_user_data(user_id)
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
        ticker_data = request.get_json()  # Get the JSON data from the request

        tickers = list(ticker_data.keys())
        tickers_data = stock_utils.fetch_and_store_stock_data(tickers, 1)  # Fetch current stock prices

        # Combine entries for the same stock and get current prices
        combined_ticker_data = {}
        for ticker, entries in ticker_data.items():
            current_price = tickers_data[ticker].iloc[-1] if ticker in tickers_data and not tickers_data[ticker].empty else 0
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

        # Save the ticker data to a file or database
        with open(f'heatmap_data_{user_id}.json', 'w') as f:
            json.dump(ticker_data, f, indent=4)

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
        ticker_data[ticker] = data  # Directly assign the list

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

@app.route('/stock_performance/<user_id>', methods=['GET'])
def stock_performance(user_id):
    try:
        period = request.args.get('period')
        period_mapping = {
            '1day': 1,
            '5days': 5,
            '1month': 30,
            '3months': 90,
            '6months': 180,
            '1year': 365,
            '3years': 1095,
            'alltime': 10000,  # Arbitrary large number for all time
        }

        if period in ['from_beginning', 'since_bought']:
            days = 0
        else:
            days = period_mapping.get(period, 10000)
            
        print(days)
        user_data = user_data_utils.load_user_data(user_id)
        if not user_data or user_id not in user_data:
            return json.dumps({'error': 'User ID not found'}), 404

        tickers = user_data[user_id].get("default_tickers", "").split(",")
        tickers = [ticker.strip() for ticker in tickers if ticker.strip()]
        stock_data = stock_utils.fetch_and_store_stock_data(tickers, days)
        current_prices = {ticker: stock_utils.get_current_price(ticker) for ticker in tickers}

        # Load weight data from heatmap data
        heatmap_data = load_heatmap_data(user_id)

        # Calculate performance and prepare the JSON response
        performance_data = {}
        for ticker in tickers:
            purchase_data = heatmap_data.get(ticker, [{}])[0]

            if period in ['from_beginning', 'since_bought']:
                old_price = purchase_data.get('purchase_price', 0)
            else:
                if ticker in stock_data:
                    dates = sorted(stock_data[ticker].keys())
                    date_days_ago = dates[-days] if len(dates) >= days else dates[0]
                    old_price = stock_data[ticker][date_days_ago]
                else:
                    old_price = 0
            
            new_price = current_prices.get(ticker, 0)
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

# Example usage:
# heatmap_data = load_heatmap_data(user_id)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
