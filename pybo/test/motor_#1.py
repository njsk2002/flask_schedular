import serial
import time
import struct

# 시리얼 포트 설정
ser = serial.Serial(
    port='COM5',       # 사용하는 포트 이름 (예: COM3)
    baudrate=115200,   # 전송 속도
    bytesize=serial.EIGHTBITS, # 데이터 비트
    parity=serial.PARITY_NONE, # 패리티 비트
    stopbits=serial.STOPBITS_ONE, # 정지 비트
    timeout=1          # 타임아웃 설정 (초 단위)
)

# CRC 계산 함수 (예시로 간단히 XOR로 계산)
def calculate_crc(data):
    crc = 0
    for byte in data:
        crc ^= byte
    return crc

# CAN 프레임 생성 함수
def create_can_frame(cob_id, data):
    frame = bytearray(15)
    frame[0] = 0xAA  # Start byte
    frame[1:5] = struct.pack('<I', cob_id)  # COB-ID (리틀 엔디안으로 변환)
    frame[5] = len(data)  # Number of Byte
    frame[6:6+len(data)] = data  # Data
    frame[14] = calculate_crc(frame[:14])  # CRC
    print('frame :', frame)
    return frame
    #frame: bytearray(b'\xAA\x7D\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
   

# 명령어 전송 함수
def send_command(command):
    ser.write(command)
    time.sleep(0.1)  # 약간의 대기 시간 추가
    response = ser.read(15)  # 15 바이트 읽기
    return response

# 모터 초기화 함수
def initialize_motor(node_id):
    # 제어 워드(컨트롤 워드) 쓰기: 0x301D, 0x1A
    control_word_index = bytearray([0x1D, 0x30])
    sub_index = 0x1A
    data = bytearray([0x00, 0x00, 0x27, 0x10])
    cob_id = 0x600 + node_id 
    sdo_data = struct.pack('<B2sB4s', 0x23, control_word_index, sub_index, data)
    can_frame = create_can_frame(cob_id, sdo_data)
    response = send_command(can_frame)
    print("Motor Initialized:", response)

# 모터 속도 설정 함수
def set_motor_speed(node_id, speed):
    # 목표 속도(타겟 벨로시티) 쓰기: 0x301D, 0x1A
    target_velocity_index = bytearray([0x1D, 0x30])
    sub_index = 0x1A
    data = struct.pack('<i', speed)  # 속도 값 4바이트 정수형
    cob_id = 0x600 + node_id
    sdo_data = struct.pack('<B2sB4s', 0x23, target_velocity_index, sub_index, data)
    can_frame = create_can_frame(cob_id, sdo_data)
    response = send_command(can_frame)
    print("Set Motor Speed:", response)

def testmotor(node_id):
    # 제어 워드(컨트롤 워드) 쓰기: 0x301C, 0x01
    control_word_index = bytearray([0x1C, 0x30])
    sub_index = 0x01
    data = bytearray([0x00, 0x00, 0x00, 0x02])
    cob_id = 0x600 + node_id 
    sdo_data = struct.pack('<B2sB4s', 0x23, control_word_index, sub_index, data)
    can_frame = create_can_frame(cob_id, sdo_data)
    response = send_command(can_frame)
    print("Motor Test:", response)

def can_addr(node_id):
    # 제어 워드(컨트롤 워드) 쓰기: 0x3017, 0x02
    control_word_index = bytearray([0x17, 0x30])
    sub_index = 0x02
    data = bytearray([0x7F, 0x00, 0x00, 0x00])
    cob_id = 0x600 + node_id 
    sdo_data = struct.pack('<B2sB4s', 0x23, control_word_index, sub_index, data)
    can_frame = create_can_frame(cob_id, sdo_data)
    response = send_command(can_frame)
    print("can_addr:", response)

def can_baud(node_id):
    # 제어 워드(컨트롤 워드) 쓰기: 0x3017, 0x03
    control_word_index = bytearray([0x17, 0x30])
    sub_index = 0x03
    data = bytearray([0x7D, 0x00, 0x00, 0x00])
    cob_id = 0x600 + node_id 
    sdo_data = struct.pack('<B2sB4s', 0x23, control_word_index, sub_index, data)
    can_frame = create_can_frame(cob_id, sdo_data)
    response = send_command(can_frame)
    print("can_baud:", response)

# 모터 ENABLE
def enable_motor(node_id):
    # 제어 워드(컨트롤 워드) 쓰기: 0x301C, 0x01
    control_word_index = bytearray([0x1C, 0x30])
    sub_index = 0x01
    data = bytearray([0x02, 0x00, 0x00, 0x00])
    cob_id = 0x600 + node_id 
    sdo_data = struct.pack('<B2sB4s', 0x23, control_word_index, sub_index, data)
    can_frame = create_can_frame(cob_id, sdo_data)
    response = send_command(can_frame)
    print("Motor Enable:", response)

# 모터 시작 함수
def start_motor(node_id):
    # 제어 워드(컨트롤 워드) 쓰기: 0x3029, 0x26
    control_word_index = bytearray([0x29, 0x30])
    sub_index = 0x26
    data = bytearray([0x00, 0x00, 0x07, 0xA8])
    cob_id = 0x600 + node_id 
    sdo_data = struct.pack('<B2sB4s', 0x23, control_word_index, sub_index, data)
    can_frame = create_can_frame(cob_id, sdo_data)
    response = send_command(can_frame)
    print("Motor Started:", response)

# 모터 정지 함수
def stop_motor(node_id):
    # 제어 워드(컨트롤 워드) 쓰기: 0x301D, 0x1A
    control_word_index = bytearray([0x1D, 0x30])
    sub_index = 0x1A
    data = bytearray([0x00, 0x00, 0x27, 0x10])
    cob_id = 0x600 + node_id
    sdo_data = struct.pack('<B2sB4s', 0x23, control_word_index, sub_index, data)
    can_frame = create_can_frame(cob_id, sdo_data)
    response = send_command(can_frame)
    print("Motor Stopped:", response)

# 메인 함수
def main():
    node_id = 127  # 예시 노드 ID
    
    # 설정
    can_addr(node_id)
    can_baud(node_id)
    time.sleep(1)
    
    # 모터 enable
    enable_motor(node_id)
    time.sleep(1)

    # # 모터 초기화
    # initialize_motor(node_id)
    # time.sleep(1)

    # # 모터 속도 설정
    # set_motor_speed(node_id, 1000)  # 1000 RPM 설정
    # time.sleep(1)

    # # 모터 시작
    # start_motor(node_id)
    # time.sleep(5)  # 5초 동안 모터 작동

    # # 모터 정지
    # stop_motor(node_id)

    # # 시리얼 포트 닫기
    # ser.close()

if __name__ == "__main__":
    main()
에서 can_frame 결과값만 보여줘 코드는 필요없어

Please write in Korean language.