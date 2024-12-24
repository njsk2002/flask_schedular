# requests 모듈 설치 필요 (pip install requests)
import requests
import json

# ===========================================================================
#    모의 투자 미지원          모의 투자 미지원
# ===========================================================================

class KAnalysis:
    ####################################################################################################
    #1 거래량순위[v1_국내주식-047]
    ####################################################################################################
    def trade_volume(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/volume-rank'
        params = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20171", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 기타(업종코드)
                "FID_DIV_CLS_CODE":"0", # 분류 구분 코드 0(전체) 1(보통주) 2(우선주)
                "FID_BLNG_CLS_CODE":"0", #소속 구분 코드 	0 : 평균거래량 1:거래증가율 2:평균거래회전율 3:거래금액순 4:평균거래금액회전율
                "FID_TRGT_CLS_CODE":"111111111", # 대상 구분 코드 	
                # 1 or 0 9자리 (차례대로 증거금 30% 40% 50% 60% 100% 신용보증금 30% 40% 50% 60%) ex) "111111111"
                "FID_TRGT_EXLS_CLS_CODE":"000000", #대상 제외 구분 코드 
                # 1 or 0 6자리 (차례대로 투자위험/경고/주의 관리종목 정리매매 불성실공시 우선주 거래정지) ex) "000000"
                "FID_INPUT_PRICE_1":"", #입력 가격1  	
                # 가격 ~ ex) "0" 전체 가격 대상 조회 시 FID_INPUT_PRICE_1, FID_INPUT_PRICE_2 모두 ""(공란) 입력
                "FID_INPUT_PRICE_2":"",  #입력 가격2
                # ~ 가격 ex) "1000000" 전체 가격 대상 조회 시 FID_INPUT_PRICE_1, FID_INPUT_PRICE_2 모두 ""(공란) 입력
                "FID_VOL_CNT":"", # 거래량 수  거래량 ~ ex) "100000" 전체 거래량 대상 조회 시 FID_VOL_CNT ""(공란) 입력
                "FID_INPUT_DATE_1":"" #입력 날짜1  	""(공란) 입력
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01710000",
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.get(url, params=params, headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text
        

    ######################################################################################################################################
    #2 국내주식 등락률 순위[v1_국내주식-088]
        # 한국투자 HTS(eFriend Plus) > [0170] 등락률 순위 화면의 기능을 API로 개발한 사항으로, 해당 화면을 참고하시면 기능을 이해하기 쉽습니다.
        # 최대 30건 확인 가능하며, 다음 조회가 불가합니다.

        # ※ 30건 이상의 목록 조회가 필요한 경우, 대안으로 종목조건검색 API를 이용해서 원하는 종목 100개까지 검색할 수 있는 기능을 제공하고 있습니다.
        # 종목조건검색 API는 HTS(efriend Plus) [0110] 조건검색에서 등록 및 서버저장한 나의 조건 목록을 확인할 수 있는 API로,
        # 자세한 사용 방법은 공지사항 - [조건검색 필독] 조건검색 API 이용안내 참고 부탁드립니다.
    #######################################################################################################################################
    def high_rate(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/fluctuation'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20170", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_rank_sort_cls_code":"0", # 순위 정렬 구분 코드 0:상승율순 1:하락율순 2:시가대비상승율 3:시가대비하락율 4:변동율
                "fid_input_cnt_1":"0", # 입력 수1 0:전체 , 누적일수 입력
                "fid_prc_cls_code":"0", #가격 구분 코드 
                            # 'fid_rank_sort_cls_code :0 상승율 순일때 (0:저가대비, 1:종가대비)
                            # fid_rank_sort_cls_code :1 하락율 순일때 (0:고가대비, 1:종가대비)
                            # fid_rank_sort_cls_code : 기타 (0:전체)'
                "fid_input_price_1":"", # 입력 가격1 입력값 없을때 전체 (가격 ~)
                "fid_input_price_2":"", # 입력 가격2 입력값 없을때 전체 (~ 가격)
                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                "fid_trgt_cls_code":"0", # 대상 구분 코드 0:전체
                "fid_trgt_exls_cls_code":"0", #대상 제외 구분 코드 	0:전체
                "fid_div_cls_code":"0", #분류 구분 코드 0:전체
                "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01700000", #거래ID
            "tr_cont": " ", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text

    #3  국내주식 시간외잔량 순위[v1_국내주식-093] ========================================
    ######################################################################################################################################
      #3  국내주식 시간외잔량 순위[v1_국내주식-093] ========================================
    #######################################################################################################################################
    def stock_remain_aftermarket(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/after-hour-balance'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20176", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_div_cls_code":"0", #분류 구분 코드 0:전체
                "fid_rank_sort_cls_code":"0", # 순위 정렬 구분 코드 0:상승율순 1:하락율순 2:시가대비상승율 3:시가대비하락율 4:변동율
                "fid_trgt_cls_code":"0", # 대상 구분 코드 0:전체
                "fid_trgt_exls_cls_code":"0", #대상 제외 구분 코드 	0:전체

                            # 'fid_rank_sort_cls_code :0 상승율 순일때 (0:저가대비, 1:종가대비)
                            # fid_rank_sort_cls_code :1 하락율 순일때 (0:고가대비, 1:종가대비)
                            # fid_rank_sort_cls_code : 기타 (0:전체)'
                "fid_input_price_1":"", # 입력 가격1 입력값 없을때 전체 (가격 ~)
                "fid_input_price_2":"", # 입력 가격2 입력값 없을때 전체 (~ 가격)
                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01760000", #거래ID 	FHPST01760000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text
        

    
    ######################################################################################################################################
     #4  국내주식 우선주/괴리율 상위[v1_국내주식-094] =====================================
    #######################################################################################################################################
    def rank_pre_stock(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/prefer-disparate-ratio'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20177", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_div_cls_code":"0", #분류 구분 코드 0:전체
                "fid_rank_sort_cls_code":"0", # 순위 정렬 구분 코드 0:상승율순 1:하락율순 2:시가대비상승율 3:시가대비하락율 4:변동율
                "fid_trgt_cls_code":"0", # 대상 구분 코드 0:전체
                "fid_trgt_exls_cls_code":"0", #대상 제외 구분 코드 	0:전체

                            # 'fid_rank_sort_cls_code :0 상승율 순일때 (0:저가대비, 1:종가대비)
                            # fid_rank_sort_cls_code :1 하락율 순일때 (0:고가대비, 1:종가대비)
                            # fid_rank_sort_cls_code : 기타 (0:전체)'
                "fid_input_price_1":"", # 입력 가격1 입력값 없을때 전체 (가격 ~)
                "fid_input_price_2":"", # 입력 가격2 입력값 없을때 전체 (~ 가격)
                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01770000", #거래ID 	FHPST01770000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text
        
    
    ######################################################################################################################################
     #5  국내주식 호가잔량 순위[국내주식-089] ============================================
    #######################################################################################################################################
    def rank_pre_stock(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/quote-balance'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20172", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_div_cls_code":"0", #분류 구분 코드 0:전체
                "fid_rank_sort_cls_code":"0", # 순위 정렬 구분 코드 0:상승율순 1:하락율순 2:시가대비상승율 3:시가대비하락율 4:변동율
                "fid_trgt_cls_code":"0", # 대상 구분 코드 0:전체
                "fid_trgt_exls_cls_code":"0", #대상 제외 구분 코드 	0:전체

                            # 'fid_rank_sort_cls_code :0 상승율 순일때 (0:저가대비, 1:종가대비)
                            # fid_rank_sort_cls_code :1 하락율 순일때 (0:고가대비, 1:종가대비)
                            # fid_rank_sort_cls_code : 기타 (0:전체)'
                "fid_input_price_1":"", # 입력 가격1 입력값 없을때 전체 (가격 ~)
                "fid_input_price_2":"", # 입력 가격2 입력값 없을때 전체 (~ 가격)
                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01720000", #거래ID 		FHPST01720000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text
        

    ######################################################################################################################################
     #6  국내주식 이격도 순위[v1_국내주식-095] ============================================
    #######################################################################################################################################
    def rank_disparity(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/disparity'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20178", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_div_cls_code":"0", #분류 구분 코드 0: 전체, 1:관리종목, 2:투자주의, 3:투자경고, 4:투자위험예고, 5:투자위험, 6:보톧주, 7:우선주
                "fid_rank_sort_cls_code":"0", # 순위 정렬 구분 코드 0:상승율순 1:하락율순 2:시가대비상승율 3:시가대비하락율 4:변동율
                "fid_trgt_cls_code":"0", # 대상 구분 코드 0:전체
                "fid_trgt_exls_cls_code":"0", #대상 제외 구분 코드 	0:전체

                            # 'fid_rank_sort_cls_code :0 상승율 순일때 (0:저가대비, 1:종가대비)
                            # fid_rank_sort_cls_code :1 하락율 순일때 (0:고가대비, 1:종가대비)
                            # fid_rank_sort_cls_code : 기타 (0:전체)'
                "fid_input_price_1":"", # 입력 가격1 입력값 없을때 전체 (가격 ~)
                "fid_input_price_2":"", # 입력 가격2 입력값 없을때 전체 (~ 가격)
                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01780000", #거래ID 		FHPST01780000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text        


   
    ######################################################################################################################################
    #7  국내주식 체결강도 상위[v1_국내주식-101] ===========================================
    #######################################################################################################################################
    def rank_volume_power(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/volume-power'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20168", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_div_cls_code":"0", #분류 구분 코드 0:전체
                "fid_rank_sort_cls_code":"0", # 순위 정렬 구분 코드 0:상승율순 1:하락율순 2:시가대비상승율 3:시가대비하락율 4:변동율
                "fid_trgt_cls_code":"0", # 대상 구분 코드 0:전체
                "fid_trgt_exls_cls_code":"0", #대상 제외 구분 코드 	0:전체

                            # 'fid_rank_sort_cls_code :0 상승율 순일때 (0:저가대비, 1:종가대비)
                            # fid_rank_sort_cls_code :1 하락율 순일때 (0:고가대비, 1:종가대비)
                            # fid_rank_sort_cls_code : 기타 (0:전체)'
                "fid_input_price_1":"", # 입력 가격1 입력값 없을때 전체 (가격 ~)
                "fid_input_price_2":"", # 입력 가격2 입력값 없을때 전체 (~ 가격)
                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01680000", #거래ID 		FHPST01680000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text        
        

    
    ######################################################################################################################################
    #8  국내주식 관심종목등록 상위[v1_국내주식-102] =========================================
    #######################################################################################################################################
    def rank_interest_stock(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/top-interest-stock'
        body = {
                "fid_input_iscd_2":"000000",
                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20180", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)

                "fid_rank_sort_cls_code":"0", # 순위 정렬 구분 코드 0:상승율순 1:하락율순 2:시가대비상승율 3:시가대비하락율 4:변동율
                "fid_trgt_cls_code":"0", # 대상 구분 코드 0:전체
                "fid_trgt_exls_cls_code":"0", #대상 제외 구분 코드 	0:전체

                            # 'fid_rank_sort_cls_code :0 상승율 순일때 (0:저가대비, 1:종가대비)
                            # fid_rank_sort_cls_code :1 하락율 순일때 (0:고가대비, 1:종가대비)
                            # fid_rank_sort_cls_code : 기타 (0:전체)'
                "fid_input_price_1":"", # 입력 가격1 입력값 없을때 전체 (가격 ~)
                "fid_input_price_2":"", # 입력 가격2 입력값 없을때 전체 (~ 가격)
                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                "fid_input_cnt_1":"1"
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01680000", #거래ID 		FHPST01680000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text                


   
    ######################################################################################################################################
     #9  국내주식 예상체결 상승/하락상위[v1_국내주식-103] ===================================
    #######################################################################################################################################
    def rank_exp_trade(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/exp-trans-updown'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20182", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_div_cls_code":"0", #0:전체 1:보통주 2:우선주
                "fid_aply_rang_prc_1":"", #입력값 없을때 전체 (가격 ~)


                            # 'fid_rank_sort_cls_code :0 상승율 순일때 (0:저가대비, 1:종가대비)
                            # fid_rank_sort_cls_code :1 하락율 순일때 (0:고가대비, 1:종가대비)
                            # fid_rank_sort_cls_code : 기타 (0:전체)'

                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                "fid_pbmn":"", #입력값 없을때 전체 (거래대금 ~) 천원단위
                "fid_blng_cls_code":"0", #0: 전체
                "fid_mkop_cls_code":"0", #0:장전예상1:장마감예상
                "fid_rank_sort_cls_code":"0" #	0:상승률1:상승폭2:보합3:하락율4:하락폭5:체결량6:거래대금
          
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01820000", #거래ID 		FHPST01820000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text                
       


    
    ######################################################################################################################################
    #10 국내주식 신고/신저근접종목 상위[v1_국내주식-105] ====================================
    #######################################################################################################################################
    def rank_new_highlow(tokenP,newhighlow): #0:신고근접, 1:신저근접
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/near-new-highlow'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"20187", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_div_cls_code":"0", #0:전체 1:보통주 2:우선주
                "fid_prc_cls_code": newhighlow, #0:신고근접, 1:신저근접
                "fid_input_cnt_1":"", #괴리율 최소
                "fid_input_cnt_2":"", #괴리율 최대

                            # 'fid_rank_sort_cls_code :0 상승율 순일때 (0:저가대비, 1:종가대비)
                            # fid_rank_sort_cls_code :1 하락율 순일때 (0:고가대비, 1:종가대비)
                            # fid_rank_sort_cls_code : 기타 (0:전체)'

                "fid_trgt_cls_code":"0", #	0: 전체
                "fid_trgt_exls_cls_code":"0", #	0:전체, 1:관리종목, 2:투자주의, 3:투자경고, 4:투자위험예고, 5:투자위험, 6:보통주, 7:우선주
                "fid_aply_rang_prc_1":"", 	#가격 ~
                "fid_aply_rang_prc_2":"",	#~가격 
                "fid_aply_rang_vol":"0" #0: 전체, 100: 100주 이상
          
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01870000", #거래ID FHPST01870000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text          

    
    ######################################################################################################################################
    #11 국내주식 대량체결건수 상위[국내주식-107] ===========================================
    #######################################################################################################################################
    def rank_bluk_trans(tokenP,trade):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/bulk-trans-num'
        body = {
                "fid_aply_rang_prc_2" :"",
                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_COND_SCR_DIV_CODE":"11909", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_input_iscd": trade, #0:매수상위, 1:매도상위
                "fid_div_cls_code":"0", #0:전체 1:보통주 2:우선주
                "fid_input_price_1": "", #	건별금액 ~
                "fid_aply_rang_prc_1":"", 	#가격 ~
                "fid_input_iscd_2" :"", #공백:전체종목, 개별종목 조회시 종목코드 (000660)
                "fid_trgt_cls_code":"0", #	0: 전체
                "fid_trgt_exls_cls_code":"0", #	0:전체, 1:관리종목, 2:투자주의, 3:투자경고, 4:투자위험예고, 5:투자위험, 6:보통주, 7:우선주              
                "fid_vol_cnt":"",	# 거래량~ 

          
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHKST190900C0", #거래ID FHKST190900C0
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text         

 
    ######################################################################################################################################
       #14 국내주식 배당률 상위[국내주식-106] =================================================
    #######################################################################################################################################
    def rank_vividend_rate(tokenP,dend_type): #	1:주식배당, 2: 현금배당
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/dividend-rate'
        body = {
                "CTS_AREA":"",
                "GB1":"0", #:전체, 1:코스피, 2: 코스피200, 3: 코스닥,
                "UPJONG":"0001", #'코스피(0001:종합, 0002:대형주.…0027:제조업 ),코스닥(1001:종합, …. 1041:IT부품 코스피200 (2001:KOSPI200, 2007:KOSPI100, 2008:KOSPI50)'
                "GB2":"0", # 	0:전체, 6:보통주, 7:우선주
                "GB3":dend_type, #	1:주식배당, 2: 현금배당
                "F_DT":"20200101", #기준일From
                "T_DT":"20240403", # 기준일To
                "GB4":"0" #	0:전체, 1:결산배당, 2:중간배당
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB13470100", #거래ID HHKDB13470100
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text         

    
    ######################################################################################################################################
    #15 국내주식 시간외등락율순위 [국내주식-138] ===========================================
    #######################################################################################################################################
    def rank_overtime_fluctuation(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/overtime-fluctuation'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "fid_mrkt_cls_code":"",
                "FID_COND_SCR_DIV_CODE":"20234", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_div_cls_code":"2", #	1(상한가), 2(상승률), 3(보합),4(하한가),5(하락률)
                "fid_trgt_cls_code":"", # 대상 구분 코드 공백
                "fid_trgt_exls_cls_code":"", #대상 제외 구분 코드 공백

                "fid_input_price_1":"", # 입력 가격1 입력값 없을때 전체 (가격 ~)
                "fid_input_price_2":"", # 입력 가격2 입력값 없을때 전체 (~ 가격)
                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST02340000", #거래ID FHPST02340000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text        
                
    
 
    ######################################################################################################################################
    #16 국내주식 시간외거래량순위 [국내주식-139]  =========================================
    #######################################################################################################################################
    def rank_overtime_volume(tokenP):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ranking/overtime-volume'
        body = {

                "FID_COND_MRKT_DIV_CODE":"J",  #조건 시장 분류 코드	
                "FID_RANK_SORT_CLS_CODE":"2", #0(매수잔량), 1(매도잔량), 2(거래량)
                "FID_COND_SCR_DIV_CODE":"20235", #조건 화면 분류 코드
                "FID_INPUT_ISCD":"0000", #입력 종목코드 	0000(전체) 코스피(0001), 코스닥(1001), 코스피200(2001)
                "fid_div_cls_code":"2", #	1(상한가), 2(상승률), 3(보합),4(하한가),5(하락률)
                "fid_trgt_cls_code":"", # 대상 구분 코드 공백
                "fid_trgt_exls_cls_code":"", #대상 제외 구분 코드 공백

                "fid_input_price_1":"", # 입력 가격1 입력값 없을때 전체 (가격 ~)
                "fid_input_price_2":"", # 입력 가격2 입력값 없을때 전체 (~ 가격)
                "fid_vol_cnt":"",       # 거래량 수 입력값 없을때 전체 (거래량 ~)
                              
             
                # "fid_rsfl_rate1":"", #등락 비율1 입력값 없을때 전체 (비율 ~)
                # "fid_rsfl_rate2":"" #등락 비율2 입력값 없을때 전체 (~ 비율)
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST02350000", #거래ID FHPST02350000
            "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
            "custtype": "P", #법인(B), 개인(P)
            "seq_no": "",  #법인(01), 개인( )
            "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
            "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
            "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
            "hashkey": "", #※ 입력 불필요
            "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
        }

        res = requests.post(url, data=json.dumps(body), headers=headers)
        rescode = res.status_code
        if rescode == 200:
            print(res.headers)
            print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text        


        
        
        

        
        

