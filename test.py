    for ticker in tickers:
        close_prices = fetch_and_store_stock_data(ticker, period)
        
        # Debugging: Check if close_prices is empty or contains invalid data
        if close_prices.empty:
            print(f"No data available for ticker {ticker}")
            continue  # Skip this ticker if no data is available
        
        print(f"Data for {ticker}: {close_prices}")  # Debugging line
        
        current_price = close_prices.iloc[-1]
        rolling_avg = close_prices.rolling(window=150).mean().iloc[-1]
        
        # Ensure valid rolling average
        if pd.isna(rolling_avg):
            print(f"Rolling average is NaN for {ticker}")
            continue  # Skip this ticker if rolling average is NaN
        
        average_price = rolling_avg
        
        if current_price is not None:
            percentage_diff = ((current_price - average_price) / average_price) * 100
            if pd.isna(percentage_diff):
                print(f"Percentage difference is NaN for {ticker}")
                continue  # Skip this ticker if percentage difference is NaN
            action = "Sell" if percentage_diff < 0 else ""
            external_link = f"https://finance.yahoo.com/quote/{ticker}/chart"
            
            results.append({'ticker': ticker, 'current_price': f"${current_price:.2f}", 
                            'average_price': f"${average_price:.2f}", 'percentage_diff': f"{percentage_diff:.2f}%", 
                            'action': action, 'external_link': external_link})

    # Same logic for the watch_list
    for ticker in watch_list:
        close_prices = fetch_and_store_stock_data(ticker, watch_list_period)
        
        # Debugging: Check if close_prices is empty or contains invalid data
        if close_prices.empty:
            print(f"No data available for ticker {ticker}")
            continue  # Skip this ticker if no data is available
        
        print(f"Data for {ticker}: {close_prices}")  # Debugging line
        
        current_price = close_prices.iloc[-1]
        rolling_avg = close_prices.rolling(window=150).mean().iloc[-1]
        
        # Ensure valid rolling average
        if pd.isna(rolling_avg):
            print(f"Rolling average is NaN for {ticker}")
            continue  # Skip this ticker if rolling average is NaN
        
        average_price = rolling_avg
        
        if current_price is not None:
            percentage_diff = ((current_price - average_price) / average_price) * 100
            if pd.isna(percentage_diff):
                print(f"Percentage difference is NaN for {ticker}")
                continue  # Skip this ticker if percentage difference is NaN
            
            # Handle trend logic:
            trend = check_upward_trend(close_prices, watch_list_trend_days, period)
            trend_status = "Upward" if trend else "Not upward"

            if trend_status == "Not upward":
                action = "Stay Away"
            elif trend_status == "Upward":
                if percentage_diff < 1.5 and current_price > average_price:
                    action = "Buy"
                elif percentage_diff < 2 and current_price < average_price:
                    action = "Get Ready"
                elif percentage_diff > 1.5 and current_price > average_price:
                    action = "Next Time"
                else:
                    action = ""
            else:
                action = ""

            plot_url = plot_stock_and_rolling_average(ticker, close_prices, period)
            external_link = f"https://finance.yahoo.com/quote/{ticker}/chart"

            results.append({'ticker': ticker, 'current_price': f"${current_price:.2f}", 'average_price': f"${average_price:.2f}", 
                            'percentage_diff': f"{percentage_diff:.2f}%", 'action': action, 'trend_status': trend_status, 
                            'plot_url': plot_url, 'external_link': external_link})

    return render_template('results.html', results=results)
