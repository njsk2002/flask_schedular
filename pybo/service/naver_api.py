import os, sys, datetime, json, re
import urllib.request

from .authorization_key import Authorization
from ..repository.repositoty_youtube import RepositoryYoutube
from ..repository.repositoty_naverdata import RepositoryNaverData


class NaverAPI:
    @staticmethod
    def getRequestUrl(url): 
        client_id, client_secret = Authorization.naver_client()
        req = urllib.request.Request(url)
        req.add_header("X-Naver-Client-Id", client_id)
        req.add_header("X-Naver-Client-Secret", client_secret)
        print(client_id,client_secret)
        try: 
            response = urllib.request.urlopen(req)
            if response.getcode() == 200:
                print ("[%s] Url Request Success" % datetime.datetime.now())
                return response.read().decode('utf-8')
        except Exception as e:
            print(e)
            print("[%s] Error for URL : %s" % (datetime.datetime.now(), url))
            return None
    
    @staticmethod
    def getNaverSearch(node, srcText, start, display):    
        base = "https://openapi.naver.com/v1/search"
        node = "/%s.json" % node
        # print("타입 및 키워드 : ", node,srcText)
        #urllib.parse.quote(srcText)는 입력된 문자열을 URL 인코딩하여, 안전하게 URL에 포함되도록 변환
        parameters = "?query=%s&start=%s&display=%s" % (urllib.parse.quote(srcText), start, display)
        
        url = base + node + parameters    
        responseDecode = NaverAPI.getRequestUrl(url)   #[CODE 1]
        
        if (responseDecode == None):
            return None
        else:
            return json.loads(responseDecode)
        
    @staticmethod
    def get_json_news(post, jsonResult, cnt):    
        title = post['title']
        description = post['description']
        org_link = post['originallink']
        link = post['link']
        
        pDate = datetime.datetime.strptime(post['pubDate'],  '%a, %d %b %Y %H:%M:%S +0900')
        pDate = pDate.strftime('%Y-%m-%d %H:%M:%S')
        
        jsonResult.append({'cnt':cnt, 'title':title, 'description': description, 
                            'org_link':org_link,   'link': org_link,   'pDate':pDate})
        return jsonResult  

    @staticmethod
    def extract_date_from_link(link):
        # 기본 날짜 값
        default_date = "2000-01-01 00:00:00"

        try:
            # 연속된 17자리 또는 15자리 숫자 추출
            match = re.search(r'(\d{4}\d{2}\d{2}\d{2}\d{2}\d{2}\d{3})|\d{2}\d{2}\d{2}\d{2}\d{2}\d{2}\d{3}', link)
            if match:
                numbers = match.group()

                if len(numbers) == 17:  # year가 4자리인 경우
                    year, month, day, hour, minute, second, millisecond = (
                        numbers[:4], numbers[4:6], numbers[6:8],
                        numbers[8:10], numbers[10:12], numbers[12:14], numbers[14:]
                    )
                elif len(numbers) == 15:  # year가 2자리인 경우
                    year, month, day, hour, minute, second, millisecond = (
                        "20" + numbers[:2], numbers[2:4], numbers[4:6],
                        numbers[6:8], numbers[8:10], numbers[10:12], numbers[12:]
                    )
                else:
                    print(f"[규격 오류] 알 수 없는 숫자 패턴: {numbers}")
                    return default_date

                # 문자열을 datetime 객체로 변환
                pDate = datetime.datetime(
                    int(year), int(month), int(day),
                    int(hour), int(minute), int(second), int(millisecond) * 1000
                )
                # 원하는 포맷으로 변환
                return pDate.strftime('%y-%m-%d %H:%M:%S')

            else:
                print(f"[규격 오류] 날짜 정보를 추출하지 못함: {link}")
                return default_date

        except Exception as e:
            print(f"[오류] 처리 중 예외 발생: {e}, 링크: {link}")
            return default_date

    @staticmethod
    def get_json_image(post, cnt):    
        title = post.get('title', '')
        thumbnail = post.get('thumbnail', '')
        link = post.get('link', '')
        sizeheight = post.get('sizeheight', '')
        sizewidth = post.get('sizewidth', '')

        # 링크에서 날짜 추출
        pDate = NaverAPI.extract_date_from_link(link)

        json_file ={
            'cnt': cnt,
            'title': title,
            'thumbnail': thumbnail,
            'link': link,
            'sizeheight': sizeheight,
            'sizewidth': sizewidth,
            'pDate': pDate
        }
        

        return json_file


    @staticmethod
    def get_json_blog(post, jsonResult, cnt):    
        title = post['title']
        description = post['description']
        org_link = post['originallink']
        link = post['link']
        
        pDate = datetime.datetime.strptime(post['pubDate'],  '%a, %d %b %Y %H:%M:%S +0900')
        pDate = pDate.strftime('%Y-%m-%d %H:%M:%S')
        
        jsonResult.append({'cnt':cnt, 'title':title, 'description': description, 
                            'org_link':org_link,   'link': org_link,   'pDate':pDate})
        return     
   

    @staticmethod
    def requestNaverAPI(type, key_word):
       
        jsonResult = []
        jsonResponse = NaverAPI.getNaverSearch(type, key_word, start = 1, display = 100) 

        total = jsonResponse['total']
        
        cnt = 0
        output_file = f"{type}_{key_word}.json" #json 파일 이름

        while ((jsonResponse != None) and (jsonResponse['display'] != 0)):         
            for post in jsonResponse['items']:
                cnt += 1
                if type == 'news':
                    json_file= NaverAPI.get_json_news(post, cnt)    

                elif type == 'image':
                    #json 파일 생성 후 jsonResult에 append 전에 
                    json_file= NaverAPI.get_json_image(post, cnt)
                    RepositoryNaverData.insert_image_data(key_word, type, output_file, json_file)

                elif type == 'blog':
                    json_file=NaverAPI.get_json_blog(post, jsonResult, cnt)
                

                jsonResult.append(json_file)
            
          
            start = jsonResponse['start'] + jsonResponse['display']
            jsonResponse = NaverAPI.getNaverSearch(type, key_word, start, 100)  #[CODE 2]

        
        print('전체 검색 : %d 건' %total)
       
        with open(output_file, 'w', encoding='utf8') as outfile:
            json_data = json.dumps(jsonResult,  indent=4, sort_keys=True,  ensure_ascii=False)
                            
            outfile.write(json_data)
            
        print("가져온 데이터 : %d 건" %(cnt))
        print ('%s_naver_%s.json SAVED' % (key_word, type))
        
            
        print(f"Summary saved to {output_file}")
      
        #정보 호출
        #result =RepositoryNaverData.read_image_data(key_word, type)
