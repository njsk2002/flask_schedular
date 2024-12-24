from pybo import db


# class Question(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     subject = db.Column(db.String(200), nullable=False)
#     content = db.Column(db.Text(), nullable=False)
#     create_date = db.Column(db.DateTime(), nullable=False)
#     #user_id = db.Column(db.String(150), db.ForeignKey('user.userid', ondelete='CASCADE', nullable=False))
#     user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=True, server_default ='1')
#     user = db.relationship('User', backref=db.backref('question_set'))

# question_voter = db.Table(
#         'question_voter',
#         db.Column('user_no', db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), primary_key=True),
#         db.Column('question_id', db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), primary_key=True)

#     )


# answer_voter = db.Table(
#         'answer_voter',
#         db.Column('user_no', db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), primary_key=True),
#         db.Column('answer_id', db.Integer, db.ForeignKey('answer.id', ondelete='CASCADE'), primary_key=True)

#     )

class QuestionVoter(db.Model):
    __tablename__ = 'question_voter'
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), primary_key=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), primary_key=True)

class AnswerVoter(db.Model):
    __tablename__ = 'answer_voter'
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), primary_key=False)
    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id', ondelete='CASCADE'), primary_key=True)



class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(201), nullable=False)
    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('question_set'))
    modify_date = db.Column(db.DateTime(), nullable=True)
    voter = db.relationship('User', secondary='question_voter', backref=db.backref('question_voter_set')) 
    

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete ='CASCADE'))
    question = db.relationship('Question',backref=db.backref('answer_set',))
    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)    
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('answer_set'))
    modify_date = db.Column(db.DateTime(), nullable=True) 
    voter = db.relationship('User', secondary='answer_voter', backref=db.backref('answer_voter_set'))


class User(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    userid= db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200),nullable=False)
    username= db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(150), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)  
    modify_date = db.Column(db.DateTime(), nullable=False)  


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('comment_set'))
    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime())
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), nullable=True)
    question = db.relationship('Question', backref=db.backref('comment_set'))
    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id', ondelete='CASCADE'), nullable=True)
    answer = db.relationship('Answer', backref=db.backref('comment_set'))


    
class Stockinfo(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), unique=True, nullable=False)
    category= db.Column(db.String(2), nullable=False)
    secondcode = db.Column(db.String(200),nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    currentvalue = db.Column(db.String(150), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)  
    modify_date = db.Column(db.DateTime(), nullable=False)  

class Chartinfo(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), nullable=False)
    date= db.Column(db.String(50), nullable=False)
    beginval = db.Column(db.String(200),nullable=False)
    highval= db.Column(db.String(150), nullable=False)
    lowval = db.Column(db.String(150), nullable=False)
    endval = db.Column(db.String(150), nullable=False) 
    tradeval = db.Column(db.String(150), nullable=False)
    tradevol = db.Column(db.String(150), nullable=False) 
    changeval= db.Column(db.String(150), nullable=False)
    changesign = db.Column(db.String(2), nullable=False)
    changevol= db.Column(db.String(150), nullable=False)

class StockinfoTemp(db.Model):  # 신기하게 db에는 stockinfo_temp로 저장됨
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), unique=True, nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    currentvalue = db.Column(db.String(150), nullable=False)
    highvalue  = db.Column(db.String(150), nullable=False) 
    lowvalue = db.Column(db.String(150), nullable=False)
    beginvalue = db.Column(db.String(150), nullable=False)
    diffrate  = db.Column(db.String(150), nullable=False)#등락률
    diffval = db.Column(db.String(150), nullable=False) #전일대비 
    tradeval = db.Column(db.String(150), nullable=False) #현재 거래량
    pre_tradeval = db.Column(db.String(150), nullable=False) #전일거래량
    tvol_vsprevious = db.Column(db.String(150), nullable=False) # 전일대비 거래량
    faceval = db.Column(db.String(150), nullable=False) #액면가
    stockvol = db.Column(db.String(150), nullable=False) #상장주수
    capital = db.Column(db.String(150), nullable=False) #자본금
    stocksum = db.Column(db.String(150), nullable=False) #시가총액
    per = db.Column(db.String(150), nullable=False) #per
    eps = db.Column(db.String(150), nullable=False) # eps
    pbr = db.Column(db.String(150), nullable=False) #pbr
    debtrate = db.Column(db.String(150), nullable=False) # 전체 융자 잔고 비율
 
