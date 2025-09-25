from PIL import Image, ImageOps, PngImagePlugin
import os, uuid, cv2
import numpy as np

# 로컬 이미지 파일 경로
file_path = r"C:/DavidProject/flask_project/카리나1.jpg"

# e-paper 해상도 설정 (f290__.png와 동일: 128x296)
EPAPER_WIDTH = 240
EPAPER_HEIGHT = 416

# 4색 팔레트 (Black, Red, Yellow, White)
COLOR_MAP = {
    "black": (0, 0, 0),        # 검정
    "red": (255, 0, 0),        # 빨강
    "yellow": (255, 255, 0),   # 노랑
    "white": (255, 255, 255)   # 흰색
}
PALETTE_VALUES = np.array(list(COLOR_MAP.values()))

# 이미지 열기 및 RGB 모드 변환 (초기에는 RGB)
try:
    img = Image.open(file_path)
    img = img.convert("RGB")
    print("이미지 열기 성공")
except Exception as e:
    print("이미지 열기 실패:", e)
    exit(1)

# 이미지 크기 조정 (너비가 700보다 크면 리사이즈)
img_width, img_height = img.size
if img_width > 700:
    scale_factor = 800 / img_width
    new_width = 800
    new_height = int(img_height * scale_factor)
    img = img.resize((new_width, new_height), Image.LANCZOS)
    print(f"이미지 크기 조정 완료: {new_width}x{new_height}")

# OpenCV 변환 (얼굴 검출용)
cv_image = np.array(img)[:, :, ::-1].copy()  # PIL(RGB) -> OpenCV(BGR)
print("OpenCV 변환 완료")

# 얼굴 인식
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
faces = face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

if len(faces) > 0:
    print(f"감지된 얼굴 수: {len(faces)}")
    x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
    print(f"가장 큰 얼굴 좌표와 크기: x={x}, y={y}, w={w}, h={h}")
    # 얼굴 중심 기준으로 크롭 (e-paper 해상도와 동일)
    left = max(x + w // 2 - EPAPER_WIDTH // 2, 0)
    top = max(y + h // 2 - EPAPER_HEIGHT // 2, 0)
    right = min(left + EPAPER_WIDTH, img.width)
    bottom = min(top + EPAPER_HEIGHT, img.height)
    print(f"잘라낼 영역: left={left}, top={top}, right={right}, bottom={bottom}")
    cropped_img = img.crop((left, top, right, bottom))
else:
    print("얼굴 감지 실패, 중앙을 기준으로 크롭")
    cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

# e-paper 크기로 조정
cropped_img = cropped_img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
print("이미지 크롭 및 크기 조정 완료")

# 4색 변환 함수 (가중치 기반)
def closest_color(pixel):
    distances = np.sum((PALETTE_VALUES - pixel) ** 2, axis=1)
    return tuple(PALETTE_VALUES[np.argmin(distances)])

# Floyd-Steinberg 디더링 적용
image_array = np.array(cropped_img, dtype=np.float32)
for y in range(image_array.shape[0]):
    for x in range(image_array.shape[1]):
        old_pixel = image_array[y, x].copy()
        new_pixel = np.array(closest_color(old_pixel))
        image_array[y, x] = new_pixel
        error = old_pixel - new_pixel
        if x + 1 < image_array.shape[1]:
            image_array[y, x + 1] += error * 7 / 16
        if x - 1 >= 0 and y + 1 < image_array.shape[0]:
            image_array[y + 1, x - 1] += error * 3 / 16
        if y + 1 < image_array.shape[0]:
            image_array[y + 1, x] += error * 5 / 16
        if x + 1 < image_array.shape[1] and y + 1 < image_array.shape[0]:
            image_array[y + 1, x + 1] += error * 1 / 16

# 0~255 범위 제한 후, 정수형 변환
image_array = np.clip(image_array, 0, 255).astype(np.uint8)

# RGBA 이미지 생성: RGB 채널에 모두 알파 255를 추가 (컬러 타입 6)
alpha_channel = np.full((image_array.shape[0], image_array.shape[1]), 255, dtype=np.uint8)
rgba_array = np.dstack((image_array, alpha_channel))
final_img = Image.fromarray(rgba_array, "RGBA")

# 추가 메타데이터 설정: gAMA, pHYs, sRGB
final_img.info["gamma"] = 0.45455      # gAMA chunk (대략 1/2.2)
final_img.info["dpi"] = (2835, 2835)     # pHYs chunk (2835 pixels/meter, 약 72 DPI)
final_img.info["srgb"] = 0             # sRGB chunk (Perceptual rendering intent)

# 파일명 생성
uuid_4 = uuid.uuid4()
bmp_name = f"e_paper_{uuid_4}.bmp"
png_name = f"e_paper_{uuid_4}.png"

# BMP 파일 저장
os.makedirs("bmp_files", exist_ok=True)
final_img.save(f"bmp_files/{bmp_name}", format="BMP")
print(f"4색 BMP 이미지 저장 완료: {bmp_name}")

# PNG 파일 저장 (추가 Chunk 포함: IHDR, sRGB, gAMA, pHYs, IDAT, IEND)
os.makedirs("png_files", exist_ok=True)
final_img.save(f"png_files/{png_name}", format="PNG", optimize=True)
print(f"4색 PNG 이미지 저장 완료 (추가 Chunk 포함): {png_name}")
