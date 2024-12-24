from datetime import datetime, timedelta
from openpyxl import Workbook
import openpyxl    
import asyncio
import time
import pandas as pd
#from aioflask import Flask, request, jsonify, Blueprint, render_template,url_for
from flask import Flask, request, jsonify, Blueprint, render_template,url_for
from werkzeug.utils import redirect
from ..models import Stockinfo, Chartinfo, StockinfoTemp, Token_temp, ObserveStock, StockListFromVB, ObserveStockFromVB, StockBalanceLists,DailyDataFromVB,DailyTrade
import json
from .. import db
from sqlalchemy import func, or_, and_ , delete
from ..service.k_trade import KTrade
from ..service.k_analysis import KAnalysis
from ..service.k_value import KValue
from ..service.k_realdata import RealTimeData,RealData
from ..service.k_trade_func import KTradeFunc
from ..service.k_db_trade import KDatabaseTrade
from ..service.k_func import KFunction
from .stock_controller import call_token, call_token_mock
from collections import defaultdict

import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

# bp = Flask(__name__)

bp = Blueprint('ktrade',__name__,url_prefix='/ktrade')

# 현재 실행 중인 연결 객체
current_connection = None

#========================================================================================#
# 주식 매수 (메뉴얼 -- 웹페이지에서 버튼 누르는 방식)
#=========================================================================================#
@bp.route('/buyrun', methods = ['GET','POST'])
def buy_run():
    kt = KTrade()
    kv = KValue()
    kr = RealTimeData()
    kd = RealData()
    kf = KTradeFunc()

    # 매수 금액
    assigned_price = '2500000'

    # 입력파라메터
    page = request.args.get('page', type=int, default=1)  # 페이지
    kw = request.args.get('kw', type=str, default='')
    so = request.args.get('so', type=str, default='recent')
    r_method = request.args.get('r_method', type=str, default='continue')
    s_no = request.args.get('no', type=str, default='')
    method_type = request.args.get('type', type=str, default='observe')
    minus_time = request.args.get('time', type=int, default=0)

    select = 'buy'
    return_val = 'all' #all: 매수 후 잔고 확인시 db 업데이트 후 모든 항목 return ,
    if request.method == 'POST':
        print('POST')
    else:
       
        # 오늘,어제, 현재시간(6자리),현재시간(hhmm00 분봉용) 호출 6자리()
        todate,ydate,totime,totime00 = KFunction.date_info(minus_time)   

        trade_type = 'mock'  # mock : 모의투자 , real : 실투자
        # SQLAlchemy ORM을 사용하여 데이터베이스에서 데이터를 가져옵니다.
        
       # stocklists = ObserveStockFromVB.query.filter_by(stockdate=ydate)
        # 일반적으로 쓰는것..잠시 홀딩
        if method_type == 'observe': # 매수 대기 항목 매수(추가매수시)
            if s_no:
                stockcodes = db.session.query(ObserveStockFromVB.stockcode).filter(
                    ObserveStockFromVB.method_1 == '1',
                    ObserveStockFromVB.selecteddate == ydate,
                    ObserveStockFromVB.no == s_no
                ).all()
            else:
                stockcodes = db.session.query(ObserveStockFromVB.stockcode).filter(
                    ObserveStockFromVB.method_1 == '1',
                    ObserveStockFromVB.selecteddate == ydate
                ).all()
        elif method_type == 'remain':  # 보유 항목 추가 매수시
            if s_no:
                stockcodes = db.session.query(StockBalanceLists.stockcode).filter(
                    StockBalanceLists.no == s_no
                ).all()
            else:
                stockcodes = db.session.query(StockBalanceLists.stockcode).all()

        #stockcodes = db.session.query(DailyDataFromVB.stockcode).filter(DailyDataFromVB.selected1 == '1').all()
        print(stockcodes)
        # tuple로 반환

        #토근 호출 
        #static_token = call_token_mock()
        
        # if omethod == '00':
        #     ordermethod = "VTTC0802U"
        # elif omethod =='11':
        #     ordermethod = "VTTC0801U"
        #매수/매도 함수 호출
        #result = kt. order(stockcode,buyqty,buyprice, static_token,ordermethod)
    
        #토근 호출 
        static_token = call_token_mock()
        #for stockcode in stockcodes:
        loop_buy = False
        for count, stockcode in enumerate(stockcodes, start=1): #카운트추가
            #print(stockcode[0])
            #if count >1 and count <=11:
                loop_buy = True
                while loop_buy:
                    print(stockcode[0],static_token, ydate, '0')
                    #time.sleep(0.5)
                    result = KDatabaseTrade.remainder_qty(stockcode[0],static_token, ydate, '0', method_type)

                    if result == loop_buy:
                        #time.sleep(0.5)
                        c_data = KValue.current_value(stockcode,static_token)
                        if c_data != None:
                            print("C_DATA =", c_data)
                            if int(c_data.get('acml_vol')) > 1000:
                                #time.sleep(0.5)
                                #매수 주문
                                order_no,buy_qty,price_buy = kf.trade_buy(assigned_price,stockcode[0],static_token)
                                print("오더넘버", order_no, "매수주문수량 ", buy_qty )
                                if order_no != "0":
                                    print('osfv 입력', stockcode[0],order_no,buy_qty,price_buy,ydate,method_type)
                                    order_no,init_qty,remain_qty,buy_qty,price_buy =  KDatabaseTrade.osfv_db(stockcode[0],order_no,buy_qty,price_buy,ydate,method_type)
                                    
                                    print("주문번호=",stockcode[0], order_no,init_qty,remain_qty,price_buy)
                                    while True: 

                                        if int(init_qty) + int(buy_qty) > int(remain_qty):         
                                            res_val, odno, msg_cd, buy_price = kf.trade_revise(stockcode[0],static_token,order_no,price_buy,select) # DB 저장 후 method_1_value를 구현하는 방법으로 궁극적 업데이트 필요

                                            if res_val == '0' or ( res_val =='1' and msg_cd =="40330000") or ( res_val =='1' and msg_cd =="40610000"):
                                                result = KDatabaseTrade.remainder_qty(stockcode[0],static_token, ydate, '1', method_type)

                                                if result == True:
                                                    order_no,init_qty,remain_qty,buy_qty,price_buy =  KDatabaseTrade.osfv_db(stockcode[0],odno,"no",buy_price,ydate,method_type) 
                                                    print("현재상황 =",order_no,"초기수량: ", init_qty,"현재수량: ",remain_qty,"매수수량: ",buy_qty,price_buy)
                                            
                                            else :
                                                print(stockcode[0], "정정주문이 실패되었습니다.")
                                        else : 
                                            loop_buy = False
                                            break
                                else:
                                    print(stockcode[0], "매수 할수 없는 종목입니다.")
                                    break
                            #time.sleep(300/1000)
                            
                        else:
                            continue
                    else:
                        continue
                

                #매수 상황 db로 전송
                stock_val_lists = KDatabaseTrade.remainder_lists(static_token,stockcode[0],return_val) 

                    #result = kt. order(stockcode,qty,buy_price, static_token,omethod)

                    #[실전투자]
                            #TTTC0802U : 주식 현금 매수 주문
                            #TTTC0801U : 주식 현금 매도 주문
                            #[모의투자]
                            #VTTC0802U : 주식 현금 매수 주문
                            #VTTC0801U : 주식 현금 매도 주문
                #print(result)
            
    return redirect(url_for('kinvestor.stock_remainders'))

