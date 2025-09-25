import struct
import zlib

def parse_png_chunks(png_file_path):
    """
    PNG 파일을 열어 시그니처 및 각 Chunk를 파싱하고,
    IHDR 정보(비트 깊이, 컬러 타입 등)를 함께 추출해 리스트로 반환
    """
    chunks = []
    with open(png_file_path, 'rb') as f:
        # 1) PNG 시그니처(8바이트) 확인
        signature = f.read(8)
        # PNG 시그니처가 맞는지 간단히 체크
        if signature != b'\x89PNG\r\n\x1a\n':
            raise ValueError("이 파일은 PNG 포맷이 아닌 것 같습니다.")

        # 2) IEND Chunk를 만날 때까지 반복해서 Chunk 읽기
        while True:
            # 길이(4바이트), 타입(4바이트)
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                # 파일 끝에 도달 (정상적이지 않은 PNG 가능)
                break

            length, chunk_type = struct.unpack(">I4s", chunk_header)
            chunk_type_str = chunk_type.decode('ascii')

            # Chunk 데이터 읽기
            chunk_data = f.read(length)
            # CRC(4바이트) 읽기
            crc_data = f.read(4)

            # Chunk 정보 저장
            chunk_info = {
                "type": chunk_type_str,
                "length": length,
                "crc": crc_data.hex().upper()  # CRC를 16진수로 저장
            }

            # IHDR Chunk면 비트 깊이, 컬러 타입 등 추가 분석
            if chunk_type_str == "IHDR":
                # IHDR 구조: width(4), height(4), bit_depth(1), color_type(1), 
                #           compression(1), filter(1), interlace(1)
                (
                    width,
                    height,
                    bit_depth,
                    color_type,
                    compression,
                    filter_method,
                    interlace
                ) = struct.unpack(">IIBBBBB", chunk_data)

                chunk_info["width"] = width
                chunk_info["height"] = height
                chunk_info["bit_depth"] = bit_depth
                chunk_info["color_type"] = color_type
                chunk_info["compression"] = compression
                chunk_info["filter_method"] = filter_method
                chunk_info["interlace"] = interlace

            chunks.append(chunk_info)

            # IEND Chunk를 만나면 종료
            if chunk_type_str == "IEND":
                break

    return chunks

def compare_png_files(png_file_1, png_file_2):
    """
    두 PNG 파일의 Chunk 구조 및 IHDR 정보를 비교하여 출력
    """
    chunks1 = parse_png_chunks(png_file_1)
    chunks2 = parse_png_chunks(png_file_2)

    # Chunk 시퀀스 목록 추출
    chunk_types_1 = [c['type'] for c in chunks1]
    chunk_types_2 = [c['type'] for c in chunks2]

    print(f"\n[파일1] {png_file_1} Chunks: {chunk_types_1}")
    print(f"[파일2] {png_file_2} Chunks: {chunk_types_2}\n")

    # IHDR 비교
    ihdr1 = next((c for c in chunks1 if c['type'] == 'IHDR'), None)
    ihdr2 = next((c for c in chunks2 if c['type'] == 'IHDR'), None)

    if ihdr1 and ihdr2:
        print("=== IHDR 정보 비교 ===")
        print(f" - Width: {ihdr1['width']} vs {ihdr2['width']}")
        print(f" - Height: {ihdr1['height']} vs {ihdr2['height']}")
        print(f" - Bit Depth: {ihdr1['bit_depth']} vs {ihdr2['bit_depth']}")
        print(f" - Color Type: {ihdr1['color_type']} vs {ihdr2['color_type']}")
        print(f" - Compression: {ihdr1['compression']} vs {ihdr2['compression']}")
        print(f" - Filter: {ihdr1['filter_method']} vs {ihdr2['filter_method']}")
        print(f" - Interlace: {ihdr1['interlace']} vs {ihdr2['interlace']}\n")
    else:
        print("IHDR Chunk가 없거나 정상적인 PNG가 아닐 수 있습니다.\n")

    # Chunk별 상세 비교
    print("=== Chunk 구조 상세 비교 ===")
    # 우선 길이가 다른지, 개수가 다른지 등 체크
    max_len = max(len(chunks1), len(chunks2))
    for i in range(max_len):
        c1 = chunks1[i] if i < len(chunks1) else None
        c2 = chunks2[i] if i < len(chunks2) else None

        if c1 and c2:
            # 두 Chunk의 타입이 같은지 확인
            if c1['type'] == c2['type']:
                # 타입이 같으면 길이나 CRC 비교
                status = "SAME TYPE"
                if c1['length'] != c2['length']:
                    status += f" | LENGTH DIFFER ({c1['length']} vs {c2['length']})"
                if c1['crc'] != c2['crc']:
                    status += f" | CRC DIFFER ({c1['crc']} vs {c2['crc']})"
                print(f"Chunk {i}: {c1['type']} -> {status}")
            else:
                print(f"Chunk {i}: {c1['type']} vs {c2['type']} (DIFFERENT TYPE)")
        elif c1 and not c2:
            print(f"Chunk {i}: {c1['type']} (파일2에는 해당 위치에 Chunk 없음)")
        elif c2 and not c1:
            print(f"Chunk {i}: {c2['type']} (파일1에는 해당 위치에 Chunk 없음)")

# 사용 예시
if __name__ == "__main__":
    # 비교할 PNG 파일 경로
    png_file_1 = "C:/DavidProject/flask_project/bmp_files/카리나/col4_29/col4_29_22ffaec8-097d-4e4c-80d5-e6f01fcd93c1.bmp"
    png_file_2 = "C:/DavidProject/flask_project/bmp_files/카리나/col4_29/col4_29_19ecca37-2508-49d4-8699-622b59faced2.bmp"

    compare_png_files(png_file_1, png_file_2)
