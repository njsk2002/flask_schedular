import os
from flask import Flask
from PIL import Image, ImageDraw

# ✅ 실제 프로젝트 경로에 맞게 import 경로만 수정해줘
from pybo.service.file_management import apply_layers_to_image


def _make_signature_png_no_ext(save_dir: str, token: str = "png_e7152adf") -> str:
    """
    _safe_photo_abs()가 token 그대로 파일을 찾는 구조라서
    확장자 없이 'png_e7152adf' 파일로 저장한다.
    """
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, token)  # 확장자 없음

    img = Image.new("RGBA", (200, 120), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    # 간단한 "서명" 느낌의 선
    d.line((10, 80, 60, 20, 110, 90, 160, 30, 190, 70), fill=(0, 0, 0, 255), width=6)
    img.save(path, format="PNG")  # 확장자 없어도 format 지정으로 저장 가능
    return path

def _make_layers_case(status_map: dict[int, str], stamp_text_map: dict[int, str] | None = None):
    """
    apply_layers_to_image()에 바로 넣을 'internal layers' 구조(signbox)를 만든다.
    status_map 예: {2:"done", 4:"rejected"} 처럼 col_index -> status
    """
    stamp_text_map = stamp_text_map or {}

    slots = []
    for col_index, (group, role, user_id, user_name, x_rel) in {
        1: ("draft", "작성", 4, "이한길", 0.0),
        2: ("draft", "검토", "njsk2005", "이한길", 0.2),
        3: ("draft", "승인", "njsk2002", "정현수", 0.4),
        4: ("check", "검토", "njsk2007", "유원조", 0.6),
        5: ("check", "승인", "njsk2006", "이종우", 0.8),
    }.items():
        slots.append({
            "status": status_map.get(col_index, ""),              # ✅ 여기로 상태 주입
            "stamp_text": stamp_text_map.get(col_index, None),    # ✅ 텍스트 강제 주입(선택)
            "id": f"TEST-{col_index}",
            "col_index": col_index,
            "group": group,
            "dept": "기술영업팀" if group == "draft" else "부설연구소",
            "role": role,
            "user_id": user_id,
            "user_name": user_name,
            # 작성자는 서명 토큰(확장자 없이) / 나머지는 빈 값
            "user_photo_1": "png_e7152adf" if col_index == 1 else "",
            "x_rel": x_rel,
            "y_rel": 0.0,
            "w_rel": 0.2,
            "h_rel": 1.0,
            "label": "기술영업팀" if group == "draft" else "부설연구소",
        })

    signbox = {
        "type": "signbox",
        "id": "APP-TEST",
        "parent": {"x": 200, "y": 180, "w": 800, "h": 180},
        # tpl은 apply_layers_to_image에서 참조하는 값들만 최소로 넣어도 됨
        "tpl": {
            "row_ratio": [1, 3, 1],
            "font_color": "#14312d",
            "line_color": "#198754",
            "stamp_scale": 0.8,
            "border_color": "#198754",
            "font_size_px": 28,
            "dept_col_ratio": 0.18,
            "line_pos_ratio": 0.72,
            "line_hpad_ratio": 0.08,
            "line_thickness_px": 2,
        },
        "slots": slots,
    }

    # 필요하면 회사직인(stamp)도 같이 테스트 가능 (지금은 signbox만으로 충분)
    return [signbox]

def _run_case(app: Flask, name: str, status_map: dict[int, str], stamp_text_map=None):
    w, h = 1200, 1600
    base = Image.new("RGB", (w, h), (245, 245, 245))  # 밝은 배경(변화 확인 쉬움)

    layers = _make_layers_case(status_map=status_map, stamp_text_map=stamp_text_map)
    out = apply_layers_to_image(base, w, h, layers)

    out_path = os.path.abspath(f"./_out_{name}.png")
    out.save(out_path)
    app.logger.debug("[TEST] saved=%s", out_path)
    print(f"[OK] {name} -> {out_path}")

def main():
    app = Flask(__name__)

    # ✅ SIGN_BASE_DIR 설정(여기에 서명 토큰 파일을 만들어줌)
    sign_dir = os.path.abspath("./_test_sign_dir")
    app.config["SIGN_BASE_DIR"] = sign_dir

    # 작성자 서명 파일(확장자 없이) 생성
    sig_path = _make_signature_png_no_ext(sign_dir, token="png_e7152adf")
    print("[OK] signature file:", sig_path)

    with app.app_context():
        # CASE 1) 기존 동작 확인: status 비어있음 → col_index=1(작성)만 찍히는지
        _run_case(app, "case1_only_writer", status_map={})

        # CASE 2) “작성 이후 첫 결재(=col_index=2)”가 done일 때 → 2번 칸에 '완료' (또는 서명) 찍히는지
        _run_case(app, "case2_first_approval_done", status_map={2: "done"}, stamp_text_map={2: "완료"})

        # CASE 3) 반려 테스트(예: col_index=2 rejected) → 2번 칸에 '반려' 찍히는지
        _run_case(app, "case3_first_approval_reject", status_map={2: "rejected"}, stamp_text_map={2: "반려"})

if __name__ == "__main__":
    main()
