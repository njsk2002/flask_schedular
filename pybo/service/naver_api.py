import os, sys, datetime, json
import urllib.request

from .authorization_key import Authorization
from ..repository.repositoty_youtube import RepositoryYoutube




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
    def getPostData(post, jsonResult, cnt):    
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
                NaverAPI.getPostData(post, jsonResult, cnt)    
            
            start = jsonResponse['start'] + jsonResponse['display']
            jsonResponse = NaverAPI.getNaverSearch(type, key_word, start, 100)  #[CODE 2]

        
        print('전체 검색 : %d 건' %total)
        output_file = f"image_imhero_{key_word}_{type}.json"
        with open(output_file, 'w', encoding='utf8') as outfile:
            json_data = json.dumps(jsonResult,  indent=4, sort_keys=True,  ensure_ascii=False)
                            
            outfile.write(json_data)
            
        print("가져온 데이터 : %d 건" %(cnt))
        print ('%s_naver_%s.json SAVED' % (key_word, type))
               
        # db에 정보 저장
        RepositoryYoutube.insert_utube_url(key_word, type, output_file, json_data)
            
        print(f"Summary saved to {output_file}")
      
        #정보 호출
        result = RepositoryYoutube.read_utube_url(star_name, type_video)
