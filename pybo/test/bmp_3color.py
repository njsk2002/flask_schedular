from PIL import Image, ImageOps
import os, uuid, cv2
import numpy as np

# 로컬 이미지 파일 경로
file_path = r"C:/DavidProject/flask_project/카리나1.jpg"

# e-paper 해상도 설정 (SSD1683과 동일)
EPAPER_WIDTH = 400
EPAPER_HEIGHT = 300

# 이미지 열기 (로컬 파일)
try:
    img = Image.open(file_path)
    img = img.convert("RGB")
    print("이미지 열기 성공")
except Exception as e:
    print("이미지 열기 실패:", e)
    exit(1)

# 이미지 크기 확인 및 크기 조정 (너비가 700 이상이면 너비 800으로 비율 유지하며 조정)
img_width, img_height = img.size
if img_width > 700:
    scale_factor = 800 / img_width
    new_width = 800
    new_height = int(img_height * scale_factor)
    img = img.resize((new_width, new_height), Image.LANCZOS)
    print(f"이미지 크기 조정 완료: {new_width}x{new_height}")

# OpenCV로 변환 (얼굴 검출용)
cv_image = np.array(img)
cv_image = cv_image[:, :, ::-1].copy()  # PIL(RGB) -> OpenCV(BGR)
print("OpenCV 변환 완료")

# 얼굴 인식 (haarcascade 사용)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
faces = face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

if len(faces) > 0:
    print(f"감지된 얼굴 수: {len(faces)}")
    # 가장 큰 얼굴 선택
    x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
    print(f"가장 큰 얼굴 좌표와 크기: x={x}, y={y}, w={w}, h={h}")
    face_center_x = x + w // 2
    face_center_y = y + h // 2

    # 얼굴 크기를 350 이하로 조정
    if w > 350 or h > 350:
        scale_factor = 350 / max(w, h)
        w = int(w * scale_factor)
        h = int(h * scale_factor)
        print(f"조정된 얼굴 크기: w={w}, h={h}")

    # 얼굴 기준 영역 설정 (비율 유지)
    face_width = max(w, EPAPER_WIDTH)  # 최소 EPAPER_WIDTH
    face_height = max(h, EPAPER_HEIGHT)  # 최소 EPAPER_HEIGHT

    left = max(face_center_x - face_width // 2, 0)
    top = max(face_center_y - face_height // 2, 0)
    right = min(left + face_width, img.width)
    bottom = min(top + face_height, img.height)

    print(f"조정된 잘라낼 영역: left={left}, top={top}, right={right}, bottom={bottom}")

    # 얼굴 주변 영역 잘라내기
    cropped_img = img.crop((left, top, right, bottom))

    # e-paper 크기로 조정
    cropped_img = cropped_img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
    print("이미지 잘라내기 및 크기 조정 완료")
else:
    # 얼굴이 없으면 상단 중앙 기준으로 조정
    print("얼굴이 감지되지 않아 상단 중앙으로 이미지 조정")
    cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

# 24비트 BMP 저장 (RGB 그대로 유지)
uuid_4 = uuid.uuid4()
bmp_name = f"e_paper_{uuid_4}.bmp"

# BMP 파일 24-bit 저장
bmp_path = os.path.join("bmp_files", bmp_name)
os.makedirs("bmp_files", exist_ok=True)
cropped_img.save(bmp_path, format="BMP")

print(f"이미지가 성공적으로 변환되어 저장되었습니다: {bmp_path}")
