from datetime import datetime, timedelta
from openpyxl import Workbook
import openpyxl    
from flask import Blueprint, render_template, request, url_for, g , flash, jsonify
from werkzeug.utils import redirect
from pybo import db  # .. import db로 되어있는데, pybo로 변경
from ..forms import QuestionForm, AnswerForm
from sqlalchemy import func
from ..models import Question, Answer, User, QuestionVoter, WaterUsage,ElecUsage,VehicleUsage,Co2Management,Stockinfo, StockListFromVB

from pybo.views.auth_views import login_required


from ..service.k_trade import KTrade
from ..service.k_analysis import KAnalysis
from ..service.k_value import KValue
from ..service.k_realdata import RealTimeData,RealData
from ..service.k_db_trade import KDatabaseTrade
from ..service.k_func import KFunction
from collections import Counter 


import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode





class Co2Cal:
    @staticmethod
    def update_elec():
        # 모든 ElecUsage 레코드를 가져옵니다.
        elec_usages = ElecUsage.query.all()
        
        for elec_usage in elec_usages:
            # 필요한 경우 값을 정수로 변환
            acum_ref = int(elec_usage.acum_ref)
            acum_jan = int(elec_usage.acum_jan or 0)
            acum_feb = int(elec_usage.acum_feb or 0)
            acum_mar = int(elec_usage.acum_mar or 0)
            acum_apr = int(elec_usage.acum_apr or 0)
            acum_may = int(elec_usage.acum_may or 0)
            acum_jun = int(elec_usage.acum_jun or 0)
            acum_jul = int(elec_usage.acum_jul or 0)
            acum_aug = int(elec_usage.acum_aug or 0)
            acum_sep = int(elec_usage.acum_sep or 0)
            acum_oct = int(elec_usage.acum_oct or 0)
            acum_nov = int(elec_usage.acum_nov or 0)
            acum_dec = int(elec_usage.acum_dec or 0)

            # 사용량 계산
            use_jan = acum_jan - acum_ref if acum_jan > 0 else 0
            use_feb = acum_feb - acum_jan if acum_feb > acum_jan else 0
            use_mar = acum_mar - acum_feb if acum_mar > acum_feb else 0
            use_apr = acum_apr - acum_mar if acum_apr > acum_mar else 0
            use_may = acum_may - acum_apr if acum_may > acum_apr else 0
            use_jun = acum_jun - acum_may if acum_jun > acum_may else 0
            use_jul = acum_jul - acum_jun if acum_jul > acum_jun else 0
            use_aug = acum_aug - acum_jul if acum_aug > acum_jul else 0
            use_sep = acum_sep - acum_aug if acum_sep > acum_aug else 0
            use_oct = acum_oct - acum_sep if acum_oct > acum_sep else 0
            use_nov = acum_nov - acum_oct if acum_nov > acum_oct else 0
            use_dec = acum_dec - acum_nov if acum_dec > acum_nov else 0

            # 총 사용량 계산
            total = sum([
                use_jan, use_feb, use_mar, use_apr, use_may,
                use_jun, use_jul, use_aug, use_sep,
                use_oct, use_nov, use_dec
            ])

            # 업데이트된 값들로 데이터베이스 레코드 수정
            elec_usage.use_jan = use_jan
            elec_usage.use_feb = use_feb
            elec_usage.use_mar = use_mar
            elec_usage.use_apr = use_apr
            elec_usage.use_may = use_may
            elec_usage.use_jun = use_jun
            elec_usage.use_jul = use_jul
            elec_usage.use_aug = use_aug
            elec_usage.use_sep = use_sep
            elec_usage.use_oct = use_oct
            elec_usage.use_nov = use_nov
            elec_usage.use_dec = use_dec
            elec_usage.total = total

            # 수정 날짜 갱신
            elec_usage.modify_date = datetime.utcnow()

        # 데이터베이스에 저장
        db.session.commit()


