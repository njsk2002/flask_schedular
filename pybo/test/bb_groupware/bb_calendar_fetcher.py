# -*- coding: utf-8 -*-
import re
import json
from collections import defaultdict
from typing import Dict, List
from datetime import date, timedelta


class BBCalendarFetcher:
    """
    BB Groupware 일정(f5) 크롤러
    - POST /f5/cal.bb?i=a1
    - HTML + JS 전역변수 yL 파싱
    """

    CAL_URL = "https://bb.bbgw.kr/f5/cal.bb?i=a1"

    def __init__(self, session):
        """
        :param session: login_and_get_session()에서 만든 requests.Session
        """
        self.sess = session
        self.raw_html = None
        self.yL = []
        self.events_by_day = defaultdict(list)

    # ------------------------------------------------------------
    # 1) 월 단위 일정 HTML 요청
    # ------------------------------------------------------------
    def fetch_month(self, year: int, month: int):
        """
        서버에 POST로 월 단위 일정 요청
        """
        r = self.sess.post(
            self.CAL_URL,
            data={
                "y": year,
                "m": month,
                "xTm": ""
            },
            timeout=10
        )
        r.raise_for_status()
        self.raw_html = r.text
        return self.raw_html

    # ------------------------------------------------------------
    # 2) <script> yL=[...] </script> 추출
    # ------------------------------------------------------------
    def parse_yL_from_html(self):
        if not self.raw_html:
            raise RuntimeError("HTML not loaded")

        m = re.search(
            r"yL\s*=\s*(\[[\s\S]*?\]);",
            self.raw_html
        )
        if not m:
            raise RuntimeError("yL not found")

        yL_raw = m.group(1)

        # ❌ eval 제거
        # self.yL = eval(yL_raw)

        # ✅ 전용 파서 사용
        self.yL = self.parse_yL_js_array(yL_raw)
        return self.yL


    # ------------------------------------------------------------
    # 3) yL 구조 해석 → 날짜별 이벤트 dict
    # ------------------------------------------------------------
    def parse_events(self, year: int, month: int):

        
        if not self.yL:
            raise RuntimeError("yL not parsed")

        self.events_by_day.clear()

        xp = 0
        # base_date = f"{year:04d}-{month:02d}-"
        cal_start = self._get_calendar_start_date(year, month)

        TOTAL = len(self.yL)
        print("yL length =", len(self.yL), "mod 10 =", len(self.yL) % 10)


        while xp + 9 < TOTAL:   # ✅ 핵심 방어
            day_offset = self.yL[xp]

            # day_offset 자체가 숫자가 아니면 깨진 블록
            if not isinstance(day_offset, int):
                break

            event_id = self.yL[xp + 1]
            title    = self.yL[xp + 7]

            # day = day_offset + 1

            # # 날짜 범위 보호 (이전달/다음달 셀 제거)
            # if day < 1 or day > 31:
            #     xp += 10
            #     continue

            # date_key = base_date + f"{day:02d}"

            real_date = cal_start + timedelta(days=day_offset)

            # 현재 월에 속한 날짜만
            if real_date.month != month:
                xp += 10
                continue

            date_key = real_date.isoformat()

            self.events_by_day[date_key].append({
                "event_id": event_id,
                "title": title
            })

            xp += 10

        return self.events_by_day



    def parse_yL_js_array(self, js_array: str):
        """
        BB Groupware yL JS 배열 파서
        - JS의 빈 슬롯(,,)을 None으로 치환
        - 문자열/숫자만 파싱
        """

        # 1) 개행 제거
        s = js_array.replace("\n", " ").strip()

        # 2) JS 배열 괄호 제거
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]

        tokens = []
        buf = ""
        in_str = False
        quote = ""

        i = 0
        while i < len(s):
            c = s[i]

            # 문자열 시작/종료
            if c in ("'", '"'):
                if not in_str:
                    in_str = True
                    quote = c
                    buf += c
                elif quote == c:
                    in_str = False
                    buf += c
                else:
                    buf += c

            elif c == "," and not in_str:
                token = buf.strip()
                tokens.append(token if token != "" else None)
                buf = ""
            else:
                buf += c
            i += 1

        # 마지막 토큰
        token = buf.strip()
        tokens.append(token if token != "" else None)

        # 문자열/숫자 변환
        out = []
        for t in tokens:
            if t is None:
                out.append(None)
            elif t.startswith(("'", '"')):
                out.append(t[1:-1])
            else:
                try:
                    out.append(int(t))
                except ValueError:
                    out.append(t)

        return out


    # ------------------------------------------------------------
    # 4) 특정 날짜 일정 조회
    # ------------------------------------------------------------
    def get_day(self, date_str: str) -> List[Dict]:
        """
        :param date_str: 'YYYY-MM-DD'
        """
        events = self.events_by_day.get(date_str, [])

        print(f"\n📅 {date_str} 일정 ({len(events)}건)")
        for i, ev in enumerate(events, 1):
            print(f"  {i}. {ev['title']} (id={ev['event_id']})")

        return events
    
    # 주간 조회 (일요일 기준)
    def get_week(self, any_date_str: str):
        d = date.fromisoformat(any_date_str)
        week_start = d - timedelta(days=(d.weekday()+1)%7)
        week_end = week_start + timedelta(days=6)

        result = {}
        cur = week_start
        while cur <= week_end:
            key = cur.isoformat()
            result[key] = self.events_by_day.get(key, [])
            cur += timedelta(days=1)

        return result
    
    #월간 조회 (달력 기준 전체)
    def get_month(self, year: int, month: int):
        return {
            k: v for k, v in self.events_by_day.items()
            if k.startswith(f"{year:04d}-{month:02d}")
        }



    # ------------------------------------------------------------
    # 내부 유틸: JS 배열 → Python list
    # ------------------------------------------------------------
    def _js_array_to_py(self, js_array: str):
        """
        JS 배열 문자열을 Python list로 변환
        (문자열/숫자만 있는 구조라 안전)
        """
        # 줄바꿈 제거
        js_array = js_array.replace("\n", " ")

        # JS -> Python 치환
        js_array = js_array.replace("null", "None")

        return eval(js_array)


    def _get_calendar_start_date(self, year: int, month: int) -> date:
        """
        해당 월 달력의 '첫 칸(일요일)' 날짜 계산
        """
        first_day = date(year, month, 1)
        weekday = (first_day.weekday() + 1) % 7  # Sun=0
        return first_day - timedelta(days=weekday)
