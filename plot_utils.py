import json
import requests
import pandas as pd
import stock_utils
import time

def fetch_stock_data(ticker, retries=3, delay=1):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    for attempt in range(retries):
        response = requests.get(url)
        print(f"Response status code for {ticker}: {response.status_code}")

        if response.status_code == 429:
            print(f"Too many requests for {ticker}. Retrying in {delay} seconds...")
            time.sleep(delay)
            delay *= 2  # Exponential backoff
            continue
        
        try:
            data = response.json()
            return data
        except json.JSONDecodeError as e:
            print(f"JSON decode error for {ticker}: {e}")
            return None  # Return None if there's an error parsing the JSON
    
    print(f"Failed to fetch data for {ticker} after {retries} attempts.")
    return None

def parse_stock_data(data):
    timestamp = data['chart']['result'][0]['timestamp']
    close_prices = data['chart']['result'][0]['indicators']['quote'][0]['close']
    df = pd.DataFrame({'timestamp': timestamp, 'close': close_prices})
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    print(f"Parsed data: {df.head()}")
    return df

def create_chart_js_script(ticker, df, rolling_window):
    labels = df['timestamp'].dt.strftime('%Y-%m-%d').tolist()
    data = df['close'].tolist()
    rolling_avg = df['close'].rolling(window=rolling_window).mean().fillna(0).tolist()

    script = f'''
    <script>
        const ctx = document.getElementById('{ticker}Chart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {labels},
                datasets: [{{
                    label: '{ticker} Stock Price',
                    data: {data},
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                }},
                {{
                    label: '{rolling_window}-Day Rolling Average',
                    data: {rolling_avg},
                    backgroundColor: 'rgba(255, 159, 64, 0.2)',
                    borderColor: 'rgba(255, 159, 64, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                scales: {{
                    y: {{
                        beginAtZero: false
                    }}
                }}
            }}
        }});
    </script>
    '''
    print(f"Generated Chart.js script for {ticker}")
    return script

def generate_plot_html(tickers, rolling_window=150):
    html = ''

    for ticker in tickers:
        data = fetch_stock_data(ticker)
        if data:
            df = parse_stock_data(data)
            html += f'<canvas id="{ticker}Chart"></canvas>'
            html += create_chart_js_script(ticker, df, rolling_window)
        else:
            print(f"No data found for {ticker}")

    print(f"Generated HTML: {html}")
    return html
