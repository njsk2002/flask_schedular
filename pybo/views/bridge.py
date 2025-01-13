from datetime import datetime
from flask import Flask, request, jsonify, Blueprint, render_template
from .creon import Creon
from ..models import Stockinfo, Chartinfo
from .. import db
#import constants
from sqlalchemy import func

# bp = Flask(__name__)
c = Creon()
bp = Blueprint('creon',__name__,url_prefix='/creon')

@bp.route('/connection', methods=['GET', 'POST', 'DELETE'])
def handle_connect():
    c = Creon()
    if request.method == 'GET':
        # check connection status
        return jsonify(c.connected())
    elif request.method == 'POST':
        # make connection
        data = request.get_json()
        _id = data['NJSK2003']
        _pwd = data['jhs000']
        _pwdcert = data['']
        return jsonify(c.connect(_id, _pwd, _pwdcert))
    elif request.method == 'DELETE':
        # disconnect
        res = c.disconnect()
        c.kill_client()
        return jsonify(res)

# 종목 코드 조회   
@bp.route('/stocklist/')
def _list():
    #입력파라메터
    page = request.args.get('page', type=int, default=1) #페이지
    kw = request.args.get('kw',type=str, default='')
    so = request.args.get('so', type=str, default='recent')
    
    # #정렬
    # if so == 'recommend':
    #     sub_query = db.session.query(QuestionVoter.question_id, func.count('*').label('num_voter'))\
    #                                  .group_by(QuestionVoter.question_id).subquery()

    #     question_list = Question.query.outerjoin(sub_query, Question.id == sub_query.c.question_id)\
    #     .order_by(sub_query.c.num_voter.desc(), Question.create_date.desc())
    # elif so == 'popular':
    #     sub_query = db.session.query(Answer.question_id, func.count('*').label('num_answer'))\
    #                                  .group_by(Answer.question_id).subquery()

    #     question_list = Question.query.outerjoin(sub_query, Question.id == sub_query.c.question_id)\
    #     .order_by(sub_query.c.num_answer.desc(), Question.create_date.desc())
    # else:
    #     question_list = Question.query.order_by(Question.create_date.desc())

    # #조회
    stock_list =  Stockinfo.query.order_by(Stockinfo.stockcode) 
    # 조회
    
    if kw:
        search = '%%{}%%'.format(kw)
        stock_list = db.session.query(Stockinfo).filter(
        (Stockinfo.stockcode.ilike(search)) | # 주식 코드
        (Stockinfo.stockname.ilike(search)) # 주식 이름
        ).distinct()
 # 페이징
    stock_list = stock_list.paginate(page=page, per_page=10)
    return render_template('stockdata/stock_list.html', stock_list=stock_list, page=page, kw=kw)

