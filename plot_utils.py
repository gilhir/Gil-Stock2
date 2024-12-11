import io
import base64
import matplotlib.pyplot as plt
import matplotlib

# Use the Agg backend for Matplotlib
matplotlib.use('Agg')

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