# #========================================================================================#
# # 주식 매수 (자동)
# #=========================================================================================#
# @bp.route('/buyautorun', methods = ['GET','POST'])
# def buy_autorun(stockcode):
#     kt = KTrade()
#     kv = KValue()
#     kr = RealTimeData()
#     kd = RealData()
#     kf = KTradeFunc()

#     # 매수 금액
#     #assigned_price = '2500000'

#     # 입력파라메터
#     # page = request.args.get('page', type=int, default=1)  # 페이지
#     # kw = request.args.get('kw', type=str, default='')
#     # so = request.args.get('so', type=str, default='recent')
#     # r_method = request.args.get('r_method', type=str, default='continue')
#     # s_no = request.args.get('no', type=str, default='')
#     # #stockcode = request.args.get('stockcode', type=str, default='')
#     method_type = request.args.get('type', type=str, default='observe')

#     if method_type == 'observe':
#         assigned_price = '250000'
#     elif method_type == 'remain':
#         assigned_price = '500000'

#     select = 'buy'
#     return_val = 'all' #all: 매수 후 잔고 확인시 db 업데이트 후 모든 항목 return ,
#     if request.method == 'POST':
#         print('POST')
#     else:
#         # 오늘,어제, 현재시간(6자리),현재시간(hhmm00 분봉용) 호출 6자리()
#         todate,ydate,totime,totime00 = KFunction.date_info(0)

