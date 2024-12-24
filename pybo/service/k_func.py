from datetime import datetime, timedelta
from openpyxl import Workbook
import openpyxl    
import asyncio
import time
import pandas as pd
#from aioflask import Flask, request, jsonify, Blueprint, render_template,url_for
from flask import Flask, request, jsonify, Blueprint, render_template,url_for
from werkzeug.utils import redirect
from ..models import Stockinfo, Chartinfo, StockinfoTemp, Token_temp, ObserveStock, StockListFromVB, ObserveStockFromVB,StockBalanceLists
import json
from .. import db
from sqlalchemy import func
from ..service.k_trade import KTrade
from ..service.k_analysis import KAnalysis
from ..service.k_value import KValue
from ..service.k_realdata import RealTimeData,RealData
from ..service.k_trade_func import KTradeFunc
from ..service.k_db_trade import KDatabaseTrade
#from ..views.stock_controller import call_token, call_token_mock


import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

class KFunction():

    def date_info(minus_days):
    # 현재 날짜와 시간을 datetime 객체로 얻어옵니다.
        today_date = datetime.now()

        # datetime 객체를 원하는 형식의 문자열로 변환합니다.
        today_date_str = today_date.strftime("%Y%m%d")

        # 문자열을 datetime 객체로 다시 변환합니다. 필요한 경우에만 사용합니다.
        today_date_dt = datetime.strptime(today_date_str, "%Y%m%d")

        # 현재 날짜에서 하루를 빼어 어제의 날짜를 구합니다.
        
        before_date = today_date_dt - timedelta(days=minus_days)

        today_time_str = today_date.strftime("%H%M%S")

        today_min_str = today_date.strftime("%H%M00")

        # 어제의 날짜를 원하는 형식의 문자열로 변환합니다.
        b_date = before_date.strftime("%Y%m%d")
        print(b_date)

        return today_date_str,b_date,today_time_str,today_min_str #현재날짜(240604),이전날짜(240604-minus_days),현재시간(hhmmss),현재시간(hhmm00)
    
    def time_info(minus_days,minus_mins):
        # 현재 날짜와 시간을 datetime 객체로 얻어옵니다.
        today_date = datetime.now()

        # datetime 객체를 원하는 형식의 문자열로 변환합니다.
        today_date_str = today_date.strftime("%Y%m%d")

        # 문자열을 datetime 객체로 다시 변환합니다. 필요한 경우에만 사용합니다.
        today_date_dt = datetime.strptime(today_date_str, "%Y%m%d")

        # 현재 날짜에서 지정된 일수를 빼어 과거의 날짜를 구합니다.
        before_date = today_date_dt - timedelta(days=minus_days)

        # 현재 시간을 문자열로 변환합니다.
        today_time_str = today_date.strftime("%H%M%S")
        
        # 현재 시간의 분을 00으로 설정한 문자열을 생성합니다.
        today_min_str = today_date.strftime("%H%M00")

        # today_min_str을 datetime 객체로 변환합니다.
        today_min_dt = datetime.strptime(today_min_str, "%H%M00")

        # today_min_dt에서 30분을 뺍니다.
        before_time_dt = today_min_dt - timedelta(minutes=minus_mins)
        
        # 30분 뺀 결과를 문자열로 변환합니다.
        before_time_str = before_time_dt.strftime("%H%M00")

        # 어제의 날짜를 원하는 형식의 문자열로 변환합니다.
        b_date = before_date.strftime("%Y%m%d")
        print(b_date)

        return today_date_str, b_date, today_time_str, today_min_str, before_time_str
    
    def beforetime_info(minus_mins):

        # 현재 날짜와 시간을 datetime 객체로 얻어옵니다.
        today_date = datetime.now()

        # 현재 시간을 문자열로 변환합니다.
        today_time_str = today_date.strftime("%H%M%S")
        
        # 현재 시간의 분을 00으로 설정한 문자열을 생성합니다.
        today_min_str = today_date.strftime("%H%M00")
        today_min = today_date.strftime("%H%M00")

        # 현재 시간이 15:20:00 이후라면 today_time_str을 '152000'으로 설정합니다.
        if today_min_str >= '152000':
            today_min_str = '152000'

        # today_min_str을 datetime 객체로 변환합니다.
        today_min_dt = datetime.strptime(today_min_str, "%H%M00")

        before_times = []
        # 현재 시간에서부터 09:00:00까지 30분 간격으로 beforetime00을 구합니다.
        while today_min_str >= '090000':
            # 30분을 뺍니다.
            before_time_dt = today_min_dt - timedelta(minutes=minus_mins)
            
            # 30분 뺀 결과를 문자열로 변환합니다.
            before_time_str = before_time_dt.strftime("%H%M00")

            # 리스트에 추가합니다.
            before_times.append(before_time_str)

            # 다음 루프를 위해 현재 시간을 30분 더 뺍니다.
            today_min_dt -= timedelta(minutes=30)
            today_min_str = today_min_dt.strftime("%H%M00")

        return today_time_str, today_min, before_times
    #========================================================================================#
    # # 주식 매수 (자동)
    # #=========================================================================================#
    def buy_autorun(stockcode,method_type,static_token):
        kt = KTrade()
        kv = KValue()
        kr = RealTimeData()
        kd = RealData()
        kf = KTradeFunc()

        # 매수 금액
        #assigned_price = '2500000'

        # 입력파라메터
        # page = request.args.get('page', type=int, default=1)  # 페이지
        # kw = request.args.get('kw', type=str, default='')
        # so = request.args.get('so', type=str, default='recent')
        # r_method = request.args.get('r_method', type=str, default='continue')
        # s_no = request.args.get('no', type=str, default='')
        # #stockcode = request.args.get('stockcode', type=str, default='')
        #method_type = request.args.get('type', type=str, default='observe')

        if method_type == 'observe':
            assigned_price = '250000'
        elif method_type == 'remain':
            assigned_price = '500000'

        select = 'buy'
        return_val = 'all' #all: 매수 후 잔고 확인시 db 업데이트 후 모든 항목 return ,
        if request.method == 'POST':
            print('POST')
        else:
            # 오늘,어제, 현재시간(6자리),현재시간(hhmm00 분봉용) 호출 6자리()
            todate,ydate,totime,totime00 = KFunction.date_info(0)

            trade_type = 'mock'  # mock : 모의투자 , real : 실투자
  

            loop_buy = True
            while loop_buy:
                print(stockcode,static_token, ydate, '0')
                #time.sleep(0.5)
                result = KDatabaseTrade.remainder_qty(stockcode,static_token, ydate, '0', method_type)
                if result == loop_buy:
                    #time.sleep(0.5)
                    c_data = KValue.current_value(stockcode,static_token)
                    if c_data != None:
                        print("C_DATA =", c_data)
                        if int(c_data.get('acml_vol')) > 1000:
                            #time.sleep(0.5)
                            #매수 주문
                            order_no,buy_qty,price_buy = kf.trade_buy(assigned_price,stockcode,static_token)
                            print("오더넘버", order_no, "매수주문수량 ", buy_qty )
                            if order_no != "0":
                                print('osfv 입력', stockcode,order_no,buy_qty,price_buy,ydate,method_type)
                                order_no,init_qty,remain_qty,buy_qty,price_buy =  KDatabaseTrade.osfv_db(stockcode,order_no,buy_qty,price_buy,ydate,method_type)
                                
                                print("주문번호=",stockcode, order_no,init_qty,remain_qty,price_buy)
                                while True: 

                                    if int(init_qty) + int(buy_qty) > int(remain_qty):         
                                        res_val, odno, msg_cd, buy_price = kf.trade_revise(stockcode,static_token,order_no,price_buy,select) # DB 저장 후 method_1_value를 구현하는 방법으로 궁극적 업데이트 필요

                                        if res_val == '0' or ( res_val =='1' and msg_cd =="40330000") or ( res_val =='1' and msg_cd =="40610000"):
                                            result = KDatabaseTrade.remainder_qty(stockcode,static_token, ydate, '1', method_type)

                                            if result == True:
                                                order_no,init_qty,remain_qty,buy_qty,price_buy =  KDatabaseTrade.osfv_db(stockcode,odno,"no",buy_price,ydate,method_type) 
                                                print("현재상황 =",order_no,"초기수량: ", init_qty,"현재수량: ",remain_qty,"매수수량: ",buy_qty,price_buy)
                                        
                                        else :
                                            print(stockcode, "정정주문이 실패되었습니다.")
                                    else : 
                                        loop_buy = False
                                        break
                            else:
                                print(stockcode, "매수 할수 없는 종목입니다.")
                                break
                        #time.sleep(300/1000)
                        
                    else:
                        continue
                else:
                    continue
            

            #매수 상황 db로 전송
            stock_val_lists = KDatabaseTrade.remainder_lists(static_token,stockcode,return_val) 

            if method_type == 'observe': # 매수 대기 항목 매수(추가매수시)
                update_qty = ObserveStockFromVB.query.filter_by(stockcode=stockcode, method_1 = '1').first()  
                update_qty.selected4 = '1'
                db.session.commit()


                #result = kt. order(stockcode,qty,buy_price, static_token,omethod)

                #[실전투자]
                        #TTTC0802U : 주식 현금 매수 주문
                        #TTTC0801U : 주식 현금 매도 주문
                        #[모의투자]
                        #VTTC0802U : 주식 현금 매수 주문
                        #VTTC0801U : 주식 현금 매도 주문
            #print(result)
                
        return True     

    #========================================================================================#
    # 주식  매도 (AUTO)
    #=========================================================================================#

    def sell_autorun(stockcode,method_type,s_no,static_token):
        kt = KTrade()
        kv = KValue()
        kr = RealTimeData()
        kd = RealData()
        kf = KTradeFunc()


        select = 'sell'
        q_sell = 0  # 향후 매도 수량 정할때 사용
        num_sell = "all" # 보유수량 모두 매도 시 사용 현재는 all로 진행
        if request.method == 'POST':
            print('POST')
        else:
        
            # 오늘,어제, 현재시간(6자리),현재시간(hhmm00 분봉용) 호출 6자리()
            todate,ydate,totime,totime00 = KFunction.date_info(0)
            print(ydate)
            trade_type = 'mock'  # mock : 모의투자 , real : 실투자
            # SQLAlchemy ORM을 사용하여 데이터베이스에서 데이터를 가져옵니다.
            return_val = 'all'
        # stocklists = ObserveStockFromVB.query.filter_by(stockdate=ydate)
        # stockcodes = db.session.query(StockBalanceLists.stockcode,StockBalanceLists.remainqty).filter(ObserveStockFromVB.stockcode == stockcode).all()
        


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
                
            return True