class Token_temp(db.Model):
     no = db.Column(db.Integer, primary_key=True)
     approval_key= db.Column(db.String(300), nullable=False)
     token_key = db.Column(db.String(500), nullable=False)
     token_expire = db.Column(db.String(200), nullable=False)
     approval_key_mock= db.Column(db.String(300), nullable=False)
     token_key_mock = db.Column(db.String(500), nullable=False)
     token_expire_mock = db.Column(db.String(200), nullable=False)


class ObserveStock(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), unique=True, nullable=False)
    category= db.Column(db.String(2), default='0', nullable=False)
    secondcode = db.Column(db.String(200), default='0', nullable=False)
    stockname= db.Column(db.String(150), default='0',  nullable=False)
    currentvalue = db.Column(db.String(150), default='0',  nullable=False)
    beginvalue = db.Column(db.String(150), default='0',  nullable=False)
    highvalue = db.Column(db.String(150), default='0',  nullable=False)
    lowvalue = db.Column(db.String(150), default='0',  nullable=False)
    tradeval = db.Column(db.String(150), default='0',  nullable=False)
    diffrate = db.Column(db.String(150), default='0',  nullable=False)
    diffval = db.Column(db.String(150), default='0',  nullable=False)
    targetvalue = db.Column(db.String(150), default='0',  nullable=False)
    stockstatus = db.Column(db.String(150), default='0',  nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)  
    modify_date = db.Column(db.DateTime(), nullable=False)

class StockListFromVB(db.Model):  # 신기하게 db에는 stockinfo_temp로 저장됨
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    stockdate= db.Column(db.String(150), nullable=False)
    method_1 = db.Column(db.String(150), nullable=False)
    method_2 = db.Column(db.String(150), nullable=False)
    currentvalue = db.Column(db.String(150), nullable=False)
    d5d20  = db.Column(db.String(150), nullable=False) # 5/20
    close5d = db.Column(db.String(150), nullable=False) # 종가/5일
    close20d = db.Column(db.String(150), nullable=False) # 종가/20일
    closebegin  = db.Column(db.String(150), nullable=False)#종가/시가
    closepreclose = db.Column(db.String(150), nullable=False) #종가/전일종가
    closelow = db.Column(db.String(150), nullable=False) #종가/저가
    highclose = db.Column(db.String(150), nullable=False) #고가/종가
    begin_1 = db.Column(db.String(150)) #+1일(시가)
    begin_2 = db.Column(db.String(150)) #+2일(시가)
    begin_3 = db.Column(db.String(150)) #+3일(시가)
    begin_4 = db.Column(db.String(150)) #+4일(시가)
    begin_5 = db.Column(db.String(150)) #+5일(시가)
    high_1 = db.Column(db.String(150)) #+1일(고가)
    high_2 = db.Column(db.String(150)) #+2일(고가)
    high_3 = db.Column(db.String(150)) #+3일(고가)
    high_4 = db.Column(db.String(150)) #+4일(고가)
    high_5 = db.Column(db.String(150)) #+5일(고가)
    first_low_date = db.Column(db.String(150)) # 1차 고가/저가
    first_low_value = db.Column(db.String(150))  # 당일종가/최저가
    first_high_date = db.Column(db.String(150))
    first_high_value = db.Column(db.String(150)) # 최고가/당일종가
    secend_low_date = db.Column(db.String(150)) # 2차 고가/저가
    secend_low_value = db.Column(db.String(150)) # 당일종가/최저가
    secend_high_date = db.Column(db.String(150))
    secend_high_value = db.Column(db.String(150))# 최고가/당일종가
    high_begin_4 = db.Column(db.String(150))# -4일 고가 - 시가
    high_begin_3 = db.Column(db.String(150))# -3일 고가 - 시가
    high_begin_2 = db.Column(db.String(150))# -2일 고가 - 시가
    high_begin_1 = db.Column(db.String(150))# -1일 고가 - 시가
    tradevol_4= db.Column(db.String(150))# -4일 거래량
    tradevol_3 = db.Column(db.String(150))# -3일 거래량
    tradevol_2 = db.Column(db.String(150))# -2일 거래량
    tradevol_1 = db.Column(db.String(150))# -1일 거래량
    tradevol_0 = db.Column(db.String(150))# -0일 거래량
    d60_d20 = db.Column(db.String(150))# -60일 평균 - 20일 평균
    d20_d5 = db.Column(db.String(150))# 20일평균 - 5일 평균
    close_close4 = db.Column(db.String(150))# 금일 종가 - 4일전종가

