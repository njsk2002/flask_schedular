from PIL import Image, ImageOps
import numpy as np
import os, uuid

# ✅ 로컬 이미지 파일 경로
file_path = r"C:/DavidProject/flask_project/카리나1.jpg"

# ✅ e-paper 해상도 설정 (JD79661AA: 296x128)
EPAPER_WIDTH = 296
EPAPER_HEIGHT = 128

# ✅ 4색 팔레트 정의 (검정, 흰색, 빨강, 노랑)
PALETTE = [
    0, 0, 0,         # 검정 (Black)
    255, 255, 255,   # 흰색 (White)
    255, 0, 0,       # 빨강 (Red)
    255, 255, 0      # 노랑 (Yellow)
]
PALETTE += [0] * (256 * 3 - len(PALETTE))  # 나머지 부분을 0으로 채움

# ✅ 이미지 열기 및 크기 조정
try:
    img = Image.open(file_path).convert("RGB")
    img = img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
    print("이미지 변환 성공")
except Exception as e:
    print("이미지 변환 실패:", e)
    exit(1)

# ✅ 4색 팔레트 적용 (Floyd-Steinberg 디더링 사용)
palette_img = Image.new("P", (1, 1))  # 팔레트 설정용 이미지 생성
palette_img.putpalette(PALETTE)
quantized_img = img.quantize(palette=palette_img, dither=Image.FLOYDSTEINBERG)
print("4색 변환 완료 (검정, 흰색, 빨강, 노랑)")

# ✅ 변환된 이미지의 픽셀 데이터를 가져옴
image_array = np.array(quantized_img)

# ✅ JD79661AA 2비트 컬러 매핑 (0, 1, 2, 3)
COLOR_MAP = {
    0: 0b00,  # 검정 (Black)
    1: 0b11,  # 흰색 (White)
    2: 0b01,  # 빨강 (Red)
    3: 0b10   # 노랑 (Yellow)
}

# ✅ 2비트 변환 (1바이트 = 4픽셀 저장)
bmp_2bpp = np.zeros((EPAPER_HEIGHT, EPAPER_WIDTH // 4), dtype=np.uint8)

for y in range(EPAPER_HEIGHT):
    for x in range(0, EPAPER_WIDTH, 4):
        byte_value = 0
        for i in range(4):
            if x + i < EPAPER_WIDTH:
                pixel = image_array[y, x + i]
                bit_value = COLOR_MAP.get(pixel, 0b00)  # 기본값 검정 (Black)
                byte_value |= (bit_value << (6 - (i * 2)))  # 2비트씩 저장
        bmp_2bpp[y, x // 4] = byte_value

# ✅ 2bpp RAW 파일 저장 (JD79661AA 전송용)
uuid_4 = uuid.uuid4()
raw_name = f"bmp_files/e_paper_{uuid_4}.raw"
os.makedirs("bmp_files", exist_ok=True)
bmp_2bpp.tofile(raw_name)
print(f"✅ 2bpp RAW 이미지 저장 완료: {raw_name}")

# ✅ **8비트 BMP 저장 (일반 이미지 뷰어용)**
bmp_8bit_name = f"bmp_files/e_paper_{uuid_4}.bmp"
quantized_img.save(bmp_8bit_name, format="BMP")
print(f"✅ 8비트 BMP 저장 완료: {bmp_8bit_name}")

# ✅ 디버깅: 파일 크기 확인
file_size = os.path.getsize(raw_name)
expected_size = (EPAPER_WIDTH * EPAPER_HEIGHT) // 4
if file_size != expected_size:
    print(f"⚠️ 예상 크기와 다름! 예상: {expected_size} 바이트, 실제: {file_size} 바이트")
else:
    print("✅ 파일 크기 정상")
