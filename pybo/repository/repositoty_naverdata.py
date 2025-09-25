from .. import db
from ..models import Question, Answer, QuestionVoter,  AnswerVoter, YoutubeURL, ImageData, NewsData, BlogData #table 이름
from sqlalchemy.exc import SQLAlchemyError
from pybo import db  # .. import db로 되어있는데, pybo로 변경
from datetime import datetime
from sqlalchemy import func


class RepositoryNaverData:

############################  image ###############################
    def insert_image_data(key_word, type_image, json_file, json_data):
    
        # 새로운 데이터 생성
        image_data = ImageData (
            key_word=key_word,
            type_image=type_image,
            json_file=json_file,
            title_image = json_data["title"],
            thumbnail = json_data["thumbnail"],
            url=json_data["link"],
            bmp_42_mono = json_data['bmp_42_mono'],
            bmp_42_3color = json_data['bmp_42_3color'],
            bmp_37_4color = json_data['bmp_37_4color'],
            # bmp_29_mono = json_data['bmp_37_4color'],
            # bmp_29_3color = json_data['bmp_37_4color'],
            bmp_29_4color = json_data['bmp_29_4color'],
            sizewidth=json_data["sizewidth"],
            sizeheight=json_data["sizeheight"],
            update_date=json_data["pDate"],
            create_date=datetime.now(),  # 현재 시간으로 생성 날짜 설정
            modify_date=None  # 초기에는 None으로 설정
        )
        
        try:
            # 데이터베이스에 추가
            db.session.add(image_data)
            db.session.commit()
            return {
                "status": "success",
                "message": "Data inserted successfully",
                "data": {
                    "key_word": key_word,
                    "type_image": type_image,
                    "url": json_data["link"]
                }
            }
        except SQLAlchemyError as e:
            # 예외 처리 및 롤백
            db.session.rollback()
            error_message = str(e.__dict__.get('orig', e))
            return {
                "status": "error",
                "message": f"Failed to insert data: {error_message}"
            }

    def read_image_data(key_word=None, type_image=None, page=1, per_page=10):
        """
        조건에 따라 YouTube URL 데이터를 조회하는 함수.

        Args:
            key_word (str, optional): 조회할 스타 이름. 기본값은 None.
            type_image (str, optional): 조회할 이미지 유형. 기본값은 None.
            page (int): 현재 페이지 번호.
            per_page (int): 한 페이지에 표시할 항목 수.

        Returns:
            dict: 조회된 데이터 리스트와 전체 데이터 개수
        """
        print("key_word: ", key_word,"type_image: ", type_image)
        try:
            # base_query에 조건 적용
            base_query = db.session.query(ImageData)
            if key_word is not None and type_image is None:
                base_data = base_query.filter_by(key_word=key_word)
            elif key_word is None and type_image is not None:
                base_data = base_query.filter_by(type_image=type_image)
            elif key_word is not None and type_image is not None:
                base_data = base_query.filter_by(key_word=key_word, type_image=type_image)
            else :
                base_data = base_query

            # 서브쿼리를 이용하여 각 key_word 그룹에서 최소 id를 찾음 (첫번째 row)
            subq = base_query.with_entities(
                ImageData.key_word, func.min(ImageData.id).label("min_id")
            ).group_by(ImageData.key_word).subquery()

            # 서브쿼리의 min_id에 해당하는 레코드의 key_word와 url을 join하여 가져옴
            unique_keys_with_url = db.session.query(
                ImageData.key_word, ImageData.url
            ).join(subq, ImageData.id == subq.c.min_id).all()

            # 결과를 딕셔너리 리스트로 변환
            unique_key = [{"key_word": row[0], "url": row[1]} for row in unique_keys_with_url]

            # 페이지네이션 처리: 필요한 데이터만 가져오기
            result = base_data.offset((page - 1) * per_page).limit(per_page).all()

            # 전체 개수 계산
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
            print("[ERROR] 오류 발생:", e)
            return {
                "data": [],
                "message": "데이터를 불러오는 중 오류가 발생했습니다.",
                "has_more": False,
                "unique_key": []
            }




    # 중복체크 
    def check_duplication_data(url=None, update_date=None):
            """
            조건에 따라 YouTube URL 데이터를 조회하는 함수.

            Args:
                url  (str, optional): 조회할 스타 이름. 기본값은 None.
                update_date (str, optional): 조회할 동영상 유형. 기본값은 None.

            Returns:
                list: 조회된 데이터 리스트
            """
            try:
                query = db.session.query(ImageData)

                if url is not None and update_date is None:
                    query = query.filter_by(url = url).first()

                elif url is None and update_date is None:
                    pass  # 모든 데이터를 조회

                elif url is not None and update_date is not None:
                    query = query.filter_by(url = url, update_date = update_date).first()

                if not query: # 중복 안됨
                    return True
                
                return False # 중복 됨 
    

            except SQLAlchemyError as e:
                error_message = str(e.__dict__.get('orig', e))
                return {
                    "status": "error",
                    "message": f"Failed to read data: {error_message}"
                }