#         trade_type = 'mock'  # mock : 모의투자 , real : 실투자
  
#         #토근 호출 
#         static_token = call_token_mock()
#         #for stockcode in stockcodes:

#         loop_buy = True
#         while loop_buy:
#             print(stockcode,static_token, ydate, '0')
#             #time.sleep(0.5)
#             result = KDatabaseTrade.remainder_qty(stockcode,static_token, ydate, '0', method_type)
#             if result == loop_buy:
#                 #time.sleep(0.5)
#                 c_data = KValue.current_value(stockcode,static_token)
#                 if c_data != None:
#                     print("C_DATA =", c_data)
#                     if int(c_data.get('acml_vol')) > 1000:
#                         #time.sleep(0.5)
#                         #매수 주문
#                         order_no,buy_qty,price_buy = kf.trade_buy(assigned_price,stockcode,static_token)
#                         print("오더넘버", order_no, "매수주문수량 ", buy_qty )
#                         if order_no != "0":
#                             print('osfv 입력', stockcode,order_no,buy_qty,price_buy,ydate,method_type)
#                             order_no,init_qty,remain_qty,buy_qty,price_buy =  KDatabaseTrade.osfv_db(stockcode,order_no,buy_qty,price_buy,ydate,method_type)
                            
#                             print("주문번호=",stockcode, order_no,init_qty,remain_qty,price_buy)
#                             while True: 

#                                 if int(init_qty) + int(buy_qty) > int(remain_qty):         
#                                     res_val, odno, msg_cd, buy_price = kf.trade_revise(stockcode,static_token,order_no,price_buy,select) # DB 저장 후 method_1_value를 구현하는 방법으로 궁극적 업데이트 필요

#                                     if res_val == '0' or ( res_val =='1' and msg_cd =="40330000") or ( res_val =='1' and msg_cd =="40610000"):
#                                         result = KDatabaseTrade.remainder_qty(stockcode,static_token, ydate, '1', method_type)

#                                         if result == True:
#                                             order_no,init_qty,remain_qty,buy_qty,price_buy =  KDatabaseTrade.osfv_db(stockcode,odno,"no",buy_price,ydate,method_type) 
#                                             print("현재상황 =",order_no,"초기수량: ", init_qty,"현재수량: ",remain_qty,"매수수량: ",buy_qty,price_buy)
                                    
#                                     else :
#                                         print(stockcode, "정정주문이 실패되었습니다.")
#                                 else : 
#                                     loop_buy = False
#                                     break
#                         else:
#                             print(stockcode, "매수 할수 없는 종목입니다.")
#                             break
#                     #time.sleep(300/1000)
                    
#                 else:
#                     continue
#             else:
#                 continue
        

#         #매수 상황 db로 전송
#         stock_val_lists = KDatabaseTrade.remainder_lists(static_token,stockcode,return_val) 

#             #result = kt. order(stockcode,qty,buy_price, static_token,omethod)

#             #[실전투자]
#                     #TTTC0802U : 주식 현금 매수 주문
#                     #TTTC0801U : 주식 현금 매도 주문
#                     #[모의투자]
#                     #VTTC0802U : 주식 현금 매수 주문
#                     #VTTC0801U : 주식 현금 매도 주문
#         #print(result)
            
#     return True




