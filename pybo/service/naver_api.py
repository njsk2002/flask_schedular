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
    def get_json_image(post, jsonResult, cnt):    
        title = post['title']
        thumbnail = post['thumbnail']
        link = post['link']
        sizeheight = post['sizeheight']
        sizeweight = post['sizeweight']


        # 링크에서 숫자 추출
        match = re.search(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{3})', post['link'])

        if match:
            year, month, day, hour, minute, second, millisecond = match.groups()
            # 문자열을 datetime 객체로 변환
            pDate = datetime.datetime(
                int(year), int(month), int(day),
                int(hour), int(minute), int(second), int(millisecond) * 1000
            )
            # 원하는 포맷으로 변환
            pDate = pDate.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            pDate = pDate.strftime('%Y-%m-%d %H:%M:%S')
            print(pDate )  # 결과: 2024-12-09 17:41:19.545
        else:
            print("날짜 정보를 링크에서 추출하지 못했습니다.")
        
        jsonResult.append({'cnt':cnt, 'title':title, 'thumbnail': thumbnail,  'link': link,
                            'sizeheight':sizeheight,   'sizeweight': sizeweight,   'pDate':pDate})
        return jsonResult  

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
        while ((jsonResponse != None) and (jsonResponse['display'] != 0)):         
            for post in jsonResponse['items']:
                cnt += 1
                if type == 'news':
                    NaverAPI.get_json_news(post, jsonResult, cnt)    
                elif type == 'image':
                    NaverAPI.get_json_image(post,jsonResult,cnt)
                elif type == 'blog':
                    NaverAPI.get_json_blog(post, jsonResult, cnt)
            
            start = jsonResponse['start'] + jsonResponse['display']
            jsonResponse = NaverAPI.getNaverSearch(type, key_word, start, 100)  #[CODE 2]

        
        print('전체 검색 : %d 건' %total)
        output_file = f"{type}_{key_word}.json"
        with open(output_file, 'w', encoding='utf8') as outfile:
            json_data = json.dumps(jsonResult,  indent=4, sort_keys=True,  ensure_ascii=False)
                            
            outfile.write(json_data)
            
        print("가져온 데이터 : %d 건" %(cnt))
        print ('%s_naver_%s.json SAVED' % (key_word, type))
               
        # db에 정보 저장
        if type == 'news':
            RepositoryNaverData.insert_data(key_word, type, output_file, json_data)
        elif type == 'image':
            RepositoryNaverData.insert_data(key_word, type, output_file, json_data)
        elif type == 'blog':
            RepositoryNaverData.insert_data(key_word, type, output_file, json_data)
        
            
        print(f"Summary saved to {output_file}")
      
        #정보 호출
        result =RepositoryNaverData.read_image_data(key_word, type)
