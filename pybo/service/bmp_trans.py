import os, requests, uuid, cv2, qrcode, platform, re
from io import BytesIO
import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFont



# 이미지 URL
# url = "https://cdn2.ppomppu.co.kr/zboard/data3/2024/0319/20240319173717_XqPTvgbNiI.jpeg"


class BMPTrans:
    ########### 사용 안함 #######################333
    def genenate_bmp(url):

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
            
            # 파일명 생성
            uuid_4 = uuid.uuid4()
            bmp_name = f"e_paper_{uuid_4}.bmp"
            # 파일 저장
            bw_img.save(f"bmp_files/{bmp_name}", format="BMP")
            print("이미지가 성공적으로 변환되어 저장되었습니다.")

            return bmp_name
        else:
            print("이미지 다운로드에 실패했습니다.")
            return None
    
    ############  사용 ######################
    @staticmethod
    def genenate_bmp_42_mono(url,key_word):
        # e-paper 해상도 설정
        # e-paper 해상도 설정
        EPAPER_WIDTH = 400
        EPAPER_HEIGHT = 300

        # 이미지 다운로드
        response = requests.get(url)
        if response.status_code == 200:
            print("이미지 다운로드 성공")
            # 이미지 열기
            img = Image.open(BytesIO(response.content))
            img = img.convert("RGB")  # OpenCV는 RGB 이미지로 처리

            # 이미지 크기 확인 및 크기 조정 (너비가 700 이상일 경우 비율 유지하며 너비 800으로 조정)
            img_width, img_height = img.size
            if img_width > 700:
                scale_factor = 800 / img_width
                new_width = 800
                new_height = int(img_height * scale_factor)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                print(f"이미지 크기 조정 완료: {new_width}x{new_height}")

            # OpenCV로 변환
            cv_image = np.array(img)
            cv_image = cv_image[:, :, ::-1].copy()  # PIL 이미지를 OpenCV 형식(BGR)으로 변환
            print("OpenCV 변환 완료")

            # 얼굴 인식
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

            if len(faces) > 0:
                print(f"감지된 얼굴 수: {len(faces)}")
                # 가장 큰 얼굴 선택
                x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
                print(f"가장 큰 얼굴 좌표와 크기: x={x}, y={y}, w={w}, h={h}")
                face_center_x = x + w // 2
                face_center_y = y + h // 2

                # 얼굴 크기를 350 이하로 조정
                if w > 350 or h > 350:
                    scale_factor = 350 / max(w, h)
                    w = int(w * scale_factor)
                    h = int(h * scale_factor)
                    print(f"조정된 얼굴 크기: w={w}, h={h}")

                # 얼굴 기준으로 영역 설정 (비율 유지)
                face_width = max(w, EPAPER_WIDTH)  # 최소 EPAPER_WIDTH로 설정
                face_height = max(h, EPAPER_HEIGHT)  # 최소 EPAPER_HEIGHT로 설정

                left = max(face_center_x - face_width // 2, 0)
                top = max(face_center_y - face_height // 2, 0)
                right = min(left + face_width, img.width)
                bottom = min(top + face_height, img.height)

                print(f"조정된 잘라낼 영역: left={left}, top={top}, right={right}, bottom={bottom}")

                # 주변 이미지 포함하도록 잘라내기
                cropped_img = img.crop((left, top, right, bottom))

                # e-paper 크기로 변환
                cropped_img = cropped_img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
                print("이미지 잘라내기 및 크기 조정 완료")
            else:
                # 얼굴이 없을 경우, 비율 유지하며 상단 중앙 기준으로 조정
                print("얼굴이 감지되지 않아 상단 중앙으로 이미지 조정")
                cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

            # 흑백 변환
            grayscale_img = cropped_img.convert("L")
            bw_img = grayscale_img.convert("1", dither=Image.FLOYDSTEINBERG)
            print("흑백 변환 완료")

            # 파일명 생성
            uuid_4 = uuid.uuid4()
            bmp_name = f"mono_42_{uuid_4}.bmp"
            

            print("keyword: ", key_word)

            # 디렉토리 생성 및 파일 저장
            os.makedirs(f"C:/DavidProject/flask_project/bmp_files/{key_word}/mono_42", exist_ok=True)
            bw_img.save(f"C:/DavidProject/flask_project/bmp_files/{key_word}/mono_42/{bmp_name}", format="BMP")
            print(f"이미지가 성공적으로 변환되어 저장되었습니다: {bmp_name}")

            return bmp_name
        else:
            print("이미지 다운로드에 실패했습니다.")
            return None

############  사용 ######################
    @staticmethod
    def genenate_bmp_42_3color(url, key_word):
        #file_path = r"C:/DavidProject/flask_project/카리나1.jpg"

        # e-paper 해상도 설정 (f290__.png와 동일: 128x296)
        EPAPER_WIDTH = 400
        EPAPER_HEIGHT = 300

        # 4색 팔레트 (Black, Red, Yellow, White)
        COLOR_MAP = {
            "black": (0, 0, 0),        # 검정
            "red": (255, 0, 0),        # 빨강
            # "yellow": (255, 255, 0),   # 노랑
            "white": (255, 255, 255)   # 흰색
        }
        PALETTE_VALUES = np.array(list(COLOR_MAP.values()))

         # 이미지 다운로드
        response = requests.get(url)
        if response.status_code == 200:
            print("이미지 다운로드 성공")
            # 이미지 열기
            try:
                img = Image.open(BytesIO(response.content))
                img = img.convert("RGB")  # OpenCV는 RGB 이미지로 처리
                print("이미지 열기 성공")
            except Exception as e:
                print("이미지 열기 실패:", e)
                exit(1)

        # 이미지 크기 조정 (너비가 700보다 크면 리사이즈)
        img_width, img_height = img.size
        if img_width > 700:
            scale_factor = 800 / img_width
            new_width = 800
            new_height = int(img_height * scale_factor)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            print(f"이미지 크기 조정 완료: {new_width}x{new_height}")

        # OpenCV 변환 (얼굴 검출용)
        cv_image = np.array(img)[:, :, ::-1].copy()  # PIL(RGB) -> OpenCV(BGR)
        print("OpenCV 변환 완료")

        # 얼굴 인식
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

        if len(faces) > 0:
            print(f"감지된 얼굴 수: {len(faces)}")
            x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
            print(f"가장 큰 얼굴 좌표와 크기: x={x}, y={y}, w={w}, h={h}")
            # 얼굴 중심 기준으로 크롭 (e-paper 해상도와 동일)
            left = max(x + w // 2 - EPAPER_WIDTH // 2, 0)
            top = max(y + h // 2 - EPAPER_HEIGHT // 2, 0)
            right = min(left + EPAPER_WIDTH, img.width)
            bottom = min(top + EPAPER_HEIGHT, img.height)
            print(f"잘라낼 영역: left={left}, top={top}, right={right}, bottom={bottom}")
            cropped_img = img.crop((left, top, right, bottom))
        else:
            print("얼굴 감지 실패, 중앙을 기준으로 크롭")
            cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

        # e-paper 크기로 조정
        cropped_img = cropped_img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
        print("이미지 크롭 및 크기 조정 완료")

        # 4색 변환 함수 (가중치 기반)
        def closest_color(pixel):
            distances = np.sum((PALETTE_VALUES - pixel) ** 2, axis=1)
            return tuple(PALETTE_VALUES[np.argmin(distances)])

        # Floyd-Steinberg 디더링 적용
        image_array = np.array(cropped_img, dtype=np.float32)
        for y in range(image_array.shape[0]):
            for x in range(image_array.shape[1]):
                old_pixel = image_array[y, x].copy()
                new_pixel = np.array(closest_color(old_pixel))
                image_array[y, x] = new_pixel
                error = old_pixel - new_pixel
                if x + 1 < image_array.shape[1]:
                    image_array[y, x + 1] += error * 7 / 16
                if x - 1 >= 0 and y + 1 < image_array.shape[0]:
                    image_array[y + 1, x - 1] += error * 3 / 16
                if y + 1 < image_array.shape[0]:
                    image_array[y + 1, x] += error * 5 / 16
                if x + 1 < image_array.shape[1] and y + 1 < image_array.shape[0]:
                    image_array[y + 1, x + 1] += error * 1 / 16

        # 0~255 범위 제한 후, 정수형 변환
        image_array = np.clip(image_array, 0, 255).astype(np.uint8)

        # RGBA 이미지 생성: RGB 채널에 모두 알파 255를 추가 (컬러 타입 6)
        alpha_channel = np.full((image_array.shape[0], image_array.shape[1]), 255, dtype=np.uint8)
        rgba_array = np.dstack((image_array, alpha_channel))
        final_img = Image.fromarray(rgba_array, "RGBA")

        # 추가 메타데이터 설정: gAMA, pHYs, sRGB
        final_img.info["gamma"] = 0.45455      # gAMA chunk (대략 1/2.2)
        final_img.info["dpi"] = (2835, 2835)     # pHYs chunk (2835 pixels/meter, 약 72 DPI)
        final_img.info["srgb"] = 0             # sRGB chunk (Perceptual rendering intent)

        # 파일명 생성
        uuid_4 = uuid.uuid4()
        bmp_name = f"col3_42_{uuid_4}.bmp"
        png_name = f"col3_42_{uuid_4}.png"

        # BMP 파일 저장
        os.makedirs(f"C:/DavidProject/flask_project/bmp_files/{key_word}/col3_42", exist_ok=True)
        final_img.save(f"C:/DavidProject/flask_project/bmp_files/{key_word}/col3_42/{bmp_name}", format="BMP")
        print(f"4색 BMP 이미지 저장 완료: {bmp_name}")
        

        # PNG 파일 저장 (추가 Chunk 포함: IHDR, sRGB, gAMA, pHYs, IDAT, IEND)
        os.makedirs(f"C:/DavidProject/flask_project/png_files/{key_word}/col3_42", exist_ok=True)
        final_img.save(f"C:/DavidProject/flask_project/png_files/{key_word}/col3_42/{png_name}", format="PNG", optimize=True)
        print(f"4색 PNG 이미지 저장 완료 (추가 Chunk 포함): {png_name}")
        
        return bmp_name
   

############  사용 ######################
    @staticmethod
    def genenate_bmp_37_4color(url,key_word):
        # file_path = r"C:/DavidProject/flask_project/카리나1.jpg"

        # e-paper 해상도 설정 (f290__.png와 동일: 128x296)
        EPAPER_WIDTH = 416
        EPAPER_HEIGHT = 240

        # 4색 팔레트 (Black, Red, Yellow, White)
        COLOR_MAP = {
            "black": (0, 0, 0),        # 검정
            "red": (255, 0, 0),        # 빨강
            "yellow": (255, 255, 0),   # 노랑
            "white": (255, 255, 255)   # 흰색
        }
        PALETTE_VALUES = np.array(list(COLOR_MAP.values()))
        
         # 이미지 다운로드
        response = requests.get(url)
        if response.status_code == 200:
            print("이미지 다운로드 성공")
            # 이미지 열기
            try:
                img = Image.open(BytesIO(response.content))
                img = img.convert("RGB")  # OpenCV는 RGB 이미지로 처리
                print("이미지 열기 성공")
            except Exception as e:
                print("이미지 열기 실패:", e)
                exit(1)

        # 이미지 크기 조정 (너비가 700보다 크면 리사이즈)
        img_width, img_height = img.size
        if img_width > 700:
            scale_factor = 800 / img_width
            new_width = 800
            new_height = int(img_height * scale_factor)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            print(f"이미지 크기 조정 완료: {new_width}x{new_height}")

        # OpenCV 변환 (얼굴 검출용)
        cv_image = np.array(img)[:, :, ::-1].copy()  # PIL(RGB) -> OpenCV(BGR)
        print("OpenCV 변환 완료")

        # 얼굴 인식
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

        if len(faces) > 0:
            print(f"감지된 얼굴 수: {len(faces)}")
            x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
            print(f"가장 큰 얼굴 좌표와 크기: x={x}, y={y}, w={w}, h={h}")
            # 얼굴 중심 기준으로 크롭 (e-paper 해상도와 동일)
            left = max(x + w // 2 - EPAPER_WIDTH // 2, 0)
            top = max(y + h // 2 - EPAPER_HEIGHT // 2, 0)
            right = min(left + EPAPER_WIDTH, img.width)
            bottom = min(top + EPAPER_HEIGHT, img.height)
            print(f"잘라낼 영역: left={left}, top={top}, right={right}, bottom={bottom}")
            cropped_img = img.crop((left, top, right, bottom))
        else:
            print("얼굴 감지 실패, 중앙을 기준으로 크롭")
            cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

        # e-paper 크기로 조정
        cropped_img = cropped_img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
        print("이미지 크롭 및 크기 조정 완료")

        # 4색 변환 함수 (가중치 기반)
        def closest_color(pixel):
            distances = np.sum((PALETTE_VALUES - pixel) ** 2, axis=1)
            return tuple(PALETTE_VALUES[np.argmin(distances)])

        # Floyd-Steinberg 디더링 적용
        image_array = np.array(cropped_img, dtype=np.float32)
        for y in range(image_array.shape[0]):
            for x in range(image_array.shape[1]):
                old_pixel = image_array[y, x].copy()
                new_pixel = np.array(closest_color(old_pixel))
                image_array[y, x] = new_pixel
                error = old_pixel - new_pixel
                if x + 1 < image_array.shape[1]:
                    image_array[y, x + 1] += error * 7 / 16
                if x - 1 >= 0 and y + 1 < image_array.shape[0]:
                    image_array[y + 1, x - 1] += error * 3 / 16
                if y + 1 < image_array.shape[0]:
                    image_array[y + 1, x] += error * 5 / 16
                if x + 1 < image_array.shape[1] and y + 1 < image_array.shape[0]:
                    image_array[y + 1, x + 1] += error * 1 / 16

        # 0~255 범위 제한 후, 정수형 변환
        image_array = np.clip(image_array, 0, 255).astype(np.uint8)

        # RGBA 이미지 생성: RGB 채널에 모두 알파 255를 추가 (컬러 타입 6)
        alpha_channel = np.full((image_array.shape[0], image_array.shape[1]), 255, dtype=np.uint8)
        rgba_array = np.dstack((image_array, alpha_channel))
        final_img = Image.fromarray(rgba_array, "RGBA")

        # 추가 메타데이터 설정: gAMA, pHYs, sRGB
        final_img.info["gamma"] = 0.45455      # gAMA chunk (대략 1/2.2)
        final_img.info["dpi"] = (2835, 2835)     # pHYs chunk (2835 pixels/meter, 약 72 DPI)
        final_img.info["srgb"] = 0             # sRGB chunk (Perceptual rendering intent)

        # 파일명 생성
        uuid_4 = uuid.uuid4()
        bmp_name = f"col4_37_{uuid_4}.bmp"
        png_name = f"col4_37_{uuid_4}.png"

        # BMP 파일 저장
        os.makedirs(f"C:/DavidProject/flask_project/bmp_files/{key_word}/col4_37", exist_ok=True)
        final_img.save(f"C:/DavidProject/flask_project/bmp_files/{key_word}/col4_37/{bmp_name}", format="BMP")
        print(f"4색 BMP 이미지 저장 완료: {bmp_name}")

        # PNG 파일 저장 (추가 Chunk 포함: IHDR, sRGB, gAMA, pHYs, IDAT, IEND)
        os.makedirs(f"C:/DavidProject/flask_project/png_files/{key_word}/col4_37", exist_ok=True)
        final_img.save(f"C:/DavidProject/flask_project/png_files/{key_word}/col4_37/{png_name}", format="PNG", optimize=True)
        print(f"4색 PNG 이미지 저장 완료 (추가 Chunk 포함): {png_name}")

        return bmp_name
    
    ############  사용 ######################
    @staticmethod
    def genenate_bmp_29_4color(url,key_word):
        # file_path = r"C:/DavidProject/flask_project/카리나1.jpg"

        # e-paper 해상도 설정 (f290__.png와 동일: 128x296)
        EPAPER_WIDTH = 296
        EPAPER_HEIGHT = 128

        # 4색 팔레트 (Black, Red, Yellow, White)
        COLOR_MAP = {
            "black": (0, 0, 0),        # 검정
            "red": (255, 0, 0),        # 빨강
            "yellow": (255, 255, 0),   # 노랑
            "white": (255, 255, 255)   # 흰색
        }
        PALETTE_VALUES = np.array(list(COLOR_MAP.values()))
        
         # 이미지 다운로드
        response = requests.get(url)
        if response.status_code == 200:
            print("이미지 다운로드 성공")
            # 이미지 열기
            try:
                img = Image.open(BytesIO(response.content))
                img = img.convert("RGB")  # OpenCV는 RGB 이미지로 처리
                print("이미지 열기 성공")
            except Exception as e:
                print("이미지 열기 실패:", e)
                exit(1)

        # 이미지 크기 조정 (너비가 700보다 크면 리사이즈)
        img_width, img_height = img.size
        if img_width > 700:
            scale_factor = 800 / img_width
            new_width = 800
            new_height = int(img_height * scale_factor)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            print(f"이미지 크기 조정 완료: {new_width}x{new_height}")

        # OpenCV 변환 (얼굴 검출용)
        cv_image = np.array(img)[:, :, ::-1].copy()  # PIL(RGB) -> OpenCV(BGR)
        print("OpenCV 변환 완료")

        # 얼굴 인식
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

        if len(faces) > 0:
            print(f"감지된 얼굴 수: {len(faces)}")
            x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
            print(f"가장 큰 얼굴 좌표와 크기: x={x}, y={y}, w={w}, h={h}")
            # 얼굴 중심 기준으로 크롭 (e-paper 해상도와 동일)
            left = max(x + w // 2 - EPAPER_WIDTH // 2, 0)
            top = max(y + h // 2 - EPAPER_HEIGHT // 2, 0)
            right = min(left + EPAPER_WIDTH, img.width)
            bottom = min(top + EPAPER_HEIGHT, img.height)
            print(f"잘라낼 영역: left={left}, top={top}, right={right}, bottom={bottom}")
            cropped_img = img.crop((left, top, right, bottom))
        else:
            print("얼굴 감지 실패, 중앙을 기준으로 크롭")
            cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

        # e-paper 크기로 조정
        cropped_img = cropped_img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
        print("이미지 크롭 및 크기 조정 완료")

        # 4색 변환 함수 (가중치 기반)
        def closest_color(pixel):
            distances = np.sum((PALETTE_VALUES - pixel) ** 2, axis=1)
            return tuple(PALETTE_VALUES[np.argmin(distances)])

        # Floyd-Steinberg 디더링 적용
        image_array = np.array(cropped_img, dtype=np.float32)
        for y in range(image_array.shape[0]):
            for x in range(image_array.shape[1]):
                old_pixel = image_array[y, x].copy()
                new_pixel = np.array(closest_color(old_pixel))
                image_array[y, x] = new_pixel
                error = old_pixel - new_pixel
                if x + 1 < image_array.shape[1]:
                    image_array[y, x + 1] += error * 7 / 16
                if x - 1 >= 0 and y + 1 < image_array.shape[0]:
                    image_array[y + 1, x - 1] += error * 3 / 16
                if y + 1 < image_array.shape[0]:
                    image_array[y + 1, x] += error * 5 / 16
                if x + 1 < image_array.shape[1] and y + 1 < image_array.shape[0]:
                    image_array[y + 1, x + 1] += error * 1 / 16

        # 0~255 범위 제한 후, 정수형 변환
        image_array = np.clip(image_array, 0, 255).astype(np.uint8)

        # RGBA 이미지 생성: RGB 채널에 모두 알파 255를 추가 (컬러 타입 6)
        alpha_channel = np.full((image_array.shape[0], image_array.shape[1]), 255, dtype=np.uint8)
        rgba_array = np.dstack((image_array, alpha_channel))
        final_img = Image.fromarray(rgba_array, "RGBA")

        # 추가 메타데이터 설정: gAMA, pHYs, sRGB
        final_img.info["gamma"] = 0.45455      # gAMA chunk (대략 1/2.2)
        final_img.info["dpi"] = (2835, 2835)     # pHYs chunk (2835 pixels/meter, 약 72 DPI)
        final_img.info["srgb"] = 0             # sRGB chunk (Perceptual rendering intent)

        # 파일명 생성
        uuid_4 = uuid.uuid4()
        bmp_name = f"col4_29_{uuid_4}.bmp"
        png_name = f"col4_29_{uuid_4}.png"

        # BMP 파일 저장
        os.makedirs(f"C:/DavidProject/flask_project/bmp_files/{key_word}/col4_29", exist_ok=True)
        final_img.save(f"C:/DavidProject/flask_project/bmp_files/{key_word}/col4_29/{bmp_name}", format="BMP")
        print(f"4색 BMP 이미지 저장 완료: {bmp_name}")

        # PNG 파일 저장 (추가 Chunk 포함: IHDR, sRGB, gAMA, pHYs, IDAT, IEND)
        os.makedirs(f"C:/DavidProject/flask_project/png_files/{key_word}/col4_29", exist_ok=True)
        final_img.save(f"C:/DavidProject/flask_project/png_files/{key_word}/col4_29/{png_name}", format="PNG", optimize=True)
        print(f"4색 PNG 이미지 저장 완료 (추가 Chunk 포함): {png_name}")

        return bmp_name
    

    ############  사용 ######################
    @staticmethod
    def genenate_bmp_397_4color(url,key_word):
        # file_path = r"C:/DavidProject/flask_project/카리나1.jpg"

        # e-paper 해상도 설정 (f290__.png와 동일: 800x480)
        EPAPER_WIDTH = 800
        EPAPER_HEIGHT = 480

        # 4색 팔레트 (Black, Red, Yellow, White)
        COLOR_MAP = {
            "black": (0, 0, 0),        # 검정
            "red": (255, 0, 0),        # 빨강
            "yellow": (255, 255, 0),   # 노랑
            "white": (255, 255, 255)   # 흰색
        }
        PALETTE_VALUES = np.array(list(COLOR_MAP.values()))
        
         # 이미지 다운로드
        response = requests.get(url)
        if response.status_code == 200:
            print("이미지 다운로드 성공")
            # 이미지 열기
            try:
                img = Image.open(BytesIO(response.content))
                img = img.convert("RGB")  # OpenCV는 RGB 이미지로 처리
                print("이미지 열기 성공")
            except Exception as e:
                print("이미지 열기 실패:", e)
                exit(1)

        # 이미지 크기 조정 (너비가 700보다 크면 리사이즈)
        img_width, img_height = img.size
        if img_width > 800:
            scale_factor = 800 / img_width
            new_width = 480
            new_height = int(img_height * scale_factor)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            print(f"이미지 크기 조정 완료: {new_width}x{new_height}")

        # OpenCV 변환 (얼굴 검출용)
        cv_image = np.array(img)[:, :, ::-1].copy()  # PIL(RGB) -> OpenCV(BGR)
        print("OpenCV 변환 완료")

        # 얼굴 인식
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

        if len(faces) > 0:
            print(f"감지된 얼굴 수: {len(faces)}")
            x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
            print(f"가장 큰 얼굴 좌표와 크기: x={x}, y={y}, w={w}, h={h}")
            # 얼굴 중심 기준으로 크롭 (e-paper 해상도와 동일)
            left = max(x + w // 2 - EPAPER_WIDTH // 2, 0)
            top = max(y + h // 2 - EPAPER_HEIGHT // 2, 0)
            right = min(left + EPAPER_WIDTH, img.width)
            bottom = min(top + EPAPER_HEIGHT, img.height)
            print(f"잘라낼 영역: left={left}, top={top}, right={right}, bottom={bottom}")
            cropped_img = img.crop((left, top, right, bottom))
        else:
            print("얼굴 감지 실패, 중앙을 기준으로 크롭")
            cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

        # e-paper 크기로 조정
        cropped_img = cropped_img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
        print("이미지 크롭 및 크기 조정 완료")

        # 4색 변환 함수 (가중치 기반)
        def closest_color(pixel):
            distances = np.sum((PALETTE_VALUES - pixel) ** 2, axis=1)
            return tuple(PALETTE_VALUES[np.argmin(distances)])

        # Floyd-Steinberg 디더링 적용
        image_array = np.array(cropped_img, dtype=np.float32)
        for y in range(image_array.shape[0]):
            for x in range(image_array.shape[1]):
                old_pixel = image_array[y, x].copy()
                new_pixel = np.array(closest_color(old_pixel))
                image_array[y, x] = new_pixel
                error = old_pixel - new_pixel
                if x + 1 < image_array.shape[1]:
                    image_array[y, x + 1] += error * 7 / 16
                if x - 1 >= 0 and y + 1 < image_array.shape[0]:
                    image_array[y + 1, x - 1] += error * 3 / 16
                if y + 1 < image_array.shape[0]:
                    image_array[y + 1, x] += error * 5 / 16
                if x + 1 < image_array.shape[1] and y + 1 < image_array.shape[0]:
                    image_array[y + 1, x + 1] += error * 1 / 16

        # 0~255 범위 제한 후, 정수형 변환
        image_array = np.clip(image_array, 0, 255).astype(np.uint8)

        # RGBA 이미지 생성: RGB 채널에 모두 알파 255를 추가 (컬러 타입 6)
        alpha_channel = np.full((image_array.shape[0], image_array.shape[1]), 255, dtype=np.uint8)
        rgba_array = np.dstack((image_array, alpha_channel))
        final_img = Image.fromarray(rgba_array, "RGBA")

        # 추가 메타데이터 설정: gAMA, pHYs, sRGB
        final_img.info["gamma"] = 0.45455      # gAMA chunk (대략 1/2.2)
        final_img.info["dpi"] = (2835, 2835)     # pHYs chunk (2835 pixels/meter, 약 72 DPI)
        final_img.info["srgb"] = 0             # sRGB chunk (Perceptual rendering intent)

        # 파일명 생성
        uuid_4 = uuid.uuid4()
        bmp_name = f"col4_397_{uuid_4}.bmp"
        png_name = f"col4_397_{uuid_4}.png"

        # BMP 파일 저장
        os.makedirs(f"C:/DavidProject/flask_project/bmp_files/{key_word}/col4_397", exist_ok=True)
        final_img.save(f"C:/DavidProject/flask_project/bmp_files/{key_word}/col4_397/{bmp_name}", format="BMP")
        print(f"4색 BMP 이미지 저장 완료: {bmp_name}")

        # PNG 파일 저장 (추가 Chunk 포함: IHDR, sRGB, gAMA, pHYs, IDAT, IEND)
        os.makedirs(f"C:/DavidProject/flask_project/png_files/{key_word}/col4_397", exist_ok=True)
        final_img.save(f"C:/DavidProject/flask_project/png_files/{key_word}/col4_397/{png_name}", format="PNG", optimize=True)
        print(f"4색 PNG 이미지 저장 완료 (추가 Chunk 포함): {png_name}")

        return bmp_name
    

    ############  사용 ######################
    @staticmethod
    def genenate_bmp_75_mono(url,key_word):
        # e-paper 해상도 설정
        # e-paper 해상도 설정
        EPAPER_WIDTH = 800
        EPAPER_HEIGHT = 480

        # 이미지 다운로드
        response = requests.get(url)
        if response.status_code == 200:
            print("이미지 다운로드 성공")
            # 이미지 열기
            img = Image.open(BytesIO(response.content))
            img = img.convert("RGB")  # OpenCV는 RGB 이미지로 처리

            # 이미지 크기 확인 및 크기 조정 (너비가 700 이상일 경우 비율 유지하며 너비 800으로 조정)
            img_width, img_height = img.size
            if img_width > 800:
                scale_factor = 800 / img_width
                new_width = 480
                new_height = int(img_height * scale_factor)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                print(f"이미지 크기 조정 완료: {new_width}x{new_height}")

            # OpenCV로 변환
            cv_image = np.array(img)
            cv_image = cv_image[:, :, ::-1].copy()  # PIL 이미지를 OpenCV 형식(BGR)으로 변환
            print("OpenCV 변환 완료")

            # 얼굴 인식
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

            if len(faces) > 0:
                print(f"감지된 얼굴 수: {len(faces)}")
                # 가장 큰 얼굴 선택
                x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
                print(f"가장 큰 얼굴 좌표와 크기: x={x}, y={y}, w={w}, h={h}")
                face_center_x = x + w // 2
                face_center_y = y + h // 2

                # 얼굴 크기를 350 이하로 조정
                if w > 350 or h > 350:
                    scale_factor = 350 / max(w, h)
                    w = int(w * scale_factor)
                    h = int(h * scale_factor)
                    print(f"조정된 얼굴 크기: w={w}, h={h}")

                # 얼굴 기준으로 영역 설정 (비율 유지)
                face_width = max(w, EPAPER_WIDTH)  # 최소 EPAPER_WIDTH로 설정
                face_height = max(h, EPAPER_HEIGHT)  # 최소 EPAPER_HEIGHT로 설정

                left = max(face_center_x - face_width // 2, 0)
                top = max(face_center_y - face_height // 2, 0)
                right = min(left + face_width, img.width)
                bottom = min(top + face_height, img.height)

                print(f"조정된 잘라낼 영역: left={left}, top={top}, right={right}, bottom={bottom}")

                # 주변 이미지 포함하도록 잘라내기
                cropped_img = img.crop((left, top, right, bottom))

                # e-paper 크기로 변환
                cropped_img = cropped_img.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
                print("이미지 잘라내기 및 크기 조정 완료")
            else:
                # 얼굴이 없을 경우, 비율 유지하며 상단 중앙 기준으로 조정
                print("얼굴이 감지되지 않아 상단 중앙으로 이미지 조정")
                cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

            # 흑백 변환
            grayscale_img = cropped_img.convert("L")
            bw_img = grayscale_img.convert("1", dither=Image.FLOYDSTEINBERG)
            print("흑백 변환 완료")

            # 파일명 생성
            uuid_4 = uuid.uuid4()
            bmp_name = f"mono_75_{uuid_4}.bmp"
            

            print("keyword: ", key_word)

            # 디렉토리 생성 및 파일 저장
            os.makedirs(f"C:/DavidProject/flask_project/bmp_files/{key_word}/mono_75", exist_ok=True)
            bw_img.save(f"C:/DavidProject/flask_project/bmp_files/{key_word}/mono_75/{bmp_name}", format="BMP")
            print(f"이미지가 성공적으로 변환되어 저장되었습니다: {bmp_name}")

            return bmp_name
        else:
            print("이미지 다운로드에 실패했습니다.")
            return None
    

    @staticmethod
    def genenate_bmp_133_6color(url, key_word):
        # === e-paper 해상도 (13.3", 1600x1200) ===
        EPAPER_WIDTH  = 1600
        EPAPER_HEIGHT = 1200

        # === Spectra 6 팔레트: Black, White, Red, Yellow, Green, Blue ===
        COLOR_MAP = {
            "black":  (0,   0,   0  ),
            "white":  (255, 255, 255),
            "red":    (255, 0,   0  ),
            "yellow": (255, 255, 0  ),
            "green":  (0,   255, 0  ),
            "blue":   (0,   0,   255)
        }
        PALETTE_VALUES = np.array(list(COLOR_MAP.values()), dtype=np.float32)

        # === (옵션) BMP/PNG를 RGBA로 저장할지 여부 (패널 구동용이면 보통 RGB만으로 충분) ===
        USE_ALPHA = True

        # === 이미지 다운로드 ===
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        try:
            img = Image.open(BytesIO(resp.content)).convert("RGB")
        except Exception as e:
            print("이미지 열기 실패:", e)
            raise

        # === 얼굴 인식 준비(OpenCV) ===
        cv_image = np.array(img)[:, :, ::-1].copy()  # PIL(RGB) -> OpenCV(BGR)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
        )

        # === 크롭 영역 계산 ===
        if len(faces) > 0:
            # 가장 큰 얼굴 기준
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            cx, cy = x + w // 2, y + h // 2
            left   = max(cx - EPAPER_WIDTH  // 2, 0)
            top    = max(cy - EPAPER_HEIGHT // 2, 0)
            right  = min(left + EPAPER_WIDTH,  img.width)
            bottom = min(top  + EPAPER_HEIGHT, img.height)

            # 이미지 경계 보정
            if right - left < EPAPER_WIDTH:
                left = max(right - EPAPER_WIDTH, 0)
            if bottom - top < EPAPER_HEIGHT:
                top = max(bottom - EPAPER_HEIGHT, 0)

            cropped = img.crop((left, top, right, bottom))
            # 만약 원본이 더 작으면 최종 해상도로 보간
            if cropped.size != (EPAPER_WIDTH, EPAPER_HEIGHT):
                cropped = cropped.resize((EPAPER_WIDTH, EPAPER_HEIGHT), Image.LANCZOS)
        else:
            # 얼굴 없으면 비율 유지해 가운데 맞춰 크롭
            cropped = ImageOps.fit(
                img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS
            )

        # === 6색 양자화 + Floyd–Steinberg 디더링 ===
        def closest_color(pixel_vec):
            # pixel_vec: shape (3,), float32
            # PALETTE_VALUES: shape (6,3)
            diffs = PALETTE_VALUES - pixel_vec
            d2 = np.einsum("ij,ij->i", diffs, diffs)  # 각 팔레트 색과의 제곱거리
            return PALETTE_VALUES[np.argmin(d2)]

        arr = np.array(cropped, dtype=np.float32)  # (H,W,3)

        H, W, _ = arr.shape
        for y in range(H):
            for x in range(W):
                old_px = arr[y, x].copy()
                new_px = closest_color(old_px)
                arr[y, x] = new_px
                err = old_px - new_px
                # 디더링 에러 분배
                if x + 1 < W:
                    arr[y, x + 1] += err * (7/16)
                if y + 1 < H and x - 1 >= 0:
                    arr[y + 1, x - 1] += err * (3/16)
                if y + 1 < H:
                    arr[y + 1, x] += err * (5/16)
                if y + 1 < H and x + 1 < W:
                    arr[y + 1, x + 1] += err * (1/16)

        arr = np.clip(arr, 0, 255).astype(np.uint8)

        # === 최종 이미지 생성 (RGBA 또는 RGB) ===
        if USE_ALPHA:
            alpha = np.full((H, W), 255, dtype=np.uint8)
            rgba = np.dstack((arr, alpha))
            final_img = Image.fromarray(rgba, "RGBA")
        else:
            final_img = Image.fromarray(arr, "RGB")

        # (선택) PNG 메타 정보
        final_img.info["gamma"] = 0.45455
        final_img.info["dpi"]   = (2835, 2835)  # 약 72 DPI
        final_img.info["srgb"]  = 0

        # === 저장 경로 / 파일명 ===
        uid = uuid.uuid4()
        bmp_name = f"col6_133_{EPAPER_WIDTH}x{EPAPER_HEIGHT}_{uid}.bmp"
        png_name = f"col6_133_{EPAPER_WIDTH}x{EPAPER_HEIGHT}_{uid}.png"

        bmp_dir = f"C:/DavidProject/flask_project/bmp_files/{key_word}/col6_133"
        png_dir = f"C:/DavidProject/flask_project/png_files/{key_word}/col6_133"
        os.makedirs(bmp_dir, exist_ok=True)
        os.makedirs(png_dir, exist_ok=True)

        # BMP/PNG 저장
        final_img.save(os.path.join(bmp_dir, bmp_name), format="BMP")
        final_img.save(os.path.join(png_dir, png_name), format="PNG", optimize=True)

        print(f"[SAVE] 6색 BMP: {bmp_name}")
        print(f"[SAVE] 6색 PNG: {png_name}")

        return bmp_name

    # ############# 사용 안함 ###########################
    # @staticmethod
    # def genenate_bmp_top(url,size_height,size_weight):
    #     # e-paper 해상도 설정
    #     EPAPER_WIDTH = 400
    #     EPAPER_HEIGHT = 300

    #     # 이미지 다운로드
    #     response = requests.get(url)
    #     if response.status_code == 200:
    #         # 이미지 열기
    #         img = Image.open(BytesIO(response.content))

    #         # 이미지 크기 확인
    #         img_width, img_height = img.size
    #         print (img_width, img_height)

    #         # 상단 중앙 기준 크기 조정
    #         left = max((img_width - EPAPER_WIDTH) // 2, 0)
    #         top = 0
    #         right = left + EPAPER_WIDTH
    #         bottom = top + EPAPER_HEIGHT

    #         # 상단 중앙 부분 자르기
    #         cropped_img = img.crop((left, top, right, bottom))

    #         # 흑백 변환
    #         grayscale_img = cropped_img.convert("L")
    #         bw_img = grayscale_img.convert("1", dither=Image.FLOYDSTEINBERG)

    #         # 파일명 생성
    #         uuid_4 = uuid.uuid4()
    #         bmp_name = f"e_paper_{uuid_4}.bmp"

    #         # 디렉토리 생성 및 파일 저장
    #         os.makedirs("bmp_files", exist_ok=True)
    #         bw_img.save(f"bmp_files/{bmp_name}", format="BMP")
    #         print("이미지가 성공적으로 변환되어 저장되었습니다.")

    #         return bmp_name
    #     else:
    #         print("이미지 다운로드에 실패했습니다.")
    #         return None

    ######## e- 명함 ##########################################3
    @staticmethod
    def generate_bmp_namecard(namecard,output_folder,qr_data):
        # 이미지 경로
        # selected_photo = r"C:/DavidProject/flask_project/출입증2.png"

        # e-paper 해상도 설정
        EPAPER_WIDTH = 400
        EPAPER_HEIGHT = 300

        # QR 코드 데이터 및 크기 설정
        # qr_data = "http://192.168.0.136:5000/naverapi/generate_vcard"
        QR_SIZE = 100  # QR 코드 크기 (100x100 픽셀)

        username = namecard.username if namecard and namecard.username else "명함 없음"
        company = namecard.company if namecard and namecard.company else "회사 정보 없음"
        department = namecard.department if namecard and namecard.department else "회사 정보 없음"
        position = namecard.position if namecard and namecard.position else "직급 정보 없음"
        email = namecard.email if namecard and namecard.email else "이메일 없음"
        phone = namecard.phone if namecard and namecard.phone else "전화번호 없음"
        tel_rep = namecard.tel_rep if namecard and namecard.tel_rep else "공용전화 없음"
        tel_dir = namecard.tel_dir if namecard and namecard.tel_dir else "직통전화 없음"
        fax = namecard.fax if namecard and namecard.fax else "팩스 없음"
        homepage = namecard.homepage if namecard and namecard.homepage else "홈페이지 없음"

        if namecard.selected_photo:
            photo = namecard.selected_photo
            split_file = photo.split("uploads/")[1]  # 'uploads/' 이후의 문자열 가져오기   
            selected_photo = "C:/DavidProject/flask_project/flask_schedular/uploads/" + split_file
        else:
            selected_photo = "/static/images/icelogo.png"
  
        if namecard and namecard.com_address: 
            com_address = BMPTrans.format_address(namecard.com_address)
        else:
            com_address = "주소 없음"

        print(selected_photo)
        # # 텍스트 정보
        # username = "홍길동"
        # department = "부설연구소"
        # position = "책임연구원"
        # email = "davidjung@icetech.co.kr"
        # phone = "010-1234-5678"
        # tel_rep = "02-1234-5678"
        # tel_dir = "070-9876-5432"
        # fax = "02-1111-2222"
        # com_address = "(우 13207)\n경기도 성남시 중원구 사기막골로 124\nSKn테크노파크 넥스센터 2층"
        # homepage = "www.openai.com"

        # 출력 폴더 생성
        # output_folder = "bmp_files"
        # os.makedirs(output_folder, exist_ok=True)

        # 폰트 경로 설정
        if platform.system() == "Windows":
            font_path = "C:/Windows/Fonts/malgun.ttf"  # Windows용 폰트 경로
        elif platform.system() == "Linux":
            font_path = "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"  # Linux용 폰트 경로
        else:
            raise Exception("지원되지 않는 운영체제입니다.")

        try:
            # 배경 이미지 열기
            img = Image.open(selected_photo)

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

            # 회사이름 제목 추가 (오른쪽 상단)
            title_text = company
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
            print("OUTPUT: ", output_folder)
            # 고유 파일명 생성 및 저장
            uuid_4 = uuid.uuid4()
            bmp_name = f"e_paper_{uuid_4}.bmp"
            bmp_path = os.path.join(output_folder, bmp_name)
            bw_img.save(bmp_path, format="BMP")

            print(f"이미지가 성공적으로 변환되어 저장되었습니다: {bmp_path}")
            return bmp_name, bmp_path  #bmp파일 네임과 풀경로 반환

        except FileNotFoundError:
            print("로컬 파일을 찾을 수 없습니다. 경로를 확인하세요.")
            return None, None
        except Exception as e:
            print(f"오류가 발생했습니다: {e}")
            return None, None

    # 주소 줄 바꿈
    def format_address(com_address):
        # ✅ 1차 줄바꿈: "광역시" 또는 "도" 앞에서 줄바꿈
        address_pattern = re.compile(r"(서울|부산|대구|인천|광주|대전|울산|세종|제주|경기도|강원도|충청북도|충청남도|전라북도|전라남도|경상북도|경상남도)")
        
        match = address_pattern.search(com_address)
        if match:
            split_pos = match.start()  # 광역시/도의 시작 위치
            com_address = com_address[:split_pos] + "\n" + com_address[split_pos:]

        # ✅ 2차 줄바꿈: 도로명 주소 앞에서 줄바꿈
        road_pattern = re.compile(r"([가-힣]+(?:로|길|대로)\s*\d+)")
        
        match = road_pattern.search(com_address)
        if match:
            #split_pos = match.start()  # 도로명 주소 시작 위치
            split_pos = match.end()  # 도로명 주소 끝 위치
            com_address = com_address[:split_pos] + "\n" + com_address[split_pos:]

        return com_address    


