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
from ..service.k_cal_data import KCalcuration
from ..service.k_func import KFunction
from .stock_controller import call_token, call_token_mock
from collections import defaultdict

import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

# bp = Flask(__name__)

bp = Blueprint('kjudge',__name__,url_prefix='/kjudge')

# 현재 실행 중인 연결 객체
current_connection = None

#========================================================================================#
# 주식 매수 
#=========================================================================================#
@bp.route('/judgebuy', methods = ['GET','POST'])
def buy_judge():
    kt = KTrade()
    kv = KValue()
    kr = RealTimeData()
    kd = RealData()
    kf = KTradeFunc()

    # 매수 금액
    assigned_price = '100000'

    # 입력파라메터
    page = request.args.get('page', type=int, default=1)  # 페이지
    kw = request.args.get('kw', type=str, default='')
    so = request.args.get('so', type=str, default='recent')
    r_method = request.args.get('r_method', type=str, default='continue')
    s_no = request.args.get('no', type=str, default='')
    #method_type = request.args.get('type', type=str, default='observe')

    select = 'buy'
    return_val = 'all' #all: 매수 후 잔고 확인시 db 업데이트 후 모든 항목 return ,
    if request.method == 'POST':
        print('POST')
    else:
        
        # 오늘,어제, 현재시간(6자리),현재시간(hhmm00 분봉용) 호출 6자리()
        todate,ydate,totime,totime00 = KFunction.date_info(0)       
        
        
        trade_type = 'mock'  # mock : 모의투자 , real : 실투자
        # SQLAlchemy ORM을 사용하여 데이터베이스에서 데이터를 가져옵니다.
        
       # stocklists = ObserveStockFromVB.query.filter_by(stockdate=ydate)
        # 일반적으로 쓰는것..잠시 홀딩
        while True:

            ob_stockcodes = db.session.query(ObserveStockFromVB.stockcode,ObserveStockFromVB.category).filter(
                ObserveStockFromVB.method_1 == '1',
                ObserveStockFromVB.selected4 == '0',
                ObserveStockFromVB.selecteddate == ydate
            ).all()
            
            re_stockcodes = db.session.query(StockBalanceLists.stockcode,
                                            StockBalanceLists.category,
                                            StockBalanceLists.buyprice,
                                            StockBalanceLists.buyamount,
                                            StockBalanceLists.remainderqty,
                                            StockBalanceLists.evalprice, #평가금액
                                            StockBalanceLists.evalpriceamount, # 평가금액  - 매입금액
                                            StockBalanceLists.evalrate, # 수익률
                                            StockBalanceLists.no
                                            ).all()

            stockcodes = ob_stockcodes + re_stockcodes

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
            m_data = []
            for stockcode in stockcodes: #카운트추가
                #print(stockcode[0])
                #if count >1 and count <=11:
                loop_buy = True
                method_type = stockcode[1] 
                

                while loop_buy:
                    print(stockcode[0],stockcode[1],static_token, ydate, '0')
                    #현재값
                    # m_data = KValue.mindata(stockcode[0],static_token, today_time_str )
                    # c_data = KValue.current_value(stockcode[0],static_token)
                    # p_data = ''
                    #장시작전 예상 체결
                    if totime > '085900' and totime < '090000':
                        p_data = KValue.cell_predict_price(stockcode[0],static_token) 
                        
                        if method_type == 'observe':
                            result_cal = KCalcuration.anticipation_market(p_data,method_type,stockcode[0],static_token)
                            break
                        elif method_type == 'remain':
                            result_cal = KCalcuration.anticipation_market(p_data,method_type,stockcode,static_token) 
                            break
                        else:
                            loop_buy = False
                            break
                    # 장시작 -- 정규장
                    elif totime >= '090000' and totime <= '235900':
                        m_data = KValue.mindata(stockcode[0],static_token, '153000')
                        c_data = KValue.current_value(stockcode[0],static_token)
                        print('MDATA: ', m_data)
                        m_len = len(m_data)
                        
                        if c_data.get('vi_cls_code') == 'Y' :
                            p_data = KValue.cell_predict_price(stockcode[0],static_token)    

                            if method_type == 'observe':
                                result_cal = KCalcuration.anticipation_market(p_data, m_len,method_type,stockcode[0],static_token)
                                break
                            elif method_type == 'remain':
                                result_cal = KCalcuration.anticipation_market(p_data,m_len,method_type,stockcode,static_token) 
                                break
                            else:
                                loop_buy = False
                                break 
                                
                        elif c_data != None and m_data != None:
                            
                            #min3, min5, min10, min20, min30, min60, min120  = KCalcuration.cal_mindata(m_data)
                            min_datas  = KCalcuration.cal_mindata(m_data)
                            #print('min값',min3, min5, min10, min20, min30, min60, min120 )
                            if method_type == 'observe':
                                result_cal = KCalcuration.regular_market(c_data, min_datas, m_len,method_type,stockcode[0],static_token)
                                break
                            elif method_type == 'remain':
                                result_cal = KCalcuration.regular_market(c_data, min_datas, m_len,method_type,stockcode,static_token) 
                                break
                            else:
                                loop_buy = False
                                break 

                        else:
                            print('조건에 맞지 않습니다.')
                            print('조건에 맞지 않습니다.')
                            loop_buy = False
                            break   
                            
                    else:
                        print('장운영 시간이 아닙니다.')
                        print('장운영 시간이 아닙니다.')
                        print('장운영 시간이 아닙니다.')
                        print('장운영 시간이 아닙니다.')
                        loop_buy = False
                        break
        #                 print("C_DATA =", c_data)
        #                 if int(c_data.get('acml_vol')) > 1000:
        #                     time.sleep(0.5)
        #                     #매수 주문
        #                     order_no,buy_qty,price_buy = kf.trade_buy(assigned_price,stockcode[0],static_token)
        #                     print("오더넘버", order_no, "매수주문수량 ", buy_qty )
        #                     if order_no != "0":
        #                         print('osfv 입력', stockcode[0],order_no,buy_qty,price_buy,ydate,method_type)
        #                         order_no,init_qty,remain_qty,buy_qty,price_buy =  KDatabaseTrade.osfv_db(stockcode[0],order_no,buy_qty,price_buy,ydate,method_type)
                                
        #                         print("주문번호=",stockcode[0], order_no,init_qty,remain_qty,price_buy)
        #                         while True: 

        #                             if int(init_qty) + int(buy_qty) > int(remain_qty):         
        #                                 res_val, odno, msg_cd, buy_price = kf.trade_revise(stockcode[0],static_token,order_no,price_buy,select) # DB 저장 후 method_1_value를 구현하는 방법으로 궁극적 업데이트 필요

        #                                 if res_val == '0' or ( res_val =='1' and msg_cd =="40330000") or ( res_val =='1' and msg_cd =="40610000"):
        #                                     result = KDatabaseTrade.remainder_qty(stockcode[0],static_token, ydate, '1', method_type)

        #                                     if result == True:
        #                                         order_no,init_qty,remain_qty,buy_qty,price_buy =  KDatabaseTrade.osfv_db(stockcode[0],odno,"no",buy_price,ydate,method_type) 
        #                                         print("현재상황 =",order_no,"초기수량: ", init_qty,"현재수량: ",remain_qty,"매수수량: ",buy_qty,price_buy)
                                        
        #                                 else :
        #                                     print(stockcode[0], "정정주문이 실패되었습니다.")
        #                             else : 
        #                                 loop_buy = False
        #                                 break
        #                     else:
        #                         print(stockcode[0], "매수 할수 없는 종목입니다.")
        #                         break
        #                 time.sleep(300/1000)
                        
        #             else:
        #                 continue
        #         else:
        #             continue
                

        # #매수 상황 db로 전송
        # stock_val_lists = KDatabaseTrade.remainder_lists(static_token,stockcode[0],return_val) 

                #result = kt. order(stockcode,qty,buy_price, static_token,omethod)

                #[실전투자]
                        #TTTC0802U : 주식 현금 매수 주문
                        #TTTC0801U : 주식 현금 매도 주문
                        #[모의투자]
                        #VTTC0802U : 주식 현금 매수 주문
                        #VTTC0801U : 주식 현금 매도 주문
            #print(result)
            
        #return redirect(url_for('kinvestor.stock_remainders'))
                # try:
                #     json.dumps(m_data)
                # except TypeError as e:
                #     return str(e)
            
    return jsonify(m_data)