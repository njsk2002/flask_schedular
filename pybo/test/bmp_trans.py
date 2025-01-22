from PIL import Image, ImageOps
import requests, uuid
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
    
    print(f'img는 ${img}이고, img_resized는 ${img_resized}이고, \n grayscale_img는 {grayscale_img}이고, bw_img는 ${bw_img} 입니다.')
    # 파일 저장
    uuid_4 = uuid.uuid4()
    bmp_name = f"e_paper_{uuid_4}.bmp"
    bw_img.save(f"bmp_files/{bmp_name}", format="BMP")
    print("이미지가 성공적으로 변환되어 저장되었습니다.")
 
else:
    print("이미지 다운로드에 실패했습니다.")

