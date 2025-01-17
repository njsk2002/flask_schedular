import pandas as pd
import openpyxl   
from datetime import datetime, timedelta 


# data=  "000100^103413^73000^2^1100^1.53^73165.54^72800^73800^72700^73000^72900^454^126363^9245403600^1372^1824^452^131.50^52790^69419^1^0.55^83.31^090019^2^200^090153^5^-800^090019^2^300^20240507^20^N^454^965^26428^15189^0.16^58478^216.09^0^^72800^000100^103413^73000^2^1100^1.53^73165.48^72800^73800^72700^73000^72900^46^126409^9248761600^1373^1824^451^131.39^52836^69419^5^0.55^83.34^090019^2^200^090153^5^-800^090019^2^300^20240507^20^N^454^965^26428^15189^0.16^58478^216.17^0^^72800^000100^103413^72900^2^1000^1.39^73165.46^72800^73800^72700^73000^72900^10^126419^9249490600^1374^1824^450^131.36^52846^69419^5^0.55^83.35^090019^2^100^090153^5^-900^090019^2^200^20240507^20^N^454^965^26428^15189^0.16^58478^216.18^0^^72800^000100^103413^72900^2^1000^1.39^73165.44^72800^73800^72700^73000^72900^10^126429^9250219600^1375^1824^449^131.34^52856^69419^5^0.55^83.35^090019^2^100^090153^5^-900^090019^2^200^20240507^20^N^454^965^26428^15189^0.16^58478^216.20^0^^72800"

# pValue = data.split('^')
# # pValue를 48개씩 나누어서 4개의 리스트로 담기
# rdata = [pValue[i:i+46] for i in range(0, len(pValue), 46)]
# #print('RDATA = ',rdata)

# file_path = "C:/projects/download/"
# file_name = "Stock_Find Max(rev5.18)_20240507.xlsm"

# df = pd.read_excel(file_path + file_name, sheet_name=['Sheet3'])

# e_data = []
# for column_name, column_data in df.items():
#     column_values = list(column_data.iloc[6:])  # 각 열의 7번째 행부터를 리스트로 변환
#     #print(column_data)
#     e_data.append(column_values)

# del e_data[0]  # 첫 번째 열의 데이터 삭제 (열의 이름)
  
#print(e_data[1])  # 첫 번째 열의 데이터 출력


# wb = openpyxl.load_workbook(file_path + file_name)  # 엑셀 파일을 엽니다.
# ws = wb["Sheet3"]  # "Sheet3" 시트를 선택합니다.

# excel_to_list_all = []  # 엑셀 전체 데이터를 담을 리스트를 초기화합니다.

# seen = set()  # 중복 데이터를 확인하기 위한 집합을 초기화합니다.

# for index, row in enumerate(ws.rows):  # 모든 행을 반복합니다.
#     if index >= 6:  # 7번째 행부터 데이터를 저장합니다.
#         excel_to_list1 = []  # 한 행의 데이터를 담을 리스트를 초기화합니다.
#         duplicate_check = (row[0].value, row[2].value)  # 중복 데이터를 확인하기 위한 튜플을 생성합니다.

#         if duplicate_check not in seen:  # 중복이 아닌 경우에만 추가합니다.
#             for cell in row:  # 행의 각 셀을 반복합니다.
#                 excel_to_list1.append(cell.value)  # 셀의 값을 리스트에 추가합니다.

#             excel_to_list_all.append(excel_to_list1)  # 행의 데이터 리스트를 전체 데이터 리스트에 추가합니다.
#             seen.add(duplicate_check)  # 중복 데이터 집합에 추가합니다.

# print(excel_to_list_all[0][1])  # 전체 데이터 리스트를 출력합니다.


rdata=  [['000660', '134620', '177800', '5', '-1800', '-1.00', '177482.35', '177600', '179400', '176000', '177900', '177800', '1', '1661938', '294965262300', '20116', '16825', '-3291', '72.69', '915417', '665435', '5', '0.41', '38.21', '090015', '2', '200', '091343', 
'5', '-1600', '113513', '2', '1800', '20240508', '20', 'N', '3421', '3088', '41510', '27747', '0.23', '3395724', '48.94', '0', '', '177600'], ['000660', '134620', '177800', '5', '-1800', '-1.00', '177482.35', '177600', '179400', '176000', '177900', '177800', '23', '1661961',
 '294969351700', '20117', '16825', '-3292', '72.69', '915440', '665435', '5', '0.41', '38.21', '090015', '2', '200', '091343', '5', '-1600', '113513', '2', '1800', '20240508', '20', 'N', '3421', '3088', '41510', '27747', '0.23', '3395724', '48.94', '0', '', '177600']] 

for row in rdata:
    print(row[0])

import json

json_str = '{"rt_cd":"0","msg_cd":"40600000","msg1":"모의투자 매수주문이 완료 되었습니다.","output":{"KRX_FWDG_ORD_ORGNO":"00950","ODNO":"11774","ORD_TMD":"145152"}}'
data_dict = json.loads(json_str)

rt_cd_value = data_dict["rt_cd"]
odno_value = data_dict["output"]["ODNO"]

# print("rt_cd 값:", rt_cd_value)
# print("ODNO 값:", odno_value)



file_path = "C:/projects/download/"
file_name = "Stock_Find Max(rev5.18)_20240516.xlsm"
     

# Read the Excel file starting from the 7th row and read data from the third sheet
df = pd.read_excel(file_path + file_name, header=None, skiprows=6, names=['Column1', 'Column2', 'Column3'], sheet_name=2)
print(df)
# 중복된 항목은 20240516 기준으로 하나만 남김
#filtered_df = df[(df['Column3'] == 20240516) & (df['Column1'].duplicated() == False)]



# Find the maximum date value in Column3
max_date = df['Column3'].max()

# Filter the DataFrame to include only values with the maximum date value
filtered_df = df[~df['Column1'].isin(df[df['Column3'] < max_date]['Column1'])]

# Further exclude duplicates based on the values in Column1
filtered_df = filtered_df.drop_duplicates(subset='Column1')


# Save the filtered DataFrame to a CSV file with UTF-8 encoding and BOM signature to support Korean characters
filtered_df.to_csv(file_path + 'filtered_data.csv', index=False, encoding='utf-8-sig')

# 현재 날짜와 시간을 datetime 객체로 얻어옵니다.
today_date = datetime.now()

# datetime 객체를 원하는 형식의 문자열로 변환합니다.
today_date_str = today_date.strftime("%Y%m%d")

# 문자열을 datetime 객체로 다시 변환합니다. 필요한 경우에만 사용합니다.
today_date_dt = datetime.strptime(today_date_str, "%Y%m%d")

# 현재 날짜에서 하루를 빼어 어제의 날짜를 구합니다.
yesterday_date = today_date_dt - timedelta(days=0)

# 어제의 날짜를 원하는 형식의 문자열로 변환합니다.
ydate = yesterday_date.strftime("%Y%m%d")
print(ydate)
