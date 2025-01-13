from flask import Flask, send_file
import io
import matplotlib.pyplot as plt
import pandas as pd
import mplfinance as mpf

app = Flask(__name__)

@app.route('/get_chart_image', methods=['GET'])
def get_chart_image():
    # Sample data for demonstration
    data = {
        'Date': ['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05'],
        'Open': [100, 110, 105, 115, 120],
        'High': [105, 115, 110, 120, 125],
        'Low': [95, 105, 100, 110, 115],
        'Close': [102, 112, 108, 118, 122],
        'Volume': [10000, 12000, 11000, 13000, 14000]
    }
    df = pd.DataFrame(data)
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)

    # Plotting using mplfinance
    mc = mpf.make_marketcolors(up='r', down='b', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='dotted')

    apds = [mpf.make_addplot(df['Close'], color='black')]

    fig, axlist = mpf.plot(df, type='candle', style=s, addplot=apds, volume=True, 
                           title='Stock Price with Moving Averages', ylabel='Price', ylabel_lower='Volume', 
                           show_nontrading=False, returnfig=True)

    # Save the figure to a BytesIO buffer
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)

    # Close the figure to release memory
    plt.close(fig)

    if buf.tell() > 0:
        print("Image successfully saved.")
    else:
        print("Failed to save the image.")

    # Return the image file as a response
    return send_file(buf, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)
