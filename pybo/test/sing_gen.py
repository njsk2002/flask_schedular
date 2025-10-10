from PIL import Image, ImageDraw, ImageFont

# 투명 배경 캔버스 생성
def create_canvas(width=400, height=200):
    return Image.new("RGBA", (width, height), (255, 255, 255, 0))

# 결재란 (작성/검토/승인 3칸짜리 예시)
def create_signbox(path="signbox.png"):
    img = create_canvas(600, 200)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    # 3칸 사각형
    cols = ["작성", "검토", "승인"]
    for i, label in enumerate(cols):
        x0 = i * 200
        x1 = (i+1) * 200
        draw.rectangle([x0, 0, x1, 200], outline="black", width=2)
        draw.text((x0+70, 80), label, fill="black", font=font)

    img.save(path, "PNG")

# 직인 (원형 빨간 도장)
def create_stamp(path="stamp.png"):
    img = create_canvas(200, 200)
    draw = ImageDraw.Draw(img)

    # 빨간 원
    draw.ellipse([10, 10, 190, 190], outline="red", width=8)

    # 가운데 텍스트
    font = ImageFont.load_default()
    draw.text((60, 80), "회사", fill="red", font=font)

    img.save(path, "PNG")

# 사인 (사용자 싸인 흉내)
def create_signature(path="signature.png"):
    img = create_canvas(400, 150)
    draw = ImageDraw.Draw(img)

    # 자유곡선 비슷하게 흉내 (실제는 사용자가 업로드해야 함)
    draw.line([(20, 100), (80, 40), (200, 120), (300, 60), (380, 100)],
              fill="black", width=4)

    img.save(path, "PNG")

# 실행
create_signbox()
create_stamp()
create_signature()
