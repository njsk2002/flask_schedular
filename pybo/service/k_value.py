# requests 모듈 설치 필요 (pip install requests)
import requests
import json
import time


class KValue:
    #1 주식현재가 시세[v1_국내주식-008]======================================================
    def current_value(stockcode,static_token):

        while True:
            url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-price'
            params = {
                    "fid_cond_mrkt_div_code": "J",    #	FID 조건 시장 분류 코드 	J : 주식, ETF, ETNW: ELW
                    "fid_input_iscd": stockcode     #FID 입력 종목코드 	종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)
            }
            #print(stockcode,static_token)
            # 현재가 시세 공통
            headers = {
                "Content-Type": "application/json",
                "authorization": "Bearer " + static_token,
                "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
                "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
                "personalSeckey": "", # 법인에 한함
                "tr_id": "FHKST01010100",

                "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
                "custtype": "P", #법인(B), 개인(P)
                "seq_no": "",  #법인(01), 개인( )
                "mac_address": "F4-A4-75-4D-38-75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
                "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
                "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
                "hashkey": "", #※ 입력 불필요
                "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
            }
            #print(headers)
            time.sleep(0.5)
            res = requests.get(url, params=params, headers=headers)
            rescode = res.status_code
            #json to dic to list
            res_list = []
            res_dic = json.loads(res.text)
    
            #res_list.append(res_dic_output)

            if "output" in res_dic:
                res_dic_output = res_dic.get('output')
                
            else:
                print("output 키가 존재하지 않습니다.")
                res_dic_output = None
        
            if rescode == 200:
            # print(res.headers)
            # print(str(rescode) + " | " + res.text)
                return res_dic_output
            else:
                print("Error Code : " + str(rescode) + " | " + res.text)
                #return res_dic_output

    #2 주식현재가 체결[v1_국내주식-009]============================================================
    def changeorder(stockcode,static_token):
        url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-ccnl'
        params = {
                "fid_cond_mrkt_div_code": "J",    #	FID 조건 시장 분류 코드 	J : 주식, ETF, ETNW: ELW
                "fid_input_iscd": stockcode     #FID 입력 종목코드 	종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)
        }

        # 현재가 시세 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + static_token,
            "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
            "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHKST01010300",	#[실전투자/모의투자] FHKST01010300 : 주식현재가 체결
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
        res = requests.get(url, params=params, headers=headers)
        rescode = res.status_code
        res_dic = json.loads(res.text)
        res_dic_output = res_dic.get('output')
        if rescode == 200:
            #print(res.headers)
            #print(str(rescode) + " | " + res.text)
            return res_dic_output
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text
        

    #3 주식현재가 일자별[v1_국내주식-010]===========================================================
    def daily_current_value(stockcode,tokenP, selectorder):
        url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-daily-price'
        params = {
                "fid_cond_mrkt_div_code": "J",    #	FID 조건 시장 분류 코드 	J : 주식, ETF, ETNW: ELW
                "fid_input_iscd": stockcode ,    #FID 입력 종목코드 	종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)
                "fid_org_adj_prc": "0000000001", #		0 : 수정주가반영   1 : 수정주가미반영
                    # * 수정주가는 액면분할/액면병합 등 권리 발생 시 과거 시세를 현재 주가에 맞게 보정한 가격
                "fid_period_div_code": "D"   #	FID 기간 분류 코드
                # D : (일)최근 30거래일
                # W : (주)최근 30주
                # M : (월)최근 30개월
        }

        # 현재가 시세 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
            "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHKST01010200",	# 거래id [실전투자/모의투자] FHKST01010200 : 주식현재가 호가 예상체결
            "tr_cont": " ", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
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
        


    #4 주식현재가 호가/예상체결[v1_국내주식-011]===========================================================
    def cell_predict_price(stockcode,tokenP):

        while True:
            url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn'
            params = {
                    "fid_cond_mrkt_div_code": "J",    #	FID 조건 시장 분류 코드 	J : 주식, ETF, ETNW: ELW
                    "fid_input_iscd": stockcode     #FID 입력 종목코드 	종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)

            }

            # 현재가 시세 공통
            headers = {
                "Content-Type": "application/json",
                "authorization": "Bearer " + tokenP,
                "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
                "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
                "personalSeckey": "", # 법인에 한함
                "tr_id": "FHKST01010200",	# 거래id [실전투자/모의투자] FHKST01010200 : 주식현재가 일자별
                "tr_cont": "", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
                "custtype": "P", #법인(B), 개인(P)
                "seq_no": "",  #법인(01), 개인( )
                "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
                "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
                "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
                "hashkey": "", #※ 입력 불필요
                "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
            }

            #print(headers)
            time.sleep(0.5)
            res = requests.get(url, params=params, headers=headers)
            rescode = res.status_code
            #json to dic to list
            res_list = []
            res_dic = json.loads(res.text)
    
            #res_list.append(res_dic_output)

            if "output2" in res_dic:
                res_dic_output = res_dic.get('output2')
                
            else:
                print("output2 키가 존재하지 않습니다.")
                res_dic_output = None
        
            if rescode == 200:
            # print(res.headers)
            # print(str(rescode) + " | " + res.text)
                return res_dic_output
            else:
                print("Error Code : " + str(rescode) + " | " + res.text)
                #return res_dic_output
        

    #5 주식현재가 투자자[v1_국내주식-012]===========================================================
    def current_investor(stockcode,tokenP, selectorder):
        url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-investor'
        params = {
                "fid_cond_mrkt_div_code": "J",    #	FID 조건 시장 분류 코드 	J : 주식, ETF, ETNW: ELW
                "fid_input_iscd": stockcode     #FID 입력 종목코드 	종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)

        }

        # 현재가 시세 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
            "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHKST01010900",	# 거래id 	[실전투자/모의투자] FHKST01010900 : 주식현재가 투자자
            "tr_cont": " ", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
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

    #6 주식현재가 회원사[v1_국내주식-013]===========================================================
    def current_trader(stockcode,tokenP, selectorder):
        url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-member'
        params = {
                "fid_cond_mrkt_div_code": "J",    #	FID 조건 시장 분류 코드 	J : 주식, ETF, ETNW: ELW
                "fid_input_iscd": stockcode     #FID 입력 종목코드 	종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)

        }

        # 현재가 시세 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
            "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHKST01010600",	# 거래id 	[실전투자/모의투자] FHKST01010600 : 주식현재가 회원사
            "tr_cont": " ", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
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


    #7 국내주식기간별시세(일/주/월/년)[v1_국내주식-016]===========================================================
    def period_price(self,stockcode,static_token,date_from,date_to):
        # res_dic_output1 =[]
        # res_dic_output2 =[]

        while True:
            url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice'
            params = {
                    "fid_cond_mrkt_div_code": "J",    #	FID 조건 시장 분류 코드 	J : 주식, ETF, ETNW: ELW         
                    "fid_input_date_1": date_from, 	#조회 시작일자 (ex. 20220501)
                    "fid_input_date_2": date_to,    #조회 종료일자 (ex. 20220530)
                    "fid_input_iscd": stockcode,     #FID 입력 종목코드 	종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)
                    "fid_org_adj_prc": "0",    #0:수정주가 1:원주가
                    "fid_period_div_code": "D"  #D:일봉, W:주봉, M:월봉, Y:년봉

            }

            # 현재가 시세 공통
            headers = {
                "Content-Type": "application/json",
                "authorization": "Bearer " + static_token,
                "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
                "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
                "tr_id": "FHKST03010100",	# 거래id [실전투자/모의투자] FHKST03010100
                "custtype": "P" #법인(B), 개인(P)
        
            }

            time.sleep(0.5)
            res = requests.get(url, params=params, headers=headers)
            rescode = res.status_code
            #json to dic to list
            res_list = []
            res_dic = json.loads(res.text)

            #res_list.append(res_dic_output)

            # if "output2" in res_dic:
            #     res_dic_output = res_dic.get('output2')
            #     #print("분봉데이터", res_dic_output)
                
            # else:
            #     print("output2 키가 존재하지 않습니다.")
            #     res_dic_output = None
            print("헤더파일:", res.headers)

            # 헤더 검사 및 처리
            if "output2" in res_dic:
                # res_dic_output1.append(res_dic["output1"])
                # res_dic_output2.append(res_dic["output2"])
                res_dic_output1 = res_dic["output1"]
                res_dic_output2 = res_dic["output2"]
                # merged_data = [item for sublist in res_dic_output for item in sublist] #간단버전 
                # merged_data = []
                # for sublist in res_dic_output:
                #     for item in sublist:
                #         merged_data.append(item)
            
            else:
                print("output2 키가 존재하지 않습니다.")
                res_dic_output = None

            
            if rescode == 200:
                print(res.headers)
                print(str(rescode) + " | " + res.text)
                return res_dic_output1,res_dic_output2
            else:
                print("Error Code : " + str(rescode) + " | " + res.text)
                # return merged_data
                
            print(res.headers)
            print(str(rescode) + " | " + res.text)


    #8 주식현재가 당일시간대별체결[v1_국내주식-023]===========================================================
    def price_fromcurrent(stockcode,tokenP,askhour, selectorder):
        url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion'
        params = {
                "fid_cond_mrkt_div_code": "J",    #	FID 조건 시장 분류 코드 	J : 주식, ETF, ETNW: ELW         
                "fid_input_iscd": stockcode,     #FID 입력 종목코드 	종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)
                "fid_input_hour_1": askhour  #조회 시작시간 	기준시간 (6자리; HH:MM:SS) ex) 155000 입력시 15시 50분 00초 기준 이전 체결 내역이 조회됨
        }

        # 현재가 시세 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
            "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01060000",	# 거래id 		[실전투자/모의투자] FHPST01060000
            "tr_cont": " ", #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
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
           # print(res.headers)
           # print(str(rescode) + " | " + res.text)
            return res.text
        else:
            print("Error Code : " + str(rescode) + " | " + res.text)
            return res.text


    #9 주식당일분봉조회[v1_국내주식-022]===========================================================
    def mindata(stockcode,tokenP,askhour):
        trcont = ""
        res_dic_output= []
        while True:
            url = 'https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice'

            params = {
                    "fid_cond_mrkt_div_code": "J",    #	FID 조건 시장 분류 코드 	J : 주식, ETF, ETNW: ELW         
                    "fid_input_iscd": stockcode,     #FID 입력 종목코드 	종목번호 (6자리) ETN의 경우, Q로 시작 (EX. Q500001)
                    "fid_input_hour_1": askhour, #조회 시작시간 	기준시간 (6자리; (HHMMSS)) ex) 155000 입력시 15시 50분 00초 기준 이전 체결 내역이 조회됨  
                    
                    # 조회대상(FID_COND_MRKT_DIV_CODE)에 따라 입력하는 값 상이
                    # 종목(J)일 경우, 조회 시작일자(HHMMSS)
                    # ex) "123000" 입력 시 12시 30분 이전부터 1분 간격으로 조회
                    # 업종(U)일 경우, 조회간격(초) (60 or 120 만 입력 가능)
                    # ex) "60" 입력 시 현재시간부터 1분간격으로 조회
                    # "120" 입력 시 현재시간부터 2분간격으로 조회
                    # ※ FID_INPUT_HOUR_1 에 미래일시 입력 시에 현재가로 조회됩니다.
                    # ex) 오전 10시에 113000 입력 시에 오전 10시~11시30분 사이의 데이터가 오전 10시 값으로 조회됨    
            
                    "fid_etc_cls_code": "",   # FID 기타 구분 코드 기타 구분 코드("")
                    "fid_pw_data_incu_yn": "" # FID 과거 데이터 포함 여부
                        # 과거 데이터 포함 여부(Y/N)
                        # * 업종(U) 조회시에만 동작하는 구분값
                        # N : 당일데이터만 조회
                        # Y : 이후데이터도 조회
                        # (조회시점이 083000(오전8:30)일 경우 전일자 업종 시세 데이터도 같이 조회됨)
            
            
            }

            # 현재가 시세 공통
            headers = {
                "Content-Type": "application/json",
                "authorization": "Bearer " + tokenP,
                "appkey": "PSol2l0pt8wdI6ZJR9mQTpyHtyHFTKKPxqeC",
                "appsecret": "waUHuVTB44bbG+5c1X1noqv9QH5dbRIrVhEo+peVqfDWabwQtPcg7ckSpEMWN5/TKJOJuY4SwSCuRbrI5GK6RPJPzU2lpHZbURhLQmo399PsjHbbkOrIkqmJXLjwa1rS6piFoZIJ8o78bJnR9ZBiKaP4s5Jy7+OvNlVJ/50HPd/gdlncFvo=",
                "personalSeckey": "", # 법인에 한함
                "tr_id": "FHKST03010200",	# 거래id 		[실전투자/모의투자] 	FHKST03010200 FHKST03010200
                "tr_cont": trcont, #공백 : 초기 조회 N : 다음 데이터 조회 (output header의 tr_cont가 M일 경우)
                "custtype": "P", #법인(B), 개인(P)
                "seq_no": "",  #법인(01), 개인( )
                "mac_address": "f4:a4:75:4d:38:75", # 일단 wifi (lan,wifi,vmware별도 mac이 달라서, 고려해야 할 사항임)
                "phone_num": "", #	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호 ex) 01011112222 (하이픈 등 구분값 제거)
                "ip_addr": "", #[법인 필수] 사용자(회원)의 IP Address
                "hashkey": "", #※ 입력 불필요
                "gt_uid": "" #	[법인 필수] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
            }


            time.sleep(0.5)
            res = requests.get(url, params=params, headers=headers)
            rescode = res.status_code
            #json to dic to list
            res_list = []
            res_dic = json.loads(res.text)

            #res_list.append(res_dic_output)

            # if "output2" in res_dic:
            #     res_dic_output = res_dic.get('output2')
            #     #print("분봉데이터", res_dic_output)
                
            # else:
            #     print("output2 키가 존재하지 않습니다.")
            #     res_dic_output = None
            print("헤더파일:", res.headers)

            # 헤더 검사 및 처리
            if res.headers.get('tr_cont') in ['M']:
                trcont = 'N'
                if "output2" in res_dic:
                    res_dic_output.append(res_dic["output2"])
                    
                else:
                    print("output2 키가 존재하지 않습니다.")
                    res_dic_output = None
            else:
                if "output2" in res_dic:
                    res_dic_output.append(res_dic["output2"])
                    # merged_data = [item for sublist in res_dic_output for item in sublist] #간단버전 
                    merged_data = []
                    for sublist in res_dic_output:
                        for item in sublist:
                            merged_data.append(item)
                
                else:
                    print("output2 키가 존재하지 않습니다.")
                    res_dic_output = None

                
                if rescode == 200:
                    print(res.headers)
                    print(str(rescode) + " | " + res.text)
                    return merged_data
                else:
                    print("Error Code : " + str(rescode) + " | " + res.text)
                   # return merged_data
                
            print(res.headers)
            print(str(rescode) + " | " + res.text)


          
        
        

