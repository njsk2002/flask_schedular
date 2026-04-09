# -*- coding: utf-8 -*-
import re
import requests
import json
import urllib3
from datetime import date, timedelta
from bb_calendar_fetcher import BBCalendarFetcher

urllib3.disable_warnings()

BASE = "https://bb.bbgw.kr"
LOGIN_URL = f"{BASE}/a/in.bb"
MAIN_URL  = f"{BASE}/p/bb.bb"


# --------------------------------------------------
# xp0 추출
# --------------------------------------------------
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
    raise RuntimeError("xp0 not found")


# --------------------------------------------------
# LOGIN
# --------------------------------------------------
def login_and_get_session(ci, ui, pw, xcn):
    s = requests.Session()
    s.verify = False

    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Connection": "keep-alive",
    })

    s.cookies.set("gl", "0", domain="bb.bbgw.kr", path="/")

    s.get(LOGIN_URL + "?q=", timeout=10)

    r1 = s.post(
        LOGIN_URL,
        data={"ci": ci, "ui": ui, "pw": pw, "xFn": "", "xCn": xcn},
        headers={"Origin": BASE, "Referer": LOGIN_URL + "?q="},
        allow_redirects=True,
        timeout=10,
    )

    xp0 = extract_hidden_xp0(r1.text)

    s.post(
        LOGIN_URL,
        data={"xp0": xp0},
        headers={"Origin": BASE, "Referer": LOGIN_URL},
        allow_redirects=True,
        timeout=10,
    )

    xb = s.cookies.get("xb")
    if not xb:
        raise RuntimeError("❌ Login failed")

    print("✅ LOGIN SUCCESS, xb =", xb[:30], "...")
    return s


# --------------------------------------------------
# CALENDAR READ (기존 기능 유지)
# --------------------------------------------------
def run_calendar_example(sess):
    cal = BBCalendarFetcher(sess)

    YEAR = 2026
    MONTH = 1
    BASE_DATE = "2026-01-01"

    cal.fetch_month(YEAR, MONTH)
    cal.parse_yL_from_html()
    cal.parse_events(YEAR, MONTH)

    day_events = cal.get_day(BASE_DATE)
    week_events = cal.get_week(BASE_DATE)
    month_events = cal.get_month(YEAR, MONTH)

    d = date.fromisoformat(BASE_DATE)
    week_start = d - timedelta(days=(d.weekday() + 1) % 7)
    week_end = week_start + timedelta(days=6)

    result = {
        "meta": {"year": YEAR, "month": MONTH, "base_date": BASE_DATE},
        "day": {"date": BASE_DATE, "events": day_events},
        "week": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "days": week_events
        },
        "month": month_events
    }

    print("\n===== 📦 CALENDAR JSON RESULT =====")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


# --------------------------------------------------
# CATEGORY SELECT (중요)
# --------------------------------------------------
def select_calendar_category(sess):
    # 1) 카테고리 팝업 진입
    r = sess.get(f"{BASE}/sa/cats.bb?c=s&i=1", timeout=10)

    m = re.search(r"yC\s*=\s*(\[[^\]]+\])", r.text)
    if not m:
        raise RuntimeError("yC not found")

    yC = json.loads(m.group(1).replace("'", '"'))
    ci = yC[0]

    # 2) ⭐ 실제 선택 확정 (이게 핵심)
    sess.post(
        f"{BASE}/xz/cats.bb",
        data={"ci": ci},
        headers={
            "Origin": BASE,
            "Referer": f"{BASE}/sa/cats.bb?c=s&i=1",
        },
        timeout=10
    )

    print("📂 CATEGORY CONFIRMED:", ci)
    return ci


# def extract_user_id(sess):
#     url = f"{BASE}/f5/add.bb?i=a1"
#     r = sess.get(url, timeout=10)

#     # 디버그용 (처음엔 반드시 찍어봐야 함)
#     print("---- add.bb html head ----")
#     print(r.text[:1000])

#     m = re.search(r'yU\s*=\s*"([^"]+)"', r.text)
#     if not m:
#         raise RuntimeError("yU not found in add.bb")

#     return m.group(1)


# --------------------------------------------------
# EVENT WRITE
# --------------------------------------------------
def post_calendar_event(sess):
    url = f"{BASE}/f5/ax.bb"

    ci = select_calendar_category(sess)
    # user_id = extract_user_id(sess)

    payload_obj = {
        "xi": "",
        "nm": "테스트",
        "th": 1,
        "cn": "<p>테스트</p>",
        "ti": 0,
        "ci": 22,          # 🔥 선택된 카테고리
        "dt": 20454,       # 🔥 2026-01-01
        "sh": "-", "sm": "-",
        "sh2": "-", "sm2": "-",
        "lo": "",
        "im": "0",
        "rp": "",
        "doc": "\b",
        "al": "",
        "att": "cgiv,cqtu",
        "bi": ""
    }

    payload = "a" + json.dumps(payload_obj, ensure_ascii=False)

    r = sess.post(
        url,
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": "text/plain; charset=UTF-8",
            "Origin": BASE,
            "Referer": f"{BASE}/f5/add.bb?i=a1",
        },
        timeout=10,
    )

    dump_response_debug(r)
    return r.text


# --------------------------------------------------
# DEBUG
# --------------------------------------------------
def dump_response_debug(r):
    print("\n====== 🔍 SERVER DEBUG ======")
    print("Status Code :", r.status_code)
    for k, v in r.headers.items():
        print(f"{k}: {v}")
    print("Raw Text:", repr(r.text))
    print("Content :", r.content)
    print("============================")


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    sess = login_and_get_session(
        ci="icetech11",
        ui="davidjung",
        pw="promise2015@",
        xcn="(주)아이스기술"
    )

    sess.get(MAIN_URL, timeout=10)

    run_calendar_example(sess)
    # post_calendar_event(sess)


if __name__ == "__main__":
    main()
