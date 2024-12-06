from flask import Flask, render_template, request, redirect, url_for
import yfinance as yf
import datetime
import json
import os
import io
import base64
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd

# Use the Agg backend for Matplotlib
matplotlib.use('Agg')

app = Flask(__name__, template_folder='C:\\Users\\P0037596\\AI PDF Sum\\Stock\\templates')

# Path to the JSON file
DATA_FILE = 'data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            try:
                data = json.load(file)
                # Ensure all necessary keys exist
                if "historical_data" not in data:
                    data["historical_data"] = {}
                if "last_updated" not in data:
                    data["last_updated"] = None
            except json.decoder.JSONDecodeError as e:
                data = {"default_tickers": "", "default_watch_list": "", "historical_data": {}, "last_updated": None}
    else:
        data = {"default_tickers": "", "default_watch_list": "", "historical_data": {}, "last_updated": None}
    return data

def save_data(data):
    try:
        with open(DATA_FILE, 'w') as file:
            json.dump(data, file, indent=4, default=str)
    except TypeError as e:
        print(f"Error saving data: {e}")

def fetch_and_store_stock_data(tickers, period):
    data = load_data()
    end_date = datetime.datetime.now().date()
    start_date = end_date - datetime.timedelta(days=period + 150)
    tickers_string = " ".join(tickers)

    try:
        ticker_data = yf.download(tickers=tickers_string, start=start_date, end=end_date, group_by='ticker')

        for ticker in tickers:
            try:
                new_data = ticker_data[ticker]
                stored_data = data["historical_data"].get(ticker, {"prices": [], "last_updated": None})

                if not new_data.empty:
                    for date, row in new_data.iterrows():
                        stored_data["prices"].append({"date": date.strftime("%Y-%m-%d"), "close": row["Close"]})
                    stored_data["last_updated"] = end_date.strftime("%Y-%m-%d")

                    stored_data["prices"] = [
                        entry for entry in stored_data["prices"]
                        if datetime.datetime.strptime(entry["date"], "%Y-%m-%d").date() >= start_date
                    ]
                    data["historical_data"][ticker] = stored_data

            except KeyError as e:
                print(f"Error fetching data for {ticker}: Missing {e} field.")

        save_data(data)

        results = {}
        for ticker in tickers:
            if ticker in data["historical_data"]:
                prices = pd.Series(
                    {entry["date"]: entry["close"] for entry in data["historical_data"][ticker]["prices"]}
                )
                prices.index = pd.to_datetime(prices.index)
                results[ticker] = prices

        return results

    except Exception as e:
        print(f"Error fetching data for tickers {tickers}: {e}")
        return {}


def plot_stock_and_rolling_average(ticker, data, rolling_window):
    rolling_average = data.rolling(window=rolling_window, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(data.index, data, label='Stock Prices', color='blue')
    if not rolling_average.isna().all():
        ax.plot(rolling_average.dropna().index, rolling_average.dropna(), 
                label=f'{rolling_window}-Day Rolling Average', color='orange')

    ax.set_title(f'{ticker} - Stock Prices and {rolling_window}-Day Rolling Average')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    ax.legend()
    ax.grid()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    string = base64.b64encode(buf.read())
    uri = 'data:image/png;base64,' + string.decode('utf-8')
    return uri

def check_upward_trend(data, trend_days, period):
    rolling_average = data.rolling(window=period).mean()
    trend_period_data = rolling_average[-trend_days:]
    return all(x < y for x, y in zip(trend_period_data, trend_period_data[1:]))

@app.route('/')
def home():
    data = load_data()
    if data['default_tickers'] or data['default_watch_list']:
        return redirect(url_for('results'))
    return render_template('index.html', default_tickers=data['default_tickers'], default_watch_list=data['default_watch_list'])

@app.route('/results', methods=['GET', 'POST'])
def results():
    if request.method == 'POST':
        tickers = [ticker.strip() for ticker in request.form['tickers'].split(',')]
        watch_list = [ticker.strip() for ticker in request.form['watch_list'].split(',')]
        period = int(request.form['period'])
        watch_list_period = int(request.form['watch_list_period'])
        watch_list_trend_days = int(request.form['watch_list_trend_days'])

        data = {
            "default_tickers": request.form['tickers'],
            "default_watch_list": request.form['watch_list']
        }
        save_data(data)
    else:
        data = load_data()
        tickers = [ticker.strip() for ticker in data['default_tickers'].split(',')]
        watch_list = [ticker.strip() for ticker in data['default_watch_list'].split(',')]
        period = 150
        watch_list_period = 150
        watch_list_trend_days = 30

    # Fetch data for tickers and watch_list together
    tickers_data = fetch_and_store_stock_data(tickers + watch_list, period + 150)
    
    results = []

    for ticker in tickers:
        if ticker in tickers_data:
            close_prices = tickers_data[ticker]
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
            
            results.append({
                'ticker': ticker,
                'current_price': f"${current_price:.2f}" if current_price else "N/A",
                'average_price': f"${rolling_avg:.2f}" if rolling_avg else "N/A",
                'percentage_diff': f"{percentage_diff:.2f}%" if percentage_diff else "N/A",
                'action': action,
                'external_link': f"https://finance.yahoo.com/quote/{ticker}/chart"
            })

    for ticker in watch_list:
        if ticker in tickers_data:
            close_prices = tickers_data[ticker]
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

            trend = check_upward_trend(close_prices, watch_list_trend_days, period)
            trend_status = "Upward" if trend else "Not upward"

            if trend_status == "Not upward":
                action = "Stay Away"
            elif trend_status == "Upward":
                if percentage_diff is not None and (-1.5 < percentage_diff < 1.5 ) and current_price > rolling_avg:
                    action = "Buy"
                elif percentage_diff is not None and -2 < percentage_diff < 2 and current_price < rolling_avg:
                    action = "Get Ready"
                elif percentage_diff is not None and percentage_diff > 1.5 and current_price > rolling_avg:
                    action = "Next Time"
                else:
                    action = ""
            else:
                action = ""

            plot_url = plot_stock_and_rolling_average(ticker, close_prices, period)
            external_link = f"https://finance.yahoo.com/quote/{ticker}/chart"

            results.append({'ticker': ticker, 'current_price': f"${current_price:.2f}" if current_price else "N/A",
                            'average_price': f"${rolling_avg:.2f}" if rolling_avg else "N/A",
                            'percentage_diff': f"{percentage_diff:.2f}%" if percentage_diff else "N/A",
                            'action': action, 'trend_status': trend_status, 
                            'plot_url': plot_url, 'external_link': external_link})

    return render_template('results.html', results=results)

@app.route('/edit')
def edit():
     data = load_data()
     return render_template('index.html', default_tickers=data['default_tickers'], default_watch_list=data['default_watch_list'])

if __name__ == '__main__':
    app.run(debug=True)