#주식 일별 차트 정보 자세히
@bp.route('/detail', methods=['GET'])
def stock_detail():
    # daishin api
    c = Creon()
    c.avoid_reqlimitwarning()

    # 입력 파라미터
    page = request.args.get('page', type=int, default=1)  # 페이지
    kw = request.args.get('kw', type=str, default='')
    so = request.args.get('so', type=str, default='recent')

    stockcode = request.args.get('stockcode')
    n = request.args.get('n', type=str)  
    date_from = request.args.get('from', type=str)
    date_to = request.args.get('to', type=str)
    # n,date_from,date_to의 경우 값이 없을 경우, get 방식으로 수신 시 ''로, 파라메터가 아예 없을 경우에는 None으로 받음에 따라,
    #처리가 용이하도록 '' 일 경우 None으로 무조건 변경
    
    if page == 1 and (n !='' or date_from !='' or date_to !='') :

        if n == '': 
            n = None
        if date_from == '' and date_to =='':
            date_from = None
            date_to = None
        
        if date_from is not None and date_to is not None:
            date_from = date_from.replace('-', '') # "-" 제거
            date_to = date_to.replace('-', '') # "-" 제거

        print("코드1= ", stockcode, "번호= ", n, "시작일=", date_from, "종료일=", date_to)
        if n is None and date_from is None and date_to is None:
            date_from = '20230101'
            date_to = datetime.today().strftime('%Y%m%d')
        print("코드2= ", stockcode, "번호= ", n, "시작일=", date_from, "종료일=", date_to)
        
        if not (n or date_from):
            return 'Need to provide "n" or "date_from" argument.', 400

        # 주식 캔들 데이터 가져오기
        print("코드3= ", stockcode, "번호= ", n, "시작일=", date_from, "종료일=", date_to)
        stockcandles = c.get_chart(stockcode, target='A', unit='D', n=n, date_from=date_from, date_to=date_to)
        
        #기존 DB값 삭제
        Chartinfo.query.delete()
        db.session.commit()

        #API LIST의 각각 DICT 값을 분리
        for data in stockcandles:
            date = str(data['date'])  # 문자열로 변환
            beginval = str(int(data['open']))  # 문자열로 변환
            highval = str(int(data['high']))  # 문자열로 변환
            lowval = str(int(data['low']))  # 문자열로 변환
            endval = str(int(data['close']))  # 문자열로 변환
            changeval = str(int(data['diff']))  # 문자열로 변환
            tradeval = str(data['volume'])  # 문자열로 변환
            tradesum = str(data['price'])  # 문자열로 변환
            changesign = data['diffsign']
            changevol = str(round(data['diffratio'], 1))  # 문자열로 변환

        # Chartinfo 객체 생성 및 속성 채우기
            chartinfo = Chartinfo(
                stockcode=stockcode,
                date=date,
                beginval=beginval,
                highval=highval,
                lowval=lowval,
                endval=endval,
                changeval=changeval,
                tradeval=tradeval,
                tradesum=tradesum,
                changesign=changesign,
                changevol=changevol
            )
        # 데이터베이스에 저장
            db.session.add(chartinfo)
            db.session.commit()
 

    
    #조회
    chart_list =  Chartinfo.query.order_by(Chartinfo.date.desc())

    chart_gragh = Chartinfo.query.order_by(Chartinfo.date).all()
        
    # 2차원 리스트로 변경
    gragh_list = []
    for chart_info in chart_gragh:
        row = [
            chart_info.date,
            int(chart_info.lowval),
            int(chart_info.beginval),
            int(chart_info.endval),
            int(chart_info.highval),
            
           
            # chart_info.changeval,
            # chart_info.tradeval,
            # chart_info.tradesum,
            # chart_info.changesign,
            # chart_info.changevol
        ]
        gragh_list.append(row)

    print(gragh_list)

    chart_count = Chartinfo.query.count() #총수량
    if chart_count >=5:
        avg_5 = db.session.query(func.avg(Chartinfo.endval)).filter(Chartinfo.no.between(1, 5)).scalar()
    if chart_count >=20:
        avg_20 = db.session.query(func.avg(Chartinfo.endval)).filter(Chartinfo.no.between(1, 20)).scalar()
    if chart_count >=60:
        avg_60 = db.session.query(func.avg(Chartinfo.endval)).filter(Chartinfo.no.between(1, 60)).scalar()
    if chart_count >=120:
        avg_120 = db.session.query(func.avg(Chartinfo.endval)).filter(Chartinfo.no.between(1, 120)).scalar()
    if chart_count >=200:
        avg_200 = db.session.query(func.avg(Chartinfo.endval)).filter(Chartinfo.no.between(1, 200)).scalar()

    # 조회
    
    if kw:
        search = '%%{}%%'.format(kw)
        stock_list = db.session.query(Chartinfo).filter(
        (Chartinfo.stockcode.ilike(search)) | # 주식 코드
        (Chartinfo.stockname.ilike(search)) # 주식 이름
        ).distinct()
 # 페이징
    print(chart_list)
    chart_list =chart_list.paginate(page=page, per_page=20)
    
    return render_template('stockdata/stock_detail.html', 
                           chart_list=chart_list, 
                           gragh_list = gragh_list,
                           page=page, 
                           kw=kw, 
                           total_pages=chart_count, 
                           stockcode=stockcode,
                           avg_5 = avg_5,
                           avg_20 = avg_20,
                        #    avg_60 = avg_60,
                        #    avg_120 = avg_120,
                        #    avg_200 = avg_200
                           )





######################   사용 안함 #######################################33
#대신api 정보를 바로 html에 뿌려주는 것으로 페이징의 처리 문제로 인해 일단 사용 안함.
@bp.route('/detail2', methods=['GET'])
def stock_detail2():
    # daishin api
    c = Creon()
    c.avoid_reqlimitwarning()

    # 입력 파라미터
    page = request.args.get('page', type=int, default=1)  # 페이지
    kw = request.args.get('kw', type=str, default='')
    so = request.args.get('so', type=str, default='recent')

    stockcode = request.args.get('stockcode')
    n = request.args.get('n', type=str)  
    date_from = request.args.get('from', type=str)
    date_to = request.args.get('to', type=str)
    # n,date_from,date_to의 경우 값이 없을 경우, get 방식으로 수신 시 ''로, 파라메터가 아예 없을 경우에는 None으로 받음에 따라,
    #처리가 용이하도록 '' 일 경우 None으로 무조건 변경
    if n == '':
        n = None
    elif date_from == '' and date_to =='':
        date_from = None
        date_to = None
    
    if date_from is not None and date_to is not None:
        date_from = date_from.replace('-', '') # "-" 제거
        date_to = date_to.replace('-', '') # "-" 제거

    print("코드= ", stockcode, "번호= ", n, "시작일=", date_from, "종료일=", date_to)
    if n is None and date_from is None and date_to is None:
        date_from = request.args.get('from', type=str, default='20240101')
        date_to = request.args.get('to', type=str, default=datetime.today().strftime('%Y%m%d'))
    
       
    if not (n or date_from):
        return 'Need to provide "n" or "date_from" argument.', 400

     # 주식 캔들 데이터 가져오기
    print("코드= ", stockcode, "번호= ", n, "시작일=", date_from, "종료일=", date_to)
    stockcandles = c.get_chart(stockcode, target='A', unit='D', n=n, date_from=date_from, date_to=date_to)
    
    # 데이터를 페이징 가능한 객체로 변환
    stockcandles_paged = paginate_data(stockcandles, page=page, per_page=10)
    
    # 페이징 처리를 위해 총 페이지 수 계산
    total_pages = len(stockcandles) // 10 + (1 if len(stockcandles) % 10 > 0 else 0)
    
    # 템플릿으로 전달할 데이터에 총 페이지 수 추가
    return render_template('stockdata/stock_detail.html', stock_graph=stockcandles_paged, page=page, kw=kw, total_pages=total_pages, stockcode=stockcode)


