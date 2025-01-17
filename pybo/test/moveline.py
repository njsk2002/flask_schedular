import pandas as pd
import matplotlib.pyplot as plt

# 엑셀 파일 불러오기
data = pd.read_excel('C:/projects/download/chartinfo.xlsx', parse_dates=True, index_col='Date')


# 이동평균선 계산
data['10_MA'] = data['Close'].rolling(window=10).mean()
data['20_MA'] = data['Close'].rolling(window=20).mean()
data['50_MA'] = data['Close'].rolling(window=50).mean()
data['100_MA'] = data['Close'].rolling(window=100).mean()

# RSI 계산 함수
def calculate_RSI(data, window):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    RS = gain / loss
    RSI = 100 - (100 / (1 + RS))
    return RSI

data['RSI_14'] = calculate_RSI(data, 14)

# MACD 계산
data['12_EMA'] = data['Close'].ewm(span=12, adjust=False).mean()
data['26_EMA'] = data['Close'].ewm(span=26, adjust=False).mean()
data['MACD'] = data['12_EMA'] - data['26_EMA']
data['Signal_Line'] = data['MACD'].ewm(span=9, adjust=False).mean()

# 볼린저 밴드 계산
data['20_SD'] = data['Close'].rolling(window=20).std()
data['Upper_Band'] = data['20_MA'] + (2 * data['20_SD'])
data['Lower_Band'] = data['20_MA'] - (2 * data['20_SD'])

# 그래프 그리기
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 14), sharex=True)

# 주가와 이동평균선
ax1.plot(data['Close'], label='Close Price')
ax1.plot(data['10_MA'], label='10 Day Moving Average')
ax1.plot(data['20_MA'], label='20 Day Moving Average')
ax1.plot(data['50_MA'], label='50 Day Moving Average')
ax1.plot(data['100_MA'], label='100 Day Moving Average')
ax1.fill_between(data.index, data['Upper_Band'], data['Lower_Band'], color='gray', alpha=0.2)
ax1.set_title('Stock Price with Moving Averages and Bollinger Bands')
ax1.set_ylabel('Price')
ax1.legend()
ax1.grid(True)

# MACD
ax2.plot(data['MACD'], label='MACD', color='blue')
ax2.plot(data['Signal_Line'], label='Signal Line', color='red')
ax2.set_title('MACD')
ax2.legend()
ax2.grid(True)

# RSI
ax3.plot(data['RSI_14'], label='RSI (14 days)', color='purple')
ax3.axhline(70, color='red', linestyle='--')
ax3.axhline(30, color='green', linestyle='--')
ax3.set_title('RSI (14 days)')
ax3.legend()
ax3.grid(True)

plt.show()