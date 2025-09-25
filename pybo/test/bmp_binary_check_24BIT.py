import struct

# BMP 파일 경로
bmp_file_path = "C:/DavidProject/flask_project/flask_bms/bmp_files/e_paper_f4d691fb-39dc-4b6e-aee1-100124a109d2.bmp"
output_file_path = "C:/DavidProject/flask_project/flask_bms/bmp_files/bmp_data2.txt"

def read_bmp_header(bmp_file):
    """ BMP 파일의 헤더를 읽고 저장 (24비트 BMP 지원) """
    with open(bmp_file, "rb") as f:
        header = f.read(54)  # BMP 기본 헤더는 54바이트
        (
            signature, file_size, reserved1, reserved2, data_offset,
            header_size, width, height, planes, bit_depth, compression,
            image_size, x_pixels_per_meter, y_pixels_per_meter,
            colors_used, important_colors
        ) = struct.unpack("<2sIHHIIIIHHIIIIII", header)

        header_info = [
            "\n📌 **BMP 헤더 정보 (24비트 지원)**\n",
            f"🔹 시그니처 (Signature): {signature.decode()}",
            f"🔹 파일 크기 (File Size): {file_size} 바이트",
            f"🔹 데이터 오프셋 (Data Offset): {data_offset} 바이트",
            f"🔹 헤더 크기 (Header Size): {header_size}",
            f"🔹 너비 (Width): {width} 픽셀",
            f"🔹 높이 (Height): {height} 픽셀",
            f"🔹 컬러 플레인 (Planes): {planes}",
            f"🔹 비트 깊이 (Bit Depth): {bit_depth} bpp (24비트 RGB)",
            f"🔹 압축 (Compression): {compression}",
            f"🔹 이미지 크기 (Image Size): {image_size} 바이트",
            f"🔹 X 해상도 (X Pixels per Meter): {x_pixels_per_meter}",
            f"🔹 Y 해상도 (Y Pixels per Meter): {y_pixels_per_meter}",
            f"🔹 사용 색상 (Colors Used): {colors_used}",
            f"🔹 중요한 색상 (Important Colors): {important_colors}",
            "\n"
        ]

        with open(output_file_path, "w", encoding="utf-8") as out_file:
            out_file.writelines("\n".join(header_info))

        return data_offset, width, height, bit_depth

def read_bmp_data(bmp_file, data_offset, width, height, bit_depth):
    """ BMP 파일의 24비트 픽셀 데이터를 읽고 저장 """
    with open(bmp_file, "rb") as f:
        f.seek(data_offset)  # 픽셀 데이터 위치로 이동
        pixel_data = f.read()

    bytes_per_pixel = bit_depth // 8  # 한 픽셀당 바이트 수 (24비트 → 3바이트)
    row_size = ((width * bit_depth + 31) // 32) * 4  # 패딩 포함 행 크기

    output_lines = ["\n📌 **BMP 픽셀 데이터 (24비트 RGB, 일부 출력)**\n"]

    for y in range(height):
        offset = y * row_size
        row_data = pixel_data[offset:offset + width * bytes_per_pixel]

        # 24비트 BMP 데이터를 RGB로 변환
        row_pixels = []
        for i in range(0, len(row_data), bytes_per_pixel):
            blue = row_data[i]  # B
            green = row_data[i + 1]  # G
            red = row_data[i + 2]  # R

            # 24비트 RGB를 2비트 색상 코드로 변환 (e-paper 지원 색상 기준)
            if red == 0 and green == 0 and blue == 0:  # 검정
                bit_val = "01"
            elif red == 255 and green == 0 and blue == 0:  # 빨강
                bit_val = "10"
            elif red == 255 and green == 255 and blue == 0:  # 노랑
                bit_val = "11"
            else:  # 흰색
                bit_val = "00"

            row_pixels.append(f"({red},{green},{blue})->{bit_val}")

        row_text = f"🔹 Row {height - y}: {' '.join(row_pixels[:400])} ..."  # 앞 10픽셀만 출력
        output_lines.append(row_text)

    with open(output_file_path, "a", encoding="utf-8") as out_file:
        out_file.writelines("\n".join(output_lines))

# 실행
data_offset, width, height, bit_depth = read_bmp_header(bmp_file_path)
read_bmp_data(bmp_file_path, data_offset, width, height, bit_depth)

print(f"✅ BMP 데이터가 {output_file_path} 파일에 저장되었습니다.")
