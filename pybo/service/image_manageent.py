import os, functools
from uuid import uuid4
from datetime import datetime
from flask import Blueprint, url_for, render_template, flash, request, session, g , jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect, secure_filename

class ImageManagement:
    # 📌 파일 처리 (사진 업로드)
    def save_uploaded_photo(photo, upload_folder):
        """ 개별 사진 업로드 및 파일명 생성 """
        if photo and photo.filename != "":
            filename = secure_filename(photo.filename)  # 보안 처리를 위한 안전한 파일명 변환

            # 📌 폴더가 없으면 생성
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            # 📌 파일명과 확장자 분리
            name, ext = os.path.splitext(filename)

            # 📌 10자 이상이면 앞 10자 + UUID4, 10자 이하면 전체 파일명 + UUID4
            short_name = name[:10] if len(name) >= 10 else name
            unique_filename = f"{short_name}_{uuid4().hex[:8]}{ext}"  # UUID 8자리 추가

            # 📌 파일 저장 경로
            photo_path = os.path.join(upload_folder, unique_filename)
            photo.save(photo_path)  # 사진 저장

            return unique_filename  # DB 저장용 파일명
        return None