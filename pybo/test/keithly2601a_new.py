import socket
import time

# Keithley 2601A 연결 정보
host = "192.168.0.19"  # Keithley의 IP 주소
port = 5025             # TSP 기본 포트

# 소켓 연결
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((host, port))

    def send_command(cmd, read_response=False, delay=0.5):
        """ TSP 명령을 전송하고 필요하면 응답을 읽음 """
        s.sendall(cmd.encode() + b'\n')
        time.sleep(delay)  # 충분한 대기 시간 추가
        if read_response:
            response = s.recv(1024).decode().strip()
            return response
        return None
    
    # ✅ 장치 정보 요청
    device_info = send_command('print(localnode.model)', read_response=True, delay=0.2)
    print("Device Info:", device_info)

    # ✅ 장치 초기화 (Reset)
    send_command('reset()', delay=1.5)

    # ✅ 전압 소스 및 측정 설정 (TSP 방식 사용)
    send_command('smua.source.func = smua.OUTPUT_DCVOLTS', delay=0.1)  # 전압 모드 설정
    send_command('smua.source.levelv = 10', delay=0.1)  # 10V 출력 설정
    send_command('smua.source.limiti = 0.01', delay=0.1)  # 10mA 제한 설정
    send_command('smua.measure.rangei = 0.01', delay=0.1)  # 전류 측정 범위 설정

    # ✅ 출력 켜기 (TSP 방식)
    send_command('smua.source.output = smua.OUTPUT_ON', delay=1.0)  # 출력 켜기

    # ✅ 측정 수행 (TSP 방식)
    # TSP 방식일 경우 반드시 값을 읽어올때는 'print()'로 호출하여야 함
    measured_current = send_command('print(smua.measure.i())', read_response=True, delay=1.0) 
    print("Measured Current:", measured_current)

    # ✅ 출력 끄기
    send_command('smua.source.output = smua.OUTPUT_OFF', delay=0.5)
