from PIL import Image, ImageOps, ImageDraw, ImageFont
import qrcode
import uuid
import os
import platform

# 이미지 경로
background_path = r"C:/DavidProject/flask_project/출입증2.png"
#background_path = r"C:/DavidProject/flask_project/카리나1.jpg"

# e-paper 해상도 설정
EPAPER_WIDTH = 400
EPAPER_HEIGHT = 300

# QR 코드 데이터 및 크기 설정
#qr_data = "http://192.168.0.9:5000/naverapi/generate_vcard"
qr_data = "http://192.168.0.136:5000/naverapi/generate_vcard"
#qr_data = "http://192.168.219.104:5000/naverapi/generate_vcard"
QR_SIZE = 100  # QR 코드 크기 (100x100 픽셀)

# 텍스트 정보
auth_date = "2025-02-03"
staff_name = "아이유"
staff_b_type = "A"
staff_condition = "고혈압"
year_grade = "장년"
security_grade = "B"

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

    # 좌측 상단 200x200 크기로 이미지 조정
    img_resized = ImageOps.fit(img, (200, 200), method=Image.LANCZOS)

    # e-paper 전체 캔버스 생성
    canvas = Image.new("RGB", (EPAPER_WIDTH, EPAPER_HEIGHT), color="white")  # 흰색 배경

    # 배경 이미지 삽입 (좌측 상단)
    canvas.paste(img_resized, (5, 50))

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

    # 출입증 제목 추가 (상단 중앙)
    title_text = "출 입 증"
    title_bbox = draw.textbbox((0, 0), title_text, font=font)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((EPAPER_WIDTH - title_width) // 2, 10), title_text, fill="black", font=font_title) # 출입증만 24

    # 텍스트 위치 설정
    text_x = 210  # 사진 오른쪽 시작 위치
    text_y = 52
    line_spacing = 24

    # 텍스트 내용 추가
    draw.text((text_x, text_y), f"허용 일자 | {auth_date}", fill="black", font=font)
    text_y += line_spacing
    draw.text((text_x, text_y), f"이름 |       {staff_name}", fill="black", font=font)
    text_y += line_spacing
    draw.text((text_x, text_y), f"혈액형 |      {staff_b_type}", fill="black", font=font)
    text_y += line_spacing
    draw.text((text_x, text_y), f"지병 |       {staff_condition}", fill="black", font=font)
    text_y += line_spacing
    draw.text((text_x, text_y), f"구분 |       {year_grade}", fill="black", font=font)
    text_y += line_spacing
    draw.text((text_x, text_y), f"보안등급 |    {security_grade}", fill="black", font=font)

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
