import io, zlib, struct
from PIL import Image

class BMPToBytes:
    # 2bit 컬러 매핑 (RGB → 2bit)
    COLOR_MAP = {
        (255, 255, 255): 0b00,  # White
        (255, 255, 0):   0b01,  # Yellow
        (255, 0, 0):     0b10,  # Red
        (0, 0, 0):       0b11,  # Black
    }

    @staticmethod
    def convert_image_to_2bit_bytes(img: Image.Image) -> bytes:
        # 800x480 리사이즈
        img = img.resize((800, 480)).convert("RGB")

        packed = bytearray()
        byte_val, bit_count = 0, 0

        for y in range(480):
            for x in range(800):
                pixel = img.getpixel((x, y))
                # 가장 가까운 팔레트 색 찾기
                color2bit = BMPToBytes._map_color(pixel)
                # 왼쪽 shift 후 append
                byte_val = (byte_val << 2) | color2bit
                bit_count += 2
                if bit_count == 8:
                    packed.append(byte_val)
                    byte_val, bit_count = 0, 0

        # 마지막 남은 비트 패딩
        if bit_count > 0:
            packed.append(byte_val << (8 - bit_count))

        return bytes(packed)

    @staticmethod
    def _map_color(rgb):
        # 간단한 최근접 매핑
        diffs = {}
        for ref, val in BMPToBytes.COLOR_MAP.items():
            dr = rgb[0] - ref[0]
            dg = rgb[1] - ref[1]
            db = rgb[2] - ref[2]
            diffs[val] = dr*dr + dg*dg + db*db
        return min(diffs, key=diffs.get)

    @staticmethod
    def image_file_to_payload(fp: str) -> bytes:
        img = Image.open(fp)
        raw = BMPToBytes.convert_image_to_2bit_bytes(img)
        # CRC32 계산
        crc = zlib.crc32(raw) & 0xffffffff
        return raw + struct.pack("<I", crc)


