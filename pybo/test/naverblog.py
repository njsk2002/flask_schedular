from bs4 import BeautifulSoup
import requests
import re
import time
import os
import sys
import urllib.request
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
#from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
import pandas as pd

# 웹드라이버 설정
options = webdriver.ChromeOptions()
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

# 버전에 상관 없이 os에 설치된 크롬 브라우저 사용
#driver = webdriver.Chrome(ChromeDriverManager().install())
driver = webdriver.Chrome()
driver.implicitly_wait(3)
# 버전에 상관 없이 os에 설치된 크롬 브라우저 사용


# Naver API key 입력
client_id = '22p1d5alb4vUR2vvcMg4' 
client_secret = 'YDFnT8VOQz'

# selenium으로 검색 페이지 불러오기 #
naver_urls = []
postdate = []
titles = []

# 검색어 입력
#keword = input("검색할 키워드를 입력해주세요:")
keword = '에이프로젠'
encText = urllib.parse.quote(keword)

# 검색을 끝낼 페이지 입력
# end = input("\n크롤링을 끝낼 위치를 입력해주세요. (기본값:1, 최대값:100):")  
# if end == "":
#     end = 1
# else:
#     end = int(end)
end = 1
print("\n 1 ~ ", end, "페이지 까지 크롤링을 진행 합니다")

# 한번에 가져올 페이지 입력
# display = input("\n한번에 가져올 페이지 개수를 입력해주세요.(기본값:10, 최대값: 100):")
# if display == "":
#     display = 10
# else:
#     display = int(display)
display = 2
print("\n한번에 가져올 페이지 : ", display, "페이지")


for start in range(end):
    url = "https://openapi.naver.com/v1/search/blog?query=" + encText + "&start=" + str(start+1) + "&display=" + str(display+1) # JSON 결과
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id",client_id)
    request.add_header("X-Naver-Client-Secret",client_secret)
    response = urllib.request.urlopen(request)
    rescode = response.getcode()
    if(rescode==200):
        response_body = response.read()
        
        data = json.loads(response_body.decode('utf-8'))['items']
        
        for row in data:
            if('blog.naver' in row['link']):
                naver_urls.append(row['link'])
                postdate.append(row['postdate'])
                title = row['title']
                # html태그제거
                pattern1 = '<[^>]*>'
                title = re.sub(pattern=pattern1, repl='', string=title)
                titles.append(title)
        time.sleep(2)
    else:
        print("Error Code:" + rescode)


###naver 기사 본문 및 제목 가져오기###

# ConnectionError방지
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/98.0.4758.102"}


contents = []
comments_texts = []
try:
    for i in naver_urls:
        print(i)
        driver.get(i)
        time.sleep(5)  # 대기시간 변경 가능

        iframe = driver.find_element(By.ID , "mainFrame") # id가 mainFrame이라는 요소를 찾아내고 -> iframe임
        driver.switch_to.frame(iframe) # 이 iframe이 내가 찾고자하는 html을 포함하고 있는 내용

        source = driver.page_source
        html = BeautifulSoup(source, "html.parser")
        # 검색결과 확인용
        # with open("Output.txt", "w") as text_file:
        #     text_file.write(str(html))
        
        # 기사 텍스트만 가져오기
        content = html.select("div.se-main-container")
        #  list합치기
        content = ''.join(str(content))

        # html태그제거 및 텍스트 다듬기
        content = re.sub(pattern=pattern1, repl='', string=content)
        pattern2 = """[\n\n\n\n\n// flash 오류를 우회하기 위한 함수 추가\nfunction _flash_removeCallback() {}"""
        content = content.replace(pattern2, '')
        content = content.replace('\n', '')
        content = content.replace('\u200b', '')
        contents.append(content)


    news_df = pd.DataFrame({'title': titles, 'content': contents, 'date': postdate})
    news_df.to_csv('blog.csv', index=False, encoding='utf-8-sig')
except:
    contents.append('error')
    news_df = pd.DataFrame({'title': titles, 'content': contents, 'date': postdate})
    news_df.to_csv('blog.csv', index=False, encoding='utf-8-sig')