def paginate_data(data, page=1, per_page=10):
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_data = data[start_idx:end_idx]
    print(paginated_data)
    return paginated_data


    # 기업정보 요청
    

# 기본 종목코드(거래소,코스탁) 업데이트 시를 제외하고는 사용 금지(수동으로 url 입력)
@bp.route('/stockcodes/', methods=['GET'])
def handle_stockcodes():
    c = Creon()
    c.avoid_reqlimitwarning()
    market = request.args.get('market')
    stock_info_list = []
    if market == 'kospi':
        stock_info_list = c.get_stockcodes(1)  # StockInfoVO 객체들의 리스트를 반환하는 함수 호출

        for stock_info in stock_info_list:
            stockcode = stock_info.stockcode
            secondcode = stock_info.secondcode
            stockname = stock_info.stockname
            currentvalue = stock_info.stdprice
            print(stockcode)

            stockinfo = Stockinfo(stockcode=stockcode,category="1", secondcode=secondcode ,stockname=stockname,currentvalue=currentvalue,create_date=datetime.now(),modify_date=datetime.now())
            db.session.add(stockinfo)
            db.session.commit()
    
        return 'Data saved to database successfully'
    
    elif market == 'kosdaq':
        stock_info_list = c.get_stockcodes(2)  # StockInfoVO 객체들의 리스트를 반환하는 함수 호출
        
        for stock_info in stock_info_list:
            stockcode = stock_info.stockcode
            secondcode = stock_info.secondcode
            stockname = stock_info.stockname
            currentvalue = stock_info.stdprice
            print(stockcode)

            stockinfo = Stockinfo(stockcode=stockcode,category="2", secondcode=secondcode ,stockname=stockname,currentvalue=currentvalue,create_date=datetime.now(),modify_date=datetime.now())
            db.session.add(stockinfo)
            db.session.commit()
    
        return 'Data saved to database successfully'
    else:
        return '"market" should be one of "kospi" and "kosdaq".', 400


    

@bp.route('/stockstatus', methods=['GET'])
def handle_stockstatus():
    c = Creon()
    c.avoid_reqlimitwarning()
   # stockcode = request.args.get('A000020')
    stockcode = 'A000020'
    if not stockcode:
        return '', 400
    status = c.get_stockstatus(stockcode)
    return jsonify(status)

@bp.route('/stockcandles', methods=['GET'])
def handle_stockcandles():
    c = Creon()
    c.avoid_reqlimitwarning()
    stockcode = request.args.get('code')
    n = request.args.get('n')
    #n = 10
    date_from = request.args.get('from')
    #date_from = '20240101'
    date_to = request.args.get('to')
    #date_to = '20240419'

    print(date_from)
    if not (n or date_from):
        return 'Need to provide "n" or "date_from" argument.', 400
    stockcandles = c.get_chart(stockcode, target='A', unit='D', n=n, date_from=date_from, date_to=date_to)
    #print(stockcandles)
    return jsonify(stockcandles)



@bp.route('/marketcandles', methods=['GET'])
def handle_marketcandles():
    c = Creon()
    c.avoid_reqlimitwarning()
    marketcode = request.args.get('code')
    n = request.args.get('n')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if marketcode == 'kospi':
        marketcode = '001'
    elif marketcode == 'kosdaq':
        marketcode = '201'
    elif marketcode == 'kospi200':
        marketcode = '180'
    else:
        return [], 400
    if not (n or date_from):
        return '', 400
    marketcandles = c.get_chart(marketcode, target='U', unit='D', n=n, date_from=date_from, date_to=date_to)
    return jsonify(marketcandles)

@bp.route('/stockfeatures/', methods=['GET'])
def handle_stockfeatures():
    c = Creon()
    c.avoid_reqlimitwarning()
    stockcode = request.args.get('code')
    #stockcode = 'A000020'
    if not stockcode:
        return '', 400
    stockfeatures = c.get_stockfeatures(stockcode)
    return jsonify(stockfeatures)

@bp.route('/short', methods=['GET'])
def handle_short():
    c = Creon()
    c.avoid_reqlimitwarning()
    stockcode = request.args.get('code')
    n = request.args.get('n')
    if not stockcode:
        return '', 400
    stockfeatures = c.get_shortstockselling(stockcode, n=n)
    return jsonify(stockfeatures)