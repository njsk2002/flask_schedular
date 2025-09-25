import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import scipy.interpolate
import temp_data  # 생성된 데이터 불러오기

# ▣ 1) 온도 데이터 불러오기 (예: (100, 12, 18) 형태)
temperature_values = np.array(temp_data.temperature_data)
time_steps = temperature_values.shape[0]  # 총 시간 스텝 개수 (예: 100)

# ▣ 2) 센서 위치 설정
#   - 가로(X) 축: 센서 13~30 (개수 18개) → x=0..17
#   - 세로(Y) 축: 센서 1~12  (개수 12개) → y=0..11
x_sensors = np.linspace(0, 17, 18)  # X축 0~17
y_sensors = np.linspace(0, 11, 12)  # Y축 0~11

# ▣ 3) 보간 좌표 (더 부드러운 그래프를 위해 50×50으로 확장)
x_new = np.linspace(0, 17, 50)
y_new = np.linspace(0, 11, 50)

# ▣ 4) Figure 생성 + 크기/비율 조정
fig, ax = plt.subplots(figsize=(10, 7))

# ▣ 5) imshow 초기화 (extent 지정)
#   - extent=[xmin, xmax, ymin, ymax] → 이미지 좌표 범위 지정
heatmap = ax.imshow(
    np.zeros((50, 50)),
    cmap='coolwarm',
    interpolation='bilinear',
    origin='lower',
    extent=[x_new[0], x_new[-1], y_new[0], y_new[-1]],  # x=0..17, y=0..11
    aspect='auto'
)

# ▣ 6) 컬러바 추가
cbar = plt.colorbar(heatmap, ax=ax)
cbar.set_label("Temperature (°C)")

# ▣ 7) 축 레이블 및 제목 설정
ax.set_title("Real-Time Temperature Heatmap")
ax.set_xlabel("X-Axis (Sensor 13~30)")
ax.set_ylabel("Y-Axis (Sensor 1~12)")

# ▣ 8) 센서 눈금(Ticks) 설정
ax.set_xticks(x_sensors)
ax.set_xticklabels([f"S{x+13}" for x in range(18)])  # 예: S13 ~ S30
ax.set_yticks(y_sensors)
ax.set_yticklabels([f"S{y+1}" for y in range(12)])   # 예: S1 ~ S12

# ▣ 9) 센서 위치에 맞춰 Grid Line 추가
for x in x_sensors:
    ax.axvline(x, color='black', linestyle='--', linewidth=0.5)
for y in y_sensors:
    ax.axhline(y, color='black', linestyle='--', linewidth=0.5)

# ▣ 10) 애니메이션 업데이트 함수
def update(frame):
    current_temp = temperature_values[frame]  # 현재 (12×18) 온도 데이터

    # (x_sensors, y_sensors) → current_temp를 2D 보간
    # 주의: interp2d의 인자는 (x, y, z)
    # 여기서 x=가로축(18개), y=세로축(12개), z=12×18 크기의 2D 배열
    interp_func = scipy.interpolate.interp2d(x_sensors, y_sensors, current_temp, kind='cubic')

    # 50×50 크기로 보간
    temp_interpolated = interp_func(x_new, y_new)

    # imshow 업데이트 (extent 동일)
    heatmap.set_array(temp_interpolated)
    heatmap.set_clim(120, 1650)  # 온도 범위 고정
    ax.set_title(f"Real-Time Temperature Heatmap (Time Step {frame})")

    return (heatmap,)

# ▣ 11) 애니메이션 실행
ani = animation.FuncAnimation(fig, update, frames=time_steps, interval=1000, blit=False)

plt.tight_layout()
plt.show()
