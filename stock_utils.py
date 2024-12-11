import os
import datetime
import yfinance as yf
import pandas as pd
from data_utils import load_data, save_data

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

def check_upward_trend(data, trend_days, period):
    rolling_average = data.rolling(window=period).mean()
    trend_period_data = rolling_average[-trend_days:]
    return all(x < y for x, y in zip(trend_period_data, trend_period_data[1:]))
