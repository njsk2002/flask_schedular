from pymodbus.client import ModbusTcpClient

class ADAM6217Modbus:
    def __init__(self, ip_address, port=502):
        """Modbus TCP 클라이언트 초기화"""
        self.client = ModbusTcpClient(ip_address, port=port)
        self.ip_address = ip_address
        self.port = port
        self.MODBUS_MAX_VALUE = 65535  # 16비트 최대값
        self.INPUT_VOLTAGE_RANGE = 10.0  # 0~10V 범위 기준
        self.INPUT_CURRENT_MAX = 20 # 4~20mA
        self.INPUT_CURRENT_MIN = 4 

    def connect(self):
        """Modbus 연결 시도"""
        if not self.client.connect():
            print(f"⚠️ {self.ip_address}:{self.port} 에 연결할 수 없습니다. 네트워크 상태를 확인하세요.")
            return False
        return True

    def read_register(self, channel):
        """특정 채널의 아날로그 입력 값 읽기 (pymodbus 3.x 호환)"""
        try:
            result = self.client.read_input_registers(address=channel, count=1)  # ✅ 최신 방식 적용
            if result.isError():
                print(f"❌ 채널 {channel} 읽기 오류 발생")
                return None
            return result.registers[0]
        except Exception as e:
            print(f"🚨 예외 발생: {e}")
            return None

    def convert_modbus_to_voltage(self, raw_value):
        """Modbus 값을 전압(V)으로 변환"""
        return (raw_value / self.MODBUS_MAX_VALUE) * self.INPUT_VOLTAGE_RANGE
    
    def convert_modbus_to_current(self, raw_value):
        """Modbus 값을 4~20mA로 변환"""
        max_current = self.INPUT_CURRENT_MAX
        min_current = self.INPUT_CURRENT_MIN
        return min_current + ((raw_value / self.MODBUS_MAX_VALUE) * (max_current - min_current))
    

    def read_all_channels(self):
        """AI0 ~ AI7 모든 채널 값을 읽고 4~20mA로 변환"""
        values = {}
        for channel in range(8):  # AI0 ~ AI7
            raw_value = self.read_register(channel)
            if raw_value is not None:
                current = self.convert_modbus_to_current(raw_value)
                values[f"AI{channel}"] = current
                print(f"📡 AI{channel}: {current:.2f}mA (Raw: {raw_value})")
        return values
    
    def close(self):
        """Modbus 클라이언트 종료"""
        self.client.close()


# ✅ 실행 코드
if __name__ == "__main__":
    adam = ADAM6217Modbus("192.168.0.238")  # ADAM-6217 IP 주소 설정

    if adam.connect():
        print("\n🔍 모든 채널 값 읽기:")
        adam.read_all_channels()
        adam.close()
