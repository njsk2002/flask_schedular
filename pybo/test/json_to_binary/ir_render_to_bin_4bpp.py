# -*- coding: utf-8 -*-
"""
IR(JSON file) -> Render(PIL) -> BIN encode (4bpp palette index)
pip install pillow
"""

import os
import json
from typing import Any, Dict, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

# -----------------------------
# Font loader with fallback (Korean)
# -----------------------------
def load_font(font_path: str, size: int) -> ImageFont.ImageFont:
    candidates = []
    if font_path:
        candidates.append(font_path)

    candidates += [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\malgunsl.ttf",
        r"C:\Windows\Fonts\NanumGothic.ttf",
        r"C:\Windows\Fonts\NanumBarunGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]

    for p in candidates:
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()

# -----------------------------
# binding: {{a.b}}, {{items[0].name}}
# -----------------------------
def _get_by_path(data: Any, path: str) -> Any:
    cur = data
    parts: List[str] = []
    buf = ""
    i = 0
    while i < len(path):
        ch = path[i]
        if ch == ".":
            if buf:
                parts.append(buf); buf = ""
            i += 1; continue
        if ch == "[":
            if buf:
                parts.append(buf); buf = ""
            j = path.find("]", i)
            idx_str = path[i+1:j]
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

def apply_binding(template: str, root: Dict[str, Any]) -> str:
    out = ""
    i = 0
    while i < len(template):
        s = template.find("{{", i)
        if s < 0:
            out += template[i:]; break
        out += template[i:s]
        e = template.find("}}", s)
        if e < 0:
            out += template[s:]; break
        expr = template[s+2:e].strip()
        val = _get_by_path(root, expr)
        out += str(val)
        i = e + 2
    return out

def resolve_value(expr_or_value: Any, root: Dict[str, Any]) -> Any:
    # if string looks like "{{...}}", resolve to actual object
    if isinstance(expr_or_value, str):
        t = expr_or_value.strip()
        if t.startswith("{{") and t.endswith("}}"):
            expr = t[2:-2].strip()
            return _get_by_path(root, expr)
        # normal string with bindings
        return apply_binding(expr_or_value, root)
    return expr_or_value

# -----------------------------
# text helpers
# -----------------------------
def truncate_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int, ellipsis: bool) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    if not ellipsis:
        while text and draw.textlength(text, font=font) > max_w:
            text = text[:-1]
        return text
    suffix = "…"
    t = text
    while t and draw.textlength(t + suffix, font=font) > max_w:
        t = t[:-1]
    return (t + suffix) if t else suffix

def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int, max_lines: int, ellipsis: bool) -> List[str]:
    words = text.split(" ")
    lines: List[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if draw.textlength(cand, font=font) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)

    if lines:
        # 마지막 줄 overflow면 ellipsis 처리
        if draw.textlength(lines[-1], font=font) > max_w:
            lines[-1] = truncate_to_width(draw, lines[-1], font, max_w, ellipsis)
    return lines[:max_lines]

