import numpy as np

# ✅ 100개의 12×18 온도 데이터 생성 (120°C ~ 1650°C 범위)
np.random.seed(42)  # 시드 고정 (재현 가능)
temperature_data = np.random.randint(120, 1650, (100, 12, 18))  # (100개, 12×18 크기)

# ✅ 생성된 온도 데이터를 파일에 저장
with open("C:/DavidProject/flask_project/flask_schedular/pybo/test/temp_data.py", "w") as f:
    f.write("temperature_data = " + str(temperature_data.tolist()))

print("✅ temp_data.py 파일이 생성되었습니다! (100개 12×18 온도 배열 저장 완료)")
