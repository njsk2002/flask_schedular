# -*- coding: utf-8 -*-
import re
import time
import urllib3
import requests
from dataclasses import dataclass
from typing import List, Optional, Dict

# Playwright
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_HTTPS = "https://bb.bbgw.kr"
BASE_HTTP  = "http://bb.bbgw.kr"
SEP = "\x08"

LOGIN_URL  = f"{BASE_HTTPS}/a/in.bb"
LOGIN_PAGE = f"{BASE_HTTPS}/a/in.bb?q="
MAIN_URL   = f"{BASE_HTTP}/p/bb.bb"

AX_F0 = f"{BASE_HTTPS}/f0/ax.bb"
AX_F4 = f"{BASE_HTTPS}/f4/ax.bb"

LIST_F4 = f"{BASE_HTTPS}/f4/list.bb?i=a"  # ✅ 형이 캡처한 리스트 페이지(필요시 변경)

# ----------------------------
# models
# ----------------------------
@dataclass
class DocumentItem:
    doc_id: int
    code: str
    title: str

# ----------------------------
# login (requests)
# ----------------------------
def extract_hidden_xp0(html: str) -> str:
    patterns = [
        r'name\s*=\s*["\']?xp0["\']?\s+value\s*=\s*["\']([^"\']+)["\']',
        r'value\s*=\s*["\']([^"\']+)["\']\s+name\s*=\s*["\']?xp0["\']?',
        r'name\s*=\s*xp0[^>]*value\s*=\s*["\']([^"\']+)["\']',
    ]
    for p in patterns:
        m = re.search(p, html, flags=re.IGNORECASE)
        if m:
            return m.group(1)

    m = re.search(
        r'<form[^>]*>\s*<input[^>]*value\s*=\s*["\']([^"\']+)["\']',
        html, flags=re.IGNORECASE
    )
    if m:
        return m.group(1)

    raise RuntimeError("xp0 not found (regex failed)")

def login_and_get_session(ci: str, ui: str, pw: str, xcn: str) -> requests.Session:
    s = requests.Session()
    s.verify = False

    # browser-like
    s.cookies.set("gl", "0", domain="bb.bbgw.kr", path="/")

    # login page
    s.get(LOGIN_PAGE, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)

    # step1: credentials
    data1 = {"ci": ci, "ui": ui, "pw": pw, "xFn": "", "xCn": xcn}
    r1 = s.post(
        LOGIN_URL,
        data=data1,
        headers={
            "Origin": BASE_HTTPS,
            "Referer": LOGIN_PAGE,
            "User-Agent": "Mozilla/5.0",
        },
        timeout=15,
        allow_redirects=True,
    )

    xp0 = extract_hidden_xp0(r1.text)

    # step2: xp0 (auto-submit token)
    s.post(
        LOGIN_URL,
        data={"xp0": xp0},
        headers={
            "Origin": BASE_HTTPS,
            "Referer": LOGIN_URL,
            "User-Agent": "Mozilla/5.0",
        },
        timeout=15,
        allow_redirects=True,
    )

    xb = s.cookies.get("xb")
    if not xb:
        raise RuntimeError("Login failed: xb not issued")
    return s

# ----------------------------
# protocol helpers
# ----------------------------
def split_0x08(text: str) -> List[str]:
    return text.split(SEP)

