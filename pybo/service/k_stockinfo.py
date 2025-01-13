# requests 모듈 설치 필요 (pip install requests)
import requests
import json

# ===========================================================================
#    모의 투자 미지원          모의 투자 미지원
# ===========================================================================

class KStockInfo:

    ####################################################################################################
    #1 예탁원정보(주식매수청구일정)[국내주식-146]
    ####################################################################################################
    def purchase_request(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/purreq'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"" #공백
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669103C0",
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

    ####################################################################################################
    #2 예탁원정보(합병/분할일정)[국내주식-147]
    ####################################################################################################
    def merge_split(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/merger-split'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"" #공백
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669104C0",
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

    ####################################################################################################
    #3 예탁원정보(액면교체일정)[국내주식-148]
    ####################################################################################################
    def merge_split(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/rev-split'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"", #공백
            "MARKET_GB" :"0" #	0:전체, 1:코스피, 2:코스닥
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669105C0",
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
        
    ####################################################################################################
    #4 예탁원정보(자본감소일정)[국내주식-149]
    ####################################################################################################
    def capital_decrease(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/cap-dcrs'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"", #공백
            #"MARKET_GB" :"0" #	0:전체, 1:코스피, 2:코스닥
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669106C0",
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

    ####################################################################################################
    #5 예탁원정보(상장정보일정)[국내주식-150]
    ####################################################################################################
    def list_info(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/list-info'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"", #공백
            #"MARKET_GB" :"0" #	0:전체, 1:코스피, 2:코스닥
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669107C0",
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
        
    ####################################################################################################
    #5 예탁원정보(공모주청약일정)[국내주식-151]
    ####################################################################################################
    def pub_offer(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/pub-offer'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"", #공백
            #"MARKET_GB" :"0" #	0:전체, 1:코스피, 2:코스닥
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669108C0",
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

    ####################################################################################################
    #6 예탁원정보(실권주일정)[국내주식-152]
    ####################################################################################################
    def forfeit(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/forfeit'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"", #공백
            #"MARKET_GB" :"0" #	0:전체, 1:코스피, 2:코스닥
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669109C0",
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

    ####################################################################################################
    #7 예탁원정보(유상증자일정) [국내주식-143]
    ####################################################################################################
    def paidin_capin(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/paidin-capin'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            "GB1":"2", #1(청약일별), 2(기준일별)
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"", #공백(전체), 특정종목 조회시(종목코드)
            #"MARKET_GB" :"0" #	0:전체, 1:코스피, 2:코스닥
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669100C0",
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

    ####################################################################################################
    #8 예탁원정보(무상증자일정) [국내주식-144]
    ####################################################################################################
    def bonus_issue(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/bonus-issue'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            #"GB1":"2", #1(청약일별), 2(기준일별)
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"", #공백(전체), 특정종목 조회시(종목코드)
            #"MARKET_GB" :"0" #	0:전체, 1:코스피, 2:코스닥
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669101C0",
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

    ####################################################################################################
    #9 예탁원정보(주주총회일정) [국내주식-154]
    ####################################################################################################
    def shareholder_meet(tokenP,fromdate,todate):
        url = 'https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/ksdinfo/sharehld-meet'
        body = {

            "cts":"",  #	공백: 전체, 특정종목 조회시 : 종목코드
            #"GB1":"2", #1(청약일별), 2(기준일별)
            "f_dt": fromdate, #조회일자From
            "t_dt": todate, #조회일자To
            "sht_cd":"", #공백(전체), 특정종목 조회시(종목코드)
            #"MARKET_GB" :"0" #	0:전체, 1:코스피, 2:코스닥
        }

        # 주문/매도, 정정/취소 공통
        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + tokenP,
            "appkey": "PSOyty5clFFuUgZ1mU5wOXCPuzYQW740XjYR",
            "appsecret": "OYAJrDYS3/ZV7xqsSER89AckaGUKYrlzI2TUrrfPqK/rBXpTeF149r5KsC7ufKdCbR6hS3wFMIpqvVSjTxQfYiOuXVx/uX2dKrm14pmi2+n8CBQvTQpAihlYVzFldRCSG3C22GaSmCMlwQOe/jMsF643T1eapoKlGyVnkXwHSucrJ3wothY=",
            "personalSeckey": "", # 법인에 한함
            "tr_id": "HHKDB669111C0",
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