class ObserveStockFromVB(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(150), default='observe')
    stockcode= db.Column(db.String(150), unique=True, nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    stockdate= db.Column(db.String(150), nullable=False)
    method_1 = db.Column(db.String(150), nullable=False)
    method_2 = db.Column(db.String(150), nullable=False)

    stockdate = db.Column(db.String(150), default='0')
    selected1= db.Column(db.String(150), default='0')
    selected2= db.Column(db.String(150), default='0')
    selected3= db.Column(db.String(150), default='0')
    selected4= db.Column(db.String(150), default='0')
    selecteddate= db.Column(db.String(150), default='0')
    buydate = db.Column(db.String(150), default='0')
    
    tradetime= db.Column(db.String(150), default='0')
    currentvalue = db.Column(db.String(150), default='0')  
    beginvalue = db.Column(db.String(150), default='0')
    highvalue = db.Column(db.String(150), default='0' )
    lowvalue = db.Column(db.String(150), default='0' )
    cellprice= db.Column(db.String(150), default='0')
    buyprice = db.Column(db.String(150), default='0')
    tradeval = db.Column(db.String(150), default='0'  )
    tradevalrate = db.Column(db.String(150), default='0'  ) # 전일 거래량 대비 
    diffrate = db.Column(db.String(150), default='0' )
    diffval = db.Column(db.String(150), default='0' )
    caution= db.Column(db.String(150), default='0' )  # 투자유의여부
    warning= db.Column(db.String(150), default='0' )  # 	00 : 없음 01 : 투자주의02 : 투자경고03 : 투자위험
    
    orderno = db.Column(db.String(150), default='0')
    initqty = db.Column(db.String(150), default='0' )
    remainqty = db.Column(db.String(150), default='0' )
    buyqty = db.Column(db.String(150), default='0' )


class ObserveMinData(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), unique=True, nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    stockdate= db.Column(db.String(150), nullable=False)
    method_1 = db.Column(db.String(150), nullable=False)
    method_2 = db.Column(db.String(150), nullable=False)

    tradetime= db.Column(db.String(150), default='0')
    currentvalue = db.Column(db.String(150), default='0')  
    beginvalue = db.Column(db.String(150), default='0')
    highvalue = db.Column(db.String(150), default='0' )
    lowvalue = db.Column(db.String(150), default='0' )
    cellprice= db.Column(db.String(150), default='0')
    buyprice = db.Column(db.String(150), default='0')
    tradeval = db.Column(db.String(150), default='0'  )
    diffrate = db.Column(db.String(150), default='0' )
    diffval = db.Column(db.String(150), default='0', )
   

class StockBalanceLists(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(150), default='remain')
    stockcode= db.Column(db.String(150), unique=True, nullable=False)
    stockname= db.Column(db.String(150), nullable=False)

    currvalue=db.Column(db.String(150), default='0')
    beginvalue=db.Column(db.String(150), default='0')
    highvalue=db.Column(db.String(150), default='0')
    lowvalue=db.Column(db.String(150), default='0')
    tradeval=db.Column(db.String(150), default='0')  # 누적거래량
    tradevalrate=db.Column(db.String(150), default='0')  # 전일 거래량 대비
    diffval=db.Column(db.String(150), default='0')  # 전일종가대비
    diffrate=db.Column(db.String(150), default='0')  # 전일종가대비비율
    caution=db.Column(db.String(150), default='0')  # 투자유의여부
    warning=db.Column(db.String(150), default='0')  # 00: 없음 01: 투자주의 02: 투자경고 03: 투자위험

    remainderqty = db.Column(db.String(150), default='0', nullable=False)
    buyprice = db.Column(db.String(150), default='0', nullable=False) 
    buyamount = db.Column(db.String(150), default='0', nullable=False) 

    currentvalue = db.Column(db.String(150), default='0', nullable=False) 
    evalprice =  db.Column(db.String(150), default='0', nullable=False) 
    evalrate =db.Column(db.String(150), default='0', nullable=False) 
    evalpriceamount = db.Column(db.String(150), default='0', nullable=False) 
    method_1 = db.Column(db.String(150), default='0', nullable=False) 
    method_2 = db.Column(db.String(150), default='0', nullable=False) 
  
    buy_previous= db.Column(db.String(150), default='0')
    sell_previous = db.Column(db.String(150), default='0')  
    buy_today = db.Column(db.String(150), default='0')
    sell_today= db.Column(db.String(150), default='0')

    orderno = db.Column(db.String(150), default='0')
    initqty = db.Column(db.String(150), default='0' )
    remainqty = db.Column(db.String(150), default='0' )  
    buyqty = db.Column(db.String(150), default='0' )







#vb에서 해당날짜의 종목(이전날짜에 없는 신규종목)을 저장
class DailyDataFromVB(db.Model):  # 신기하게 db에는 stockinfo_temp로 저장됨
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    stockdate= db.Column(db.String(150), nullable=False)
    fromvb= db.Column(db.String(150), default='0') # vb 파일에서 가져온 종목
    selecteddate = db.Column(db.String(150), default = '20000101')
    selected1= db.Column(db.String(150), default='0', nullable=False) # 1차 검토 (바로 매수)
    selected2= db.Column(db.String(150), default='0', nullable=False) # 특정 조건 시 매수 
    selected3= db.Column(db.String(150), default='0')
    selected4= db.Column(db.String(150), default='0')
    

class StockListFromKInvestor(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), unique=True, nullable=False)
    stockstdcode= db.Column(db.String(150), unique=True, nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    cate_large= db.Column(db.String(150), default='0', nullable=False) #업종구분 대
    cate_medium= db.Column(db.String(150), default='0', nullable=False) #중
    cate_small= db.Column(db.String(150), default='0', nullable=False) # 소
    x1_stock= db.Column(db.String(150), default='0', nullable=False) #거래정지
    x2_stock = db.Column(db.String(150), default='0',  nullable=False) #정리매매
    x3_stock = db.Column(db.String(150), default='0',  nullable=False) # 관리종목
    warning_stock = db.Column(db.String(150), default='0',  nullable=False) #시장경고
    pre_warning_stock = db.Column(db.String(150), default='0',  nullable=False) #경고예고
    x4_stock  = db.Column(db.String(150), default='0',  nullable=False)  # 불성실공시
    backdoor_listing = db.Column(db.String(150), default='0',  nullable=False) # 우회상장
    facevalue  = db.Column(db.String(150), default='0',  nullable=False) #액면가
    listingdate = db.Column(db.String(150), default='0',  nullable=False) #상장일
    listingvolume = db.Column(db.String(150), default='0',  nullable=False) #상장주수
    capital = db.Column(db.String(150), default='0',  nullable=False) # 자본금
    closingmonth = db.Column(db.String(150), default='0',  nullable=False)  # 결산월
    pre_stock = db.Column(db.String(150), default='0',  nullable=False)  #우선주유무
    category = db.Column(db.String(150), default='0',  nullable=False)  #코스피,코스닥,기타(n)
    sales = db.Column(db.String(150), default='0',  nullable=False)  # 매출액
    sales_profit = db.Column(db.String(150), default='0',  nullable=False) 
    ordinary_profit = db.Column(db.String(150), default='0',  nullable=False) 
    profit = db.Column(db.String(150), default='0',  nullable=False) 
    roe = db.Column(db.String(150), default='0',  nullable=False) 
    basedyear = db.Column(db.String(150), default='0',  nullable=False) 
    stock_amount = db.Column(db.String(150), default='0',  nullable=False)  

class ThemeCode(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    themecode= db.Column(db.String(150),nullable=False)
    themename= db.Column(db.String(150), nullable=False)
    stockcode= db.Column(db.String(150), nullable=False)

class RankTrade(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    rank = db.Column(db.String(150), nullable=False)#데이터 순위
    currentvalue = db.Column(db.String(150), nullable=False)
    tradeval =db.Column(db.String(150), nullable=False)#현재 거래량
    sign =db.Column(db.String(150), nullable=False)#전일 대비 부호
    diffrate =db.Column(db.String(150), nullable=False) #등락률
    diffval =db.Column(db.String(150), nullable=False) #전일대비 
    pre_tradeval =db.Column(db.String(150), nullable=False) #전일거래량
    stockvol =db.Column(db.String(150), nullable=False) #상장주수
    # tvol_vsprevious =db.Column(db.String(150), nullable=False) # 전일대비 거래량
    # faceval =db.Column(db.String(150), nullable=False) #액면가
    avg_vol =db.Column(db.String(150), nullable=False) #평균 거래량
    nday_prpr_rate =db.Column(db.String(150), nullable=False) #N일전종가대비현재가대비율
    vol_incr =db.Column(db.String(150), nullable=False) #거래량증가율
    vol_tnrt =db.Column(db.String(150), nullable=False)# 거래량 회전율
    nday_vol_tnrt =db.Column(db.String(150), nullable=False)#N일 거래량 회전율
    avg_tr_pbmn =db.Column(db.String(150), nullable=False) # 	평균 거래 대금
    tr_pbmn_tnrt=db.Column(db.String(150), nullable=False) # 거래대금회전율
    nday_tr_pbmn_tnrt =db.Column(db.String(150), nullable=False) # N일 거래대금 회전율
    acml_tr_pbmn =db.Column(db.String(150), nullable=False) # 	누적 거래 대금

    in_buy_list = db.Column(db.String(150), default='0',  nullable=False) # 잔고보유 유무
    in_observe_list = db.Column(db.String(150), default='0',  nullable=False) # 매수대기 항목 유무
    method_1 = db.Column(db.String(150), default='0',  nullable=False)
    method_2 = db.Column(db.String(150), default='0',  nullable=False)
    stockdate = db.Column(db.String(150), default='20000101', nullable=False)
    selected_1 = db.Column(db.String(150), default='0',  nullable=False)
    selected_2 = db.Column(db.String(150), default='0',  nullable=False)
    selected_3 = db.Column(db.String(150), default='0',  nullable=False)
    selected_4 = db.Column(db.String(150), default='0',  nullable=False)
    selecteddate = db.Column(db.String(150), default='20000101',  nullable=False)

# class RankHigh(db.Model):
#     no = db.Column(db.Integer, primary_key=True)
#     stockcode= db.Column(db.String(150), unique=True, nullable=False)
#     stockname= db.Column(db.String(150), nullable=False)
#     rank = db.Column(db.String(150), nullable=False)#데이터 순위




#일별 거래 현황
class DailyTrade(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    tradedate = db.Column(db.String(150), default='0',  nullable=False) # 주문일자
    orderno= db.Column(db.String(150), default='0',  nullable=False) # 주문 번호
    orderno_origin = db.Column(db.String(150), default='0',  nullable=False) #원주문번호
    trade = db.Column(db.String(150), default='0',  nullable=False) # 거래구분	01 : 매도 02 : 매수 
    trade_name  = db.Column(db.String(150), default='0',  nullable=False) #반대매매 인경우 "임의매도"로 표시됨 정정취소여부가 Y이면 *이 붙음 ex) 매수취소* = 매수취소가 완료됨
    orderqty = db.Column(db.String(150), default='0',  nullable=False) #주문수량
    orderprice= db.Column(db.String (150), default='0',  nullable=False) #주문단가
    ordertime = db.Column(db.String(150), default='0',  nullable=False) #주문시간
    total_trade_qty = db.Column(db.String(150), default='0',  nullable=False) #총체결수량
    avg_price = db.Column(db.String(150), default='0',  nullable=False) #평균가
    total_trade_amount = db.Column(db.String(150), default='0',  nullable=False) #총 체결금액
    order_code = db.Column(db.String(150), default='0',  nullable=False) #주문구분코드
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
    remain_qty = db.Column(db.String(150), default='0',  nullable=False) #잔여수량
    trade_condition = db.Column(db.String(150), default='0',  nullable=False) # 채결조건명
    market = db.Column(db.String(150), default='0',  nullable=False) # 거래소 구분코드 	01 : 한국증권 02 : 증권거래소  03 : 코스닥

    #OUTPUT2 
    amount_order = db.Column(db.String(150), default='0',  nullable=False) #총주문수량
    amount_trade_qty = db.Column(db.String(150), default='0',  nullable=False) #총체결수량
    avg_buy_cost = db.Column(db.String(150), default='0',  nullable=False) # 매입평균가격
    amount_cost = db.Column(db.String(150), default='0',  nullable=False) #총결제금액
    exp_tax = db.Column(db.String(150), default='0',  nullable=False) # 추정 제비용 합계


# class RankHigh(db.Model):
#     no = db.Column(db.Integer, primary_key=True)
#     stockcode= db.Column(db.String(150), unique=True, nullable=False)
#     stockname= db.Column(db.String(150), nullable=False)
#     rank = db.Column(db.String(150), nullable=False)#데이터 순위
    

# 자동으로 할때 observe와 remain을 합칠려고 했는데, 일단 보류 
class StocksForAutoTrade(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    stockcode= db.Column(db.String(150), unique=True, nullable=False)
    stockname= db.Column(db.String(150), nullable=False)
    stockdate= db.Column(db.String(150), nullable=False)
    method_1 = db.Column(db.String(150), nullable=False)
    method_2 = db.Column(db.String(150), nullable=False)

    stockdate = db.Column(db.String(150), default='0')
    selected1= db.Column(db.String(150), default='0')
    selected2= db.Column(db.String(150), default='0')
    selected3= db.Column(db.String(150), default='0')
    selected4= db.Column(db.String(150), default='0')
    selecteddate= db.Column(db.String(150), default='0')
    buydate = db.Column(db.String(150), default='0')
    
    tradetime= db.Column(db.String(150), default='0')
    currentvalue = db.Column(db.String(150), default='0')  
    beginvalue = db.Column(db.String(150), default='0')
    highvalue = db.Column(db.String(150), default='0' )
    lowvalue = db.Column(db.String(150), default='0' )
    cellprice= db.Column(db.String(150), default='0')
    buyprice = db.Column(db.String(150), default='0')
    tradeval = db.Column(db.String(150), default='0'  )
    tradevalrate = db.Column(db.String(150), default='0'  ) # 전일 거래량 대비 
    diffrate = db.Column(db.String(150), default='0' )
    diffval = db.Column(db.String(150), default='0' )
    caution= db.Column(db.String(150), default='0' )  # 투자유의여부
    warning= db.Column(db.String(150), default='0' )  # 	00 : 없음 01 : 투자주의02 : 투자경고03 : 투자위험
    
    orderno = db.Column(db.String(150), default='0')
    initqty = db.Column(db.String(150), default='0' )
    remainqty = db.Column(db.String(150), default='0' )
    buyqty = db.Column(db.String(150), default='0' )

    remainderqty = db.Column(db.String(150), default='0', nullable=False)
    buyprice = db.Column(db.String(150), default='0', nullable=False) 
    buyamount = db.Column(db.String(150), default='0', nullable=False) 

    evalprice =  db.Column(db.String(150), default='0', nullable=False) 
    evalrate =db.Column(db.String(150), default='0', nullable=False) 
    evalpriceamount = db.Column(db.String(150), default='0', nullable=False) 



class Co2Management(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    use_date = db.Column(db.String(150), nullable=False)
    use_elec = db.Column(db.String(150), nullable=True)
    co2_elec = db.Column(db.String(150), nullable=True)
    use_water = db.Column(db.String(150), nullable=True)
    co2_water = db.Column(db.String(150), nullable=True)
    use_waste = db.Column(db.String(150), nullable=True)
    co2_waste = db.Column(db.String(150), nullable=True)
    use_vehicle = db.Column(db.String(150), nullable=True)
    co2_vehicle = db.Column(db.String(150), nullable=True)
    use_gas = db.Column(db.String(150), nullable=True)
    co2_gas = db.Column(db.String(150), nullable=True)
    use_total = db.Column(db.String(150), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)
    

class ElecUsage(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    room_no = db.Column(db.String(150), nullable=False)
    use_year = db.Column(db.String(150), nullable=False)
    acum_ref = db.Column(db.String(150), nullable=False)
    acum_jan = db.Column(db.String(150), nullable=True)
    use_jan = db.Column(db.String(150), nullable=True)
    acum_feb = db.Column(db.String(150), nullable=True)
    use_feb = db.Column(db.String(150), nullable=True)
    acum_mar = db.Column(db.String(150), nullable=True)
    use_mar = db.Column(db.String(150), nullable=True)
    acum_apr = db.Column(db.String(150), nullable=True)
    use_apr = db.Column(db.String(150), nullable=True)
    acum_may = db.Column(db.String(150), nullable=True)
    use_may = db.Column(db.String(150), nullable=True)
    acum_jun = db.Column(db.String(150), nullable=True)
    use_jun = db.Column(db.String(150), nullable=True)
    acum_jul = db.Column(db.String(150), nullable=True)
    use_jul = db.Column(db.String(150), nullable=True)
    acum_aug = db.Column(db.String(150), nullable=True)
    use_aug = db.Column(db.String(150), nullable=True)
    acum_sep = db.Column(db.String(150), nullable=True)
    use_sep = db.Column(db.String(150), nullable=True)
    acum_oct = db.Column(db.String(150), nullable=True)
    use_oct = db.Column(db.String(150), nullable=True)
    acum_nov = db.Column(db.String(150), nullable=True)
    use_nov= db.Column(db.String(150), nullable=True)
    acum_dec = db.Column(db.String(150), nullable=True)
    use_dec = db.Column(db.String(150), nullable=True)
    total = db.Column(db.String(150), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)

class VehicleUsage(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    car_no = db.Column(db.String(150), nullable=False)
    car_name= db.Column(db.String(150), nullable=False)
    car_fuel= db.Column(db.String(150), nullable=False)
    use_year = db.Column(db.String(150), nullable=False)
    acum_ref = db.Column(db.String(150), nullable=False)
    acum_jan = db.Column(db.String(150), nullable=True)
    use_jan = db.Column(db.String(150), nullable=True)
    acum_feb = db.Column(db.String(150), nullable=True)
    use_feb = db.Column(db.String(150), nullable=True)
    acum_mar = db.Column(db.String(150), nullable=True)
    use_mar = db.Column(db.String(150), nullable=True)
    acum_apr = db.Column(db.String(150), nullable=True)
    use_apr = db.Column(db.String(150), nullable=True)
    acum_may = db.Column(db.String(150), nullable=True)
    use_may = db.Column(db.String(150), nullable=True)
    acum_jun = db.Column(db.String(150), nullable=True)
    use_jun = db.Column(db.String(150), nullable=True)
    acum_jul = db.Column(db.String(150), nullable=True)
    use_jul = db.Column(db.String(150), nullable=True)
    acum_aug = db.Column(db.String(150), nullable=True)
    use_aug = db.Column(db.String(150), nullable=True)
    acum_sep = db.Column(db.String(150), nullable=True)
    use_sep = db.Column(db.String(150), nullable=True)
    acum_oct = db.Column(db.String(150), nullable=True)
    use_oct = db.Column(db.String(150), nullable=True)
    acum_nov = db.Column(db.String(150), nullable=True)
    use_nov= db.Column(db.String(150), nullable=True)
    acum_dec = db.Column(db.String(150), nullable=True)
    use_dec = db.Column(db.String(150), nullable=True)
    total = db.Column(db.String(150), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)

class WaterUsage(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    room_no = db.Column(db.String(150), nullable=False)
    use_year = db.Column(db.String(150), nullable=False)
    acum_ref = db.Column(db.String(150), nullable=False)
    acum_jan = db.Column(db.String(150), nullable=True)
    use_jan = db.Column(db.String(150), nullable=True)
    acum_feb = db.Column(db.String(150), nullable=True)
    use_feb = db.Column(db.String(150), nullable=True)
    acum_mar = db.Column(db.String(150), nullable=True)
    use_mar = db.Column(db.String(150), nullable=True)
    acum_apr = db.Column(db.String(150), nullable=True)
    use_apr = db.Column(db.String(150), nullable=True)
    acum_may = db.Column(db.String(150), nullable=True)
    use_may = db.Column(db.String(150), nullable=True)
    acum_jun = db.Column(db.String(150), nullable=True)
    use_jun = db.Column(db.String(150), nullable=True)
    acum_jul = db.Column(db.String(150), nullable=True)
    use_jul = db.Column(db.String(150), nullable=True)
    acum_aug = db.Column(db.String(150), nullable=True)
    use_aug = db.Column(db.String(150), nullable=True)
    acum_sep = db.Column(db.String(150), nullable=True)
    use_sep = db.Column(db.String(150), nullable=True)
    acum_oct = db.Column(db.String(150), nullable=True)
    use_oct = db.Column(db.String(150), nullable=True)
    acum_nov = db.Column(db.String(150), nullable=True)
    use_nov= db.Column(db.String(150), nullable=True)
    acum_dec = db.Column(db.String(150), nullable=True)
    use_dec = db.Column(db.String(150), nullable=True)
    total = db.Column(db.String(150), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)


class CalendarSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 명시적으로 autoincrement 추가
    content = db.Column(db.String(300), nullable=False)
    start_time = db.Column(db.String(150), nullable=True)
    end_time = db.Column(db.String(150), nullable=True)
    cal_date = db.Column(db.String(150), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)

class UserAuthorization(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 명시적으로 autoincrement 추가
    email = db.Column(db.String(300), nullable=False)
    password = db.Column(db.String(150), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)
   

    