########################### 업데이트 -- water ###################################3333
    @staticmethod
    def update_water():
       
        water_usages = WaterUsage.query.all()
        
        for water_usage in water_usages:
            # 필요한 경우 값을 정수로 변환
            acum_ref = int(water_usage.acum_ref)
            acum_jan = int(water_usage.acum_jan or 0)
            acum_feb = int(water_usage.acum_feb or 0)
            acum_mar = int(water_usage.acum_mar or 0)
            acum_apr = int(water_usage.acum_apr or 0)
            acum_may = int(water_usage.acum_may or 0)
            acum_jun = int(water_usage.acum_jun or 0)
            acum_jul = int(water_usage.acum_jul or 0)
            acum_aug = int(water_usage.acum_aug or 0)
            acum_sep = int(water_usage.acum_sep or 0)
            acum_oct = int(water_usage.acum_oct or 0)
            acum_nov = int(water_usage.acum_nov or 0)
            acum_dec = int(water_usage.acum_dec or 0)

            # 사용량 계산
            use_jan = acum_jan - acum_ref if acum_jan > 0 else 0
            use_feb = acum_feb - acum_jan if acum_feb > acum_jan else 0
            use_mar = acum_mar - acum_feb if acum_mar > acum_feb else 0
            use_apr = acum_apr - acum_mar if acum_apr > acum_mar else 0
            use_may = acum_may - acum_apr if acum_may > acum_apr else 0
            use_jun = acum_jun - acum_may if acum_jun > acum_may else 0
            use_jul = acum_jul - acum_jun if acum_jul > acum_jun else 0
            use_aug = acum_aug - acum_jul if acum_aug > acum_jul else 0
            use_sep = acum_sep - acum_aug if acum_sep > acum_aug else 0
            use_oct = acum_oct - acum_sep if acum_oct > acum_sep else 0
            use_nov = acum_nov - acum_oct if acum_nov > acum_oct else 0
            use_dec = acum_dec - acum_nov if acum_dec > acum_nov else 0

            # 총 사용량 계산
            total = sum([
                use_jan, use_feb, use_mar, use_apr, use_may,
                use_jun, use_jul, use_aug, use_sep,
                use_oct, use_nov, use_dec
            ])

            # 업데이트된 값들로 데이터베이스 레코드 수정
            water_usage.use_jan = use_jan
            water_usage.use_feb = use_feb
            water_usage.use_mar = use_mar
            water_usage.use_apr = use_apr
            water_usage.use_may = use_may
            water_usage.use_jun = use_jun
            water_usage.use_jul = use_jul
            water_usage.use_aug = use_aug
            water_usage.use_sep = use_sep
            water_usage.use_oct = use_oct
            water_usage.use_nov = use_nov
            water_usage.use_dec = use_dec
            water_usage.total = total

            # 수정 날짜 갱신
            water_usage.modify_date = datetime.utcnow()

        # 데이터베이스에 저장
        db.session.commit()


########################### 업데이트 -- Vehicle ###################################3333
    @staticmethod
    def update_vehicle():
       
        vehicle_usages =  VehicleUsage.query.all()
        
        for vehicle_usage in vehicle_usages:
            # 필요한 경우 값을 정수로 변환
            acum_ref = int(vehicle_usage.acum_ref)
            acum_jan = int(vehicle_usage.acum_jan or 0)
            acum_feb = int(vehicle_usage.acum_feb or 0)
            acum_mar = int(vehicle_usage.acum_mar or 0)
            acum_apr = int(vehicle_usage.acum_apr or 0)
            acum_may = int(vehicle_usage.acum_may or 0)
            acum_jun = int(vehicle_usage.acum_jun or 0)
            acum_jul = int(vehicle_usage.acum_jul or 0)
            acum_aug = int(vehicle_usage.acum_aug or 0)
            acum_sep = int(vehicle_usage.acum_sep or 0)
            acum_oct = int(vehicle_usage.acum_oct or 0)
            acum_nov = int(vehicle_usage.acum_nov or 0)
            acum_dec = int(vehicle_usage.acum_dec or 0)

            # 사용량 계산
            use_jan = acum_jan - acum_ref if acum_jan > 0 else 0
            use_feb = acum_feb - acum_jan if acum_feb > acum_jan else 0
            use_mar = acum_mar - acum_feb if acum_mar > acum_feb else 0
            use_apr = acum_apr - acum_mar if acum_apr > acum_mar else 0
            use_may = acum_may - acum_apr if acum_may > acum_apr else 0
            use_jun = acum_jun - acum_may if acum_jun > acum_may else 0
            use_jul = acum_jul - acum_jun if acum_jul > acum_jun else 0
            use_aug = acum_aug - acum_jul if acum_aug > acum_jul else 0
            use_sep = acum_sep - acum_aug if acum_sep > acum_aug else 0
            use_oct = acum_oct - acum_sep if acum_oct > acum_sep else 0
            use_nov = acum_nov - acum_oct if acum_nov > acum_oct else 0
            use_dec = acum_dec - acum_nov if acum_dec > acum_nov else 0

            # 총 사용량 계산
            total = sum([
                use_jan, use_feb, use_mar, use_apr, use_may,
                use_jun, use_jul, use_aug, use_sep,
                use_oct, use_nov, use_dec
            ])

            # 업데이트된 값들로 데이터베이스 레코드 수정
            vehicle_usage.use_jan = use_jan
            vehicle_usage.use_feb = use_feb
            vehicle_usage.use_mar = use_mar
            vehicle_usage.use_apr = use_apr
            vehicle_usage.use_may = use_may
            vehicle_usage.use_jun = use_jun
            vehicle_usage.use_jul = use_jul
            vehicle_usage.use_aug = use_aug
            vehicle_usage.use_sep = use_sep
            vehicle_usage.use_oct = use_oct
            vehicle_usage.use_nov = use_nov
            vehicle_usage.use_dec = use_dec
            vehicle_usage.total = total

            # 수정 날짜 갱신
            vehicle_usage.modify_date = datetime.utcnow()

        # 데이터베이스에 저장
        db.session.commit()

