from PIL import Image, ImageOps
import requests
from io import BytesIO

# 이미지 URL
url = "https://cdn2.ppomppu.co.kr/zboard/data3/2024/0319/20240319173717_XqPTvgbNiI.jpeg"

# e-paper 해상도 설정
EPAPER_WIDTH = 400
EPAPER_HEIGHT = 300

# 이미지 다운로드 및 변환
response = requests.get(url)
if response.status_code == 200:
    # 이미지 열기
    img = Image.open(BytesIO(response.content))
    
    # 원본 유지 및 크기 조정
    img_resized = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)
    
    # 그레이스케일 변환
    grayscale_img = img_resized.convert("L")
    
    # 디더링을 사용한 흑백 변환
    bw_img = grayscale_img.convert("1", dither=Image.FLOYDSTEINBERG)
    
    # 파일 저장
    bw_img.save("e_paper_image.bmp", format="BMP")
    print("이미지가 성공적으로 변환되어 저장되었습니다.")
else:
    print("이미지 다운로드에 실패했습니다.")
