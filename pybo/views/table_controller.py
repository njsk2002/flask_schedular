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

# bp = Flask(__name__)

bp = Blueprint('ktable',__name__,url_prefix='/ktable')

# 'Agg' 백엔드 사용
plt.switch_backend('Agg')

# 현재 실행 중인 연결 객체
current_connection = None

#plt 한글설정
plt.rcParams['font.family'] = 'Malgun Gothic'



@bp.route('/create')
def create_table():
    # 입력파라메터
    stockcode = request.args.get('stockcode', type=str, default='')  # 페이지
    table_name = 'temp_table_' + stockcode
    create_temp_table(table_name)
    return f"Temporary table '{table_name}' created."

@bp.route('/drop')
def drop_table():
    stockcode = request.args.get('stockcode', type=str, default='')  # 페이지
    table_name = 'temp_table_' + stockcode
    drop_temp_table(table_name)
    return f"Temporary table '{table_name}' dropped."

# @bp.route('/insert/<table_name>', methods=['POST'])
# def insert_data(table_name):
#     data = request.form['data']
#     metadata = MetaData()
#     temp_table = Table(table_name, metadata, autoload_with=db.engine)
#     ins = temp_table.insert().values(data=data)
#     db.engine.execute(ins)
#     return f"Data inserted into table '{table_name}'."

# @bp.route('/get_data/<table_name>')
# def get_data(table_name):
#     metadata = MetaData()
#     temp_table = Table(table_name, metadata, autoload_with=db.engine)
#     sel = temp_table.select()
#     result = db.engine.execute(sel)
#     data = result.fetchall()
#     return {"data": [dict(row) for row in data]}


def create_temp_table(table_name):
    metadata = MetaData()
    temp_table = Table(
        table_name, metadata,
        Column('no', Integer, primary_key=True),
        Column('currentvalue', String(150), unique=True, nullable=False),
        Column('previousvalue', String(150), unique=True, nullable=False),
        Column('acmlvol', String(150), unique=True, nullable=False), #누적거래량
        Column('diffrate', String(150), unique=True, nullable=False),
        Column('daffval', String(150), unique=True, nullable=False),
       
        Column('tradetime', String(150), unique=True, nullable=False),
        Column('open', String(150), unique=True, nullable=False),
        Column('high', String(150), unique=True, nullable=False),
        Column('low', String(150), unique=True, nullable=False),
        Column('close', String(150), unique=True, nullable=False),
        Column('tradevol', String(150), unique=True, nullable=False),
    )

    metadata.create_all(db.engine)
    return temp_table

def drop_temp_table(table_name):
    metadata = MetaData()
    temp_table = Table(table_name, metadata, autoload_with=db.engine)
    temp_table.drop(db.engine)