# -*- coding: utf-8 -*-
"""
IR(JSON) -> Render(PIL) -> BIN encode (BW 1bpp / 4bpp 6-color index)
pip install pillow
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

# =========================================================
# 1) 샘플 IR(JSON)
# =========================================================
SAMPLE_IR_JSON = r"""
{
  "meta": {
    "doc_id": "notice_20260123_001",
    "version": 1
  },
  "canvas": {
    "width": 400,
    "height": 300,
    "bpp": 1,
    "rotation": 0,
    "background": "#FFFFFF"
  },
  "data": {
    "title": "보일러 공지",
    "items": [
      {"name": "점검", "value": "14:00 ~ 16:00"},
      {"name": "구역", "value": "Furnace/SH/RH"},
      {"name": "담당", "value": "운전팀"}
    ]
  },
  "style": {
    "font_path": "",
    "font_size": 18,
    "title_size": 26,
    "line_height": 26,
    "padding": 16
  },
  "constraints": {
    "truncate_ellipsis": true,
    "max_lines_default": 1
  },
  "blocks": [
    {
      "type": "rect",
      "x": 10, "y": 10, "w": 380, "h": 60,
      "fill": "#FFFFFF",
      "outline": "#000000",
      "stroke": 2
    },
    {
      "type": "text",
      "x": 20, "y": 20,
      "text": "{{title}}",
      "font_size": 26,
      "color": "#000000",
      "max_lines": 1
    },

    {
      "type": "rect",
      "x": 10, "y": 80, "w": 380, "h": 200,
      "fill": "#FFFFFF",
      "outline": "#000000",
      "stroke": 2
    },

    {
      "type": "text",
      "x": 20, "y": 95,
      "text": "1) {{items[0].name}} : {{items[0].value}}",
      "font_size": 18,
      "color": "#000000",
      "max_lines": 1
    },
    {
      "type": "text",
      "x": 20, "y": 125,
      "text": "2) {{items[1].name}} : {{items[1].value}}",
      "font_size": 18,
      "color": "#000000",
      "max_lines": 1
    },
    {
      "type": "text",
      "x": 20, "y": 155,
      "text": "3) {{items[2].name}} : {{items[2].value}}",
      "font_size": 18,
      "color": "#000000",
      "max_lines": 1
    },

    {
      "type": "text",
      "x": 20, "y": 230,
      "text": "※ 문의: {{items[2].value}}",
      "font_size": 18,
      "color": "#000000",
      "max_lines": 1
    }
  ]
}
"""


# =========================================================
# 2) 간단한 바인딩( {{a.b}}, {{items[0].name}} )
# =========================================================
def _get_by_path(data: Dict[str, Any], path: str) -> Any:
    # path: "title" or "items[0].name"
    cur: Any = data
    parts: List[str] = []
    buf = ""
    i = 0
    while i < len(path):
        ch = path[i]
        if ch == ".":
            if buf:
                parts.append(buf)
                buf = ""
            i += 1
            continue
        if ch == "[":
            if buf:
                parts.append(buf)
                buf = ""
            j = path.find("]", i)
            idx_str = path[i + 1 : j]
            parts.append(f"[{idx_str}]")
            i = j + 1
            continue
        buf += ch
        i += 1
    if buf:
        parts.append(buf)

    for p in parts:
        if p.startswith("[") and p.endswith("]"):
            idx = int(p[1:-1])
            cur = cur[idx]
        else:
            cur = cur[p]
    return cur


def apply_binding(template: str, binding_root: Dict[str, Any]) -> str:
    # replace {{...}} tokens
    out = ""
    i = 0
    while i < len(template):
        start = template.find("{{", i)
        if start < 0:
            out += template[i:]
            break
        out += template[i:start]
        end = template.find("}}", start)
        if end < 0:
            out += template[start:]
            break
        expr = template[start + 2 : end].strip()
        val = _get_by_path(binding_root, expr)
        out += str(val)
        i = end + 2
    return out


# =========================================================
# 3) 텍스트 오버플로우 처리 (폭 기준 축약, 간단 버전)
# =========================================================
def truncate_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int, ellipsis: bool) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    if not ellipsis:
        # 그냥 잘라내기
        while text and draw.textlength(text, font=font) > max_w:
            text = text[:-1]
        return text
    # ... 붙이기
    suffix = "…"
    t = text
    while t and draw.textlength(t + suffix, font=font) > max_w:
        t = t[:-1]
    return (t + suffix) if t else suffix


# =========================================================
# 4) Renderer (IR -> PIL Image)
# =========================================================
# def load_font(font_path: str, size: int) -> ImageFont.ImageFont:
#     # font_path가 비어있으면 PIL 기본 폰트
#     if font_path:
#         return ImageFont.truetype(font_path, size=size)
#     return ImageFont.load_default()

import os
from PIL import ImageFont

def load_font(font_path: str, size: int) -> ImageFont.ImageFont:
    """
    - font_path가 있으면 우선 사용
    - 없으면 OS 기본 한글 폰트 후보를 순서대로 시도
    """
    candidates = []
    if font_path:
        candidates.append(font_path)

    # Windows Korean fonts
    candidates += [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\malgunsl.ttf",
        r"C:\Windows\Fonts\NanumGothic.ttf",
        r"C:\Windows\Fonts\NanumBarunGothic.ttf",
    ]

    # Linux common paths (서버가 리눅스면)
    candidates += [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]

    for p in candidates:
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size=size)

    # 최후 fallback (한글 안 나올 수 있음)
    return ImageFont.load_default()


def render_ir_to_image(ir: Dict[str, Any]) -> Image.Image:
    canvas = ir["canvas"]
    style = ir.get("style", {})
    constraints = ir.get("constraints", {})
    binding_root = {**ir.get("data", {}), "items": ir.get("data", {}).get("items", [])}

    W, H = int(canvas["width"]), int(canvas["height"])
    bg = canvas.get("background", "#FFFFFF")
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    default_font_path = style.get("font_path", "")
    default_font_size = int(style.get("font_size", 18))
    ellipsis = bool(constraints.get("truncate_ellipsis", True))
    max_lines_default = int(constraints.get("max_lines_default", 1))

    for b in ir.get("blocks", []):
        t = b.get("type", "").lower()

        if t == "rect":
            x, y = int(b["x"]), int(b["y"])
            w, h = int(b["w"]), int(b["h"])
            fill = b.get("fill", None)
            outline = b.get("outline", None)
            stroke = int(b.get("stroke", 1))
            # fill이 없으면 투명 개념이 없으니 생략
            if fill:
                draw.rectangle([x, y, x + w, y + h], fill=fill)
            if outline:
                # stroke 흉내: 여러 번 그리기
                for s in range(stroke):
                    draw.rectangle([x + s, y + s, x + w - s, y + h - s], outline=outline)
            continue

        if t == "text":
            x, y = int(b["x"]), int(b["y"])
            raw_text = str(b.get("text", ""))
            text = apply_binding(raw_text, binding_root)
            color = b.get("color", "#000000")

            font_size = int(b.get("font_size", default_font_size))
            font = load_font(default_font_path, font_size)

            max_lines = int(b.get("max_lines", max_lines_default))
            box_w = int(b.get("max_width", ir["canvas"]["width"] - x - 5))

            # 여기서는 단순히 1줄 축약만 지원(형 시스템은 줄바꿈 규칙을 더 넣으면 됨)
            if max_lines <= 1:
                text = truncate_to_width(draw, text, font, box_w, ellipsis)
                draw.text((x, y), text, fill=color, font=font)
            else:
                # 매우 단순한 multi-line: 공백 기준으로 줄 나누기
                words = text.split(" ")
                lines: List[str] = []
                cur = ""
                for w in words:
                    cand = (cur + " " + w).strip()
                    if draw.textlength(cand, font=font) <= box_w or not cur:
                        cur = cand
                    else:
                        lines.append(cur)
                        cur = w
                        if len(lines) >= max_lines:
                            break
                if len(lines) < max_lines and cur:
                    lines.append(cur)

                # 마지막 줄 오버면 ellipsis
                if lines:
                    last = lines[-1]
                    if draw.textlength(last, font=font) > box_w:
                        lines[-1] = truncate_to_width(draw, last, font, box_w, ellipsis)

                line_h = int(ir.get("style", {}).get("line_height", font_size + 6))
                for i, line in enumerate(lines[:max_lines]):
                    draw.text((x, y + i * line_h), line, fill=color, font=font)
            continue

        # QR/바코드/이미지 등은 여기서 확장
        # if t == "qr": ...
        # if t == "barcode": ...
        # if t == "image": ...
        # 지금은 샘플이라 pass
    rot = int(canvas.get("rotation", 0))
    if rot in (90, 180, 270):
        img = img.rotate(rot, expand=True)
    return img


# =========================================================
# 5) BIN Encoder
#    - BW 1bpp: white=1 black=0 (MSB-first)
#    - 4bpp 6-color: pixel index (0..15), 2px per byte
# =========================================================
def rgb_to_bw_bit(rgb: Tuple[int, int, int], threshold: int = 200) -> int:
    r, g, b = rgb
    # luminance approx
    y = int(0.299 * r + 0.587 * g + 0.114 * b)
    # 흰=1, 검=0
    return 1 if y >= threshold else 0


def encode_bw_1bpp(img_rgb: Image.Image) -> bytes:
    img = img_rgb.convert("RGB")
    W, H = img.size
    px = img.load()

    row_bytes = (W + 7) // 8
    out = bytearray(row_bytes * H)

    k = 0
    for y in range(H):
        byte = 0
        bitpos = 7
        for x in range(W):
            bit = rgb_to_bw_bit(px[x, y])
            byte |= (bit & 1) << bitpos
            bitpos -= 1
            if bitpos < 0:
                out[k] = byte
                k += 1
                byte = 0
                bitpos = 7
        # 남은 비트는 흰(1)로 패딩
        if bitpos != 7:
            while bitpos >= 0:
                byte |= 1 << bitpos
                bitpos -= 1
            out[k] = byte
            k += 1

    return bytes(out)


# 6색 패널용 "인덱스" 매핑 (필요하면 형 팔레트 규격에 맞춰 교체)
PALETTE_6 = {
    0: (255, 255, 255),  # white
    1: (0, 0, 0),        # black
    2: (255, 0, 0),      # red
    3: (255, 255, 0),    # yellow
    4: (0, 0, 255),      # blue
    5: (0, 255, 0),      # green
}

def nearest_palette_index(rgb: Tuple[int, int, int], palette: Dict[int, Tuple[int, int, int]]) -> int:
    r, g, b = rgb
    best_i = 0
    best_d = 10**18
    for i, (pr, pg, pb) in palette.items():
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def encode_4bpp_6color(img_rgb: Image.Image) -> bytes:
    img = img_rgb.convert("RGB")
    W, H = img.size
    px = img.load()

    # 2 pixels -> 1 byte
    out = bytearray(((W + 1) // 2) * H)

    k = 0
    for y in range(H):
        x = 0
        while x < W:
            idx0 = nearest_palette_index(px[x, y], PALETTE_6)
            if x + 1 < W:
                idx1 = nearest_palette_index(px[x + 1, y], PALETTE_6)
            else:
                idx1 = 0  # pad white
            out[k] = ((idx0 & 0x0F) << 4) | (idx1 & 0x0F)
            k += 1
            x += 2
    return bytes(out)


# =========================================================
# 6) End-to-end: IR -> Render -> BIN
# =========================================================
def ir_json_to_bin(ir_json: str, out_mode: str = "BW") -> Tuple[bytes, Image.Image, Dict[str, Any]]:
    """
    out_mode:
      - "BW": 1bpp
      - "C6": 4bpp 6-color index
    """
    ir = json.loads(ir_json)

    # IR에서 canvas.bpp에 따라 자동 선택하고 싶으면 여기서 분기
    img = render_ir_to_image(ir)

    if out_mode.upper() == "BW":
        bin_data = encode_bw_1bpp(img)
    elif out_mode.upper() == "C6":
        bin_data = encode_4bpp_6color(img)
    else:
        raise ValueError("out_mode must be 'BW' or 'C6'")

    return bin_data, img, ir


if __name__ == "__main__":
    # 1) BW(1bpp) 테스트
    bw_bin, bw_img, ir = ir_json_to_bin(SAMPLE_IR_JSON, out_mode="BW")
    bw_img.save("render_bw.png")
    with open("out_bw.bin", "wb") as f:
        f.write(bw_bin)
    print("BW done:", len(bw_bin), "bytes")

    # 2) 6-color 4bpp 테스트 (IR canvas.bpp와 무관하게 강제로 C6)
    c6_bin, c6_img, _ = ir_json_to_bin(SAMPLE_IR_JSON, out_mode="C6")
    c6_img.save("render_c6.png")
    with open("out_c6.bin", "wb") as f:
        f.write(c6_bin)
    print("C6 done:", len(c6_bin), "bytes")
