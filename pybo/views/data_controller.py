from datetime import datetime, timedelta
from openpyxl import Workbook
import openpyxl    
import asyncio
import time
import os
import pandas as pd
#from aioflask import Flask, request, jsonify, Blueprint, render_template,url_for
from flask import Flask, request, jsonify, Blueprint, render_template,url_for
from werkzeug.utils import redirect
from ..models import Stockinfo, Chartinfo, StockinfoTemp, Token_temp, ObserveStock, StockListFromVB, ObserveStockFromVB
import json
from .. import db
from sqlalchemy import func
from ..service.k_trade import KTrade
from ..service.k_analysis import KAnalysis
from ..service.k_value import KValue
from ..service.k_realdata import RealTimeData,RealData
from ..data_search.naver_search import NaverSearch


import websockets
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

# bp = Flask(__name__)

bp = Blueprint('kdata',__name__,url_prefix='/kdata')

# 현재 실행 중인 연결 객체
current_connection = None

@bp.route('/navernews')
def naver_news():
    nc = NaverSearch()
    #stock_list =  Stockinfo.query.order_by(Stockinfo.stockcode) 
    stock_info = db.session.query(Stockinfo.stockcode, Stockinfo.stockname).order_by(Stockinfo.stockcode).all()

    for count, (stockcode, stockname) in enumerate(stock_info, start=1): #카운트추가
        if count <= 5:
            key_word = stockname + ' '+ '테마' + ' ' + '주식'
            print('키워드는? ',key_word)
            num_search = 1
            num_per_page = 5
            nc.navernews_search(stockcode,stockname,key_word, num_search, num_per_page )
            print('종목수누적: ', count)

    return 'ok'

# blogsearch
@bp.route('/naverblog')
def naver_blog():
    nc = NaverSearch()
    #stock_list =  Stockinfo.query.order_by(Stockinfo.stockcode) 
    stock_info = db.session.query(Stockinfo.stockcode, Stockinfo.stockname).order_by(Stockinfo.stockcode).all()

    for count, (stockcode, stockname) in enumerate(stock_info, start=1): #카운트추가
        if count <= 3894:
            key_word = stockname + ' '+ '테마' + ' ' + '주식'
            print('키워드는? ',key_word)
            num_search = 1
            num_per_page = 99
            nc.naverblog_search(stockcode,stockname,key_word, num_search, num_per_page )
            print('종목수누적: ', count)

    return 'ok'



@bp.route('/sortblog1')
def sort_blog_1():
    nc = NaverSearch()
    # 디렉토리 경로 설정
    directory = 'C:/projects/blogdata/rowdata/'

    # 디렉토리 내의 모든 파일 경로 찾기
    file_paths = [os.path.join(directory, file) for file in os.listdir(directory) if file.endswith('.csv')]
    ## 디렉토리 내의 모든 CSV 파일명 가져오기
    file_names = [file for file in os.listdir(directory) if file.endswith('.csv')]

    # 모든 파일의 데이터를 담을 빈 리스트 생성
    all_data = []

    # 각 파일을 읽어와서 데이터를 결합
    for file_name in file_names:
        #data = pd.read_csv(file_path)
        print(file_name)        
        nc.word_sort(file_name)

    return 'ok'
