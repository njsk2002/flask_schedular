# repository/repositoty_naverdata.py

from pybo import db
from ..models import ImageData
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func  
from datetime import datetime


class RepositoryNaverData:

    @staticmethod
    def insert_image_data(key_word, type_image, json_file, json_data):
        """
        ImageData 1건 insert. 실패 시 상세 오류 반환.
        - 모델의 create_date/modify_date는 models.py 기본값(KST) 사용을 권장하지만,
          여기에 명시적으로 넣어도 무방합니다.
        """
        try:
            image_data = ImageData(
                key_word=key_word,
                type_image=type_image,
                json_file=json_file,
                title_image=json_data["title"],
                thumbnail=json_data["thumbnail"],
                url=json_data["link"],
                bmp_42_mono=json_data.get('bmp_42_mono'),
                bmp_42_3color=json_data.get('bmp_42_3color'),
                bmp_37_4color=json_data.get('bmp_37_4color'),
                # 모델에 bmp_29_mono / bmp_29_3color 컬럼은 있지만 값이 없으면 NULL로 둡니다.
                bmp_29_4color=json_data.get('bmp_29_4color'),
                sizewidth=json_data["sizewidth"],
                sizeheight=json_data["sizeheight"],
                update_date=json_data["pDate"],
                # create_date, modify_date: 모델 기본값(kst_now_naive) 사용
            )
            db.session.add(image_data)
            db.session.commit()

            return {
                "status": "success",
                "message": "Data inserted successfully",
                "data": {"key_word": key_word, "type_image": type_image, "url": json_data["link"]}
            }

        except SQLAlchemyError as e:
            db.session.rollback()
            err = str(e.__dict__.get('orig', e))
            print("[DB ERROR] insert_image_data:", err)
            return {"status": "error", "message": f"Failed to insert data: {err}"}

    @staticmethod
    def read_image_data(key_word=None, type_image=None, page=1, per_page=10):
        """
        조건에 따라 ImageData 조회 + 페이지네이션 + key_word별 대표 URL 리스트 제공
        """
        print("key_word:", key_word, "type_image:", type_image)
        try:
            base_query = db.session.query(ImageData)

            # 필터 구성
            if key_word is not None and type_image is None:
                base_data = base_query.filter_by(key_word=key_word)
            elif key_word is None and type_image is not None:
                base_data = base_query.filter_by(type_image=type_image)
            elif key_word is not None and type_image is not None:
                base_data = base_query.filter_by(key_word=key_word, type_image=type_image)
            else:
                base_data = base_query

            # ✅ key_word 그룹별 첫 레코드 URL(대표 URL)
            subq = base_query.with_entities(
                ImageData.key_word, func.min(ImageData.id).label("min_id")
            ).group_by(ImageData.key_word).subquery()

            unique_keys_with_url = db.session.query(
                ImageData.key_word, ImageData.url
            ).join(subq, ImageData.id == subq.c.min_id).all()

            unique_key = [{"key_word": row[0], "url": row[1]} for row in unique_keys_with_url]

            # 페이지네이션
            result = (
                base_data
                .order_by(ImageData.id.desc())  # ✅ 최신순 정렬(원하면 변경)
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )

            total_count = base_query.count()

            return {
                "data": [
                    {
                        "key_word": record.key_word,
                        "type_image": record.type_image,
                        "title_image": record.title_image,
                        "json_file": record.json_file,
                        "thumbnail": record.thumbnail,
                        "bmp_42_mono": record.bmp_42_mono,
                        "bmp_42_3color": record.bmp_42_3color,
                        "bmp_37_4color": record.bmp_37_4color,
                        "bmp_29_4color": record.bmp_29_4color,
                        "url": record.url,
                        "sizewidth": record.sizewidth,
                        "sizeheight": record.sizeheight,
                        "update_date": record.update_date,
                        "create_date": record.create_date,
                    }
                    for record in result
                ],
                "total_count": total_count,
                "unique_key": unique_key
            }
        except Exception as e:
            print("[ERROR] read_image_data 오류:", e)
            return {
                "data": [],
                "message": "데이터를 불러오는 중 오류가 발생했습니다.",
                "has_more": False,
                "unique_key": []
            }

    @staticmethod
    def check_duplication_data(url=None, update_date=None):
        """
        ImageData 중복 체크.
        - url만으로 체크하거나, url + update_date로 더 엄격히 체크 가능.
        반환: True(중복 아님, 삽입해도 됨) / False(중복됨)
        """
        try:
            query = db.session.query(ImageData)

            if url is not None and update_date is None:
                existing = query.filter_by(url=url).first()
            elif url is not None and update_date is not None:
                existing = query.filter_by(url=url, update_date=update_date).first()
            else:
                # url이 없으면 중복 판별 의미가 없으므로 False(삽입 보류)로 처리하는 게 안전
                return False

            return existing is None

        except SQLAlchemyError as e:
            err = str(e.__dict__.get('orig', e))
            print("[DB ERROR] check_duplication_data:", err)
            # 중복 판별 실패 시 보수적으로 False 리턴
            return False