#========================================================================================#
# 주식  매도 
#=========================================================================================#
@bp.route('/sellrun', methods = ['GET','POST'])
def sell_run():
    kt = KTrade()
    kv = KValue()
    kr = RealTimeData()
    kd = RealData()
    kf = KTradeFunc()



    # 입력파라메터
    page = request.args.get('page', type=int, default=1)  # 페이지
    kw = request.args.get('kw', type=str, default='')
    so = request.args.get('so', type=str, default='recent')
    r_method = request.args.get('r_method', type=str, default='continue')
    s_no = request.args.get('no', type=str, default='')
    method_type = request.args.get('type', type=str, default='observe')
    minus_time = request.args.get('time', type=int, default=0)
    print(s_no,method_type)

    select = 'sell'
    q_sell = 0  # 향후 매도 수량 정할때 사용
    num_sell = "all" # 보유수량 모두 매도 시 사용 현재는 all로 진행
    if request.method == 'POST':
        print('POST')
    else:
       
        # 오늘,어제, 현재시간(6자리),현재시간(hhmm00 분봉용) 호출 6자리()
        todate,ydate,totime,totime00 = KFunction.date_info(minus_time)  

        trade_type = 'mock'  # mock : 모의투자 , real : 실투자
        # SQLAlchemy ORM을 사용하여 데이터베이스에서 데이터를 가져옵니다.
        return_val = 'all'
       # stocklists = ObserveStockFromVB.query.filter_by(stockdate=ydate)
       # stockcodes = db.session.query(StockBalanceLists.stockcode,StockBalanceLists.remainqty).filter(ObserveStockFromVB.stockcode == stockcode).all()
       
        #토근 호출 
        static_token = call_token_mock()


        stock_val_lists = KDatabaseTrade.remainder_lists(static_token,'0',return_val) 

        #stockcodes = db.session.query(StockBalanceLists.stockcode,StockBalanceLists.remainqty).all()

        ## 중요  -- tuple(,)과 list[(,),(,)]을 하나의 for문으로 쓰고 싶을때 tuple을 list tuple로 만들어주면됨 아래와 같이 
         #stockcode =  ('006340', '2422')   stockcodes = [stockcode] #tuple을 list tuple로 변경
         #stockcodes = [('006340', '2422'), ('009190', '2182'), ('009730', '5107'), ('064480', '839'), ('064800', '2005'), ('066790', '719'), ('136410', '136'), ('260970', '171')] 
        if method_type == 'remain':
            if s_no:
                stockcodes = db.session.query(StockBalanceLists.stockcode, StockBalanceLists.remainderqty).filter(
                    StockBalanceLists.no == s_no
                ).all()
                # if stockcode:
                #     stockcodes = [stockcode]
                # else:
                #     stockcode = []
                print("remain,s_no:",stockcodes)
            else:
                stockcodes = db.session.query(StockBalanceLists.stockcode, StockBalanceLists.remainderqty).all()        
        
        
        
        print(stockcodes)


        #for stockcode in stockcodes:
        loop_sell = False
        for count, item in enumerate(stockcodes, start=1): #카운트추가
            print(item[0])
            loop_sell = True
            while loop_sell:

                #result, s_qty = KDatabaseTrade.remainder_qty(stockcode[0],static_token, ydate, '0')
                    # 종목코드별 보유수량 모두 팔지, 정한 수량만 매도할지 결정
                # if num_sell != "all":
                #     qty_sell = q_sell
                # else:
                #     qty_sell = item[1]
                # 종목코드별 보유수량 모두 팔지, 정한 수량만 매도할지 결정 (위의 코드 한줄로 표현)
                qty_sell = q_sell if num_sell != "all" else item[1]

                if loop_sell:
                    c_data = KValue.current_value(item[0],static_token)
                    if c_data != None:
                        print("C_DATA =", c_data)
                        #if int(c_data.get('acml_vol')) > 1000:

                        #time.sleep(300/1000)
                        #매도 주문
                        order_no,sell_qty,price_sell = kf.trade_sell(item[0],qty_sell,static_token)
                        print("오더넘버", order_no, "매도주문수량 ", sell_qty )
                        if order_no != "0":
                                return_val = 'remainder' #all: 매수 후 잔고 확인시 db 업데이트 후 모든 항목 return , remainder : stockcode의 현재 잔량만 리턴
                                time.sleep(0.3)
                                remainder_qty = KDatabaseTrade.remainder_lists(static_token,item[0],return_val) 
                                
                                print("주문번호=",item[0], order_no,item[1],remainder_qty,price_sell)
                                while True: 
                                    if remainder_qty == None: # 잔고(품목이 없어졌을 경우)
                                        remainder_qty = '0'

                                    if int(item[1]) - int(qty_sell) != int(remainder_qty):   #item[1]은 최초 보유수량임으로, init_qty와 동일        
                                        res_val, odno, msg_cd, sell_price = kf.trade_revise(item[0],static_token,order_no,price_sell,select) # DB 저장 후 method_1_value를 구현하는 방법으로 궁극적 업데이트 필요

                                        if res_val == '0' or ( res_val =='1' and msg_cd =="40330000"):
                                            time.sleep(0.3)
                                            remainder_qty = KDatabaseTrade.remainder_lists(static_token,item[0],return_val) 
                                            order_no = odno
                                            price_sell = sell_price
                                            print("현재상황 =",odno,"초기수량: ", item[1],"현재수량: ",remainder_qty,"매도수량: ",qty_sell,sell_price)
                                        else :
                                            print(item[0], "정정주문이 실패되었습니다.")
                                    else : 
                                        loop_sell = False
                                        break
                        else:
                            print(item[0], "매도주문 실패")
                        time.sleep(0.3)
                        
                    else:
                        continue
                else:
                    continue
            #result = kt. order(stockcode,qty,sell_price, static_token,omethod)

            #[실전투자]
                    #TTTC0802U : 주식 현금 매수 주문
                    #TTTC0801U : 주식 현금 매도 주문
                    #[모의투자]
                    #VTTC0802U : 주식 현금 매수 주문
                    #VTTC0801U : 주식 현금 매도 주문
        #print(result)
            
        return redirect(url_for('kinvestor.stock_remainders'))

