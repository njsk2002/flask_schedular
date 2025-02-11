from PIL import Image, ImageOps, ImageDraw, ImageFont
import qrcode
import uuid
import os
import platform

# 이미지 경로
background_path = r"C:/DavidProject/flask_project/출입증2.png"

# e-paper 해상도 설정
EPAPER_WIDTH = 400
EPAPER_HEIGHT = 300

# QR 코드 데이터 및 크기 설정
qr_data = "http://192.168.0.136:5000/naverapi/generate_vcard"
QR_SIZE = 100  # QR 코드 크기 (100x100 픽셀)

# 텍스트 정보
username = "홍길동"
department = "부설연구소"
position = "책임연구원"
email = "davidjung@icetech.co.kr"
phone = "010-1234-5678"
tel_rep = "02-1234-5678"
tel_dir = "070-9876-5432"
fax = "02-1111-2222"
com_address = "(우 13207)\n경기도 성남시 중원구 사기막골로 124\nSKn테크노파크 넥스센터 2층"
homepage = "www.openai.com"

# 출력 폴더 생성
output_folder = "bmp_files"
os.makedirs(output_folder, exist_ok=True)

# 폰트 경로 설정
if platform.system() == "Windows":
    font_path = "C:/Windows/Fonts/malgun.ttf"  # Windows용 폰트 경로
elif platform.system() == "Linux":
    font_path = "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"  # Linux용 폰트 경로
else:
    raise Exception("지원되지 않는 운영체제입니다.")

try:
    # 배경 이미지 열기
    img = Image.open(background_path)

    # 좌측 상단 150x150 크기로 이미지 조정
    img_resized = ImageOps.fit(img, (150, 150), method=Image.LANCZOS)

    # e-paper 전체 캔버스 생성
    canvas = Image.new("RGB", (EPAPER_WIDTH, EPAPER_HEIGHT), color="white")  # 흰색 배경

    # 배경 이미지 삽입 (좌측 상단, 여백 조정)
    canvas.paste(img_resized, (10, 10))  # X=10, Y=10으로 위치 조정

    # QR 코드 생성 및 크기 조정
    qr = qrcode.QRCode(
        version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img = qr_img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)

    # QR 코드 삽입 (우측 하단)
    canvas.paste(qr_img, (EPAPER_WIDTH - QR_SIZE - 10, EPAPER_HEIGHT - QR_SIZE - 10))

    # 텍스트 추가
    draw = ImageDraw.Draw(canvas)
    font_title = ImageFont.truetype(font_path, size=24)  # 제목 글씨 크기 설정
    font = ImageFont.truetype(font_path, size=16)  # 일반 텍스트 크기 설정

    # 아이스기술 제목 추가 (오른쪽 상단)
    title_text = "아이스기술"
    title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
    title_width = title_bbox[2] - title_bbox[0]

    # 오른쪽 상단 정렬 (오른쪽 끝에서 10px 여백)
    title_x = EPAPER_WIDTH - title_width - 10
    title_y = 10  # 상단 여백

    # 텍스트 추가
    draw.text((title_x, title_y), title_text, fill="black", font=font_title)

    # 텍스트 위치 설정
    text_x = 170  # 왼쪽 정렬 기준점 (사진 오른쪽)
    text_y = 52
    line_spacing = 24

    # 텍스트 크기 측정
    department_text = f"{department} |"
    position_text = f"{position} |"
    username_text = f"{username}"

    # 텍스트 크기 측정
    department_height = draw.textbbox((0, 0), department_text, font=font)[3]  # 높이 측정
    position_height = draw.textbbox((0, 0), position_text, font=font)[3]
    username_height = draw.textbbox((0, 0), username_text, font=font)[3]

    # 중앙 배치를 위해 중간값 계산
    total_height = department_height + position_height
    username_y_centered = text_y + (total_height // 2) - (username_height // 2)  # 중앙 정렬

    # 텍스트 내용 추가 (이름을 department & position의 세로 중앙에 배치)
    draw.text((text_x, text_y), department_text, fill="black", font=font)
    text_y += line_spacing
    draw.text((text_x, text_y), position_text, fill="black", font=font)

    # username을 중앙 정렬한 위치에 배치
    draw.text((text_x + 110, username_y_centered), username_text, fill="black", font=font)

    # 이메일 및 전화번호 (기존 위치 유지)
    text_y += line_spacing
    draw.text((text_x, text_y), f"TEL : {phone} ", fill="black", font=font)
    text_y += line_spacing
    draw.text((text_x, text_y), f"E : {email}", fill="black", font=font)
    text_y += line_spacing
    draw.text((text_x, text_y), f"FAX : {fax}", fill="black", font=font)

    # 📌 **전화번호 및 주소를 이미지 하단 왼쪽으로 배치**
    bottom_text_x = 10  # 왼쪽 정렬
    bottom_text_y = EPAPER_HEIGHT - 100  # 하단 정렬 (QR 코드 위쪽)

    draw.text((bottom_text_x, bottom_text_y), f"{tel_rep} | {tel_dir}", fill="black", font=font)
    bottom_text_y += line_spacing  # 줄 간격 추가

    # 📌 **주소 줄바꿈 처리 (여러 줄 출력)**
    address_lines = com_address.split("\n")  # 주소를 줄마다 리스트로 변환
    for line in address_lines:
        draw.text((bottom_text_x, bottom_text_y), line.strip(), fill="black", font=font)
        bottom_text_y += line_spacing  # 줄 간격 유지

    # 흑백 변환 및 디더링 적용
    bw_img = canvas.convert("1", dither=Image.FLOYDSTEINBERG)

    # 고유 파일명 생성 및 저장
    uuid_4 = uuid.uuid4()
    bmp_name = f"e_paper_{uuid_4}.bmp"
    bmp_path = os.path.join(output_folder, bmp_name)
    bw_img.save(bmp_path, format="BMP")

    print(f"이미지가 성공적으로 변환되어 저장되었습니다: {bmp_path}")

except FileNotFoundError:
    print("로컬 파일을 찾을 수 없습니다. 경로를 확인하세요.")
except Exception as e:
    print(f"오류가 발생했습니다: {e}")
