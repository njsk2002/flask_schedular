from playwright.sync_api import sync_playwright
import time

BASE = "https://bb.bbgw.kr"

CI  = "icetech11"
UI  = "davidjung"
PW  = "promise2015@"
XCN = "(주)아이스기술"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,   # 👈 반드시 False
            slow_mo=50        # 👈 안정성용
        )
        context = browser.new_context()
        page = context.new_page()

        # 1️⃣ 로그인 페이지
        page.goto(f"{BASE}/a/in.bb?q=")
        page.wait_for_load_state("networkidle")

        # 2️⃣ 로그인 입력
        page.fill("input[name=ci]", CI)
        page.fill("input[name=ui]", UI)
        page.fill("input[name=pw]", PW)
        page.fill("input[name=xCn]", XCN)

        # submit
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        # 3️⃣ xp0 자동 submit 페이지 통과
        time.sleep(1)  # JS 자동 submit 대기

        # 4️⃣ 일정 추가 페이지 직접 진입
        page.goto(f"{BASE}/f5/add.bb?i=a1")
        page.wait_for_load_state("networkidle")

        # 🔍 개발자 콘솔과 동일한 JS 컨텍스트
        js_code = """
        (() => {
            if (typeof x$A === 'undefined' || typeof x$A.Ac === 'undefined') {
                return 'x$A not ready';
            }

            x$A.Ac({
                xi: "",
                nm: "테스트",
                th: 1,
                cn: "<p>테스트</p>",
                ti: 0,
                ci: 22,
                dt: 20454,
                sh: "-",
                sm: "-",
                sh2: "-",
                sm2: "-",
                lo: "",
                im: "0",
                rp: "",
                doc: "\\b",
                al: "",
                att: "cqtu",
                bi: ""
            });

            return 'OK';
        })();
        """

        result = page.evaluate(js_code)
        print("JS RESULT:", result)

        # 5️⃣ 서버 처리 대기
        time.sleep(3)

        print("✅ DONE. 일정 생성 여부 확인")

        # 브라우저 유지 (확인용)
        input("엔터 누르면 종료...")
        browser.close()

if __name__ == "__main__":
    main()
