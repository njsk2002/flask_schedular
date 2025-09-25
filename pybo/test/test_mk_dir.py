import os

directory = "아이유"
test_dir = f"C:/DavidProject/flask_project/bmp_files/{directory}/mono_42"
os.makedirs(test_dir, exist_ok=True)
print(f"디렉토리가 생성되었습니다: {test_dir}")