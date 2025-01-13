# requests 모듈 설치 필요 (pip install requests)
import requests
import json
import time 

#1모의투자 /토큰발급용 / 토큰 발급후 24시간 사용 가능

class KTrade:

    def approvalKey(key,secret,url):
        
        #print(key,secret,url)
        body = {
        "grant_type": "client_credentials",
        "appkey": key,
        "secretkey": secret
        }
        headers = {
        }
       # print(body)
        key = requests.post(url, data=json.dumps(body))
        rescode = key.status_code
        if rescode == 200:
          #  print(key)
            print(str(rescode) + " | " + key.text)

        else:
            print("Error Code : " + str(rescode) + " | " + key.text)
        
        # JSON 문자열 파싱
        dic_key = json.loads(key.text)      
        # access_token 값 추출하여 변수에 할당
        approval_key = dic_key['approval_key']
        #print("승인키= ", approval_key)

        return approval_key

    #2접근토큰발급(P)[인증-001]
    def tokenP(key,secret,url):
        

        body = {
        "grant_type": "client_credentials",
        "appkey": key,
        "appsecret": secret
        }
        headers = {
        }
        #print(body)
        token = requests.post(url, data=json.dumps(body))
        rescode = token.status_code
        if rescode == 200:
            #print(token)
            print(str(rescode) + " | " + token.text)
          
        else:
            print("Error Code : " + str(rescode) + " | " + token.text)
        
        #JSON 문자열 파싱
        dic_token = json.loads(token.text)
        #access_token 값 추출하여 변수 전달
        access_token = dic_token['access_token']
        token_expire = dic_token['access_token_token_expired']
        return access_token, token_expire

    #3발급토큰 폐기 
    def revoke_token(tokenP):
        url = 'https://openapivts.koreainvestment.com:29443/oauth2/revokeP'

        body = {
        "grant_type": "client_credentials",
        "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
        "token" : tokenP
        }
        headers = {
        }

        reboke = requests.post(url, data=json.dumps(body))
        rescode =  reboke.status_code
        if rescode == 200:
            print( reboke)
            print(str(rescode) + " | " +  reboke.text)
            return reboke.text
        else:
            print("Error Code : " + str(rescode) + " | " +  reboke.text)
            return reboke.text

    #4.주문 / 매도===================================================================
    def order(stockcode,buyqty,buyprice,tokenP,ordermethod):

        url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/trading/order-cash'
        body = {
            "CANO": "50110575", #종합계좌번호
            "ACNT_PRDT_CD": "", #계좌상품코드
            "PDNO": stockcode,#종목코드 6자리(A제외, Q는 Q포함 7자리)
            "ORD_DVSN": "00",#주문구분
            # 00 : 지정가
            # 01 : 시장가
            # 02 : 조건부지정가
            # 03 : 최유리지정가
            # 04 : 최우선지정가
            # 05 : 장전 시간외 (08:20~08:40)
            # 06 : 장후 시간외 (15:30~16:00)
            # 07 : 시간외 단일가(16:00~18:00)
            # 08 : 자기주식
            # 09 : 자기주식S-Option
            # 10 : 자기주식금전신탁
            # 11 : IOC지정가 (즉시체결,잔량취소)
            # 12 : FOK지정가 (즉시체결,전량취소)
            # 13 : IOC시장가 (즉시체결,잔량취소)
            # 14 : FOK시장가 (즉시체결,전량취소)
            # 15 : IOC최유리 (즉시체결,잔량취소)
            # 16 : FOK최유리 (즉시체결,전량취소)
            "ORD_QTY": buyqty, #주문수량
            "ORD_UNPR": buyprice, #주문단가
            "CTAC_TLNO": "01067894764" #연락전화번호
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
            "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": ordermethod,
            #[실전투자]
            #TTTC0802U : 주식 현금 매수 주문
            #TTTC0801U : 주식 현금 매도 주문
            #[모의투자]
            #VTTC0802U : 주식 현금 매수 주문
            #VTTC0801U : 주식 현금 매도 주문
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }
        time.sleep(0.5)
        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
       
        data_dict = json.loads(res.text)
        rt_cd_value = data_dict["rt_cd"]
        msg_cd = data_dict["msg_cd"]

        if "output" in data_dict:
            odno_value = data_dict["output"].get("ODNO")
            if odno_value is not None:
                print("ODNO 값:", odno_value)
            else:
                print("ODNO 키에 대한 값이 존재하지 않습니다.")
        else:
            print("output 키가 존재하지 않습니다.")
            odno_value = '0'

       # print(res_dic)
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return rt_cd_value, odno_value, msg_cd
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            odno_value = '0'
            return rt_cd_value, odno_value, msg_cd

    #5 정정/취소
    def changeorder(ordernum,buyqty,buyprice,tokenP,ordermethod, selectorder):
        url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/trading/order-rvsecncl'
        body = {
            #실계좌
            # "CANO": "71017340", #종합계좌번호
            # "ACNT_PRDT_CD": "01", #계좌상품코드
            #모의투자
            "CANO": "50110575", #종합계좌번호
            "ACNT_PRDT_CD": "", #계좌상품코드

            "KRX_FWDG_ORD_ORGNO": "", # 정정취소/ 	"" (Null 값 설정) 주문시 한국투자증권 시스템에서 지정된 영업점코드
            "ORGN_ODNO": ordernum, # 원주문번호 /주식일별주문체결조회 API output1의 odno(주문번호) 값 입력주문시 한국투자증권 시스템에서 채번된 주문번호

            # "PDNO": stockcode,#종목코드 6자리(A제외, Q는 Q포함 7자리)
            "ORD_DVSN": "00",#주문구분
            # 00 : 지정가
            # 01 : 시장가
            # 02 : 조건부지정가
            # 03 : 최유리지정가
            # 04 : 최우선지정가
            # 05 : 장전 시간외 (08:20~08:40)
            # 06 : 장후 시간외 (15:30~16:00)
            # 07 : 시간외 단일가(16:00~18:00)
            # 08 : 자기주식
            # 09 : 자기주식S-Option
            # 10 : 자기주식금전신탁
            # 11 : IOC지정가 (즉시체결,잔량취소)
            # 12 : FOK지정가 (즉시체결,전량취소)
            # 13 : IOC시장가 (즉시체결,잔량취소)
            # 14 : FOK시장가 (즉시체결,전량취소)
            # 15 : IOC최유리 (즉시체결,잔량취소)
            # 16 : FOK최유리 (즉시체결,전량취소)

            "RVSE_CNCL_DVSN_CD": selectorder, # 정정취소 / 정정취소구분코드  정정 : 01 취소 : 02
            "ORD_QTY": buyqty, #주문수량
            # [잔량전부 취소/정정주문]
            # "0" 설정 ( QTY_ALL_ORD_YN=Y 설정 )

            # [잔량일부 취소/정정주문]
            # 취소/정정 수량           

            "ORD_UNPR": buyprice, #주문단가
            # [정정]
            # (지정가) 정정주문 1주당 가격
            # (시장가) "0" 설정
            # [취소]
            # "0" 설정

            # "CTAC_TLNO": "01067894764" #연락전화번호
            "QTY_ALL_ORD_YN": "Y" # 정정취소 /	잔량전부주문여부 
                # [정정/취소]
                # Y : 잔량전부
                # N : 잔량일부
        }


        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
            "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": ordermethod,
            # [실전투자]
            # TTTC0803U : 주식 정정 취소 주문
            # [모의투자]
            # VTTC0803U : 주식 정정 취소 주문

            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }
        time.sleep(0.5)
        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code

        data_dict = json.loads(res.text)
        rt_cd_value = data_dict["rt_cd"]
        msg_cd = data_dict["msg_cd"]  # 200 | {"rt_cd":"1","msg_cd":"40330000","msg1":"모의투자 정정/취소할 수량이 없습니다."}
        print("rt_cd_value:",rt_cd_value,"msg_cd: ", msg_cd)

        if "output" in data_dict:
            odno_value = data_dict["output"].get("ODNO")
            if odno_value is not None:
                print("ODNO 값:", odno_value)
            else:
                print("ODNO 키에 대한 값이 존재하지 않습니다.")
        else:
            print("output 키가 존재하지 않습니다.")
            odno_value = '0'

       # print(res_dic)
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            print("rt_cd_value222:",rt_cd_value,"msg_cd222: ", msg_cd)
  
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            odno_value = '0'

        return rt_cd_value, odno_value, msg_cd


    # 6주식정정취소가능주문조회[v1_국내주식-004] // 
    # ================= 모의 투자 사용 불가 ==================================
    def numremainder(ordernum,buyqty,buyprice,tokenP,ordermethod, selectorder):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl'
        params = {
            "CANO": "71017340", #종합계좌번호
            "ACNT_PRDT_CD": "01", #계좌상품코드

            "CTX_AREA_FK100": "", #	연속조회검색조건100 -	공란 : 최초 조회시 이전 조회 Output CTX_AREA_FK100 값 : 다음페이지 조회시(2번째부터)
            "CTX_AREA_NK100": "", # 연속조회키100 - 공란 : 최초 조회시 이전 조회 Output CTX_AREA_NK100 값 : 다음페이지 조회시(2번째부터)
            "INQR_DVSN_1": "0", # 조회구분1
            #	0 : 조회순서
            # 1 : 주문순
            # 2 : 종목순
            "INQR_DVSN_2": "0"
            # 0 : 전체
            # 1 : 매도
            # 2 : 매수
        
        }


        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
            "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": ordermethod,
            #[실전투자]
            #TTTC0802U : 주식 현금 매수 주문
            #TTTC0801U : 주식 현금 매도 주문
            #[모의투자]
            #VTTC0802U : 주식 현금 매수 주문
            #VTTC0801U : 주식 현금 매도 주문
            "tr_cont": " ", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }
        # GET 방식 주의
        res = requests.get(url, params=params, headers=headers) 
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text

    # 7.매수가능조회[v1_국내주식-007]
    def bal_amount(stockcode,tokenP,ordermethod):
        url = 'https://openapi.koreainvestment.com:29443/uapi/domestic-stock/v1/trading/inquire-psbl-order'
        params = {
            "CANO": "71017340", #종합계좌번호
            "ACNT_PRDT_CD": "01", #계좌상품코드
            "PDNO": stockcode,#종목코드 6자리(A제외, Q는 Q포함 7자리)
            "ORD_DVSN": "00",#주문구분
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
            # 51 : 장중대량
            # 52 : 장중바스켓
            # 62 : 장개시전 시간외대량
            # 63 : 장개시전 시간외바스켓
            # 67 : 장개시전 금전신탁자사주
            # 69 : 장개시전 자기주식
            # 72 : 시간외대량
            # 77 : 시간외자사주신탁
            # 79 : 시간외대량자기주식
            # 80 : 바스켓

            # "ORD_QTY": buyqty, #주문수량
            # "ORD_UNPR": buyprice, #주문단가
            # "CTAC_TLNO": "01067894764" #연락전화번호
            "CMA_EVLU_AMT_ICLD_YN": "N", #CMA평가금액포함여부 -	Y : 포함 N : 포함하지 않음
            "OVRS_ICLD_YN": "N" #해외포함여부	 #	Y : 포함 N : 포함하지 않음
        }


        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
            "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": ordermethod,
            #[실전투자]
            #TTTC0802U : 주식 현금 매수 주문
            #TTTC0801U : 주식 현금 매도 주문
            #[모의투자]
            #VTTC0802U : 주식 현금 매수 주문
            #VTTC0801U : 주식 현금 매도 주문
            "tr_cont": " ", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }
        # GET 방식 주의
        res = requests.get(url, params=params, headers=headers) 
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text

    # 8. 주식일별주문체결조회[v1_국내주식-005]
    def daily_trade_list(startdate,enddate,tokenP,ordermethod,selecttrade):
        url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/trading/inquire-daily-ccld'
        
        fk100 = ''
        nk100 = ''
        res_dic_output =[]
        while True:
            params = {
                #실계좌
                # "CANO": "71017340", #종합계좌번호
                # "ACNT_PRDT_CD": "01", #계좌상품코드
                # 모의투자
                "CANO": "50110575", #종합계좌번호 
                "ACNT_PRDT_CD": "", #계좌상품코드

                "INQR_STRT_DT": startdate, #조회시작일자 YYYYMMDD
                "INQR_END_DT": enddate, #조회종료일자 YYYYMMDD
                "SLL_BUY_DVSN_CD":selecttrade, #	매도매수구분코드 00:전체 01:매도  02:매수
                "INQR_DVSN": "00", #조회구분  00 : 역순 01 : 정순
                "PDNO": "", # 종목번호(6자리) 공란 : 전체 조회
                "CCLD_DVSN": "00", # 체결구분 	00 : 전체 01 : 체결 02 : 미체결
                "ORD_GNO_BRNO": "", #주문채번지점번호 null
                "ODNO": "", # 주문번호 null
                "INQR_DVSN_3": "00", #조회구분3 00 : 전체 01 : 현금 02 : 융자 03 : 대출 04 : 대주
                "INQR_DVSN_1": "", # 공란 : 전체 1 : ELW 2 : 프리보드
                "CTX_AREA_FK100": fk100, #연속조회검색조건100 
                # 공란 : 최초 조회시
                # 이전 조회 Output CTX_AREA_FK100 값 : 다음페이지 조회시(2번째부터)
                "CTX_AREA_NK100": nk100 #연속조회키100
                # 공란 : 최초 조회시
                # 이전 조회 Output CTX_AREA_NK100 값 : 다음페이지 조회시(2번째부터)

            }


            # 주문/매도, 정정/취소 공통
            headers = {
                "Content-Type": "application/json",
                "authorization": "Bearer " + tokenP,
                "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
                "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
                "personalSeckey": "", # 법인에 한함
                "tr_id": ordermethod,
                #[실전투자]
                #TTTC0802U : 주식 현금 매수 주문
                #TTTC0801U : 주식 현금 매도 주문
                #[모의투자]
                #VTTC0802U : 주식 현금 매수 주문
                #VTTC0801U : 주식 현금 매도 주문
                "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
                "custtype": "P", #법인(B), 개인(P)
                "seq_no": "",  #법인(01), 개인( )
                "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
                "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
                "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
                "hashkey": "", #※ 입력 불필요
                "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
            }
            # GET 방식 주의
            time.sleep(0.5)
            res = requests.get(url, params=params, headers=headers) 
            rescode = res.status_code
            print(res)
            print('헤더카운트는:', res.headers.get('tr_cont'))

            res_dic = json.loads(res.text)
     
            # if res.headers.get('tr_cont') =='F' or res.headers.get('tr_cont') == 'M':
            #     fk100 = res_dic.get('ctx_area_fk100')
            #     nk100 = res_dic.get('ctx_area_nk100')
            #     if "output1" in res_dic:
   
                        
            # 헤더 검사 및 처리
            if res.headers.get('tr_cont') in ['F', 'M']:
                fk100 = res_dic.get('ctx_area_fk100')
                nk100 = res_dic.get('ctx_area_nk100')
                if "output1" in res_dic:
                    res_dic_output.append(res_dic["output1"])
                else:
                    print("output 키가 존재하지 않습니다.")
                    res_dic_output = None
            else:
                if "output1" in res_dic:
                    res_dic_output.append(res_dic["output1"])
                    # merged_data = [item for sublist in res_dic_output for item in sublist] #간단버전 
                    merged_data = []
                    for sublist in res_dic_output:
                        for item in sublist:
                            merged_data.append(item)
                
                else:
                    print("output 키가 존재하지 않습니다.")
                    res_dic_output = None

                
                if rescode == 200:
                    print(res.headers)
                    print(str(rescode) + " | " + res.text)
                    return merged_data
                else:
                    print("Error Code : " + str(rescode) + " | " + res.text)
                    return merged_data
                
            print(res.headers)
            print(str(rescode) + " | " + res.text)



    # 9. 주식잔고조회[v1_국내주식-006]#######################################################33
    def trade_remainder_list(tokenP):

        url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/trading/inquire-balance'
        
        fk100 = ''
        nk100 = ''
        res_dic_output =[]
        while True:
            params = {
                #실계좌
                # "CANO": "71017340", #종합계좌번호
                # "ACNT_PRDT_CD": "01", #계좌상품코드

                # 모의투자
                "CANO": "50110575", #종합계좌번호 
                "ACNT_PRDT_CD": "", #계좌상품코드

                "AFHR_FLPR_YN": "N", #	시간외단일가여부 	N : 기본값 Y : 시간외단일가
                "OFL_YN": "N",  #오프라인여부 	공란(Default)
                "INQR_DVSN": "02", # 조회구분 01:대출일별 02:종목별
                "UNPR_DVSN": "01", #단가조회 01:기본값
                "FUND_STTL_ICLD_YN": "N", #펀드결제품포함여부 N: 미포함, Y:포함
                "FNCG_AMT_AUTO_RDPT_YN": "N", #융자금액자동상환여부 N : 기본값 
                "PRCS_DVSN": "01", #처리구분 	00 : 전일매매포함 01 : 전일매매미포함
                "CTX_AREA_FK100": fk100, #연속조회검색조건100 
                # 공란 : 최초 조회시
                # 이전 조회 Output CTX_AREA_FK100 값 : 다음페이지 조회시(2번째부터)
                "CTX_AREA_NK100": nk100 #연속조회키100
                # 공란 : 최초 조회시
                # 이전 조회 Output CTX_AREA_NK100 값 : 다음페이지 조회시(2번째부터)

            }


            # 주문/매도, 정정/취소 공통
            headers = {
                "Content-Type": "application/json",
                "authorization": "Bearer " + tokenP,
                "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
                "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
                "personalSeckey": "", # 법인에 한함
                "tr_id": 'VTTC8434R', # 모의 투자
            # [실전투자]
            # TTTC8434R : 주식 잔고 조회

            # [모의투자]
            # VTTC8434R : 주식 잔고 조회

                "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
                "custtype": "P", #법인(B), 개인(P)
                "seq_no": "",  #법인(01), 개인( )
                "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
                "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
                "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
                "hashkey": "", #※ 입력 불필요
                "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
            }
            # GET 방식 주의
            time.sleep(0.5)
            res = requests.get(url, params=params, headers=headers) 
            rescode = res.status_code
            print(res)
            print('헤더카운트는:', res.headers.get('tr_cont'))

            res_dic = json.loads(res.text)
            print('res_dic : ', res_dic)
     
            # if res.headers.get('tr_cont') =='F' or res.headers.get('tr_cont') == 'M':
            #     fk100 = res_dic.get('ctx_area_fk100')
            #     nk100 = res_dic.get('ctx_area_nk100')
            #     if "output1" in res_dic:
   
                        
            # 헤더 검사 및 처리
            if res.headers.get('tr_cont') in ['F', 'M']:
                fk100 = res_dic.get('ctx_area_fk100')
                nk100 = res_dic.get('ctx_area_nk100')
                if "output1" in res_dic:
                    res_dic_output.append(res_dic["output1"])
                else:
                    print("output 키가 존재하지 않습니다.")
                    res_dic_output = None
            else:
                #########################################################################
                # 여기에서   File "C:\projects\daram\pybo\service\k_trade.py", line 609, in trade_remainder_list
                #res_dic_output.append(res_dic["output1"])
                # AttributeError: 'NoneType' object has no attribute 'append'  에러발생
                #########################################################################
                if "output1" in res_dic:
                    res_dic_output.append(res_dic["output1"])
                    # merged_data = [item for sublist in res_dic_output for item in sublist] #간단버전 
                    merged_data = []
                    for sublist in res_dic_output:
                        for item in sublist:
                            merged_data.append(item)
                
                else:
                    print("output 키가 존재하지 않습니다.")
                    res_dic_output = None

                
                if rescode == 200:
                    print(res.headers)
                    print(str(rescode) + " | " + res.text)
                    return merged_data
                else:
                    print("Error Code : " + str(rescode) + " | " + res.text)
                    #return merged_data
                
            print(res.headers)
            print(str(rescode) + " | " + res.text)