# -----------------------------
# renderer: rect, text, list, table
# -----------------------------
def render_ir_to_image(ir: Dict[str, Any]) -> Image.Image:
    canvas = ir["canvas"]
    style = ir.get("style", {})
    constraints = ir.get("constraints", {})
    W, H = int(canvas["width"]), int(canvas["height"])
    bg = canvas.get("background", "#FFFFFF")

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    root = ir.get("data", {})
    ellipsis = bool(constraints.get("truncate_ellipsis", True))
    max_lines_default = int(constraints.get("max_lines_default", 1))
    default_font_path = style.get("font_path", "")
    default_font_size = int(style.get("font_size", 24))
    default_line_height = int(style.get("line_height", default_font_size + 10))

    for b in ir.get("blocks", []):
        t = str(b.get("type", "")).lower()

        if t == "rect":
            x, y = int(b["x"]), int(b["y"])
            w, h = int(b["w"]), int(b["h"])
            fill = b.get("fill")
            outline = b.get("outline")
            stroke = int(b.get("stroke", 1))
            if fill:
                draw.rectangle([x, y, x + w, y + h], fill=fill)
            if outline:
                for s in range(stroke):
                    draw.rectangle([x + s, y + s, x + w - s, y + h - s], outline=outline)
            continue

        if t == "text":
            x, y = int(b["x"]), int(b["y"])
            font_size = int(b.get("font_size", default_font_size))
            font = load_font(default_font_path, font_size)
            color = b.get("color", "#000000")
            max_w = int(b.get("max_width", W - x - 5))
            max_lines = int(b.get("max_lines", max_lines_default))
            raw = str(b.get("text", ""))
            text = apply_binding(raw, root)

            if max_lines <= 1:
                text = truncate_to_width(draw, text, font, max_w, ellipsis)
                draw.text((x, y), text, fill=color, font=font)
            else:
                lh = int(b.get("line_height", default_line_height))
                lines = wrap_lines(draw, text, font, max_w, max_lines, ellipsis)
                for i, line in enumerate(lines):
                    draw.text((x, y + i * lh), line, fill=color, font=font)
            continue

        if t == "list":
            x, y = int(b["x"]), int(b["y"])
            w, h = int(b["w"]), int(b["h"])
            font_size = int(b.get("font_size", default_font_size))
            font = load_font(default_font_path, font_size)
            color = b.get("color", "#000000")
            lh = int(b.get("line_height", default_line_height))
            max_items = int(b.get("max_items", 999))

            items = resolve_value(b.get("items", []), root)
            item_template = str(b.get("item_template", "{{item}}"))

            # 화면 높이에 맞춰 자동 제한
            max_fit = max(0, h // lh)
            limit = min(max_items, max_fit)

            yy = y
            for i in range(min(len(items), limit)):
                item = items[i]
                # item은 dict일 수 있으니 임시 root로 바인딩
                local_root = {**item}
                line = apply_binding(item_template, local_root)
                line = truncate_to_width(draw, line, font, w, True)
                draw.text((x, yy), line, fill=color, font=font)
                yy += lh
            continue

        if t == "table":
            x, y = int(b["x"]), int(b["y"])
            w, h = int(b["w"]), int(b["h"])
            font_size = int(b.get("font_size", 22))
            font = load_font(default_font_path, font_size)
            grid = b.get("grid", "#000000")
            header_fill = b.get("header_fill", "#FFFFFF")
            row_h = int(b.get("row_height", 40))
            col_widths = b.get("col_widths")
            if not col_widths:
                # 균등 분할
                col_count_guess = 5
                col_widths = [w // col_count_guess] * col_count_guess

            headers = resolve_value(b.get("headers", []), root)
            rows = resolve_value(b.get("rows", []), root)

            cols = len(col_widths)
            # 헤더 영역
            draw.rectangle([x, y, x + w, y + row_h], fill=header_fill)
            # grid
            draw.rectangle([x, y, x + w, y + row_h], outline=grid, width=2)

            # 세로선
            xx = x
            for cw in col_widths[:-1]:
                xx += int(cw)
                draw.line([xx, y, xx, y + h], fill=grid, width=2)

            # 가로선
            yy = y + row_h
            while yy <= y + h:
                draw.line([x, yy, x + w, yy], fill=grid, width=2)
                yy += row_h

            # 헤더 텍스트
            xx = x
            for ci in range(cols):
                txt = str(headers[ci]) if ci < len(headers) else ""
                txt = truncate_to_width(draw, txt, font, int(col_widths[ci]) - 10, True)
                draw.text((xx + 6, y + 8), txt, fill="#000000", font=font)
                xx += int(col_widths[ci])

            # 바디 텍스트
            max_rows_fit = max(0, (h - row_h) // row_h)
            for ri in range(min(len(rows), max_rows_fit)):
                row = rows[ri]
                base_y = y + row_h * (ri + 1) + 8
                xx = x
                for ci in range(cols):
                    cell = str(row[ci]) if ci < len(row) else ""
                    cell = truncate_to_width(draw, cell, font, int(col_widths[ci]) - 10, True)
                    draw.text((xx + 6, base_y), cell, fill="#000000", font=font)
                    xx += int(col_widths[ci])
            continue

        # 확장용: qr/barcode/image 등
        # if t == "qr": ...
        # if t == "barcode": ...
        # if t == "image": ...

    rot = int(canvas.get("rotation", 0))
    if rot in (90, 180, 270):
        img = img.rotate(rot, expand=True)
    return img

# -----------------------------
# 4bpp encoder (palette index, 2px per byte)
# -----------------------------
def hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.strip()
    if h.startswith("#"):
        h = h[1:]
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def build_palette(ir: Dict[str, Any]) -> Dict[int, Tuple[int, int, int]]:
    p = ir.get("palette", {})
    out: Dict[int, Tuple[int, int, int]] = {}
    for k, v in p.items():
        out[int(k)] = hex_to_rgb(str(v))
    # 최소 white/black 확보
    out.setdefault(0, (255, 255, 255))
    out.setdefault(1, (0, 0, 0))
    return out

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

def encode_4bpp_palette(img_rgb: Image.Image, palette: Dict[int, Tuple[int, int, int]]) -> bytes:
    img = img_rgb.convert("RGB")
    W, H = img.size
    px = img.load()

    out = bytearray(((W + 1) // 2) * H)

    k = 0
    for y in range(H):
        x = 0
        while x < W:
            idx0 = nearest_palette_index(px[x, y], palette)
            if x + 1 < W:
                idx1 = nearest_palette_index(px[x + 1, y], palette)
            else:
                idx1 = 0  # pad white
            out[k] = ((idx0 & 0x0F) << 4) | (idx1 & 0x0F)
            k += 1
            x += 2
    return bytes(out)

# -----------------------------
# main
# -----------------------------
def main():
    ir_path = "C:/DavidProject/flask_project/flask_scheduler/pybo/test/json_to_binary/sample_ir_1200x1600_4bpp.json"
    with open(ir_path, "r", encoding="utf-8") as f:
        ir = json.load(f)

    img = render_ir_to_image(ir)
    img.save("render_1200x1600.png")

    palette = build_palette(ir)
    bin_data = encode_4bpp_palette(img, palette)

    with open("out_1200x1600_4bpp.bin", "wb") as f:
        f.write(bin_data)

    W, H = img.size
    print(f"OK: render_1200x1600.png, out_1200x1600_4bpp.bin")
    print(f"Image: {W}x{H}  BIN bytes: {len(bin_data)}  (expected ~{(W*H)//2})")

if __name__ == "__main__":
    main()
