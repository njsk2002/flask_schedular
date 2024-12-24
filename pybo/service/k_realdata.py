# -*- coding: utf-8 -*-
### 모듈 임포트 ###
import websockets
import json
import requests
import os
import asyncio
import time

#추가 DB용
from ..models import Token_temp, ObserveStock, ObserveStockFromVB
import json
from .. import db
from sqlalchemy import func

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode





class RealTimeData():

    clearConsole = lambda: os.system('cls' if os.name in ('nt', 'dos') else 'clear')
    key_bytes = 32
    ### 함수 정의 ###

    # AES256 DECODE
    def aes_cbc_base64_dec(self,key, iv, cipher_text):
        """
        :param key:  str type AES256 secret key value
        :param iv: str type AES256 Initialize Vector
        :param cipher_text: Base64 encoded AES256 str
        :return: Base64-AES256 decodec str
        """
        cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
        return bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))


    # # 웹소켓 접속키 발급
    # def get_approval(self, key, secret):
    #     url = 'https://openapivts.koreainvestment.com:29443' # 모의투자계좌     
    #     #url = 'https://openapi.koreainvestment.com:9443' # 실전투자계좌
    #     headers = {"content-type": "application/json"}
    #     body = {"grant_type": "client_credentials",
    #             "appkey": key,
    #             "secretkey": secret}
    #     PATH = "oauth2/Approval"
    #     URL = f"{url}/{PATH}"
    #     res = requests.post(URL, headers=headers, data=json.dumps(body))
    #     approval_key = res.json()["approval_key"]
    #     return approval_key

    ### 1-1. 국내주식 ###

    # 국내주식호가 출력라이브러리
    def stockhoka_domestic(self, data):
        """ 넘겨받는데이터가 정상인지 확인
        print("stockhoka[%s]"%(data))
        """
        recvvalue = data.split('^')  # 수신데이터를 split '^'

        print("유가증권 단축 종목코드 [" + recvvalue[0] + "]")
        print("영업시간 [" + recvvalue[1] + "]" + "시간구분코드 [" + recvvalue[2] + "]")
        print("======================================")
        print("매도호가10 [%s]    잔량10 [%s]" % (recvvalue[12], recvvalue[32]))
        print("매도호가09 [%s]    잔량09 [%s]" % (recvvalue[11], recvvalue[31]))
        print("매도호가08 [%s]    잔량08 [%s]" % (recvvalue[10], recvvalue[30]))
        print("매도호가07 [%s]    잔량07 [%s]" % (recvvalue[9], recvvalue[29]))
        print("매도호가06 [%s]    잔량06 [%s]" % (recvvalue[8], recvvalue[28]))
        print("매도호가05 [%s]    잔량05 [%s]" % (recvvalue[7], recvvalue[27]))
        print("매도호가04 [%s]    잔량04 [%s]" % (recvvalue[6], recvvalue[26]))
        print("매도호가03 [%s]    잔량03 [%s]" % (recvvalue[5], recvvalue[25]))
        print("매도호가02 [%s]    잔량02 [%s]" % (recvvalue[4], recvvalue[24]))
        print("매도호가01 [%s]    잔량01 [%s]" % (recvvalue[3], recvvalue[23]))
        print("--------------------------------------")
        print("매수호가01 [%s]    잔량01 [%s]" % (recvvalue[13], recvvalue[33]))
        print("매수호가02 [%s]    잔량02 [%s]" % (recvvalue[14], recvvalue[34]))
        print("매수호가03 [%s]    잔량03 [%s]" % (recvvalue[15], recvvalue[35]))
        print("매수호가04 [%s]    잔량04 [%s]" % (recvvalue[16], recvvalue[36]))
        print("매수호가05 [%s]    잔량05 [%s]" % (recvvalue[17], recvvalue[37]))
        print("매수호가06 [%s]    잔량06 [%s]" % (recvvalue[18], recvvalue[38]))
        print("매수호가07 [%s]    잔량07 [%s]" % (recvvalue[19], recvvalue[39]))
        print("매수호가08 [%s]    잔량08 [%s]" % (recvvalue[20], recvvalue[40]))
        print("매수호가09 [%s]    잔량09 [%s]" % (recvvalue[21], recvvalue[41]))
        print("매수호가10 [%s]    잔량10 [%s]" % (recvvalue[22], recvvalue[42]))
        print("======================================")
        print("총매도호가 잔량        [%s]" % (recvvalue[43]))
        print("총매도호가 잔량 증감   [%s]" % (recvvalue[54]))
        print("총매수호가 잔량        [%s]" % (recvvalue[44]))
        print("총매수호가 잔량 증감   [%s]" % (recvvalue[55]))
        print("시간외 총매도호가 잔량 [%s]" % (recvvalue[45]))
        print("시간외 총매수호가 증감 [%s]" % (recvvalue[46]))
        print("시간외 총매도호가 잔량 [%s]" % (recvvalue[56]))
        print("시간외 총매수호가 증감 [%s]" % (recvvalue[57]))
        print("예상 체결가            [%s]" % (recvvalue[47]))
        print("예상 체결량            [%s]" % (recvvalue[48]))
        print("예상 거래량            [%s]" % (recvvalue[49]))
        print("예상체결 대비          [%s]" % (recvvalue[50]))
        print("부호                   [%s]" % (recvvalue[51]))
        print("예상체결 전일대비율    [%s]" % (recvvalue[52]))
        print("누적거래량             [%s]" % (recvvalue[53]))
        print("주식매매 구분코드      [%s]" % (recvvalue[58]))

        
    # 국내주식체결처리 출력라이브러리
    def stockspurchase_domestic(self,data_cnt, data):
        # print("DATA CNT = ", data_cnt)
        # print("DATA= ", data)

        print("============================================")
        menulist = "유가증권단축종목코드|주식체결시간|주식현재가|전일대비부호|전일대비|전일대비율|가중평균주식가격|주식시가|주식최고가|주식최저가|매도호가1|매수호가1|체결거래량|누적거래량|누적거래대금|매도체결건수|매수체결건수|순매수체결건수|체결강도|총매도수량|총매수수량|체결구분|매수비율|전일거래량대비등락율|시가시간|시가대비구분|시가대비|최고가시간|고가대비구분|고가대비|최저가시간|저가대비구분|저가대비|영업일자|신장운영구분코드|거래정지여부|매도호가잔량|매수호가잔량|총매도호가잔량|총매수호가잔량|거래량회전율|전일동시간누적거래량|전일동시간누적거래량비율|시간구분코드|임의종료구분코드|정적VI발동기준가"
        menustr = menulist.split('|')
        pValue = data.split('^')
        # pValue를 48개씩 나누어서 4개의 리스트로 담기
        rdata = [pValue[i:i+46] for i in range(0, len(pValue), 46)]
        print("rdata= ", rdata)

        for data in rdata:
    # 데이터베이스에서 주어진 stockcode에 해당하는 레코드를 가져옵니다.
            observe_from_vb = ObserveStockFromVB.query.filter_by(stockcode=data[0]).first()

            if observe_from_vb:
                # 주어진 데이터로 업데이트합니다.
                observe_from_vb.tradetime = data[1]
                observe_from_vb.currentvalue = data[2]
                observe_from_vb.beginvalue = data[7]
                observe_from_vb.highvalue = data[8]
                observe_from_vb.lowvalue = data[9]
                observe_from_vb.cellprice = data[10]
                observe_from_vb.buyprice = data[11]
                observe_from_vb.tradeval = data[13]
                observe_from_vb.diffrate = data[5]
                observe_from_vb.diffval = data[4]

                # 변경사항을 커밋하여 데이터베이스에 업데이트합니다.
                db.session.commit()

    
        # i = 0
        # for cnt in range(data_cnt):  # 넘겨받은 체결데이터 개수만큼 print 한다
        #     print("### [%d / %d]" % (cnt + 1, data_cnt))
        #     for menu in menustr:
        #         print("%-13s[%s]" % (menu, pValue[i]))
        #         i += 1


    # 국내주식체결통보 출력라이브러리
    def stocksigningnotice_domestic(self, data, key, iv):
       
        # AES256 처리 단계
        aes_dec_str = self.aes_cbc_base64_dec(key, iv, data)
        pValue = aes_dec_str.split('^')

        if pValue[13] == '2': # 체결통보
            print("#### 국내주식 체결 통보 ####")
            menulist = "고객ID|계좌번호|주문번호|원주문번호|매도매수구분|정정구분|주문종류|주문조건|주식단축종목코드|체결수량|체결단가|주식체결시간|거부여부|체결여부|접수여부|지점번호|주문수량|계좌명|체결종목명|신용구분|신용대출일자|체결종목명40|주문가격"
            menustr1 = menulist.split('|')
        else:
            print("#### 국내주식 주문·정정·취소·거부 접수 통보 ####")
            menulist = "고객ID|계좌번호|주문번호|원주문번호|매도매수구분|정정구분|주문종류|주문조건|주식단축종목코드|주문수량|주문가격|주식체결시간|거부여부|체결여부|접수여부|지점번호|주문수량|계좌명|주문종목명|신용구분|신용대출일자|체결종목명40|체결단가"
            menustr1 = menulist.split('|')
        
        i = 0
        for menu in menustr1:
            print("%s  [%s]" % (menu, pValue[i]))
            i += 1

    # 국내주식 실시간회원사 출력라이브러리
    def stocksmember_domestic(self, data_cnt, data):
        print("============================================")
        print(data)
        menulist = "유가증권단축종목코드|매도2회원사명1|매도2회원사명2|매도2회원사명3|매도2회원사명4|매도2회원사명5|매수회원사명1|매수회원사명2|매수회원사명3|매수회원사명4|매수회원사명5|총매도수량1|총매도수량2|총매도수량3|총매도수량4|총매도수량5|총매수2수량1|총매수2수량2|총매수2수량3|총매수2수량4|총매수2수량5|매도거래원구분1|매도거래원구분2|매도거래원구분3|매도거래원구분4|매도거래원구분5|매수거래원구분1|매수거래원구분2|매수거래원구분3|매수거래원구분4|매수거래원구분5|매도거래원코드1|매도거래원코드2|매도거래원코드3|매도거래원코드4|매도거래원코드5|매수거래원코드1|매수거래원코드2|매수거래원코드3|매수거래원코드4|매수거래원코드5|매도회원사비중1|매도회원사비중2|매도회원사비중3|매도회원사비중4|매도회원사비중5|매수2회원사비중1|매수2회원사비중2|매수2회원사비중3|매수2회원사비중4|매수2회원사비중5|매도수량증감1|매도수량증감2|매도수량증감3|매도수량증감4|매도수량증감5|매수2수량증감1|매수2수량증감2|매수2수량증감3|매수2수량증감4|매수2수량증감5|외국계총매도수량|외국계총매수2수량|외국계총매도수량증감|외국계총매수2수량증감|외국계순매수수량|외국계매도비중|외국계매수2비중|매도2영문회원사명1|매도2영문회원사명2|매도2영문회원사명3|매도2영문회원사명4|매도2영문회원사명5|매수영문회원사명1|매수영문회원사명2|매수영문회원사명3|매수영문회원사명4|매수영문회원사명5"
        menustr = menulist.split('|')
        pValue = data.split('^')
        i = 0
        for cnt in range(data_cnt):  # 넘겨받은 체결데이터 개수만큼 print 한다
            print("### [%d / %d]" % (cnt + 1, data_cnt))
            for menu in menustr:
                print("%-13s[%s]" % (menu, pValue[i]))
                i += 1              
                
                
    # 국내주식 실시간프로그램매매 출력라이브러리
    def stocksprogramtrade_domestic(self, data_cnt, data):
        print("============================================")
        menulist = "유가증권단축종목코드|주식체결시간|매도체결량|매도거래대금|매수2체결량|매수2거래대금|순매수체결량|순매수거래대금|매도호가잔량|매수호가잔량|전체순매수호가잔량"
        menustr = menulist.split('|')
        pValue = data.split('^')
        i = 0
        for cnt in range(data_cnt):  # 넘겨받은 체결데이터 개수만큼 print 한다
            print("### [%d / %d]" % (cnt + 1, data_cnt))
            for menu in menustr:
                print("%-13s[%s]" % (menu, pValue[i]))
                i += 1
                
                
    # 국내주식 장운영정보 출력라이브러리
    def stocksmarketinfo_domestic(data_cnt, data):
        print("============================================")
        print(data)
        menulist = "유가증권단축종목코드|거래정지여부|거래정지사유내용|장운영구분코드|예상장운영구분코드|임의연장구분코드|동시호가배분처리구분코드|종목상태구분코드|VI적용구분코드|시간외단일가VI적용구분코드"
        menustr = menulist.split('|')
        pValue = data.split('^')
        i = 0
        for cnt in range(data_cnt):  # 넘겨받은 체결데이터 개수만큼 print 한다
            print("### [%d / %d]" % (cnt + 1, data_cnt))
            for menu in menustr:
                print("%-13s[%s]" % (menu, pValue[i]))
                i += 1                  

    ### 1-2. 국내지수 ###

    # 국내지수체결 출력라이브러리
    def indexpurchase_domestic(self,data_cnt, data):
        print("============================================")
        menulist = "업종구분코드|영업시간|현재가지수|전일대비부호|업종지수전일대비|누적거래량|누적거래대금|건별거래량|건별거래대금|전일대비율|시가지수|지수최고가|지수최저가|시가대비지수현재가|시가대비지수부호|최고가대비지수현재가|최고가대비지수부호|최저가대비지수현재가|최저가대비지수부호|전일종가대비시가2비율|전일종가대비최고가비율|전일종가대비최저가비율|상한종목수|상승종목수|보합종목수|하락종목수|하한종목수|기세상승종목수|기세하락종목수|TICK대비"
        menustr = menulist.split('|')
        pValue = data.split('^')
        i = 0
        for cnt in range(data_cnt):  # 넘겨받은 체결데이터 개수만큼 print 한다
            print("### [%d / %d]" % (cnt + 1, data_cnt))
            for menu in menustr:
                print("%-13s[%s]" % (menu, pValue[i]))
                i += 1

    # 국내지수예상체결 출력라이브러리
    def indexexppurchase_domestic(self,data_cnt, data):
        print("============================================")
        menulist = "업종구분코드|영업시간|현재가지수|전일대비부호|업종지수전일대비|누적거래량|누적거래대금|건별거래량|건별거래대금|전일대비율|상한종목수|상승종목수|보합종목수|하락종목수|하한종목수"
        menustr = menulist.split('|')
        pValue = data.split('^')
        i = 0
        for cnt in range(data_cnt):  # 넘겨받은 체결데이터 개수만큼 print 한다
            print("### [%d / %d]" % (cnt + 1, data_cnt))
            for menu in menustr:
                print("%-13s[%s]" % (menu, pValue[i]))
                i += 1

    # 국내지수 실시간프로그램매매 출력라이브러리
    def indexprogramtrade_domestic(self,data_cnt, data):
        print("============================================")
        menulist = "업종구분코드|영업시간|차익매도위탁체결량|차익매도자기체결량|차익매수2위탁체결량|차익매수2자기체결량|비차익매도위탁체결량|비차익매도자기체결량|비차익매수2위탁체결량|비차익매수2자기체결량|차익매도위탁체결금액|차익매도자기체결금액|차익매수2위탁체결금액|차익매수2자기체결금액|비차익매도위탁체결금액|비차익매도자기체결금액|비차익매수2위탁체결금액|비차익매수2자기체결금액|차익합계매도거래량|차익합계매도거래량비율|차익합계매도거래대금|차익합계매도거래대금비율|차익합계매수2거래량|차익합계매수거래량비율|차익합계매수2거래대금|차익합계매수거래대금비율|차익합계순매수수량|차익합계순매수수량비율|차익합계순매수거래대금|차익합계순매수거래대금비율|비차익합계매도거래량|비차익합계매도거래량비율|비차익합계매도거래대금|비차익합계매도거래대금비율|비차익합계매수2거래량|비차익합계매수거래량비율|비차익합계매수2거래대금|비차익합계매수거래대금비율|비차익합계순매수수량|비차익합계순매수수량비율|비차익합계순매수거래대금|비차익합계순매수거래대금비|전체위탁매도거래량|위탁매도거래량비율|전체위탁매도거래대금|위탁매도거래대금비율|전체위탁매수2거래량|위탁매수거래량비율|전체위탁매수2거래대금|위탁매수거래대금비율|전체위탁순매수수량|위탁순매수수량비율|전체위탁순매수거래대금|위탁순매수금액비율|전체자기매도거래량|자기매도거래량비율|전체자기매도거래대금|자기매도거래대금비율|전체자기매수2거래량|자기매수거래량비율|전체자기매수2거래대금|자기매수거래대금비율|전체자기순매수수량|자기순매수량비율|전체자기순매수거래대금|자기순매수대금비율|총매도수량|전체매도거래량비율|총매도거래대금|전체매도거래대금비율|총매수수량|전체매수거래량비율|총매수2거래대금|전체매수거래대금비율|전체순매수수량|전체합계순매수수량비율|전체순매수거래대금|전체순매수거래대금비율|차익위탁순매수수량|차익위탁순매수거래대금|차익자기순매수수량|차익자기순매수거래대금|비차익위탁순매수수량|비차익위탁순매수거래대금|비차익자기순매수수량|비차익자기순매수거래대금|누적거래량|누적거래대금"
        menustr = menulist.split('|')
        pValue = data.split('^')
        i = 0
        for cnt in range(data_cnt):  # 넘겨받은 체결데이터 개수만큼 print 한다
            print("### [%d / %d]" % (cnt + 1, data_cnt))
            for menu in menustr:
                print("%-13s[%s]" % (menu, pValue[i]))
                i += 1            
                
            
