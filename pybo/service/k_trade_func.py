from datetime import datetime, timedelta
from openpyxl import Workbook
import openpyxl    
import asyncio
import time
import pandas as pd
#from aioflask import Flask, request, jsonify, Blueprint, render_template,url_for
from flask import Flask, request, jsonify, Blueprint, render_template,url_for
from werkzeug.utils import redirect
from ..models import Stockinfo, Chartinfo, StockinfoTemp, Token_temp, ObserveStock, StockListFromVB, ObserveStockFromVB
import json
from .. import db
from sqlalchemy import func
from ..service.k_trade import KTrade
from ..service.k_value import KValue
from ..service.k_realdata import RealTimeData,RealData
#from ..views.stock_controller import call_token, call_token_mock
from collections import defaultdict


import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

class KTradeFunc():
    def trade_buy(self,assigned_price,stockcode,static_token):
         
        kt = KTrade()
        kv = KValue()
        kr = RealTimeData()
        kd = RealData()
        kf = KTradeFunc()
        
        while True:
            #time.sleep(0.5)
            c_data = KValue.current_value(stockcode,static_token) # 현재가
            #print(self,assigned_price,stockcode,static_token)
            #c_data = KValue.changeorder(stockcode,static_token) # 체결가 (요게 좀 리턴값이 심플)
            print("c 데이터는=",c_data)
            

            if c_data != None:
                #current_value # 현재가 실행했을때
                hoka_unit = self.value_unit(int(c_data.get('stck_prpr')))
                buy_qty_int = int(int(assigned_price) / int(c_data.get('stck_prpr'))) # 소숫점 제거
                buy_qty_1 = int(int(assigned_price) / (int(c_data.get('stck_prpr')) - hoka_unit)) #현재가 대비호가 하나 밑에

               
                # changeorder( # 체결가 (요게 좀 리턴값이 심플) 실행했을때           
                # hoka_unit = self.value_unit(int(c_data[0]['stck_prpr']))
                # buy_qty_int = int(int(assigned_price) / int(c_data[0]['stck_prpr'])) # 소숫점 제거
                # buy_qty_1 = int(int(assigned_price) / (int(c_data[0]['stck_prpr']) - hoka_unit)) #현재가 대비호가 하나 밑에
                 
                order_qty = round(buy_qty_int* 0.5) + int(buy_qty_1 *0.5)
                
                buy_qty = str(buy_qty_int) # str 변경
                # if omethod == '00':
                ordermethod = "VTTC0802U"
                # elif omethod =='11':
                #     ordermethod = "VTTC0801U"

                # [실전투자]
                # TTTC0802U : 주식 현금 매수 주문
                # TTTC0801U : 주식 현금 매도 주문

                # [모의투자]
                # VTTC0802U : 주식 현금 매수 주문
                # VTTC0801U : 주식 현금 매도 주문
                #매수/매도 함수 호출
                ### current_Value 호출시 

                price_buy = c_data.get('stck_prpr')
                #time.sleep(0.5)
                rt_cd_value, odno_value , msg_cd= KTrade.order(stockcode,buy_qty,price_buy , static_token,ordermethod)
                print(stockcode,buy_qty,c_data.get('stck_prpr'), static_token,ordermethod)
                #### changeorder요청시
                #print(stockcode,buy_qty,c_data[0]['stck_prpr'], static_token,ordermethod)
                #rt_cd_value, odno_value = KTrade.order(stockcode,buy_qty,c_data[0]['stck_prpr'], static_token,ordermethod)
                #time.sleep(1000)
                print("리턴값= ", rt_cd_value, odno_value, buy_qty, price_buy )
                if rt_cd_value == '0' :
                    break
                elif rt_cd_value =='1' and msg_cd =="40070000":
                    print(stockcode, '거래할수 없는 종목 입니다.')
                    print(stockcode, '거래할수 없는 종목 입니다.')
                    print(stockcode, '거래할수 없는 종목 입니다.')
                    print(stockcode, '거래할수 없는 종목 입니다.')
                    break
                else:
                    continue
        return odno_value, buy_qty, price_buy 
    

    def trade_sell(self,stockcode,sell_qty,static_token):
         
        kt = KTrade()
        kv = KValue()
        kr = RealTimeData()
        kd = RealData()
        kf = KTradeFunc()
        
        while True:
            #time.sleep(0.5)
            c_data = KValue.current_value(stockcode,static_token) # 현재가
            #print(self,assigned_price,stockcode,static_token)
            #c_data = KValue.changeorder(stockcode,static_token) # 체결가 (요게 좀 리턴값이 심플)
            print("c 데이터는=",c_data)
            

            if c_data != None:
                #current_value # 현재가 실행했을때
                hoka_unit = self.value_unit(int(c_data.get('stck_prpr')))
                # buy_qty_int = int(int(assigned_price) / int(c_data.get('stck_prpr'))) # 소숫점 제거
                # buy_qty_1 = int(int(assigned_price) / (int(c_data.get('stck_prpr')) - hoka_unit)) #현재가 대비호가 하나 밑에

               
                # changeorder( # 체결가 (요게 좀 리턴값이 심플) 실행했을때           
                # hoka_unit = self.value_unit(int(c_data[0]['stck_prpr']))
                # buy_qty_int = int(int(assigned_price) / int(c_data[0]['stck_prpr'])) # 소숫점 제거
                # buy_qty_1 = int(int(assigned_price) / (int(c_data[0]['stck_prpr']) - hoka_unit)) #현재가 대비호가 하나 밑에
                 
                #order_qty = round(buy_qty_int* 0.5) + int(buy_qty_1 *0.5)
                
                #buy_qty = str(buy_qty_int) # str 변경
                # if omethod == '00':
                ordermethod = "VTTC0801U"
                # elif omethod =='11':
                #     ordermethod = "VTTC0801U"

                # [실전투자]
                # TTTC0802U : 주식 현금 매수 주문
                # TTTC0801U : 주식 현금 매도 주문

                # [모의투자]
                # VTTC0802U : 주식 현금 매수 주문
                # VTTC0801U : 주식 현금 매도 주문
                #매수/매도 함수 호출
                ### current_Value 호출시 

                price_sell = c_data.get('stck_prpr')
                #time.sleep(0.5)
                rt_cd_value, odno_value, msg_cd = KTrade.order(stockcode,sell_qty, price_sell, static_token,ordermethod)
                #print(stockcode,sell_qty,c_data.get('stck_prpr'), static_token,ordermethod)
                #### changeorder요청시
                #print(stockcode,buy_qty,c_data[0]['stck_prpr'], static_token,ordermethod)
                #rt_cd_value, odno_value = KTrade.order(stockcode,buy_qty,c_data[0]['stck_prpr'], static_token,ordermethod)
                #time.sleep(1000)
                print("리턴값= ", rt_cd_value, odno_value,msg_cd, sell_qty, price_sell )
                if rt_cd_value == '0' :
                    break
                else:
                    continue
        return odno_value, sell_qty, price_sell
    

    def trade_revise(self,stockcode,static_token,order_no,price_buy,select):
            
            kt = KTrade()
            kv = KValue()
            kr = RealTimeData()
            kd = RealData()
            kf = KTradeFunc()
            
            while True:
                #c_data = KValue.current_value(stockcode,static_token) # 현재가
                #time.sleep(0.5)
                c_data = KValue.changeorder(stockcode,static_token) # 체결가 (요게 좀 리턴값이 심플)


                if c_data != None:
                # changeorder( # 체결가 (요게 좀 리턴값이 심플) 실행했을때           
                    hoka_unit = self.value_unit(int(c_data[0]['stck_prpr']))

                    # if omethod == '00':
                    ordermethod = "VTTC0803U"   # [실전투자] TTTC0803U : 주식 정정 취소 주문  [모의투자] VTTC0803U : 주식 정정 취소 주문
                    selectorder = "01"  # 정정01  취소:02
                    buy_qty = "0" 	#[잔량전부 취소/정정주문] "0" 설정 ( QTY_ALL_ORD_YN=Y 설정 )
                    print("원래값", price_buy)
                    print("읽은값", c_data[0]['stck_prpr'])
                    if int(price_buy) == int(c_data[0]['stck_prpr']):
                        if select == 'buy':
                            buyprice = int(price_buy) + hoka_unit
                        elif select == 'sell':
                            buyprice = int(price_buy) - hoka_unit
                        buy_price = str(buyprice)
                        print('호가더한 가격:', buy_price)
                    else:
                        buy_price = c_data[0]['stck_prpr']
                    print("정정가격 " ,buy_price)
                    #time.sleep(0.5)
                    rt_cd_value, odno_value , msg_cd = KTrade.changeorder(order_no,buy_qty,buy_price,static_token,ordermethod, selectorder)

                    print("리턴값= ", rt_cd_value, odno_value, msg_cd, buy_price)
                    if rt_cd_value == '0' or (rt_cd_value == '1' and msg_cd =="40330000"):
                        break

                    elif rt_cd_value == '1' and msg_cd =="40610000":
                        print('===============================')
                        print('모의투자 주문번호 없음!! 확인 필요')
                        print('모의투자 주문번호 없음!! 확인 필요')
                        print('================================')
                        break

                    else:
                        continue

            return rt_cd_value, odno_value, msg_cd, buy_price
    


        #result = kt. order(stockcode,qty,buy_price, static_token,omethod)

    # 주식 가격별 호가 단위
    def value_unit(self,price): 

        if price < 2000:
            hoka_unit = 1
        elif price >=2000 and price < 5000:
            hoka_unit = 5
        elif price >=5000 and price <20000:
            hoka_unit = 10
        elif price >=20000 and price < 50000:
            hoka_unit = 50
        elif price >=50000 and price < 200000:
            hoka_unit = 100
        elif price >= 200000 and price < 500000:
            hoka_unit = 5000
        else: 
            hoka_unit = 1000
        
        return hoka_unit
         
    