#========================================================================================#
# 일별 매매현황 
#=========================================================================================#
@bp.route('/dailytrade', methods = ['GET','POST'])
def daily_trade():
    kt = KTrade()
    kv = KValue()
    kr = RealTimeData()
    kd = RealData()
    kf = KTradeFunc()



    # 입력파라메터
    page = request.args.get('page', type=int, default=1)  # 페이지
    kw = request.args.get('kw', type=str, default='')
    so = request.args.get('so', type=str, default='recent')
    dbupdate = request.args.get('dbupdate', type=str, default='0')
    start_date = request.args.get('startdate', type=str, default='')
    end_date = request.args.get('enddate', type=str, default='')
    minus_time = request.args.get('time', type=int, default=0)


    stockcode = '' # 스탁코드가 공란이면 전체 조회
    ordermethod = 'VTTC8001R' # VTTC8001R : 주식 일별 주문 체결 조회(3개월이내)
        # [실전투자]
        # TTTC8001R : 주식 일별 주문 체결 조회(3개월이내)
        # CTSC9115R : 주식 일별 주문 체결 조회(3개월이전)

        # [모의투자]
        # VTTC8001R : 주식 일별 주문 체결 조회(3개월이내)
        # VTSC9115R : 주식 일별 주문 체결 조회(3개월이전)
        # * 일별 조회로, 당일 주문내역은 지연될 수 있습니다.
        # * 3개월이내 기준: 개월수로 3개월
        # 오늘이 4월22일이면 TTC8001R에서 1월~ 3월 + 4월 조회 가능
        # 5월이 되면 1월 데이터는 TTC8001R에서 조회 불가, TSC9115R로 조회 가능
    
    selecttrade = '00' #매도매수구분코드 00:전체 01:매도  02:매수
    
    
    select = 'sell'
    q_sell = 0  # 향후 매도 수량 정할때 사용
    num_sell = "all" # 보유수량 모두 매도 시 사용 현재는 all로 진행

    if request.method == 'POST':
        print('POST')
    else:
    
        # 오늘,어제, 현재시간(6자리),현재시간(hhmm00 분봉용) 호출 6자리()
        todate,ydate,totime,totime00 = KFunction.date_info(minus_time)      

        fromdate =  ydate
        todate = ydate
        #dbupdate = '1' # "1"일일매매현황 업데이 트 
        trade_type = 'mock'  # mock : 모의투자 , real : 실투자
        # SQLAlchemy ORM을 사용하여 데이터베이스에서 데이터를 가져옵니다.
        return_val = 'all'
    # stocklists = ObserveStockFromVB.query.filter_by(stockdate=ydate)
    # stockcodes = db.session.query(StockBalanceLists.stockcode,StockBalanceLists.remainqty).filter(ObserveStockFromVB.stockcode == stockcode).all()
        
        if dbupdate =='1':
            #토근 호출 
            static_token = call_token_mock()
            print('입력데이터', stockcode,fromdate,todate,static_token,ordermethod,selecttrade)
            result_trade= KTrade.daily_trade_list(start_date,end_date,static_token,ordermethod,selecttrade)
            print(result_trade)
            
            # DailyTrade.query.delete()
            # db.session.commit()

            # tradedate가 ydate와 같은 행을 삭제하는 쿼리 생성
            delete_query = delete(DailyTrade).where(DailyTrade.tradedate == ydate)

            # 쿼리 실행
            db.session.execute(delete_query)
            db.session.commit()

            for stockinfo in result_trade:
                stockinfor = DailyTrade(
                        stockcode= stockinfo['pdno'],
                        stockname=stockinfo['prdt_name'],
                        tradedate =stockinfo['ord_dt'], # 주문일자
                        orderno =stockinfo['odno'], # 주문 번호
                        orderno_origin =stockinfo['orgn_odno'], #원주문번호
                        trade =stockinfo['sll_buy_dvsn_cd'], # 거래구분	01 : 매도 02 : 매수 
                        trade_name  =stockinfo['sll_buy_dvsn_cd_name'] , #반대매매 인경우 "임의매도"로 표시됨 정정취소여부가 Y이면 *이 붙음 ex) 매수취소* = 매수취소가 완료됨
                        orderqty =stockinfo['ord_qty'], #주문수량
                        orderprice =stockinfo['ord_unpr'],#주문단가
                        ordertime  =stockinfo['ord_tmd'], #주문시간
                        total_trade_qty =stockinfo['tot_ccld_qty'], #총체결수량
                        avg_price =stockinfo['avg_prvs'], #평균가
                        total_trade_amount =stockinfo['tot_ccld_amt'], #총 체결금액
                        order_code =stockinfo['ord_dvsn_cd'], #주문구분코드
                        # 00 : 지정가
                        # 01 : 시장가
                        # 02 : 조건부지정가
                        # 03 : 최유리지정가
                        # 04 : 최우선지정가
                        # 05 : 장전 시간외
                        # 06 : 장후 시간외
                        # 07 : 시간외 단일가
                        # 08 : 자기주식
                        # 09 : 자기주식S-Option
                        # 10 : 자기주식금전신탁
                        # 11 : IOC지정가 (즉시체결,잔량취소)
                        # 12 : FOK지정가 (즉시체결,전량취소)
                        # 13 : IOC시장가 (즉시체결,잔량취소)
                        # 14 : FOK시장가 (즉시체결,전량취소)
                        # 15 : IOC최유리 (즉시체결,잔량취소)
                        # 16 : FOK최유리 (즉시체결,전량취소)
                        remain_qty =stockinfo['rmn_qty'], #잔여수량
                        trade_condition =stockinfo['ccld_cndt_name'], # 채결조건명
                        market =stockinfo['prdt_type_cd'], # 거래소 구분코드 	01 : 한국증권 02 : 증권거래소  03 : 코스닥

                        # #OUTPUT2 
                        # amount_order =stockinfo['tot_ord_qty'], #총주문수량
                        # amount_trade_qty =stockinfo['tot_ccld_qty'], #총체결수량
                        # avg_buy_cost =stockinfo['pchs_avg_pric'] ,# 매입평균가격
                        # amount_cost =stockinfo['tot_ccld_amt'], #총결제금액
                        # exp_tax =stockinfo['prsm_tlex_smtl'] # 추정 제비용 합계
                    )

                # 데이터베이스에 저장
                db.session.add(stockinfor)
                db.session.commit()



        

        #result_trades = DailyTrade.query.filter_by(tradedate= ydate).filter(DailyTrade.total_trade_qty > 0).all()
        #result_trades = DailyTrade.query.filter(DailyTrade.total_trade_qty > 0).all()



        # 하나의 쿼리로 매도('01')와 매수('02') 데이터를 가져오기
            # result_sell = DailyTrade.query.filter_by(tradedate= ydate,trade='01').filter(DailyTrade.total_trade_qty > 0).all()
            # result_buy = DailyTrade.query.filter_by(trade='02').filter(DailyTrade.total_trade_qty > 0).all()
        # 위의 쿼리 2개를 아래 코드 하나로 합침

        # 범위를 포함하는 쿼리 생성
        result_trades = DailyTrade.query.filter(
            or_(
                and_(DailyTrade.trade == '01', DailyTrade.tradedate.between(start_date, end_date), DailyTrade.total_trade_qty > 0),
                and_(DailyTrade.trade == '02', DailyTrade.total_trade_qty > 0)
            )
        ).all()

        # trades = []
        # for stockinfo in result_trades:
        #     trades.append({
        #         'stockcode': stockinfo.stockcode,
        #         'stockname': stockinfo.stockname,
        #         'tradedate': stockinfo.tradedate,
        #         'orderno': stockinfo.orderno,
        #         'orderno_origin': stockinfo.orderno_origin,
        #         'trade': stockinfo.trade,
        #         'trade_name': stockinfo.trade_name,
        #         'orderqty': stockinfo.orderqty,
        #         'orderprice': stockinfo.orderprice,
        #         'ordertime': stockinfo.ordertime,
        #         'total_trade_qty': stockinfo.total_trade_qty,
        #         'avg_price': stockinfo.avg_price,
        #         'total_trade_amount': stockinfo.total_trade_amount,
        #         'order_code': stockinfo.order_code,
        #         'remain_qty': stockinfo.remain_qty,
        #         'trade_condition': stockinfo.trade_condition,
        #         'market': stockinfo.market
        #     })
        # print(trades)


        trades = defaultdict(lambda: {'stockname': '', 'trade_01_amount': 0, 'trade_02_amount': 0, 'total_trade_qty_01': 0, 'total_trade_qty_02': 0})

        for stockinfo in result_trades:
            key = stockinfo.stockcode
            trades[key]['stockname'] = stockinfo.stockname

            
            if stockinfo.trade == '01':
                trades[key]['trade_01_amount'] += float(stockinfo.total_trade_amount)
                trades[key]['total_trade_qty_01'] += int(stockinfo.total_trade_qty)
            elif stockinfo.trade == '02':
                trades[key]['trade_02_amount'] += float(stockinfo.total_trade_amount)
                trades[key]['total_trade_qty_02'] += int(stockinfo.total_trade_qty)

        aggregated_trades = []
        differences = []
        total_profit = 0  # 모든 주식코드의 profit을 더하기 위한 변수
        
        for stockcode, value in trades.items():
            trade_01_amount = value['trade_01_amount']
            trade_02_amount = value['trade_02_amount']
            total_trade_qty_01 = value['total_trade_qty_01']
            total_trade_qty_02 = value['total_trade_qty_02']
            
            avg_price_01 = round(trade_01_amount / total_trade_qty_01) if total_trade_qty_01 > 0 else 0
            avg_price_02 = round(trade_02_amount / total_trade_qty_02) if total_trade_qty_02 > 0 else 0
            
            profit = 0
            profit_rate = 0
            if total_trade_qty_01 > 0:
                profit = (avg_price_01 * total_trade_qty_01) - (avg_price_02 * total_trade_qty_01)
                
                total_profit += profit
                if avg_price_02 * total_trade_qty_01 != 0:
                    profit_rate = round((profit / (avg_price_02 * total_trade_qty_01)) * 100, 1)  # 백분율로 계산
            
            aggregated_trades.append({
                'stockcode': stockcode,
                'stockname': value['stockname'],
                'trade_01_amount': int(trade_01_amount),
                'trade_02_amount': int(trade_02_amount),
                'total_trade_qty_01': total_trade_qty_01,
                'total_trade_qty_02': total_trade_qty_02,
                'avg_price_01': avg_price_01,
                'avg_price_02': avg_price_02,
                'profit': profit,
                'profit_rate': profit_rate
            })

            if trade_01_amount > 0 and trade_02_amount > 0:
                differences.append({
                    'stockcode': stockcode,
                    'stockname': value['stockname'],
                    'amount_difference': trade_02_amount - trade_01_amount
                })

        sorted_aggregated_trades = sorted(aggregated_trades, key=lambda x: x['stockcode'])
        sorted_differences = sorted(differences, key=lambda x: x['stockcode'])

        # 검색 쿼리를 수행하여 검색 결과를 가져옴
        if kw:
            search = '%%{}%%'.format(kw)
            stock_list = db.session.query(DailyTrade).filter(
                (DailyTrade.stockcode.ilike(search)) |  # 주식 코드
                (DailyTrade.stockname.ilike(search))  # 주식 이름
            ).distinct().all()
        else:
            stock_list = []

    return render_template(
                            'stockdata/daily_trade_result.html',
                            aggregated_trades=sorted_aggregated_trades,
                            stock_list = stock_list,
                            differences=sorted_differences,
                            total_profit=total_profit,
                            start_date = start_date,
                            end_date = end_date
                            )


