from pymodbus.client import ModbusTcpClient

class ADAM6217DualPort:
    def __init__(self, ip_port1, ip_port2, port=502):
        """ADAM-6217의 두 개의 이더넷 포트를 지원하는 Modbus 클라이언트"""
        self.client1 = ModbusTcpClient(ip_port1, port=port)
        self.client2 = ModbusTcpClient(ip_port2, port=port)
        
        # Modbus 범위 및 센서 설정
        self.MODBUS_MAX_VALUE = 65535
        self.INPUT_CURRENT_RANGE = (4.0, 20.0)  # 4~20mA 범위
        self.TEMP_RANGE = (120.0, 1650.0)  # 온도 범위 (120°C ~ 1650°C)

    def connect(self):
        """두 개의 포트 모두 연결 시도"""
        connected1 = self.client1.connect()
        connected2 = self.client2.connect()
        if not connected1:
            print(f"⚠️ {self.client1.host} 연결 실패")
        if not connected2:
            print(f"⚠️ {self.client2.host} 연결 실패")
        return connected1 and connected2

    def read_register(self, client, channel):
        """특정 클라이언트(ModbusTCP)에서 특정 채널 읽기"""
        try:
            result = client.read_input_registers(address=channel, count=1)
            if result.isError():
                print(f"❌ 채널 {channel} 읽기 오류 발생")
                return None
            return result.registers[0]
        except Exception as e:
            print(f"🚨 예외 발생: {e}")
            return None

    def convert_modbus_to_current(self, raw_value):
        """Modbus 값을 4~20mA로 변환"""
        min_mA, max_mA = self.INPUT_CURRENT_RANGE
        return min_mA + ((raw_value / self.MODBUS_MAX_VALUE) * (max_mA - min_mA))

    def convert_current_to_temperature(self, current):
        """4~20mA 전류 값을 온도로 변환"""
        min_temp, max_temp = self.TEMP_RANGE
        min_mA, max_mA = self.INPUT_CURRENT_RANGE
        return min_temp + ((current - min_mA) / (max_mA - min_mA)) * (max_temp - min_temp)

    def convert_modbus_to_temperature(self, raw_value):
        """Modbus 값을 온도로 직접 변환"""
        current = self.convert_modbus_to_current(raw_value)
        return self.convert_current_to_temperature(current)

    def read_all_channels(self):
        """두 개의 포트에서 모든 채널을 읽고 출력 (mA 및 온도)"""
        values = {}

        print("\n🔍 Port1 데이터 수집:")
        for channel in range(8):
            raw_value = self.read_register(self.client1, channel)
            if raw_value is not None:
                current = self.convert_modbus_to_current(raw_value)
                temperature = self.convert_modbus_to_temperature(raw_value)
                values[f"Port1_AI{channel}"] = (current, temperature)
                print(f"📡 Port1 AI{channel}: {current:.2f}mA / {temperature:.2f}°C (Raw: {raw_value})")

        print("\n🔍 Port2 데이터 수집:")
        for channel in range(8):
            raw_value = self.read_register(self.client2, channel)
            if raw_value is not None:
                current = self.convert_modbus_to_current(raw_value)
                temperature = self.convert_modbus_to_temperature(raw_value)
                values[f"Port2_AI{channel}"] = (current, temperature)
                print(f"📡 Port2 AI{channel}: {current:.2f}mA / {temperature:.2f}°C (Raw: {raw_value})")

        return values

    def close(self):
        """Modbus 클라이언트 종료"""
        self.client1.close()
        self.client2.close()


# ✅ 실행 코드
if __name__ == "__main__":
    adam = ADAM6217DualPort("192.168.0.238", "192.168.0.239")  # Port1, Port2 IP 설정

    if adam.connect():
        print("\n🔍 두 개의 포트에서 모든 채널 값 읽기:")
        adam.read_all_channels()
        adam.close()


