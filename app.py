from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import os
import pandas as pd
import data_utils
import stock_utils
import plot_utils
import user_data_utils

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_secret_key_here'  # Required for flash messages

@app.route('/')
def home():
    return render_template('index.html', default_tickers='', default_watch_list='')

@app.route('/results', methods=['POST'])
def results():
    try:
        user_id = request.form.get('user_id')

        tickers = [ticker.strip() for ticker in request.form.get('tickers', '').split(',')]
        watch_list = [ticker.strip() for ticker in request.form.get('watch_list', '').split(',')]
        
        # Remove duplicate tickers
        tickers = list(set(tickers))
        watch_list = list(set(watch_list))

        period = int(request.form.get('period', 150))
        watch_list_period = int(request.form.get('watch_list_period', 150))
        watch_list_trend_days = int(request.form.get('watch_list_trend_days', 30))

        tickers = [ticker if ticker != 'APPL' else 'AAPL' for ticker in tickers]
        watch_list = [ticker if ticker != 'APPL' else 'AAPL' for ticker in watch_list]

        user_data = {
            "default_tickers": request.form.get('tickers', ''),
            "default_watch_list": request.form.get('watch_list', '')
        }
        user_data_utils.save_user_data(user_id, user_data)

        tickers_data = stock_utils.fetch_and_store_stock_data(tickers + watch_list, period + 150)

        # Log data for specific problematic tickers
        problematic_tickers = ['UNH', 'TXN', 'TEL']
        for ticker in problematic_tickers:
            if ticker in tickers_data:
                print(f"DEBUG: Data for {ticker}: {tickers_data[ticker]}")

        results = {
            "portfolio": [],
            "watch_list": [],
            "missing": []
        }

        for ticker in tickers:
            if ticker in tickers_data and not tickers_data[ticker].empty:
                close_prices = tickers_data[ticker]
                dates = close_prices.index[-50:].strftime('%Y-%m-%d').tolist()
                last_50_closes = close_prices[-50:].tolist()
                last_50_ma = close_prices.rolling(window=150).mean().iloc[-50:].tolist()

                if ticker in problematic_tickers:
                    print(f"DEBUG: Chart data for {ticker}: Dates: {dates}, Closes: {last_50_closes}, MAs: {last_50_ma}")

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

                results["portfolio"].append({
                    'ticker': ticker,
                    'current_price': f"${current_price:.2f}" if current_price else "N/A",
                    'average_price': f"${rolling_avg:.2f}" if rolling_avg else "N/A",
                    'percentage_diff': f"{percentage_diff:.2f}%" if percentage_diff else "N/A",
                    'action': action,
                    'external_link': f"https://finance.yahoo.com/quote/{ticker}/chart",
                    'last_50_closes': last_50_closes,
                    'last_50_ma': last_50_ma,
                    'dates': dates
                })
            else:
                results["missing"].append(ticker)

        for ticker in watch_list:
            if ticker in tickers_data and not tickers_data[ticker].empty:
                close_prices = tickers_data[ticker]
                dates = close_prices.index[-50:].strftime('%Y-%m-%d').tolist()
                last_50_closes = close_prices[-50:].tolist()
                last_50_ma = close_prices.rolling(window=150).mean().iloc[-50:].tolist()
                
                if len(close_prices) < 150:
                    rolling_avg = None
                    percentage_diff = None
                else:
                    rolling_avg = close_prices.rolling(window=150).mean().iloc[-1]

                if rolling_avg is not None and not pd.isna(rolling_avg):
                    current_price = close_prices.iloc[-1]
                    percentage_diff = ((current_price - rolling_avg) / rolling_avg) * 100
                else:
                    current_price = None
                    percentage_diff = None
                    action = "Insufficient Data"

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

                external_link = f"https://finance.yahoo.com/quote/{ticker}/chart"

                results["watch_list"].append({
                    'ticker': ticker,
                    'current_price': f"${current_price:.2f}" if current_price else "N/A",
                    'average_price': f"${rolling_avg:.2f}" if rolling_avg else "N/A",
                    'percentage_diff': f"{percentage_diff:.2f}%" if percentage_diff else "N/A",
                    'action': action,
                    'trend_status': trend_status,
                    'external_link': external_link,
                    'last_50_closes': last_50_closes,
                    'last_50_ma': last_50_ma,
                    'dates': dates
                })
            else:
                results["missing"].append(ticker)

        return render_template('results.html', results=results, missing_tickers=results["missing"], user_id=user_id)
    except Exception as e:
        print(f"DEBUG: Error processing request: {e}")
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('home'))

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
