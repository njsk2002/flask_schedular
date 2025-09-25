import os, sys, datetime, json, re
import urllib.request

from .authorization_key import Authorization
from ..repository.repositoty_youtube import RepositoryYoutube
from ..repository.repositoty_naverdata import RepositoryNaverData
from ..service.bmp_trans import BMPTrans


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
        # parameters = "?query=카리나&start=1&display=100"
        print("파라메터 : ", parameters)
        url = base + node + parameters    
        print("URL : ", url)
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
    def get_json_image(post, cnt, key_word):    
        title = post.get('title', '')
        thumbnail = post.get('thumbnail', '')
        url = post.get('link', '')
        sizeheight = post.get('sizeheight', '')
        sizewidth = post.get('sizewidth', '')

        # 링크에서 날짜 추출
        pDate = NaverAPI.extract_date_from_link(url)

        # BMP 이미지 생성
        #bmp_file = BMPTrans.genenate_bmp_top(url,sizeheight,sizewidth)
        bmp_42_mono = BMPTrans.genenate_bmp_42_mono(url,key_word)
        bmp_75_mono = BMPTrans.genenate_bmp_75_mono(url,key_word)
        bmp_42_3color = BMPTrans.genenate_bmp_42_3color(url,key_word)
        bmp_37_4color = BMPTrans.genenate_bmp_37_4color(url,key_word)
        bmp_29_4color = BMPTrans.genenate_bmp_29_4color(url,key_word)
        bmp_397_4color = BMPTrans.genenate_bmp_397_4color(url,key_word)


        print(f"BMP 파일명은 {bmp_42_mono}, {bmp_75_mono},{bmp_42_3color}, {bmp_37_4color}, {bmp_29_4color}, {bmp_397_4color} 입니다.")

        if bmp_42_mono is None or bmp_42_3color is None or bmp_42_3color is None or bmp_29_4color is None or bmp_75_mono is None or bmp_397_4color is None:
            return None  # 실패 시 명시적으로 None 반환
        
        else:
            json_file ={
                'cnt': cnt,
                'title': title,
                'thumbnail': thumbnail,
                'link': url,
                'sizeheight': sizeheight,
                'sizewidth': sizewidth,
                'bmp_42_mono' : bmp_42_mono,
                'bmp_75_mono' : bmp_75_mono,
                'bmp_42_3color' : bmp_42_3color,
                'bmp_37_4color' : bmp_37_4color ,
                'bmp_29_4color' : bmp_29_4color ,
                'bmp_397_4color' : bmp_397_4color ,               
                'pDate': pDate
            }
            return json_file

    #출입증용_Image 및 DB DATA 전송
    @staticmethod
    def get_json_permission(post, cnt):    
        title = post.get('title', '')
        thumbnail = post.get('thumbnail', '')
        url = post.get('link', '')
        sizeheight = post.get('sizeheight', '')
        sizewidth = post.get('sizewidth', '')

        # 링크에서 날짜 추출
        pDate = NaverAPI.extract_date_from_link(url)

        # BMP 이미지 생성
        #bmp_file = BMPTrans.genenate_bmp_top(url,sizeheight,sizewidth)
        bmp_file = BMPTrans.genenate_bmp_ai(url)
        print(f"BMP 파일명은 {bmp_file} 입니다.")

        if bmp_file is None:
            return None  # 실패 시 명시적으로 None 반환
        
        else:
            json_file ={
                'cnt': cnt,
                'title': title,
                'thumbnail': thumbnail,
                'link': url,
                'sizeheight': sizeheight,
                'sizewidth': sizewidth,
                'bmp_file' : bmp_file,
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
        output_file = f"{type}_{key_word}.json"  # JSON 파일 이름
        cnt = 0
        
        start_points = [1, 51]  # 2번 요청하여 최대 200개 가져오기
        for start in start_points:
            jsonResponse = NaverAPI.getNaverSearch(type, key_word, start, 50)
            
            if jsonResponse is None or jsonResponse['display'] == 0:
                break  # 더 이상 결과가 없으면 종료
            
            for post in jsonResponse['items']:
                cnt += 1
                json_file = None  # 기본값
                
                if type == 'news':
                    json_file = NaverAPI.get_json_news(post, cnt)    
                elif type == 'image':
                    try:
                        json_file = NaverAPI.get_json_image(post, cnt,key_word)
                        if json_file is not None:
                            RepositoryNaverData.insert_image_data(key_word, type, output_file, json_file)
                        else:
                            print(f"JSON 파일 생성 실패: post={post}, cnt={cnt}")
                    except Exception as e:
                        print(f"오류 발생: {e}")
                elif type == 'blog':
                    json_file = NaverAPI.get_json_blog(post, jsonResult, cnt)
                
                if json_file is not None:
                    jsonResult.append(json_file)
        
        # JSON 파일 저장
        with open(output_file, 'w', encoding='utf8') as outfile:
            json_data = json.dumps(jsonResult, indent=4, sort_keys=True, ensure_ascii=False)
            outfile.write(json_data)

        print(f"전체 검색 결과: {cnt}건 저장 완료")
        print(f"{output_file} 파일이 저장되었습니다.")
        return True