####################### CO2 데이터 업데이트 #######################################33
    @staticmethod
    def sum_update():
        # 각 사용량 테이블의 모든 레코드를 가져옵니다.
        water_list = WaterUsage.query.order_by(WaterUsage.no).all()
        elec_list = ElecUsage.query.order_by(ElecUsage.no).all()
        vehicle_list = VehicleUsage.query.order_by(VehicleUsage.no).all()

        # 월별 사용량 합계 계산
        total_use_jan_water = sum([int(item.use_jan) for item in water_list])
        total_use_feb_water = sum([int(item.use_feb) for item in water_list])
        total_use_mar_water = sum([int(item.use_mar) for item in water_list])
        total_use_apr_water = sum([int(item.use_apr) for item in water_list])
        total_use_may_water = sum([int(item.use_may) for item in water_list])
        total_use_jun_water = sum([int(item.use_jun) for item in water_list])
        total_use_jul_water = sum([int(item.use_jul) for item in water_list])
        total_use_aug_water = sum([int(item.use_aug) for item in water_list])
        total_use_sep_water = sum([int(item.use_sep) for item in water_list])
        total_use_oct_water = sum([int(item.use_oct) for item in water_list])
        total_use_nov_water = sum([int(item.use_nov) for item in water_list])
        total_use_dec_water = sum([int(item.use_dec) for item in water_list])

        total_use_jan_elec = sum([int(item.use_jan) for item in elec_list])
        total_use_feb_elec = sum([int(item.use_feb) for item in elec_list])
        total_use_mar_elec = sum([int(item.use_mar) for item in elec_list])
        total_use_apr_elec = sum([int(item.use_apr) for item in elec_list])
        total_use_may_elec = sum([int(item.use_may) for item in elec_list])
        total_use_jun_elec = sum([int(item.use_jun) for item in elec_list])
        total_use_jul_elec = sum([int(item.use_jul) for item in elec_list])
        total_use_aug_elec = sum([int(item.use_aug) for item in elec_list])
        total_use_sep_elec = sum([int(item.use_sep) for item in elec_list])
        total_use_oct_elec = sum([int(item.use_oct) for item in elec_list])
        total_use_nov_elec = sum([int(item.use_nov) for item in elec_list])
        total_use_dec_elec = sum([int(item.use_dec) for item in elec_list])

        total_use_jan_vehicle = sum([int(item.use_jan) for item in vehicle_list])
        total_use_feb_vehicle = sum([int(item.use_feb) for item in vehicle_list])
        total_use_mar_vehicle = sum([int(item.use_mar) for item in vehicle_list])
        total_use_apr_vehicle = sum([int(item.use_apr) for item in vehicle_list])
        total_use_may_vehicle = sum([int(item.use_may) for item in vehicle_list])
        total_use_jun_vehicle = sum([int(item.use_jun) for item in vehicle_list])
        total_use_jul_vehicle = sum([int(item.use_jul) for item in vehicle_list])
        total_use_aug_vehicle = sum([int(item.use_aug) for item in vehicle_list])
        total_use_sep_vehicle = sum([int(item.use_sep) for item in vehicle_list])
        total_use_oct_vehicle = sum([int(item.use_oct) for item in vehicle_list])
        total_use_nov_vehicle = sum([int(item.use_nov) for item in vehicle_list])
        total_use_dec_vehicle = sum([int(item.use_dec) for item in vehicle_list])

        print( total_use_jan_elec)
        
        # 모든 데이터 삭제
        db.session.query(Co2Management).delete()

        # 월별 이름 리스트
        months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

        # 월별 데이터를 저장하기 위한 루프
        for i, month in enumerate(months):
            # 각 월별 사용량과 CO2 계산
            total_use_elec = locals()[f"total_use_{month}_elec"]
            total_use_water = locals()[f"total_use_{month}_water"]
            total_use_vehicle = locals()[f"total_use_{month}_vehicle"]

            co2_elec = round(total_use_elec * 0.4781, 3)
            co2_water = round(total_use_water * 0.234, 3)
            co2_vehicle = round(total_use_vehicle / 15.35 * 2.582, 3)

            total_co2 = round(co2_elec + co2_water + co2_vehicle, 3)
           
          

            # Co2Management 레코드 생성
            new_co2_management = Co2Management(
                use_date=datetime.utcnow().strftime(f'%Y-{i+1:02}'),  # 월을 01, 02, ... 12 형식으로
                use_elec=str(total_use_elec),
                co2_elec=co2_elec,
                use_water=str(total_use_water),
                co2_water=co2_water,
                use_vehicle=str(total_use_vehicle),
                co2_vehicle=co2_vehicle,
                use_total=str(total_co2),
                co2_waste=None,  # 아직 사용하지 않는 필드
                use_waste=None,  # 아직 사용하지 않는 필드
                co2_gas=None,    # 아직 사용하지 않는 필드
                use_gas=None,    # 아직 사용하지 않는 필드
                create_date=datetime.utcnow(),
                modify_date=None
            )

            # 데이터베이스에 저장
            db.session.add(new_co2_management)

        # 모든 레코드를 커밋
        db.session.commit()