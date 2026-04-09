# -*- coding: utf-8 -*-
"""
bb.bbgw.kr 문서 목록 + vw.bb 본문(스크립트 aV 배열 내 HTML 문자열) 추출

✅ 기능
1) /f0/ax.bb 로 문서 목록 조회 (커스텀 0x08 구분자)
2) /f4/vw.bb?i=... 로 문서 뷰 HTML 조회
3) vw.bb HTML 안 <script>의 aV=[...] 배열에서 <table>...</table> 본문 HTML 문자열 추출
4) 본문 HTML → 텍스트로 정리 출력

⚠️ 주의
- VIEW_ID(i 값)는 DevTools에서 vw.bb?i=... 로 확인한 값을 넣어야 함
- SSL 인증서 체인 문제 때문에 verify=False 사용
"""

import re
import requests
import urllib3
from dataclasses import dataclass
from typing import List, Optional

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------
# SSL 경고 제거 (verify=False 사용 시)
# ---------------------------------------------------------------------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------
SEP = "\x08"   # 서버가 쓰는 구분자 (0x08)
BASE_URL = "https://bb.bbgw.kr"
AX_URL = f"{BASE_URL}/f0/ax.bb"
VW_URL = f"{BASE_URL}/f4/vw.bb"

# ---------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------
@dataclass
class DocumentItem:
    doc_id: int
    code: str
    title: str

# ---------------------------------------------------------------------
# 목록 파서
# ---------------------------------------------------------------------
def parse_document_list(resp_text: str) -> List[DocumentItem]:
    """
    응답 예:
    f4␈20443␈kcecno␈01-08. 출장품의서 : 기술팀␈20441␈...
    """
    parts = resp_text.split(SEP)

    # 첫 토큰이 board_prefix(f4)면 제거
    if parts and parts[0].startswith("f"):
        parts = parts[1:]

    items: List[DocumentItem] = []
    i = 0
    while i + 2 < len(parts):
        a, b, c = parts[i], parts[i + 1], parts[i + 2]
        if a.isdigit():
            items.append(DocumentItem(doc_id=int(a), code=b, title=c))
            i += 3
        else:
            i += 1
    return items

# ---------------------------------------------------------------------
# 세션 생성
# ---------------------------------------------------------------------
def make_session(xb_cookie: str) -> requests.Session:
    s = requests.Session()
    s.verify = False  # ✅ SSL 인증서 문제 우회
    s.cookies.set("xb", xb_cookie, domain="bb.bbgw.kr", path="/")
    return s

# ---------------------------------------------------------------------
# 목록 조회
# ---------------------------------------------------------------------
def fetch_document_list(session: requests.Session, menu_code: str, board_prefix: str = "f4") -> List[DocumentItem]:
    payload = f"{board_prefix}{SEP}{menu_code}"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/f0/main.bb",
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    }

    resp = session.post(
        AX_URL,
        data=payload.encode("utf-8", errors="ignore"),
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return parse_document_list(resp.text)

# ---------------------------------------------------------------------
# vw.bb HTML 조회
# ---------------------------------------------------------------------
def fetch_document_view_html(session: requests.Session, view_id: str) -> str:
    headers = {
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/p/bb.bb",
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,*/*",
    }
    r = session.get(VW_URL, params={"i": view_id}, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text

# ---------------------------------------------------------------------
# vw.bb HTML 내부 script의 aV 배열에서 본문 HTML(<table>..</table>) 추출
# ---------------------------------------------------------------------
def extract_body_html_from_av(html_text: str) -> Optional[str]:
    """
    로그에서 확인된 형태:
    <script> ... yDl=[];aV=['cmxq',0,'','6. 휴가원',...,'<table ...>...</table>', ...] ... </script>

    1) aV=[ ... ]; 덩어리 추출
    2) 그 안에서 <table ...>...</table> 찾기
    """
    m = re.search(r"aV\s*=\s*\[(.*?)\];", html_text, re.DOTALL)
    if not m:
        return None

    array_body = m.group(1)

    # table 본문 찾기 (대부분 결재 양식이 table로 내려옴)
    m2 = re.search(r"(<table.*?</table>)", array_body, re.DOTALL | re.IGNORECASE)
    if not m2:
        return None

    body_html = m2.group(1)

    # 문자열 안에 \" 같은 이스케이프가 섞였을 수 있어 기본적인 정리
    body_html = body_html.replace(r"\/", "/")
    body_html = body_html.replace(r"\n", "\n").replace(r"\t", "\t")

    return body_html

# ---------------------------------------------------------------------
# HTML → 텍스트
# ---------------------------------------------------------------------
def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style"]):
        tag.decompose()

    for br in soup.find_all("br"):
        br.replace_with("\n")

    # td/tr 기반 문서라 줄바꿈을 넉넉히
    for blk in soup.find_all(["p", "div", "li", "tr", "td"]):
        blk.append("\n")

    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)

# ---------------------------------------------------------------------
# 실행부
# ---------------------------------------------------------------------
if __name__ == "__main__":

    # ✅ 브라우저 DevTools에서 복사한 xb 쿠키
    XB_COOKIE = (
        "01010540a4a102000aolsqhkgpwtlhpwnlhpgkwjptlwqqolkcanpftnpgwqsewfofwpsh"
        "wjoswpriwmrrwtrivjrsttoivfnswsrovhnmsiqeuiqnvlqsvpniucr"
    )

    # ✅ DevTools에서 확인한 메뉴 코드
    MENU_CODE = "clqtvw"

    # ✅ DevTools에서 확인한 vw.bb?i= 값
    VIEW_ID = "azmEdecb"

    session = make_session(XB_COOKIE)

    # 1) 목록 출력
    docs = fetch_document_list(session, MENU_CODE, board_prefix="f4")
    print("\n===== 문서 목록 =====")
    for d in docs:
        print(f"[{d.doc_id}] {d.code} | {d.title}")

    # 2) 본문 추출
    print("\n===== 문서 본문 추출 (vw.bb) =====")
    vw_html = fetch_document_view_html(session, VIEW_ID)

    body_html = extract_body_html_from_av(vw_html)
    if not body_html:
        print("❌ aV 배열에서 <table> 본문을 찾지 못했습니다.")
        print("   힌트: 다른 태그(<div> 등)로 내려올 수 있으니, vw_html에서 키워드(휴가/출장)로 검색해보세요.")
        print("\n--- vw.bb RAW (first 1200) ---")
        print(vw_html[:1200])
    else:
        print("\n--- BODY HTML (first 500) ---")
        print(body_html[:500])

        text = html_to_text(body_html)
        print("\n--- DOCUMENT TEXT (first 2000) ---")
        print(text[:2000])
