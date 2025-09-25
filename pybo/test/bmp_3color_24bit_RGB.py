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

    # 얼굴 기준 영역 설정 (비율 유지)
    left = max(face_center_x - EPAPER_WIDTH // 2, 0)
    top = max(face_center_y - EPAPER_HEIGHT // 2, 0)
    right = min(left + EPAPER_WIDTH, img.width)
    bottom = min(top + EPAPER_HEIGHT, img.height)

    print(f"조정된 잘라낼 영역: left={left}, top={top}, right={right}, bottom={bottom}")
    cropped_img = img.crop((left, top, right, bottom))
    cropped_img = cropped_img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
    print("이미지 잘라내기 및 크기 조정 완료")
else:
    print("얼굴이 감지되지 않아 상단 중앙으로 이미지 조정")
    cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

# 3색 변환 (블랙, 레드, 화이트) - 디더링 적용
def map_to_three_colors(pixel):
    colors = {
        "black": np.array([0, 0, 0]),
        "red": np.array([255, 0, 0]),
        "white": np.array([255, 255, 255])
    }
    min_dist = float("inf")
    closest = None
    for name, ref_color in colors.items():
        dist = np.linalg.norm(pixel - ref_color)
        if dist < min_dist:
            min_dist = dist
            closest = ref_color
    return closest

# 이미지 데이터를 NumPy 배열로 변환 및 디더링 적용
image_array = np.array(cropped_img)
dither_matrix = np.array([[0, 128], [192, 64]]) / 256.0 * 255  # 기본적인 Bayer 디더링 패턴
for i in range(image_array.shape[0]):
    for j in range(image_array.shape[1]):
        pixel = image_array[i, j]
        dither_value = dither_matrix[i % 2, j % 2]  # 패턴을 활용한 디더링 적용
        modified_pixel = np.clip(pixel + dither_value, 0, 255)
        image_array[i, j] = map_to_three_colors(modified_pixel)

# PIL 이미지로 변환 (3색 변환된 24-bit RGB)
final_img = Image.fromarray(image_array.astype(np.uint8), "RGB")

print("3색 변환 완료 (블랙, 레드, 화이트) - 디더링 적용")

# 파일명 생성
uuid_4 = uuid.uuid4()
bmp_name = f"e_paper_{uuid_4}.bmp"

# 디렉토리 생성 및 파일 저장
os.makedirs("bmp_files", exist_ok=True)
final_img.save(f"bmp_files/{bmp_name}", format="BMP")

print(f"이미지가 성공적으로 변환되어 저장되었습니다: {bmp_name}")
