import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

# 엑셀 파일 불러오기
file_path = 'C:/projects/download/chartinfo.xlsx'  # 업로드된 파일 경로로 변경하세요
data = pd.read_excel(file_path, dtype={'Date': str})

# Date 형식 변환 (예: 20230102 -> 2023-01-02) 및 데이터 역순으로 정렬
data['Date'] = pd.to_datetime(data['Date'], format='%Y%m%d')
data.set_index('Date', inplace=True)
data = data[::-1]  # 데이터 역순으로 정렬
print('역순데이터', data)

# 데이터 확인
print(f"Total data points: {len(data)}")

# 일봉, 주봉, 월봉으로 변환하는 함수
def resample_data(data, period):
    if period == 'D':
        return data
    elif period == 'W':
        return data.resample('W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
    elif period == 'M':
        return data.resample('M').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()

# 기간 선택 (일봉 'D', 주봉 'W', 월봉 'M')
period = 'D'
resampled_data = resample_data(data, period)

# 이동평균선을 계산 및 표시할 조건을 설정
moving_averages = {
    '3_MA': 3,
    '5_MA': 5,
    '10_MA': 10,
    '20_MA': 20,
    '60_MA': 60,
    '120_MA': 120
}

# 이동평균선 계산 및 유효한 데이터만 남기기
for ma_name, window in moving_averages.items():
    if len(resampled_data) >= window:
        resampled_data[ma_name] = resampled_data['Close'].rolling(window=window).mean()

# NaN 값 제거
resampled_data = resampled_data.dropna()

# 120일 이동평균선이 없을 경우 60일 이동평균선 추가
if '120_MA' not in resampled_data.columns:
    moving_averages.pop('120_MA')
    if len(resampled_data) >= 60:
        resampled_data['60_MA'] = resampled_data['Close'].rolling(window=60).mean()

# 데이터 확인
print(resampled_data)

# 데이터가 비어 있는지 확인
if resampled_data.empty:
    print("No data available for the selected period.")
else:
    # marketcolors 객체 생성
    #mc = mpf.make_marketcolors(up='g', down='r')  # 양봉은 초록색, 음봉은 빨간색으로 설정
    mc = mpf.make_marketcolors(up='r', down='b', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle='dotted')  # 점선 그리드 스타일 추가

    # 유효한 이동평균선을 추가할 plot 리스트 생성
    apds = []
    for ma_name in moving_averages.keys():
        if ma_name in resampled_data.columns:
            color = {'3_MA': 'red', '5_MA': 'blue', '10_MA': 'green', '20_MA': 'orange', '60_MA': 'purple', '120_MA': 'brown'}
            apds.append(mpf.make_addplot(resampled_data[ma_name], color=color[ma_name], linestyle='-', width=0.7))
            #apds.append(mpf.make_addplot(resampled_data['Volume'], panel=1, type='bar', color='b', ylabel='Volume', secondary_y=True))

    # 캔들 차트 그리기
    mpf.plot(resampled_data, type='candle', style= s, addplot=apds, volume=True, 
             title='Stock Price with Moving Averages', ylabel='Price', ylabel_lower='Volume', 
             show_nontrading=False) # show_nontrading=True로 설정하여 비거래일도 표시  # marketcolors 객체 설정

    plt.show()
