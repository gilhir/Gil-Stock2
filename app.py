from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
import os
import pandas as pd
import stock_utils
import json
import user_data_utils
import git
import datetime

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_secret_key_here'  # Required for flash messages

@app.route('/')
def home():
    return render_template('index.html', default_tickers='', default_watch_list='')

@app.route('/results', methods=['GET', 'POST'])
def results():
    try:
        if request.method == 'POST':
            # Extract user input from the form
            user_id = request.form.get('user_id')
            tickers = [ticker.strip() for ticker in request.form.get('tickers', '').split(',')]
            watch_list = [ticker.strip() for ticker in request.form.get('watch_list', '').split(',')]
            tickers = list(set(tickers))  # Remove duplicates
            watch_list = list(set(watch_list))  # Remove duplicates
            period = int(request.form.get('period', 150))
            watch_list_trend_days = int(request.form.get('watch_list_trend_days', 30))
            user_data = {
                "default_tickers": request.form.get('tickers', ''),
                "default_watch_list": request.form.get('watch_list', '')
            }
            user_data_utils.save_user_data(user_id, user_data)
            session['user_id'] = user_id
            tickers_data = stock_utils.fetch_and_store_stock_data(tickers + watch_list, period + 150)
            results = {"portfolio": [], "watch_list": [], "missing": []}
            
            # Process portfolio tickers
            for ticker in tickers:
                process_ticker(ticker, tickers_data, results["portfolio"], missing_list=results["missing"])

            # Process watch list tickers
            for ticker in watch_list:
                process_ticker(ticker, tickers_data, results["watch_list"], watch_list_trend_days, period, missing_list=results["missing"])

            user_data["results"] = results
            return render_template('results.html', results=results, missing_tickers=results["missing"], user_id=user_id)

        elif request.method == 'GET':
            results = user_data.get('results', None)
            if not results:
                print("No results available. Please submit your data first.", "warning")
                return redirect(url_for('home'))

            return render_template('results.html', results=results, missing_tickers=results.get("missing", []), user_id=user_id)

    except Exception as e:
        print(f"DEBUG: Error processing request: {e}")
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('home'))
    
# Helper function to process each ticker for both portfolio and watch list
def process_ticker(ticker, tickers_data, result_list, watch_list_trend_days=None, period=None, missing_list=None):
    if ticker in tickers_data and not tickers_data[ticker].empty:
        close_prices = tickers_data[ticker]
        dates = close_prices.index[-50:].strftime('%Y-%m-%d').tolist()
        last_50_closes = close_prices[-50:].tolist()
        last_50_ma = close_prices.rolling(window=150).mean().iloc[-50:].tolist()

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
        if watch_list_trend_days and period:
            trend = stock_utils.check_upward_trend(close_prices, watch_list_trend_days, period)
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
        if not stock_utils.market_is_open_now(current_date):
            next_open = stock_utils.next_market_open()
            return json.dumps({'market_status': 'closed','next_open': next_open}), 200

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
        return json.dumps(latest_prices)

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
        if request.method == 'POST':
            repo = git.Repo('/')
            origin = repo.remotes.origin
            origin.pull()
            return 'Updated PythonAnywhere successfully', 200
        else:
            return 'Wrong event type', 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
