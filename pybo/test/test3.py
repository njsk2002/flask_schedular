import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

# 예제 데이터 생성
data = {
    'Date': ['20240604', '20240603', '20240531', '20240530', '20240529', '20240528', '20240527', '20240524', '20240523', '20240522', '20240521', '20240520', '20240517', '20240516', '20240514', '20240513', '20240510'],
    'Open': [43200, 41700, 42800, 44050, 44550, 44200, 45100, 45550, 46150, 44850, 45100, 44700, 45500, 45700, 45750, 44600, 42650],
    'High': [43200, 43750, 43250, 44100, 44800, 45200, 45250, 45550, 46150, 46750, 45450, 45500, 45750, 46200, 45800, 45800, 44700],
    'Low': [42100, 41700, 41650, 42650, 43600, 44200, 44100, 44900, 45300, 44800, 44600, 44250, 44550, 45050, 44700, 43850, 42450],
    'Close': [42300, 43650, 41750, 42750, 44050, 44500, 44350, 44900, 45550, 46150, 44800, 45000, 44750, 45500, 45150, 45750, 44500],
    'Volume': [822049200, 1295197850, 994712700, 1004282400, 565642200, 863989500, 821847850, 664023050, 1258327450, 2556372400, 744625750, 885553750, 835147650, 1720806700, 1267116500, 2869014150, 2409038500]
}

# 데이터프레임 생성
df = pd.DataFrame(data)
df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
df.set_index('Date', inplace=True)
df.sort_index(ascending=False, inplace=True)  # 날짜를 역순으로 정렬

# 최근 5일의 데이터 선택
recent_data = df.head(6).iloc[::-1]  # 최근 6일을 선택하고 역순으로 정렬하여 최근 5일만 남김

# 5일선 계산
recent_data['5_MA'] = recent_data['Close'].rolling(window=5).mean()

# 캔들 차트 그리기
mpf.plot(recent_data, type='candle', style='charles', volume=True, 
         title='Stock Price with 5-day Moving Average (Recent 5 days)', 
         ylabel='Price', ylabel_lower='Volume',
         addplot=[mpf.make_addplot(recent_data['5_MA'], color='blue')])

plt.show()
