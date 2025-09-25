import numpy as np
import matplotlib.pyplot as plt
import scipy.interpolate

# ✅ 6×9 크기의 샘플 온도 데이터 생성
np.random.seed(42)  # 랜덤 시드 고정
temperature_data = np.random.randint(120, 1650, (9, 6))  # 120°C ~ 1650°C 범위 데이터

# ✅ 보간을 위한 X, Y 좌표 설정
x = np.arange(0, 6)  # X 축 (좌우 6개)
y = np.arange(0, 9)  # Y 축 (상하 9개)
X, Y = np.meshgrid(x, y)

# ✅ 2D 보간 (Bilinear)
interp_func = scipy.interpolate.interp2d(x, y, temperature_data, kind='linear')

# ✅ X, Y축 교차점의 좌표 계산 (0.5 간격)
x_new = np.linspace(0, 5, 11)  # 보간된 X 좌표
y_new = np.linspace(0, 8, 17)  # 보간된 Y 좌표
X_new, Y_new = np.meshgrid(x_new, y_new)
temperature_interp = interp_func(x_new, y_new)  # 보간 적용

# ✅ 히트맵 출력
plt.figure(figsize=(8, 6))
plt.imshow(temperature_interp, cmap='coolwarm', interpolation='bilinear', origin='lower')
plt.colorbar(label="Temperature (°C)")
plt.title("Interpolated Temperature Heatmap")
plt.xlabel("X-Axis (Left to Right)")
plt.ylabel("Y-Axis (Bottom to Top)")
plt.xticks(range(len(x_new)), labels=[f"{v:.1f}" for v in x_new])
plt.yticks(range(len(y_new)), labels=[f"{v:.1f}" for v in y_new])
plt.show()
