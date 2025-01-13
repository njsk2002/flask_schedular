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
from .k_trade import KTrade
from .k_func import KFunction
from .k_analysis import KAnalysis
from .k_value import KValue
from .k_realdata import RealTimeData,RealData



import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

class KCalcuration():


    def cal_mindata(m_data):
         
        # 주어진 데이터

        # m_data의 길이 구하기
        length= len(m_data)
        #print("Length of m_data:", length_m_data)

        # 3,5,10,20  간격으로 데이터 저장 -- 심플방식
        #three_minute_data = [m_data[i:i+3] for i in range(1, len(m_data)-2)] #  simple 방식 
        # five_minute_data = [m_data[i:i+5] for i in range(1, len(m_data)-4)]
        # ten_minute_data = [m_data[i:i+10] for i in range(1, len(m_data)-9)]
        # twenty_minute_data = [m_data[i:i+20] for i in range(1, len(m_data)-19)]


        # 3분 간격 데이터를 저장할 리스트를 초기화합니다
        min3_ori_data = []
        # 3분 간격의 하위 리스트를 생성하는 루프
        if length >= 3:
            for i in range(1, length - 2):
                temp_data = m_data[i:i+3]
                min3_ori_data.append(temp_data)

            # 평균 및 합계 데이터를 저장할 리스트를 초기화합니다
            min3_data = []

            # 각 3분 간격을 반복합니다
            for window in min3_ori_data:
                # 'stck_prpr' 값의 평균을 계산하여 end_prc_avg에 저장합니다
                end_prc_avg = sum(int(item['stck_prpr']) for item in window) // 3
                # 'cntg_vol' 값의 합계를 계산하여 trade_vol_sum에 저장합니다
                trade_vol_sum = sum(int(item['cntg_vol']) for item in window)
                # 계산된 값을 딕셔너리로 min3_data에 추가합니다
                min3_data.append({'end_prc_avg': end_prc_avg, 'trade_vol_sum': trade_vol_sum})
        else:
            min3_data = 0

            # 5분 간격 데이터를 저장할 리스트를 초기화합니다
        min5_ori_data = []
        # 5분 간격의 하위 리스트를 생성하는 루프
        if length >= 5:
            for i in range(1, length - 4):
                temp_data = m_data[i:i+5]
                min5_ori_data.append(temp_data)

            # 평균 및 합계 데이터를 저장할 리스트를 초기화합니다
            min5_data = []

            # 각 5분 간격을 반복합니다
            for window in min5_ori_data:
                # 'stck_prpr' 값의 평균을 계산하여 end_prc_avg에 저장합니다
                end_prc_avg = sum(int(item['stck_prpr']) for item in window) // 5
                # 'cntg_vol' 값의 합계를 계산하여 trade_vol_sum에 저장합니다
                trade_vol_sum = sum(int(item['cntg_vol']) for item in window)
                # 계산된 값을 딕셔너리로 min5_data에 추가합니다
                min5_data.append({'end_prc_avg': end_prc_avg, 'trade_vol_sum': trade_vol_sum})
        else:
            min5_data = 0

        # 10분 간격 데이터를 저장할 리스트를 초기화합니다
        min10_ori_data = []
        # 10분 간격의 하위 리스트를 생성하는 루프
        if length >= 10:
            for i in range(1, length - 9):
                temp_data = m_data[i:i+10]
                min10_ori_data.append(temp_data)

            # 평균 및 합계 데이터를 저장할 리스트를 초기화합니다
            min10_data = []

            # 각 10분 간격을 반복합니다
            for window in min10_ori_data:
                # 'stck_prpr' 값의 평균을 계산하여 end_prc_avg에 저장합니다
                end_prc_avg = sum(int(item['stck_prpr']) for item in window) // 10
                # 'cntg_vol' 값의 합계를 계산하여 trade_vol_sum에 저장합니다
                trade_vol_sum = sum(int(item['cntg_vol']) for item in window)
                # 계산된 값을 딕셔너리로 min10_data에 추가합니다
                min10_data.append({'end_prc_avg': end_prc_avg, 'trade_vol_sum': trade_vol_sum})
        else:
            min10_data = 0

        # 20분 간격 데이터를 저장할 리스트를 초기화합니다
        min20_ori_data = []
        # 20분 간격의 하위 리스트를 생성하는 루프
        if length >= 20:
            for i in range(1, length - 19):
                temp_data = m_data[i:i+20]
                min20_ori_data.append(temp_data)

        # 평균 및 합계 데이터를 저장할 리스트를 초기화합니다
            min20_data = []
            # 각 20분 간격을 반복합니다
            for window in min20_ori_data:
                # 'stck_prpr' 값의 평균을 계산하여 end_prc_avg에 저장합니다
                end_prc_avg = sum(int(item['stck_prpr']) for item in window) // 20
                # 'cntg_vol' 값의 합계를 계산하여 trade_vol_sum에 저장합니다
                trade_vol_sum = sum(int(item['cntg_vol']) for item in window)
                # 계산된 값을 딕셔너리로 min20_data에 추가합니다
                min20_data.append({'end_prc_avg': end_prc_avg, 'trade_vol_sum': trade_vol_sum})
        else:
            min20_data = 0

        # 30분 간격 데이터를 저장할 리스트를 초기화합니다
        min30_ori_data = []
        # 30분 간격의 하위 리스트를 생성하는 루프
        if length >= 30:
            for i in range(1, length - 29):
                temp_data = m_data[i:i+30]
                min30_ori_data.append(temp_data)

            # 평균 및 합계 데이터를 저장할 리스트를 초기화합니다
            min30_data = []

            # 각 30분 간격을 반복합니다
            for window in min30_ori_data:
                # 'stck_prpr' 값의 평균을 계산하여 end_prc_avg에 저장합니다
                end_prc_avg = sum(int(item['stck_prpr']) for item in window) // 30
                # 'cntg_vol' 값의 합계를 계산하여 trade_vol_sum에 저장합니다
                trade_vol_sum = sum(int(item['cntg_vol']) for item in window)
                # 계산된 값을 딕셔너리로 min30_data에 추가합니다
                min30_data.append({'end_prc_avg': end_prc_avg, 'trade_vol_sum': trade_vol_sum})
        else:
            min30_data = 0

        # 60분 간격 데이터를 저장할 리스트를 초기화합니다
        min60_ori_data = []
      # 60분 간격의 하위 리스트를 생성하는 루프
        if length >= 60:
            for i in range(1, length - 59):
                temp_data = m_data[i:i+60]
                min60_ori_data.append(temp_data)

            # 평균 및 합계 데이터를 저장할 리스트를 초기화합니다
            min60_data = []

            # 각 60분 간격을 반복합니다
            for window in min60_ori_data:
                # 'stck_prpr' 값의 평균을 계산하여 end_prc_avg에 저장합니다
                end_prc_avg = sum(int(item['stck_prpr']) for item in window) // 60
                # 'cntg_vol' 값의 합계를 계산하여 trade_vol_sum에 저장합니다
                trade_vol_sum = sum(int(item['cntg_vol']) for item in window)
                # 계산된 값을 딕셔너리로 min60_data에 추가합니다
                min60_data.append({'end_prc_avg': end_prc_avg, 'trade_vol_sum': trade_vol_sum})
        else:
            min60_data = 0

        # 120분 간격 데이터를 저장할 리스트를 초기화합니다
        min120_ori_data = []
        # 120분 간격의 하위 리스트를 생성하는 루프
        if length >= 120:
            for i in range(1, length - 119):
                temp_data = m_data[i:i+120]
                min120_ori_data.append(temp_data)

        # 평균 및 합계 데이터를 저장할 리스트를 초기화합니다
            min120_data = []
            # 각 120분 간격을 반복합니다
            for window in min120_ori_data:
                # 'stck_prpr' 값의 평균을 계산하여 end_prc_avg에 저장합니다
                end_prc_avg = sum(int(item['stck_prpr']) for item in window) // 120
                # 'cntg_vol' 값의 합계를 계산하여 trade_vol_sum에 저장합니다
                trade_vol_sum = sum(int(item['cntg_vol']) for item in window)
                # 계산된 값을 딕셔너리로 min120_data에 추가합니다
                min120_data.append({'end_prc_avg': end_prc_avg, 'trade_vol_sum': trade_vol_sum})
        else:
            min120_data = 0
        # 결과를 출력합니다
        # print("3-minute interval data with averages and sums:", min3_data)
        # print("5-minute interval data with averages and sums:", min5_data)
        # print("10-minute interval data with averages and sums:", min10_data)
        # print("20-minute interval data with averages and sums:", min20_data)
        # print("30-minute interval data with averages and sums:", min30_data)
        # print("60-minute interval data with averages and sums:", min60_data)
        # print("120-minute interval data with averages and sums:", min120_data)

        # if length == 3:
        #     return min3_data
        # if length <= 5: 
        #    return min3_data,min5_data
        # if length <= 10:
        #     return min3_data, min5_data, min10_data
        # if length <= 20:
        #     return min3_data, min5_data, min10_data, min20_data
        # if length <= 30:
        #     return min3_data, min5_data, min10_data, min20_data, min30_data
        # if length <= 60:
        #     return min3_data, min5_data, min10_data, min20_data, min30_data, min60_data
        # if length <= 120:
        return min3_data, min5_data, min10_data, min20_data, min30_data, min60_data, min120_data
    

    def regular_market(c_data,min_datas,m_len,method_type,stockcode,static_token):

        #mindatas [0]~ min3,min5,min10,min20,min30,min60,min120
        
        # 오늘,어제, 현재시간(6자리),현재시간(hhmm00 분봉용) 호출 6자리()
        todate,ydate,totime,totime00 = KFunction.date_info(0)
        
        print("c_data", c_data)
        openprice = c_data.get('stck_oprc', 0) # 시가
        highprice = c_data.get('stck_hgpr', 0)
        lowprice = c_data.get('stck_lwpr', 0)
        maxprice = c_data.get('stck_mxpr', 0)
        minprice = c_data.get('stck_llam', 0)
        stdprice = c_data.get('stck_sdpr', 0) # 주식 기준가
        currprice = c_data.get('stck_prpr', 0) # 현재가
        price_vs_pre = c_data.get('prdy_vrss', 0)
        rate_vs_pre = c_data.get('prdy_ctrt', 0)
        tradevol = c_data.get('acml_vol', 0)
        trade_rate_pre = c_data.get('prdy_vrss_vol_rate', 0)
        vi_state = c_data.get('vi_cls_code', 0)
        wg_stock_price = c_data.get('wghn_avrg_stck_prc', 0) #	가중 평균 주식 가격
            
        print("데이터는?", openprice,currprice, method_type)
       

        if method_type == 'observe':
            if int(currprice) >=  (int(openprice) * 1.02) and totime <= '120000':           
                result = KFunction.buy_autorun(stockcode,method_type,static_token)
                print("매수 결과는?", result)
        
        elif method_type == 'remain':
            if int(currprice) >= (int(stockcode[2]) * 1.02) and int(stockcode[3]) <= 10000000 and  totime <= '143000':
                result = KFunction.buy_autorun(stockcode[0],method_type,static_token)

            elif float(stockcode[7]) < -1.9 :
                result = KFunction.sell_autorun(stockcode[1],method_type,stockcode[8],static_token)

                # StockBalanceLists.stockcode,
                # StockBalanceLists.category,
                # StockBalanceLists.buyprice,
                # StockBalanceLists.buyamount,
                # StockBalanceLists.remainderqty,
                # StockBalanceLists.evalprice, #평가금액
                # StockBalanceLists.evalpriceamount, # 평가금액  - 매입금액
                # StockBalanceLists.evalrate # 수익률
                # StockBalanceLists.no # 

        return True    
    
    # 장 시작전 예상 체결
    def anticipation_market(p_data,method_type,stockcode,static_token):

        #mindatas [0]~ min3,min5,min10,min20,min30,min60,min120


        # 오늘,어제, 현재시간(6자리),현재시간(hhmm00 분봉용) 호출 6자리()
        todate,ydate,totime,totime00 = KFunction.date_info(0)
        
        print("p_data", p_data)
        openprice = p_data.get('stck_oprc', 0) # 시가
        highprice = p_data.get('stck_hgpr', 0)
        lowprice = p_data.get('stck_lwpr', 0)
        stdprice = p_data.get('stck_sdpr', 0) # 주식 기준가       
        currprice = p_data.get('stck_prpr', 0) # 현재가

        antprice = p_data.get('antc_cnpr', 0) # 예상 체결가 (9시 이전 또는 VI)
        antprice_vs_pre = p_data.get('antc_cntg_vrss', 0) #예상체결 대비
        antrate_vs_pre = p_data.get('antc_cntg_prdy_ctrt', 0)#예상체결률
        anttradevol = p_data.get('antc_vol', 0)
        
        vi_state = p_data.get('vi_cls_code', 0)
        begin_antmarket = p_data.get('antc_mkop_cls_code', 0)  #311 : 예상체결시작 112 : 예상체결종료
            
        print("데이터는?", openprice,currprice, method_type)
        # 매수 
        if method_type == 'observe':
            if int(antprice) >= (int(stdprice) * 1.02) and totime <= '090000':           
                result = KFunction.buy_autorun(stockcode,method_type,static_token)
                print("매수 결과는?", result)
        
        elif method_type == 'remain':
            if  int(antprice) >= (int(stockcode[2]) * 1.02) and int(stockcode[3]) <= 10000000 and anttradevol > 50000 and  totime <= '090000':
                result = KFunction.buy_autorun(stockcode[0],method_type,static_token)
               
        # 매도 
            elif int(antprice) <= (int(stockcode[2]) * 0.98) and int(anttradevol) > 30000 and  totime <= '090000':
                 result = KFunction.sell_autorun(stockcode[1],method_type,stockcode[8],static_token)
            

        return True    