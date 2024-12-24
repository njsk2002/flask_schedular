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
from .k_trade import KTrade
from .k_analysis import KAnalysis
from .k_value import KValue
from .k_realdata import RealTimeData,RealData


import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode



class KDatabaseTrade():
    def remainder_qty(stockcode,tokenP, ydate,method, method_type):
     #잔고 조회 -- 모의투자의 경우 주문잔량 수량을 제공하지 않음으로 ,부득히 매수전 잔고를 확인하여 체결 수량 계산 필요.
        #time.sleep(0.5)
        r_data = KTrade.trade_remainder_list(tokenP)
        print ("잔고내역", r_data)
                
        if r_data:
            for item in r_data:
                print(item['pdno'])
                if item['pdno'] == stockcode:
                    stock_qty = item['hldg_qty']
                    print ('수량 :', stock_qty)
                    break
                else:
                    stock_qty = '0'
        else:
            stock_qty = '0'            
        #db로 전송
        print(stockcode, stock_qty)

        if method_type == 'observe': # 매수 대기 항목 매수(추가매수시)
            update_qty = ObserveStockFromVB.query.filter_by(stockcode=stockcode, method_1 = '1').first()
        
        elif method_type == 'remain':  # 보유 항목 추가 매수시
            update_qty = StockBalanceLists.query.filter_by(stockcode=stockcode).first()

       
        if method == '0' or method =='2': # 거래할 종목 최초 잔고 수량
            update_qty.initqty = stock_qty
        elif method == '1': # 일부 매수/매도 후 거래 수량
            update_qty.remainqty = stock_qty

        db.session.commit()

        if method == '0' or method == '1':
            return True
        elif method == '2':
            return True, stock_qty
    

    def osfv_db(stockcode, order_no, buy_qty, price_buy, ydate, method_type):
        
        update = None
        orderno_value = None

        if method_type == 'observe': # 매수 대기 항목 매수(추가매수시)
            update = ObserveStockFromVB.query.filter_by(stockcode=stockcode, method_1='1').first()
        elif method_type == 'remain':  # 보유 항목 추가 매수시
            update = StockBalanceLists.query.filter_by(stockcode=stockcode).first()
            
        if update:
            update.orderno = order_no      
            if buy_qty != 'no':
                update.buyqty = buy_qty
            update.buyprice = price_buy
            db.session.commit()
        else:
            print("update 값이 없습니다.")
    

        if method_type == 'observe': # 매수 대기 항목 매수(추가매수시)
            orderno_value = ObserveStockFromVB.query.filter_by(stockcode=stockcode, method_1='1') \
                            .with_entities(ObserveStockFromVB.orderno, ObserveStockFromVB.remainqty, ObserveStockFromVB.initqty, ObserveStockFromVB.buyqty, ObserveStockFromVB.buyprice) \
                            .first()  # 첫 번째 결과만 가져옵니다.   
        elif method_type == 'remain':  # 보유 항목 추가 매수시
            orderno_value = StockBalanceLists.query.filter_by(stockcode=stockcode) \
                            .with_entities(StockBalanceLists.orderno, StockBalanceLists.remainqty, StockBalanceLists.initqty, StockBalanceLists.buyqty, StockBalanceLists.buyprice) \
                            .first()
            
        if orderno_value:
            print(orderno_value.orderno, orderno_value.initqty, orderno_value.remainqty, orderno_value.buyqty, orderno_value.buyprice)
        
        else:
            print(' orderno_value값이 없습니다.!')
        return orderno_value.orderno, orderno_value.initqty, orderno_value.remainqty, orderno_value.buyqty, orderno_value.buyprice

    
 
    

    #체결 완료되면 db에 잔고 수량 업데이트
    def remainder_lists(tokenP,stock_code,return_val):
        #잔고 조회 -- 모의투자의 경우 주문잔량 수량을 제공하지 않음으로 ,부득히 매수전 잔고를 확인하여 체결 수량 계산 필요.
            time.sleep(0.5)
            r_data = KTrade.trade_remainder_list(tokenP)
            print ("잔고내역", r_data)

            #기존 DB값 삭제
            StockBalanceLists.query.delete()
            db.session.commit()                
            if r_data != None:
                for item in r_data:
                    # Chartinfo 객체 생성 및 속성 채우기
                    sbLists = StockBalanceLists(
                        stockcode= item['pdno'],
                        category = 'remain',
                        stockname= item['prdt_name'],
                        remainderqty = item['hldg_qty'],
                        buyprice = str(round(float(item['pchs_avg_pric']))), #평균매매가격
                        buyamount = item['pchs_amt'],

                        currentvalue = item['prpr'],
                        evalprice =  item['evlu_amt'], #평가금액
                        evalpriceamount = item['evlu_pfls_amt'], # 평가금액  - 매입금액
                        evalrate =item['evlu_pfls_rt'],

                        buy_previous= item['bfdy_buy_qty'],
                        sell_previous = item['bfdy_sll_qty'], 
                        buy_today = item['thdt_buyqty'],
                        sell_today= item['thdt_sll_qty']
                
                    )
                # 데이터베이스에 저장
                    db.session.add(sbLists)
                    db.session.commit()

        
            #조회
            if return_val == 'all':
                stock_bal_lists =  StockBalanceLists.query.order_by(StockBalanceLists.stockcode.desc())
                return stock_bal_lists
            elif return_val == 'remainder':
                query_result = db.session.query(StockBalanceLists.remainderqty).filter(StockBalanceLists.stockcode == stock_code).first()
                reminader_qty = query_result.remainderqty if query_result else None
                return reminader_qty