##############################################################################################
        ################  모의 투자 미 지원 ##################################
#10 변동성완화장치(VI) 현황 [v1_국내주식-055] ===========================================================
##############################################################################################
    def vidata(tokenP,currentdate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-vi-status'
        params = {
                "fid_cond_scr_div_code":"20139",#분류코드 20139
                "fid_mrkt_cls_code":"0", #0:전체 K:거래소 Q:코스닥
                "fid_input_iscd":"", #종목코드
                "fid_rank_sort_cls_code":"0", #0:전체1:정적2:동적3:정적&동적
                "fid_input_date_1": currentdate, #영업일
                "fid_trgt_cls_code":"",
                "fid_trgt_exls_cls_code":"",
                "fid_div_cls_code":"0" #	0:전체 1:상승 2:하락
        
        }

        # 현재가 시세 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPST01390000",	# 거래id [실전투자] 	FHPST01390000
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


##############################################################################################
        ################  모의 투자 미 지원 ##################################
#11 국내업종 현재지수[v1_국내주식-063] ===========================================================
##############################################################################################
    def industry_current(tokenP,stock_industry):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-index-price'
        params = {
                    "fid_cond_mrkt_div_code":"U", #업종(U)
                    "fid_input_iscd":stock_industry #코스피(0001), 코스닥(1001), 코스피200(2001) 포탈 (FAQ : 종목정보 다운로드(국내) - 업종코드 참조)
                }

        # 현재가 시세 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPUP02100000",	# 거래id [실전투자] FHPUP02100000
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


##############################################################################################
        ################  모의 투자 미 지원 ##################################
#12 국내업종 일자별지수[v1_국내주식-065] ===========================================================
##############################################################################################
    def industry_daily(tokenP,stock_industry,askdate,category):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-index-daily-price'
        params = {
                   "fid_cond_mrkt_div_code":"U", #	시장구분코드 (업종 U)
                    "fid_input_iscd": stock_industry, #	코스피(0001), 코스닥(1001), 코스피200(2001) 포탈 (FAQ : 종목정보 다운로드(국내) - 업종코드 참조)
                    "fid_input_date_1":askdate, #입력 날짜(ex. 20240223)
                    "fid_period_div_code":category #일/주/월 구분코드 ( D:일별 , W:주별, M:월별 )
                }

        # 현재가 시세 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "FHPUP02120000",	# 거래id [실전투자] FHPUP02120000
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