def post_ax(session: requests.Session, url: str, payload: str, referer: str) -> str:
    r = session.post(
        url,
        data=payload.encode("utf-8", errors="ignore"),
        headers={
            "Origin": BASE_HTTPS,
            "Referer": referer,
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Accept": "*/*",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.text

# ----------------------------
# menu code finder (optional)
# ----------------------------
def extract_menu_codes_from_main(html_text: str) -> List[str]:
    codes = set()
    for m in re.finditer(r'/f4/menu\.bb\?i=([a-zA-Z0-9]+)', html_text):
        codes.add(m.group(1))
    for m in re.finditer(r'menu\.bb\?i=([a-zA-Z0-9]+)', html_text):
        codes.add(m.group(1))
    return sorted(codes)

def get_main_html(session: requests.Session) -> str:
    r = session.get(MAIN_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    return r.text

# ----------------------------
# document list
# ----------------------------
def parse_document_list(resp_text: str) -> List[DocumentItem]:
    parts = split_0x08(resp_text)
    if parts and parts[0].startswith("f"):
        parts = parts[1:]

    items: List[DocumentItem] = []
    i = 0
    while i + 2 < len(parts):
        a, b, c = parts[i], parts[i+1], parts[i+2]
        if a.isdigit():
            items.append(DocumentItem(doc_id=int(a), code=b, title=c))
            i += 3
        else:
            i += 1
    return items

def fetch_document_list(session: requests.Session, menu_code: str, board_prefix: str="f4") -> List[DocumentItem]:
    payload = f"{board_prefix}{SEP}{menu_code}"
    txt = post_ax(session, AX_F0, payload, referer=f"{BASE_HTTPS}/f0/main.bb")
    return parse_document_list(txt)

# ----------------------------
# (optional) view_id discovery from ax (keep, but not required with Playwright)
# ----------------------------
def try_discover_view_id_from_ax(session: requests.Session, doc_code: str) -> Optional[str]:
    candidates = [
        f"v{SEP}{doc_code}",
        f"i{SEP}{doc_code}",
        f"n{SEP}{doc_code}",
    ]
    for p in candidates:
        try:
            txt = post_ax(session, AX_F4, p, referer=f"{BASE_HTTPS}/f4/menu.bb")
            m = re.search(r'\bi=([A-Za-z0-9]{6,40})\b', txt)
            if m:
                return m.group(1)
        except Exception:
            pass
    return None

# ----------------------------
# Playwright: rendered DOM fetch (Option B)
# ----------------------------
from playwright.sync_api import sync_playwright

def _pw_new_context_with_xb(xb: str):
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    context.add_cookies([{
        "name": "xb",
        "value": xb,
        "domain": "bb.bbgw.kr",
        "path": "/",
    }])
    return p, browser, context


def fetch_rendered_doc_by_click(
    xb_cookie: str,
    list_url: str,
    doc: DocumentItem,
    wait_ms: int = 1500,
) -> str:
    """
    list_url을 열고, 프레임 포함 전체에서 문서 텍스트를 찾아 클릭한 뒤
    렌더링된 HTML(가장 큰 프레임 content)을 반환한다.
    """

    p, browser, context = _pw_new_context_with_xb(xb_cookie)
    page = context.new_page()

    def _dump_debug(tag: str):
        try:
            html = page.content()
            with open(f"debug_{tag}.html", "w", encoding="utf-8", errors="ignore") as f:
                f.write(html)
        except Exception:
            pass
        try:
            page.screenshot(path=f"debug_{tag}.png", full_page=True)
        except Exception:
            pass
        try:
            print("=== FRAME URLS ===")
            for i, fr in enumerate(page.frames):
                print(f"[{i}] {fr.url}")
            print("==================")
        except Exception:
            pass

    try:
        print("▶ goto list:", list_url)
        page.goto(list_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(wait_ms)

        # (중요) 네트워크가 idle이 안 되는 사이트가 많아서 domcontentloaded + 짧은 sleep 조합
        page.wait_for_timeout(800)

        # 프레임 전체에서 "클릭 대상" 탐색
        queries = [
            doc.title.strip(),
            str(doc.doc_id),
            doc.code,
        ]

        clicked = False
        clicked_where = None

        # 1) 먼저 메인 페이지에서 시도
        for q in queries:
            if not q:
                continue
            try:
                page.get_by_text(q, exact=False).first.click(timeout=2000)
                clicked = True
                clicked_where = f"main:{q}"
                break
            except Exception:
                pass

        # 2) 실패하면 모든 iframe(frame)에서 시도
        if not clicked:
            for fr in page.frames:
                for q in queries:
                    if not q:
                        continue
                    try:
                        fr.get_by_text(q, exact=False).first.click(timeout=2500)
                        clicked = True
                        clicked_where = f"frame:{fr.url}::{q}"
                        break
                    except Exception:
                        pass
                if clicked:
                    break

        if not clicked:
            _dump_debug("list_click_fail")
            raise RuntimeError(
                f"Cannot click document row. doc_id={doc.doc_id}, code={doc.code}, title={doc.title}"
            )

        print("✅ clicked:", clicked_where)

        # 클릭 후 렌더링 대기
        page.wait_for_timeout(1200)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(wait_ms)

        # 결과 페이지/프레임들 중 "가장 큰 HTML"을 반환
        biggest = ""
        for fr in page.frames:
            try:
                c = fr.content()
                if len(c) > len(biggest):
                    biggest = c
            except Exception:
                pass

        if not biggest:
            biggest = page.content()

        # 디버그로 저장(성공해도 1개는 남기는 게 좋음)
        with open(f"rendered_{doc.doc_id}_{doc.code}.html", "w", encoding="utf-8", errors="ignore") as f:
            f.write(biggest)

        return biggest

    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass


# ----------------------------
# Save helpers
# ----------------------------
def safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)
    s = re.sub(r'\s+', " ", s).strip()
    return s[:120] if len(s) > 120 else s

# ----------------------------
# main
# ----------------------------
def main():
    CI  = "icetech11"
    UI  = "davidjung"
    PW  = "promise2015@"         # ※ 실제 입력은 promise2015@ (requests가 urlencode 처리)
    XCN = "(주)아이스기술"

    # 1) login (requests)
    sess = login_and_get_session(CI, UI, PW, XCN)
    xb = sess.cookies.get("xb", "")
    print("✅ login ok. xb =", xb[:35], "...")

    # 2) (optional) main에서 menu codes 후보
    main_html = get_main_html(sess)
    menu_candidates = extract_menu_codes_from_main(main_html)
    print("menu candidates:", menu_candidates[:10], "..." if len(menu_candidates) > 10 else "")

    # 3) 문서 목록
    MENU_CODE = "clqtvw"
    docs = fetch_document_list(sess, MENU_CODE, board_prefix="f4")

    print("\n===== 문서 목록 =====")
    for d in docs[:20]:
        print(f"[{d.doc_id}] {d.code} | {d.title}")

    if not docs:
        print("❗ 문서가 없음")
        return

    # 4) 본문 추출: Playwright (Option B)
    #    - 우선 앞에서 N개만 테스트
    N = 3
    targets = docs[:N]

    print(f"\n===== Playwright로 본문 수집 시작 (N={N}) =====")
    for idx, doc in enumerate(targets, 1):
        print(f"\n[{idx}/{N}] click & render: doc_id={doc.doc_id}, code={doc.code}, title={doc.title}")

        # (선택) view_id 자동탐색은 남겨두되, 성공해도 굳이 vw를 파싱할 필요가 없음.
        # view_id = try_discover_view_id_from_ax(sess, doc.code)

        rendered_html = fetch_rendered_doc_by_click(
            xb_cookie=xb,
            list_url=LIST_F4,
            doc=doc,
            wait_ms=1500,
        )

        fname = safe_filename(f"{doc.doc_id}_{doc.code}_{doc.title}") + ".html"
        with open(fname, "w", encoding="utf-8", errors="ignore") as f:
            f.write(rendered_html)

        print("✅ saved:", fname, "len=", len(rendered_html))

        # 간단 확인: 휴가/출장 키워드가 들어왔는지
        hit = ("휴가" in rendered_html) or ("출장" in rendered_html) or ("<table" in rendered_html.lower())
        print("   keyword/table hit:", hit)

    print("\nDONE.")


if __name__ == "__main__":
    main()
