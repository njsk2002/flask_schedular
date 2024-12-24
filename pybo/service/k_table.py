from datetime import datetime, timedelta
from openpyxl import Workbook
import openpyxl    
import asyncio
import time
import pandas as pd
import matplotlib.pyplot as plt
import base64
import mplfinance as mpf
#from pylab import *
import os
import io
#from aioflask import Flask, request, jsonify, Blueprint, render_template,url_for
from flask import Flask, request, jsonify, Blueprint, render_template,url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc, and_, Table, Column, Integer, String, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import aliased

from werkzeug.utils import redirect
from ..models import Stockinfo, Chartinfo, StockinfoTemp,Token_temp, ObserveStock, StockListFromVB, ObserveStockFromVB, DailyDataFromVB, StockListFromKInvestor,ThemeCode,StockBalanceLists
import json
from .. import db


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




class KTempTable():
    def create_min_table(stockcode,method):
        if method == 'observe':
            table_name = 'table_min_' + stockcode
        elif method == 'daily':
            table_name = 'daily_min_' + stockcode
        metadata = MetaData()
        temp_table = Table(
            table_name, metadata,
            Column('no', Integer, primary_key=True),
            Column('currentvalue', String(150),default='0'),
            Column('previousvalue', String(150),default='0'),
            Column('acmlvol', String(150),default='0'), #누적거래량
            Column('diffrate', String(150),default='0'),
            Column('daffval', String(150),default='0'),
        
            Column('tradetime', String(150),default='0'),
            Column('open', String(150),default='0'),
            Column('high', String(150),default='0'),
            Column('low', String(150),default='0'),
            Column('close', String(150),default='0'),
            Column('tradevol', String(150),default='0'),
        )

        metadata.create_all(db.engine)
        return temp_table
    
    #stockcode가 'all'일 경우, "table_min_"로 시작하는 모든 테이블 삭제
    def drop_min_table(stockcode,method):
        if stockcode == 'all': 
            if method == 'observe':    
                prefix = 'table_min_'
            elif method == 'daily':
                prefix = 'daily_min_'
            metadata = MetaData()
            metadata.reflect(bind=db.engine)

            tables_to_drop = [table for table in metadata.tables.keys() if table.startswith(prefix)]

            # # 빈 리스트를 생성합니다.
            # tables_to_drop = []

            # # 모든 테이블 이름을 반복하면서 필터링합니다.
            # for table_name in metadata.tables.keys():
            #     if table_name.startswith(prefix):
            #         tables_to_drop.append(table_name)
        
            for table_name in tables_to_drop:
                table = metadata.tables[table_name]
                table.drop(db.engine)
        else:
            table_name = 'table_min_' + stockcode
            metadata = MetaData()
            temp_table = Table(table_name, metadata, autoload_with=db.engine)
            temp_table.drop(db.engine)

        return True