class RealData():   
    running = False

    def __init__(self):
        
        self.websocket = None
        self.task = None
   
    ### 앱키 정의 ###
    async def connect(self,code_list,trade_type):
        RealData.running = True
        rd = RealTimeData()
        #print(code_list,trade_type)

        if trade_type == 'mock':
            g_approval_key = Token_temp.query.with_entities(Token_temp.approval_key_mock).first()[0]
            url = 'ws://ops.koreainvestment.com:31000' # 모의투자계좌
        elif trade_type == 'real':
            g_approval_key = Token_temp.query.with_entities(Token_temp.approval_key).first()[0]
            url = 'ws://ops.koreainvestment.com:21000' # 실전투자계좌
        else :
            return False
        print('코드리스트 = ', code_list,trade_type,g_approval_key)
        # 원하는 호출을 [tr_type, tr_id, tr_key] 순서대로 리스트 만들기
        
        ### 1-1. 국내주식 호가, 체결가, 체결통보 ### # 모의투자 국내주식 체결통보: H0STCNI9
        # code_list = [['1','H0STASP0','005930'],['1','H0STCNT0','005930'],['1','H0STCNI0','HTS ID를 입력하세요']]
        
        ### 1-2. 국내주식 실시간회원사, 실시간프로그램매매, 장운영정보 ###
        # code_list = [['1', 'H0STMBC0', '005930'], ['1', 'H0STPGM0', '005930'], ['1', 'H0STMKO0', '005930']]
        
        ### 1-3. 국내지수 체결, 예상체결, 실시간프로그램매매 ###
        # code_list = [['1', 'H0UPCNT0', '0001'], ['1', 'H0UPANC0', '0001'], ['1', 'H0UPPGM0', '0001']]
        
        
        # code_list = [['1', 'H0UPCNT0', '0001'], ['1', 'H0UPANC0', '0001'], ['1', 'H0UPPGM0', '0001'],
        #             ['1','H0STASP0','005930'],['1','H0STCNT0','005930'],['1','H0STCNI9','njsk2002'],
        #             ['1', 'H0STMBC0', '005930'], ['1', 'H0STPGM0', '005930'], ['1', 'H0STMKO0', '005930']
        #             ]

        senddata_list=[]
        
        for i,j,k in code_list:
            temp = '{"header":{"approval_key": "%s","custtype":"P","tr_type":"%s","content-type":"utf-8"},"body":{"input":{"tr_id":"%s","tr_key":"%s"}}}'%(g_approval_key,i,j,k)
            senddata_list.append(temp)
        
        while RealData.running:
            try:    
                async with websockets.connect(url, ping_interval=None) as websocket:

                    for senddata in senddata_list:
                        await websocket.send(senddata)
                        await asyncio.sleep(0.5)
                        print(f"Input Command is :{senddata}")

                    while RealData.running:
                        
                        print('셀프러닝 ==', RealData.running)

                        try:
                            
                            data = await websocket.recv()
                    

                           
                            # await asyncio.sleep(0.5)
                            print(f"Recev Command is :{data}")  # 정제되지 않은 Request / Response 출력
                            print("데이터[0]: ", data[0])
                            if data[0] == '0':
                                recvstr = data.split('|')  # 수신데이터가 실데이터 이전은 '|'로 나뉘어져있어 split
                                trid0 = recvstr[1]

                                if trid0 == "H0STCNPO":
                                    data_cnt = int(recvstr[2])
                                    pValue = recvstr[3].split('^')
                                    rdata = [pValue[i:i + 46] for i in range(0, len(pValue), 46)]
                                    #return rdata
                                    


                                
                                    # await asyncio.sleep(0.2)

                                elif trid0 == "H0STCNT0":  # 주식체결 데이터 처리
                                    print("#### 주식체결 ####")
                                    data_cnt = int(recvstr[2])  # 체결데이터 개수
                                    print(type(data_cnt),data_cnt)
                                    print(type(recvstr[3]),recvstr[3])
                                    print('RealData.running== ', RealData.running)
                                    if RealData.running == 'False':
                                        return False
                                    else:
                                        rd.stockspurchase_domestic(data_cnt, recvstr[3])
                                  
                                   
  
                                    
                                elif trid0 == "H0STMBC0":  # 국내주식 실시간회원사 데이터 처리
                                    print("#### 국내주식 실시간회원사 ####")
                                    data_cnt = int(recvstr[2])  # 데이터 개수
                                    rd.stocksmember_domestic(data_cnt, recvstr[3])
                                    # await asyncio.sleep(0.2) 

                                elif trid0 == "H0STPGM0":  # 국내주식 실시간프로그램매매 데이터 처리
                                    print("#### 국내주식 실시간프로그램매매 ####")
                                    data_cnt = int(recvstr[2])  # 데이터 개수
                                    rd.stocksprogramtrade_domestic(data_cnt, recvstr[3])
                                    # await asyncio.sleep(0.2)                        
                                    
                                elif trid0 == "H0STMKO0":  # 국내주식 장운영정보 데이터 처리
                                    print("#### 국내주식 장운영정보 ####")
                                    data_cnt = int(recvstr[2])  # 데이터 개수
                                    rd.stocksmarketinfo_domestic(data_cnt, recvstr[3])  
                                    
                                elif trid0 == "H0UPCNT0":  # 국내지수 체결 데이터 처리
                                    print("#### 국내지수 체결 ####")
                                    data_cnt = int(recvstr[2])  # 체결데이터 개수
                                    rd.indexpurchase_domestic(data_cnt, recvstr[3])
                                    # await asyncio.sleep(0.2) 
                                    
                                elif trid0 == "H0UPANC0":  # 국내지수 예상체결 데이터 처리
                                    print("#### 국내지수 예상체결 ####")
                                    data_cnt = int(recvstr[2])  # 체결데이터 개수
                                    rd.indexexppurchase_domestic(data_cnt, recvstr[3])
                                    # await asyncio.sleep(0.2) 
                                    
                                elif trid0 == "H0UPPGM0":  # 국내지수 예상체결 데이터 처리
                                    print("#### 국내지수 실시간프로그램매매 ####")
                                    data_cnt = int(recvstr[2])  # 체결데이터 개수
                                    rd.indexprogramtrade_domestic(data_cnt, recvstr[3])
                                    # await asyncio.sleep(0.2)    

                                
                            elif data[0] == '1':

                                recvstr = data.split('|')  # 수신데이터가 실데이터 이전은 '|'로 나뉘어져있어 split
                                trid0 = recvstr[1]

                                if trid0 == "H0STCNI0" or trid0 == "H0STCNI9":  # 주실체결 통보 처리
                                    rd.stocksigningnotice_domestic(recvstr[3], aes_key, aes_iv)
                                    # await asyncio.sleep(0.2)


                            else:

                                jsonObject = json.loads(data)
                                trid = jsonObject["header"]["tr_id"]

                                if trid != "PINGPONG":
                                    rt_cd = jsonObject["body"]["rt_cd"]

                                    if rt_cd == '1':  # 에러일 경우 처리

                                        if jsonObject["body"]["msg1"] != 'ALREADY IN SUBSCRIBE':
                                            print("### ERROR RETURN CODE [ %s ][ %s ] MSG [ %s ]" % (jsonObject["header"]["tr_key"], rt_cd, jsonObject["body"]["msg1"]))
                                        break

                                    elif rt_cd == '0':  # 정상일 경우 처리
                                        print("### RETURN CODE [ %s ][ %s ] MSG [ %s ]" % (jsonObject["header"]["tr_key"], rt_cd, jsonObject["body"]["msg1"]))

                                        # 체결통보 처리를 위한 AES256 KEY, IV 처리 단계
                                        if trid == "H0STCNI0" or trid == "H0STCNI9": # 국내주식
                                            aes_key = jsonObject["body"]["output"]["key"]
                                            aes_iv = jsonObject["body"]["output"]["iv"]
                                            print("### TRID [%s] KEY[%s] IV[%s]" % (trid, aes_key, aes_iv))



                                elif trid == "PINGPONG":
                                    print("### RECV [PINGPONG] [%s]" % (data))
                                    await websocket.pong(data)
                                    print("### SEND [PINGPONG] [%s]" % (data))

                        except websockets.ConnectionClosed:
                            print("WebSocket connection closed. Reconnecting...")
                            break
                            
            except websockets.ConnectionClosed:
                print("WebSocket connection closed. Reconnecting...")
                continue
            except Exception as e:
                print(f"An error occurred: {e}")
                break                
    # 비동기로 서버에 접속한다.
    # asyncio.get_event_loop().run_until_complete(connect())
    # asyncio.get_event_loop().close()
            
    #비동기 동작 정지       
    async def stop(self):       
        RealData.running = False
        print("스탑인데..", RealData.running)
        if self.task:
            self.task.cancel()  # Cancel the asyncio task
            await self.task  # Wait for the task to be cancelled

    async def start(self, code_list, trade_type, r_method):
        # Start the asyncio task
        self.task = asyncio.create_task(self.connect(code_list, trade_type, r_method))
        await self.task  # Wait for the task to be completed

  