# return 'ok'

# ############################## 엑셀 파일 다운로드 업로드 ###########################################3

# # 다운로드 FROM DB
# @bp.route('/dbdownload', methods = ['GET','POST'])
# def excel_download():
#     write_wb = Workbook()
#     write_ws = write_wb.active
#     edata = Stockinfo.query.all()

#     ws_title = "종목명 종목코드"
#     l_title = ws_title.split("\t")
#     write_ws.append(l_title)

#     # Append each row of stock info to the worksheet
#     for stock_info in edata:
#         row_data = (stock_info.stockname, stock_info.stockcode)  # Extract name and code attributes
#         write_ws.append(row_data)
    
#     file_path = "C:/projects/download/"
#     flie_name = "stockcode_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".xlsx"
        
#     write_wb.save(file_path + flie_name)

#     return 'ok'


# # 업로드 From excel to DB
# @bp.route('/dbupload', methods = ['GET','POST'])
# def excel_upload():
#     file_path = "C:/projects/download/"
#     file_name = "Stock_Find Max(rev5.18)_20240513.xlsm"

#     wb = openpyxl.load_workbook(file_path + file_name)  # 엑셀 파일을 엽니다.
#     ws = wb["Sheet3"]  # "Sheet3" 시트를 선택합니다.

#     excel_to_list_all = []  # 엑셀 전체 데이터를 담을 리스트를 초기화합니다.

