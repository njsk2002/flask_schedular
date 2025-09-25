import struct
import os

def parse_bmp_header(bmp_file_path):
    """
    BMP 파일을 열어 헤더 정보를 파싱하고, 주요 메타데이터를 추출하는 함수
    """
    with open(bmp_file_path, 'rb') as f:
        # BMP 파일 헤더 (14바이트)
        file_type = f.read(2).decode('ascii')  # "BM"인지 확인
        if file_type != "BM":
            raise ValueError(f"{bmp_file_path} - 올바른 BMP 파일이 아닙니다.")
        file_size, reserved, data_offset = struct.unpack('<IHI', f.read(10))
        
        # DIB 헤더 (40바이트, BITMAPINFOHEADER 기준)
        header_size = struct.unpack('<I', f.read(4))[0]
        if header_size != 40:
            raise ValueError(f"{bmp_file_path} - 지원되지 않는 BMP 포맷입니다.")
        
        width, height, planes, bit_depth, compression = struct.unpack('<iiHHI', f.read(16))
        
        header_info = {
            "file_size": file_size,
            "data_offset": data_offset,
            "width": width,
            "height": height,
            "bit_depth": bit_depth,
            "compression": compression,
        }
        return header_info

def compare_bmp_files(bmp_file_1, bmp_file_2):
    """
    두 BMP 파일의 헤더 정보를 비교하고 결과를 출력하는 함수
    """
    print("\n=== BMP 파일 비교 시작 ===")
    print(f"파일1: {bmp_file_1}")
    print(f"파일2: {bmp_file_2}\n")
    
    try:
        bmp1_info = parse_bmp_header(bmp_file_1)
        bmp2_info = parse_bmp_header(bmp_file_2)
    except ValueError as e:
        print(e)
        return
    
    print("=== BMP 헤더 정보 비교 ===")
    for key in bmp1_info.keys():
        value1, value2 = bmp1_info[key], bmp2_info[key]
        status = "일치" if value1 == value2 else f"다름 ({value1} vs {value2})"
        print(f"{key}: {status}")
    
    # 파일 크기 비교
    file_size_1 = os.path.getsize(bmp_file_1)
    file_size_2 = os.path.getsize(bmp_file_2)
    print(f"파일 크기 비교: {'일치' if file_size_1 == file_size_2 else f'다름 ({file_size_1} vs {file_size_2})'}")
    
    # 픽셀 데이터 비교 (선택적, 용량이 클 경우 생략 가능)
    with open(bmp_file_1, 'rb') as f1, open(bmp_file_2, 'rb') as f2:
        f1.seek(bmp1_info['data_offset'])  # 픽셀 데이터 시작 위치
        f2.seek(bmp2_info['data_offset'])
        pixel_data_1 = f1.read()
        pixel_data_2 = f2.read()
        
        if pixel_data_1 == pixel_data_2:
            print("픽셀 데이터: 일치")
        else:
            print("픽셀 데이터: 다름")
    
# 사용 예시
if __name__ == "__main__":
    # 비교할 BMP 파일 경로
    bmp_file_1 = "C:/DavidProject/flask_project/bmp_files/카리나/col4_29/col4_29_22ffaec8-097d-4e4c-80d5-e6f01fcd93c1.bmp"
    bmp_file_2 = "C:/DavidProject/flask_project/bmp_files/카리나/col4_29/col4_29_27b67e7e-148f-4ba5-ba6e-89390e022d04.bmp"

    compare_bmp_files(bmp_file_1, bmp_file_2)