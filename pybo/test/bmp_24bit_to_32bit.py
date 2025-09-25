import struct

def map_to_four_colors(r, g, b):
    # 목표 색상 정의: (r, g, b)
    target_colors = [
        (0, 0, 0),         # Black
        (255, 0, 0),       # Red
        (255, 255, 0),     # Yellow
        (255, 255, 255)    # White
    ]
    # 각 목표 색상과의 유클리드 거리 제곱을 계산
    distances = [ (r - tr)**2 + (g - tg)**2 + (b - tb)**2 for (tr, tg, tb) in target_colors ]
    # 가장 가까운 색상의 인덱스 선택
    min_index = distances.index(min(distances))
    return target_colors[min_index]

def convert_bmp24_to_bmp32(input_path, output_path):
    with open(input_path, 'rb') as f:
        # BMP 파일 헤더 (14바이트)
        bmp_header = f.read(14)
        if bmp_header[0:2] != b'BM':
            raise ValueError("유효한 BMP 파일이 아닙니다.")
        file_size = struct.unpack('<I', bmp_header[2:6])[0]
        reserved1 = struct.unpack('<H', bmp_header[6:8])[0]
        reserved2 = struct.unpack('<H', bmp_header[8:10])[0]
        data_offset = struct.unpack('<I', bmp_header[10:14])[0]
        
        # DIB 헤더 (BITMAPINFOHEADER, 40바이트)
        dib_header = f.read(40)
        header_size = struct.unpack('<I', dib_header[0:4])[0]
        if header_size != 40:
            raise ValueError("현재는 BITMAPINFOHEADER(40바이트) 포맷만 지원합니다.")
        width = struct.unpack('<i', dib_header[4:8])[0]
        height = struct.unpack('<i', dib_header[8:12])[0]
        planes = struct.unpack('<H', dib_header[12:14])[0]
        bit_count = struct.unpack('<H', dib_header[14:16])[0]
        compression = struct.unpack('<I', dib_header[16:20])[0]
        image_size = struct.unpack('<I', dib_header[20:24])[0]
        x_pixels_per_meter = struct.unpack('<I', dib_header[24:28])[0]
        y_pixels_per_meter = struct.unpack('<I', dib_header[28:32])[0]
        colors_used = struct.unpack('<I', dib_header[32:36])[0]
        important_colors = struct.unpack('<I', dib_header[36:40])[0]
        
        if bit_count != 24:
            raise ValueError("입력 BMP 파일은 24비트가 아닙니다.")
        
        # 24비트 BMP의 각 행은 (width*3) 바이트에 4바이트 배수를 맞추기 위한 패딩이 추가됨.
        row_size_in = ((width * 3 + 3) // 4) * 4
        # 32비트 BMP는 각 픽셀이 4바이트이므로 추가 패딩이 필요없음.
        row_size_out = width * 4
        
        # 픽셀 데이터를 행 단위로 읽음 (BMP는 기본적으로 bottom-up)
        abs_height = abs(height)
        f.seek(data_offset)
        pixel_rows = []
        for _ in range(abs_height):
            row = f.read(row_size_in)
            # 앞의 width*3바이트가 실제 픽셀 데이터임.
            pixel_rows.append(row[:width*3])
    
    # 24비트 데이터를 32비트로 변환하면서 4가지 색상으로 매핑
    new_pixel_rows = []
    for row in pixel_rows:
        new_row = bytearray()
        for i in range(0, len(row), 3):
            b, g, r = row[i], row[i+1], row[i+2]
            # 네 가지 색상 중 가장 가까운 색상으로 매핑
            mapped_r, mapped_g, mapped_b = map_to_four_colors(r, g, b)
            new_row.extend([mapped_b, mapped_g, mapped_r, 0xFF])
        new_pixel_rows.append(new_row)
    
    # 새로운 이미지 크기 및 전체 파일 크기 계산
    new_image_size = row_size_out * abs_height
    new_data_offset = 14 + 40  # 기본 헤더 크기 (색상 팔레트 없음)
    new_file_size = new_data_offset + new_image_size

    # 새로운 BMP 파일 헤더 생성
    new_bmp_header = bytearray()
    new_bmp_header.extend(b'BM')
    new_bmp_header.extend(struct.pack('<I', new_file_size))
    new_bmp_header.extend(struct.pack('<H', 0))  # reserved1
    new_bmp_header.extend(struct.pack('<H', 0))  # reserved2
    new_bmp_header.extend(struct.pack('<I', new_data_offset))
    
    # 새로운 DIB 헤더 (BITMAPINFOHEADER, 40바이트)
    new_dib_header = bytearray()
    new_dib_header.extend(struct.pack('<I', 40))  # 헤더 크기
    new_dib_header.extend(struct.pack('<i', width))
    new_dib_header.extend(struct.pack('<i', height))
    new_dib_header.extend(struct.pack('<H', planes))
    new_dib_header.extend(struct.pack('<H', 32))  # 32비트로 변경
    new_dib_header.extend(struct.pack('<I', 0))   # BI_RGB (무압축)
    new_dib_header.extend(struct.pack('<I', new_image_size))
    new_dib_header.extend(struct.pack('<I', x_pixels_per_meter))
    new_dib_header.extend(struct.pack('<I', y_pixels_per_meter))
    new_dib_header.extend(struct.pack('<I', 0))   # colors_used
    new_dib_header.extend(struct.pack('<I', 0))   # important_colors
    
    # 변환된 파일 저장
    with open(output_path, 'wb') as out_f:
        out_f.write(new_bmp_header)
        out_f.write(new_dib_header)
        for row in new_pixel_rows:
            out_f.write(row)
    
    print(f"'{input_path}' 파일을 24비트에서 32비트로 변환하여 '{output_path}'에 저장했습니다.")

# 사용 예시
if __name__ == "__main__":
    input_bmp = "C:/DavidProject/flask_project/bmp_files/고윤정/col4_29/내셔널5.bmp"
    output_bmp = "C:/DavidProject/flask_project/bmp_files/고윤정/col4_29/col4_29_48550b80-dfd5-4146-a91b-b5d934ca24d6.bmp"
    convert_bmp24_to_bmp32(input_bmp, output_bmp)
