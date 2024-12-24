import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

# 엑셀 파일 경로
file_path = 'C:/projects/download/chartinfo.xlsx'

# 데이터 불러오기
data = pd.read_excel(file_path, parse_dates=True, index_col='Date')

# 이동평균선을 계산할 조건 설정
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
    if len(data) >= window:
        data[ma_name] = data['Close'].rolling(window=window).mean()

# NaN 값 제거
data.dropna(inplace=True)

# changevol 값을 숫자로 변환하여 처리
data['changevol'] = data['changevol'].str.replace('%', '').astype(float)

# changevol 값의 양수와 음수에 따라 색상을 지정합니다.
data['color'] = data['changevol'].apply(lambda x: 'red' if x > 0 else 'blue')

# 데이터가 비어 있는지 확인
if data.empty:
    print("선택한 기간에 대한 데이터가 없습니다.")
else:
    # 유효한 이동평균선을 추가할 plot 리스트 생성
    apds = []
    for ma_name in moving_averages.keys():
        if ma_name in data.columns:
            color = {'3_MA': 'red', '5_MA': 'blue', '10_MA': 'green', '20_MA': 'orange', '60_MA': 'purple', '120_MA': 'brown'}
            apds.append(mpf.make_addplot(data[ma_name], color=color[ma_name], linestyle='-', width=0.7))

    # 캔들스틱 차트 그리기
    mpf.plot(data, type='candle', style='charles', addplot=apds, volume=True,
             title='이동평균선 및 Changevol이 포함된 주가 차트',
             ylabel='가격', ylabel_lower='거래량')

    # changevol에 대한 주석 추가
    for i in range(len(data)):
        if not pd.isnull(data['changevol'][i]):
            plt.annotate(f"{data['changevol'][i]:.1f}%", (data.index[i], data['Low'][i]),
                         textcoords="offset points", xytext=(10, 10),
                         fontsize=8, arrowprops=dict(facecolor=data['color'][i], arrowstyle='->'))

    plt.show()
