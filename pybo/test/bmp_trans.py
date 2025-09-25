from PIL import Image, ImageOps
import requests, uuid
from io import BytesIO

# 이미지 URL
#url = "https://cdn2.ppomppu.co.kr/zboard/data3/2024/0319/20240319173717_XqPTvgbNiI.jpeg"
# 로컬 이미지 경로
url = r"C:/DavidProject/flask_project/nationalGeographic1.png"

# e-paper 해상도 설정
EPAPER_WIDTH = 296
EPAPER_HEIGHT = 128

# 이미지 열기 및 변환
try:
    # 로컬 파일 열기
    img = Image.open(url)
    
    # 원본 유지 및 크기 조정
    img_resized = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)
    
    # 그레이스케일 변환
    grayscale_img = img_resized.convert("L")
    
    # 디더링을 사용한 흑백 변환
    bw_img = grayscale_img.convert("1", dither=Image.FLOYDSTEINBERG)
    
    # 디버깅용 출력
    print(f"img: {img}, img_resized: {img_resized}, \ngrayscale_img: {grayscale_img}, bw_img: {bw_img}")
    
    # 파일 저장
    uuid_4 = uuid.uuid4()
    bmp_name = f"e_paper_{uuid_4}.bmp"
    bw_img.save(f"bmp_files/{bmp_name}", format="BMP")
    print("이미지가 성공적으로 변환되어 저장되었습니다.")

except FileNotFoundError:
    print("로컬 파일을 찾을 수 없습니다. 경로를 확인하세요.")
except Exception as e:
    print(f"오류가 발생했습니다: {e}")

