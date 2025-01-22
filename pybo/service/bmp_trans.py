from PIL import Image, ImageOps
import os, requests, uuid, cv2
from io import BytesIO
import numpy as np




# 이미지 URL
# url = "https://cdn2.ppomppu.co.kr/zboard/data3/2024/0319/20240319173717_XqPTvgbNiI.jpeg"


class BMPTrans:
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

    # @staticmethod
    # def genenate_bmp_ai(url):
    #     # e-paper 해상도 설정
    #     EPAPER_WIDTH = 400
    #     EPAPER_HEIGHT = 300

    #     # 이미지 다운로드
    #     response = requests.get(url)
    #     if response.status_code == 200:
    #         # 이미지 열기
    #         img = Image.open(BytesIO(response.content))
    #         img = img.convert("RGB")  # OpenCV는 RGB 이미지로 처리

    #         # OpenCV로 변환
    #         cv_image = np.array(img)
    #         cv_image = cv_image[:, :, ::-1].copy()  # PIL 이미지를 OpenCV 형식(BGR)으로 변환

    #         # 얼굴 인식
    #         face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    #         gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    #         faces = face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

    #         if len(faces) > 0:
    #             # 가장 큰 얼굴을 기준으로 잘라냄
    #             x, y, w, h = faces[0]  # 첫 번째 얼굴 가져오기
    #             face_center_x = x + w // 2
    #             face_center_y = y + h // 2

    #             # 얼굴 기준으로 크기 조정
    #             left = max(face_center_x - EPAPER_WIDTH // 2, 0)
    #             top = max(face_center_y - EPAPER_HEIGHT // 2, 0)
    #             right = left + EPAPER_WIDTH
    #             bottom = top + EPAPER_HEIGHT

    #             cropped_img = img.crop((left, top, right, bottom))
    #         else:
    #             # 얼굴이 없을 경우 상단 중앙으로 크기 조정
    #             print("얼굴이 감지되지 않아 상단 중앙으로 이미지 조정")
    #             cropped_img = ImageOps.fit(img, (EPAPER_WIDTH, EPAPER_HEIGHT), method=Image.LANCZOS)

    #         # 흑백 변환
    #         grayscale_img = cropped_img.convert("L")
    #         bw_img = grayscale_img.convert("1", dither=Image.FLOYDSTEINBERG)

    #         # 파일명 생성
    #         uuid_4 = uuid.uuid4()
    #         bmp_name = f"e_paper_{uuid_4}.bmp"
            
    #         # 파일 저장
    #         bw_img.save(f"bmp_files/{bmp_name}", format="BMP")
    #         print("이미지가 성공적으로 변환되어 저장되었습니다.")

    #         return bmp_name
    #     else:
    #         print("이미지 다운로드에 실패했습니다.")
    #         return None


    @staticmethod
    def genenate_bmp_ai(url):
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
            bmp_name = f"e_paper_{uuid_4}.bmp"

            # 디렉토리 생성 및 파일 저장
            os.makedirs("bmp_files", exist_ok=True)
            bw_img.save(f"bmp_files/{bmp_name}", format="BMP")
            print(f"이미지가 성공적으로 변환되어 저장되었습니다: {bmp_name}")

            return bmp_name
        else:
            print("이미지 다운로드에 실패했습니다.")
            return None


    
    @staticmethod
    def genenate_bmp_top(url,size_height,size_weight):
        # e-paper 해상도 설정
        EPAPER_WIDTH = 400
        EPAPER_HEIGHT = 300

        # 이미지 다운로드
        response = requests.get(url)
        if response.status_code == 200:
            # 이미지 열기
            img = Image.open(BytesIO(response.content))

            # 이미지 크기 확인
            img_width, img_height = img.size
            print (img_width, img_height)

            # 상단 중앙 기준 크기 조정
            left = max((img_width - EPAPER_WIDTH) // 2, 0)
            top = 0
            right = left + EPAPER_WIDTH
            bottom = top + EPAPER_HEIGHT

            # 상단 중앙 부분 자르기
            cropped_img = img.crop((left, top, right, bottom))

            # 흑백 변환
            grayscale_img = cropped_img.convert("L")
            bw_img = grayscale_img.convert("1", dither=Image.FLOYDSTEINBERG)

            # 파일명 생성
            uuid_4 = uuid.uuid4()
            bmp_name = f"e_paper_{uuid_4}.bmp"

            # 디렉토리 생성 및 파일 저장
            os.makedirs("bmp_files", exist_ok=True)
            bw_img.save(f"bmp_files/{bmp_name}", format="BMP")
            print("이미지가 성공적으로 변환되어 저장되었습니다.")

            return bmp_name
        else:
            print("이미지 다운로드에 실패했습니다.")
            return None

