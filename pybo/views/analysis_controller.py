from datetime import datetime, timedelta
from openpyxl import Workbook
import openpyxl    
import asyncio
import time
import pandas as pd
#from aioflask import Flask, request, jsonify, Blueprint, render_template,url_for
from flask import Flask, request, jsonify, Blueprint, render_template,url_for
from werkzeug.utils import redirect
from ..models import Stockinfo,Chartinfo, StockinfoTemp,Token_temp,ObserveStock, StockListFromVB, ObserveStockFromVB, DailyDataFromVB, StockListFromKInvestor,ThemeCode,RankTrade
import json
from .. import db
from sqlalchemy import func, desc, and_ 
# from flask_sqlalchemy import pagination
from sqlalchemy.orm import aliased
from ..service.k_trade import KTrade
from ..service.k_analysis import KAnalysis
from ..service.k_value import KValue
from ..service.k_analysis import KAnalysis
from ..service.k_realdata import RealTimeData,RealData
from ..service.k_db_trade import KDatabaseTrade
from collections import Counter 
from .stock_controller import call_token, call_token_mock


import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

# bp = Flask(__name__)

bp = Blueprint('kanalysis',__name__,url_prefix='/kanalysis')

# 현재 실행 중인 연결 객체
current_connection = None

# approvalkey와 token 얻기


@bp.route('/mindata')
def min_data():
    page = request.args.get('page', type=int, default=1) #페이지
    kw = request.args.get('kw',type=str, default='')
    so = request.args.get('so', type=str, default='recent')
    stock_code = request.args.get('stockcode',type=str, default='')
    
    ka = KValue
    # #조회
    # 토근 DB로 부터 호출
    # token = Token_temp.query.first()
    # static_token = token.token_key
    static_token = call_token()
    static_token_mock = call_token_mock()
    return_val = 'all'

     # 현재 날짜와 시간을 datetime 객체로 얻어옵니다.
    today_date = datetime.now()

    # datetime 객체를 원하는 형식의 문자열로 변환합니다.
    today_date_str = today_date.strftime("%Y%m%d")

    # 문자열을 datetime 객체로 다시 변환합니다. 필요한 경우에만 사용합니다.
    today_date_dt = datetime.strptime(today_date_str, "%Y%m%d")

    # 현재 날짜에서 하루를 빼어 어제의 날짜를 구합니다. 
    yesterday_date = today_date_dt - timedelta(days=0)

    current_time_str = today_date.strftime("%H%M") + '00'
    print('현재시간:', current_time_str)

    # 어제의 날짜를 원하는 형식의 문자열로 변환합니다.
    ydate = yesterday_date.strftime("%Y%m%d")
    print(ydate)

    data_min = KValue.mindata(stock_code,static_token_mock,current_time_str)
    print(data_min)

    return jsonify(data_min)

# 종목 코드 조회   
@bp.route('/tradevol/')
def trade_vol():
    #입력파라메터
    page = request.args.get('page', type=int, default=1) #페이지
    kw = request.args.get('kw',type=str, default='')
    so = request.args.get('so', type=str, default='recent')

    # #조회
    # 토근 DB로 부터 호출
    # token = Token_temp.query.first()
    # static_token = token.token_key
    static_token = call_token()
    static_token_mock = call_token_mock()
    return_val = 'all'

    # 데이터 불러오기
    json_data = KAnalysis.trade_volume(static_token)
    dic_data = json.loads(json_data)
    tradevolumes = dic_data["output"]

    # balance_stock 불러오기
    balance_stock = KDatabaseTrade.remainder_lists(static_token_mock, '0', return_val)
    balance_stock_codes = [stock.stockcode for stock in balance_stock]

    #daily_Data 불러오기
    daily_data = DailyDataFromVB.query.order_by(DailyDataFromVB.stockdate.desc()).all()
    daily_stock_code = [(stock.stockcode, stock.selected1, stock.selected2,stock.selecteddate,stock.stockdate)for stock in daily_data]

    print("스탁리스트", json_data)

        #기존 DB값 삭제
    RankTrade.query.delete()
    db.session.commit()
   
    # Chartinfo 객체 생성 및 속성 채우기
    for tradevol in tradevolumes:
        stock_code = tradevol['mksc_shrn_iscd']
        # 현재 tradevol의 stockcode가 balance_stock의 stockcode 리스트에 있는지 확인
        if stock_code in balance_stock_codes:
            in_buy_list_value = '1'
        else:
            in_buy_list_value = '0'
        
        # daily_stock_code 확인
        
        # daily_stock_code 확인
        in_ob_list = '0'
        selected1 = '0'
        selected2 = '0'
        selectdate = '20000101'
        stock_date = '20000101'
        
        
        for code, sel1, sel2, seldate, sdate in daily_stock_code:
            if stock_code == code:
                in_ob_list = '1'
                selected1 = sel1
                selected2 = sel2
                selectdate = seldate
                stock_date = sdate
                break



        ranktrade = RankTrade(
            stockcode= stock_code,
            stockname=tradevol['hts_kor_isnm'],

            rank =tradevol['data_rank'],#데이터 순위
            currentvalue =tradevol['stck_prpr'],
            tradeval =tradevol['acml_vol'], #현재 거래량

            sign  =tradevol['prdy_vrss_sign'] ,#전일 대비 부호
            diffrate  =tradevol['prdy_ctrt'], #등락률
            diffval =tradevol['prdy_vrss'], #전일대비 
            pre_tradeval =tradevol['prdy_vol'], #전일거래량
            stockvol =tradevol['lstn_stcn'], #상장주수
            #tvol_vsprevious =tradevol['prdy_vrss_vol'], # 전일대비 거래량
            #aceval =tradevol['stck_fcam'], #액면가

            avg_vol =tradevol['avrg_vol'], #평균 거래량
            nday_prpr_rate =tradevol['n_befr_clpr_vrss_prpr_rate'], #N일전종가대비현재가대비율
            vol_incr =tradevol['vol_inrt'], #거래량증가율
            vol_tnrt =tradevol['vol_tnrt'] ,# 거래량 회전율
            nday_vol_tnrt =tradevol['nday_vol_tnrt'], #N일 거래량 회전율
            avg_tr_pbmn =tradevol['avrg_tr_pbmn'], # 	평균 거래 대금
            tr_pbmn_tnrt=tradevol['tr_pbmn_tnrt'], # 거래대금회전율
            nday_tr_pbmn_tnrt =tradevol['nday_tr_pbmn_tnrt'], # N일 거래대금 회전율
            acml_tr_pbmn =tradevol['acml_tr_pbmn'], # 	누적 거래 대금
            in_buy_list=in_buy_list_value,


            in_observe_list = in_ob_list,
            stockdate = stock_date,
            selected_1 = selected1,
            selected_2 = selected2,
            selecteddate = selectdate
        )

        # 데이터베이스에 저장
        db.session.add(ranktrade)

    # 커밋하여 변경 사항 저장
    db.session.commit()


    # 조회
    rank_trade = RankTrade.query.order_by(RankTrade.rank.asc())
    
    if kw:
            search = f'%{kw}%'
            stock_list = rank_trade.filter(
                (RankTrade.stockcode.ilike(search)) |  # 주식 코드
                (RankTrade.stockname.ilike(search))    # 주식 이름
            ).paginate(page=page, per_page=10)  # 페이징
    else:
        stock_list = rank_trade.paginate(page=page, per_page=10)  # 페이징만 적용

    return render_template('ranking/trade_volume.html', stock_list=stock_list, page=page, kw=kw)