#     seen = set()  # 중복 데이터를 확인하기 위한 집합을 초기화합니다.

#     for index, row in enumerate(ws.rows):  # 모든 행을 반복합니다.
#         if index >= 6:  # 7번째 행부터 데이터를 저장합니다.
#             excel_to_list1 = []  # 한 행의 데이터를 담을 리스트를 초기화합니다.
#             duplicate_check = (row[0].value, row[2].value)  # 중복 데이터를 확인하기 위한 튜플을 생성합니다.

#             if duplicate_check not in seen:  # 중복이 아닌 경우에만 추가합니다.
#                 for cell in row:  # 행의 각 셀을 반복합니다.
#                     excel_to_list1.append(cell.value)  # 셀의 값을 리스트에 추가합니다.

#                 excel_to_list_all.append(excel_to_list1)  # 행의 데이터 리스트를 전체 데이터 리스트에 추가합니다.
#                 seen.add(duplicate_check)  # 중복 데이터 집합에 추가합니다.

#     print(excel_to_list_all[0][1])  # 전체 데이터 리스트를 출력합니다.

#     # Chartinfo 객체 생성 및 속성 채우기


#     for i in range(len(excel_to_list_all) - 1):  # excel_to_list_all의 길이만큼 반복합니다.
#         stocklist_fromvb = StockListFromVB(
#             stockcode= excel_to_list_all[i][0],
#             stockname= excel_to_list_all[i][1],
#             stockdate= excel_to_list_all[i][2],
#             method_1 = excel_to_list_all[i][3],
#             method_2 = excel_to_list_all[i][4],
#             currentvalue = excel_to_list_all[i][6],
#             d5d20  = excel_to_list_all[i][7],
#             close5d =excel_to_list_all[i][8],
#             close20d = excel_to_list_all[i][9],
#             closebegin  = excel_to_list_all[i][10],
#             closepreclose = excel_to_list_all[i][11],
#             closelow = excel_to_list_all[i][12],
#             highclose = excel_to_list_all[i][13],
#             begin_1 = excel_to_list_all[i][23],
#             begin_2 = excel_to_list_all[i][24],
#             begin_3 = excel_to_list_all[i][25],
#             begin_4 = excel_to_list_all[i][26],
#             begin_5 = excel_to_list_all[i][27],
#             high_1 = excel_to_list_all[i][28],
#             high_2 = excel_to_list_all[i][29],
#             high_3 = excel_to_list_all[i][30],
#             high_4 = excel_to_list_all[i][31],
#             high_5 = excel_to_list_all[i][32],
#             first_low_date = excel_to_list_all[i][33],
#             first_low_value = excel_to_list_all[i][34],
#             first_high_date = excel_to_list_all[i][35],
#             first_high_value = excel_to_list_all[i][36],
#             secend_low_date = excel_to_list_all[i][37],
#             secend_low_value = excel_to_list_all[i][38],
#             secend_high_date = excel_to_list_all[i][39],
#             secend_high_value = excel_to_list_all[i][40],
#             high_begin_4 = excel_to_list_all[i][41],
#             high_begin_3 = excel_to_list_all[i][42],
#             high_begin_2 = excel_to_list_all[i][43],
#             high_begin_1 = excel_to_list_all[i][44],
#             tradevol_4= excel_to_list_all[i][45],
#             tradevol_3 = excel_to_list_all[i][46],
#             tradevol_2 = excel_to_list_all[i][47],
#             tradevol_1 = excel_to_list_all[i][48],
#             tradevol_0 = excel_to_list_all[i][49],
#             d60_d20 = excel_to_list_all[i][50],
#             d20_d5 = excel_to_list_all[i][51],
#             close_close4 = excel_to_list_all[i][52]
               
#             )

#         # 데이터베이스에 저장
#         db.session.add(stocklist_fromvb)
#         db.session.commit()

#     return 'ok'


