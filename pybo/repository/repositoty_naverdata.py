from .. import db
from ..models import Question, Answer, QuestionVoter,  AnswerVoter, YoutubeURL, ImageData, NewsData, BlogData #table 이름
from sqlalchemy.exc import SQLAlchemyError
from pybo import db  # .. import db로 되어있는데, pybo로 변경
from datetime import datetime


class RepositoryNaverData:

############################  image ###############################
    def insert_image_data(star_name, type_image, json_file, json_data):
    
        # 새로운 데이터 생성
        naver_data = ImageData (
            star_name=star_name,
            type_image=type_image,
            json_file=json_file,
            title_image = json_data["title"],
            thumbnail = json_data["thumbnail"],
            url=json_data["link"],
            sizeweight=json_data["sizeweight"],
            sizeheight=json_data["sizeheight"],
            update_date=json_data["pDate"],
            create_date=datetime.now(),  # 현재 시간으로 생성 날짜 설정
            modify_date=None  # 초기에는 None으로 설정
        )
        
        try:
            # 데이터베이스에 추가
            db.session.add(naver_data)
            db.session.commit()
            return {
                "status": "success",
                "message": "Data inserted successfully",
                "data": {
                    "star_name": star_name,
                    "type_video": type_image,
                    "url": json_data["url"]
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

    def read_image_data(star_name=None, type_video=None):
        """
        조건에 따라 YouTube URL 데이터를 조회하는 함수.

        Args:
            star_name (str, optional): 조회할 스타 이름. 기본값은 None.
            type_video (str, optional): 조회할 동영상 유형. 기본값은 None.

        Returns:
            list: 조회된 데이터 리스트
        """
        try:
            query = db.session.query(ImageData)

            if star_name is not None and type_video is None:
                query = query.filter_by(star_name=star_name)

            elif star_name is None and type_video is None:
                pass  # 모든 데이터를 조회

            elif star_name is not None and type_video is not None:
                query = query.filter_by(star_name=star_name, type_video=type_video)

            result = query.all()

            return [
                {
                    "star_name": record.star_name,
                    "type_image": record.type_image,
                    "title_image": record.title_image,
                    "json_file" : record.json_file,
                    "thumbnail " : record.thumbnail,
                    "url": record.url,                  
                    "sizeweight": record.sizeweight,
                    "sizeheight": record.sizeheight,
                    "update_date": record.update_date,
                    "create_date": record.create_date
                }
                for record in result
            ]
                

        except SQLAlchemyError as e:
            error_message = str(e.__dict__.get('orig', e))
            return {
                "status": "error",
                "message": f"Failed to read data: {error_message}"
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