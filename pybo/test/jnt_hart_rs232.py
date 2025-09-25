import serial
import time

# 실제 HART 어댑터에 맞게 COM 포트를 설정 (예: COM12)
hart_serial = serial.Serial(
    port='COM12',
    baudrate=1200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_ODD,
    stopbits=serial.STOPBITS_ONE,
    timeout=1,
    rtscts=True
)

# 어댑터 전원 ON (DTR=1) 및 초기 수신 모드 (RTS=0)
hart_serial.dtr = True
hart_serial.rts = False

def calculate_checksum(data):
    """Start Byte부터 마지막 Data Byte까지 XOR 연산으로 체크섬 계산"""
    checksum = 0
    for b in data:
        checksum ^= b
    return checksum

def build_frame(cmd_body, use_first_preamble=False):
    """
    주어진 명령어 바디(cmd_body)에 대해 체크섬을 계산한 후,
    프리앰블을 붙여 전체 프레임을 생성.
      - 최초 전송 시: FIRST_PREAMBLE = 0x0D 0xFF 0xFF 0xFF
      - 이후 전송 시: 기본 프리앰블 = 0xFF 0xFF 0xFF 0xFF
    """
    if use_first_preamble:
        preamble = bytes([0x0D, 0xFF, 0xFF, 0xFF])
    else:
        preamble = bytes([0xFF, 0xFF, 0xFF, 0xFF])
    chksum = calculate_checksum(cmd_body)
    return preamble + cmd_body + bytes([chksum])

def reset_adapter():
    """
    Slave 타임아웃 발생 시, DTR을 0으로 하여 어댑터 전원을 끄고,
    다시 DTR을 1로 설정하여 어댑터를 리셋합니다.
    """
    print("🔄 Slave timeout: resetting adapter by setting DTR=0.")
    hart_serial.dtr = False
    time.sleep(0.5)
    hart_serial.dtr = True
    time.sleep(0.5)
    print("✅ Adapter reset complete.")

def send_hart_command(frame):
    """
    HART 프로토콜 절차:
      1. 전송 전, DCD가 inactive(0) 상태가 될 때까지 최대 1초 대기.
      2. DTR은 1인 상태에서 RTS를 1로 설정하여 송신 모드로 전환 (최소 50ms 대기).
      3. 프리앰블부터 체크섬까지 전체 프레임을 gap 없이 전송하고 flush()로 전송 완료.
      4. 송신이 완료되면 즉시 RTS를 OFF하여 수신 모드로 전환.
      5. 전송 후, DCD가 inactive(0) 상태가 될 때까지 최대 1초 대기 후 그 시점을 기록.
      6. 기록된 시점부터 최대 350ms 내에 DCD가 active(1)로 전환되는지 확인.
         - 350ms 내 전환되지 않으면 slave timeout으로 간주하고 어댑터를 리셋한 후 None 반환.
      7. DCD가 active(1)인 동안 수신 버퍼의 데이터를 모두 읽어 응답으로 구성.
    """
    try:
        print("\n🔄 Sending HART Command...")
        print("   Frame (hex):", frame.hex())

        # Step 1: 전송 전, DCD가 inactive(0) 상태가 될 때까지 최대 1초 대기
        t_deadline = time.time() + 1.0
        while hart_serial.cd:
            if time.time() > t_deadline:
                print("⚠ DCD did not become inactive within 1 second; proceeding.")
                break
            time.sleep(0.001)
        print("Step 1: DCD assumed inactive.")

        # 전송 전 입출력 버퍼 초기화
        hart_serial.reset_output_buffer()
        hart_serial.reset_input_buffer()

        # Step 2: DTR은 1인 상태에서 RTS를 1로 설정하여 송신 모드로 전환
        hart_serial.rts = True
        time.sleep(0.05)  # 최소 50ms 대기
        print("Step 2: RTS turned ON (Sending Mode).")

        # Step 3: 전체 프레임을 gap 없이 전송
        bytes_sent = hart_serial.write(frame)
        hart_serial.flush()
        print("Step 3: Frame transmitted ({} bytes).".format(bytes_sent))

        # Step 4: 송신 버퍼가 비워지면 즉시 RTS OFF
        start_out = time.time()
        while hart_serial.out_waiting > 0:
            if time.time() - start_out > 0.05:
                break
            time.sleep(0.001)
        hart_serial.rts = False
        print("Step 4: RTS turned OFF (Receive Mode).")

        # Step 5: 전송 후, DCD가 inactive(0) 상태가 될 때까지 최대 1초 대기 후 그 시점을 기록
        t_deadline = time.time() + 1.0
        print("Step 5: Waiting until DCD becomes inactive after transmission...")
        while hart_serial.cd:
            if time.time() > t_deadline:
                print("⚠ DCD did not become inactive within 1 second; proceeding.")
                break
            time.sleep(0.001)
        t_inactive = time.time()
        print("DCD became inactive at {:.3f}.".format(t_inactive))

        # Step 6: 기록된 시점부터 최대 350ms 내에 DCD가 active(1)로 전환되는지 확인
        print("Step 6: Waiting for DCD to switch ON (slave response)...")
        t_timeout = time.time() + 0.350
        while not hart_serial.cd:
            if time.time() > t_timeout:
                print("⏳ Slave timeout: DCD did not switch ON within 350 ms.")
                reset_adapter()
                return None
            time.sleep(0.001)
        dt = (time.time() - t_inactive) * 1000
        print("DCD switched ON after {:.1f} ms.".format(dt))

        # Step 7: DCD가 active(1)인 동안 수신 버퍼에서 데이터를 모두 읽어 응답 구성
        print("Step 7: Receiving data while DCD is active...")
        response = b""
        while hart_serial.cd:
            if hart_serial.in_waiting:
                response += hart_serial.read(hart_serial.in_waiting)
            time.sleep(0.001)
        print("Reception complete; DCD is now inactive.")
        return response

    except Exception as e:
        print("Error during HART command transmission:", e)
        return None

def main():
    print("\n🔵 Starting HART Data Acquisition...\n")

    # 첫 번째 명령어: 0x82 00 00 00 00 00 6D 01 00
    # 최초 전송 시에는 FIRST_PREAMBLE 사용, 이후 전송 시 기본 프리앰블 사용
    command1_body = bytes([0x82, 0x00, 0x00, 0x00, 0x00, 0x00, 0x6D, 0x01, 0x00])
    frame1_first = build_frame(command1_body, use_first_preamble=True)
    frame1_repeat = build_frame(command1_body, use_first_preamble=False)

    # 두 번째 명령어: 0x02 00 00 00 02 (항상 기본 프리앰블 사용)
    command2_body = bytes([0x02, 0x00, 0x00, 0x00, 0x02])
    frame2 = build_frame(command2_body, use_first_preamble=False)

    print("--- Sending First Command (10 repetitions) ---")
    # 최초 1회 전송
    response = send_hart_command(frame1_first)
    if response:
        print("Response for initial command:", response.hex())
    else:
        print("No response for initial command.")
    # 이후 9회 전송
    for i in range(9):
        print("\n--- Repetition {} for First Command ---".format(i+2))
        response = send_hart_command(frame1_repeat)
        if response:
            print("Response received:", response.hex())
        else:
            print("No response received.")

    print("\n--- Sending Second Command (5 repetitions) ---")
    for i in range(5):
        print("\n--- Repetition {} for Second Command ---".format(i+1))
        response = send_hart_command(frame2)
        if response:
            print("Response received:", response.hex())
        else:
            print("No response received.")

    print("\n✅ Data Acquisition Completed.")
    hart_serial.close()

if __name__ == "__main__":
    main()
