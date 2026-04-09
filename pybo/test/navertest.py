import os
import sys
import urllib.request
import urllib.parse
import datetime
import json

client_id = '22p1d5alb4vUR2vvcMg4'
client_secret = 'YDFnT8VOQz'


# --------------------------------------------------
# [1] URL 요청
# --------------------------------------------------
def getRequestUrl(url, body=None, is_json=False):
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", client_id)
    req.add_header("X-Naver-Client-Secret", client_secret)

    if is_json:
        req.add_header("Content-Type", "application/json")

    try:
        if body:
            response = urllib.request.urlopen(req, data=body)
        else:
            response = urllib.request.urlopen(req)

        if response.getcode() == 200:
            print(f"[{datetime.datetime.now()}] URL Request Success")
            return response.read().decode("utf-8")
    except Exception as e:
        print(e)
        print(f"[{datetime.datetime.now()}] Error for URL : {url}")
        return None


# --------------------------------------------------
# [2] 네이버 검색 API (news / blog / book / image)
# --------------------------------------------------
def getNaverSearch(node, query, start=1, display=50):
    base = "https://openapi.naver.com/v1/search"
    url = (
        f"{base}/{node}.json"
        f"?query={urllib.parse.quote(query)}"
        f"&start={start}&display={display}"
    )

    res = getRequestUrl(url)
    return json.loads(res) if res else None


# --------------------------------------------------
# [3] 네이버 쇼핑 API (베스트셀러)
# --------------------------------------------------
def getNaverShopping(query, start=1, display=50):
    url = (
        "https://openapi.naver.com/v1/search/shop.json"
        f"?query={urllib.parse.quote(query)}"
        f"&start={start}&display={display}"
        f"&category=50000000"
        f"&sort=sim"
    )

    res = getRequestUrl(url)
    return json.loads(res) if res else None


# --------------------------------------------------
# [4] 네이버 DataLab 검색 트렌드 API
# --------------------------------------------------
def getNaverDatalabSearch():
    url = "https://openapi.naver.com/v1/datalab/search"

    body = {
        "startDate": "2025-01-01",
        "endDate": "2026-01-01",
        "timeUnit": "month",
        "keywordGroups": [
            {
                "groupName": "검색어",
                "keywords": ["베스트셀러", "경제 뉴스", "책 추천"]
            }
        ],
        "device": "pc",
        "ages": ["2", "3", "4"]
    }

    body_bytes = json.dumps(body).encode("utf-8")
    res = getRequestUrl(url, body=body_bytes, is_json=True)
    return json.loads(res) if res else None


# --------------------------------------------------
# [5] 공통 스키마 정규화
# --------------------------------------------------
def normalize_post(post, cnt, node):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    base = {
        "id": cnt,
        "source": "naver",
        "type": node,
        "title": None,
        "description": None,
        "link": None,
        "origin_link": None,
        "image": None,
        "author": None,
        "publisher": None,
        "isbn": None,
        "price": None,
        "pub_date": None,
        "created_at": now
    }

    if node == "book":
        base.update({
            "title": post.get("title"),
            "description": post.get("description"),
            "link": post.get("link"),
            "image": post.get("image"),
            "author": post.get("author"),
            "publisher": post.get("publisher"),
            "isbn": post.get("isbn"),
            "price": post.get("discount"),
        })
        if post.get("pubdate"):
            base["pub_date"] = datetime.datetime.strptime(
                post["pubdate"], "%Y%m%d"
            ).strftime("%Y-%m-%d")

    elif node in ("news", "blog"):
        base.update({
            "title": post.get("title"),
            "description": post.get("description"),
            "link": post.get("link"),
            "origin_link": post.get("originallink"),
        })
        if post.get("pubDate"):
            base["pub_date"] = datetime.datetime.strptime(
                post["pubDate"], "%a, %d %b %Y %H:%M:%S +0900"
            ).strftime("%Y-%m-%d %H:%M:%S")

    elif node == "image":
        base.update({
            "title": post.get("title"),
            "description": post.get("description"),
            "link": post.get("link"),
            "image": post.get("thumbnail"),
        })

    elif node == "bestseller":
        base.update({
            "title": post.get("title"),
            "description": post.get("category2"),
            "link": post.get("link"),
            "image": post.get("image"),
            "price": int(post.get("lprice")) if post.get("lprice") else None,
            "publisher": post.get("maker"),
        })

    return base


# --------------------------------------------------
# [0] MAIN
# --------------------------------------------------
def main():
    query = input("검색어 입력: ")

    print("""
선택하세요:
1. news
2. blog
3. book
4. image
5. shopping (bestseller)
6. all
7. datalab (검색 트렌드)
""")

    choice = input("번호 입력: ").strip()

    results = []
    cnt = 0

    if choice == "7":
        data = getNaverDatalabSearch()
        filename = f"{query}_naver_datalab.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ DataLab 저장 완료: {filename}")
        return

    choice_map = {
        "1": ["news"],
        "2": ["blog"],
        "3": ["book"],
        "4": ["image"],
        "5": ["bestseller"],
        "6": ["news", "blog", "book", "image", "bestseller"]
    }

    targets = choice_map.get(choice)
    if not targets:
        print("잘못된 선택")
        return

    for node in targets:
        data = getNaverShopping(query) if node == "bestseller" else getNaverSearch(node, query)
        if not data:
            continue
        for post in data.get("items", []):
            cnt += 1
            results.append(normalize_post(post, cnt, node))

    filename = f"{query}_naver_{'_'.join(targets)}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"✅ 저장 완료: {filename} ({len(results)}건)")


if __name__ == "__main__":
    main()
