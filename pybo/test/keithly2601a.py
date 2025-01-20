import socket

# Keithley 2601A 연결 정보
host = "192.168.0.17"  # Keithley의 IP 주소
port = 5025             # SCPI 기본 포트

# 소켓 연결
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((host, port))

    # *IDN? 명령: 장치 정보 요청
    s.sendall(b'*IDN?\n')
    response = s.recv(1024)
    print("Device Info:", response.decode())

    # 전압 설정 및 측정 예제
    s.sendall(b':SOUR:VOLT 5.0\n')  # 전압 설정
    s.sendall(b':OUTP ON\n')        # 출력 켜기
    s.sendall(b':MEAS:CURR?\n')     # 전류 측정
    current = s.recv(1024)
    print("Measured Current:", current.decode())

    s.sendall(b':OUTP OFF\n')       # 출력 끄기
