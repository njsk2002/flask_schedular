import socket
import time

# KIKUSUI PWX 전원공급기 연결 정보
HOST = "192.168.0.21"  # PWX의 IP 주소
PORT = 5025            # SCPI 기본 포트

# 소켓 연결
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    
    def send_command(cmd, read_response=False, delay=0.5):
        """ SCPI 명령을 전송하고 필요하면 응답을 읽음 """
        s.sendall((cmd + "\n").encode())  # 명령 전송
        time.sleep(delay)  # 응답 대기
        if read_response:
            response = s.recv(1024).decode().strip()
            return response
        return None

    def set_voltage_current(voltage, current):
        """ 전압과 전류를 설정하는 함수 """
        send_command(f"VOLT {voltage}")  # 전압 설정
        send_command(f"CURR {current}")  # 전류 설정
        print(f"✅ 전압 {voltage}V, 전류 {current}A 설정 완료")

    def measure_voltage_current():
        """ 현재 출력 전압 및 전류를 측정하는 함수 """
        measured_voltage = send_command("MEAS:VOLT?", read_response=True, delay=0.5)
        measured_current = send_command("MEAS:CURR?", read_response=True, delay=0.5)

        # ✅ 단위 변환 (과학적 표기법 → 일반 숫자)
        voltage_value = float(measured_voltage)
        current_value = float(measured_current)

        print(f"📊 Measured Voltage: {voltage_value:.3f} V")
        print(f"📊 Measured Current: {current_value:.3f} A")
        
        return voltage_value, current_value

    def charge_until_threshold(threshold=0.1):
        """ 충전 중 전류가 특정 임계값 이하(예: 0.1A)가 될 때까지 모니터링 """
        print(f"🔄 충전 시작... 전류가 {threshold}A 이하가 될 때까지 모니터링 중")

        # ✅ 출력 켜기
        send_command("OUTP ON", delay=2.0)

        while True:
            voltage, current = measure_voltage_current()

            # ✅ 전류가 threshold(0.1A) 이하로 내려가면 종료
            if current <= threshold:
                print("⚡ 충전 완료! 전류가 임계값 이하로 내려감.")
                break

            time.sleep(2)  # 2초마다 측정 반복

        # ✅ 충전 완료 후 출력 OFF
        send_command("OUTP OFF", delay=0.5)
        print("🔴 Power Supply Output OFF 완료.")

    # ✅ 장치 초기화
    send_command("*RST", delay=1.0)
    print("🔄 장치 초기화 완료.")

    # ✅ 전압 및 전류 설정 (5V 출력, 최대 1A)
    set_voltage_current(voltage=4.2, current=2.0)

    # ✅ 충전 완료 조건 (전류 0.1A 이하까지 모니터링)
    charge_until_threshold(threshold=0.1)
