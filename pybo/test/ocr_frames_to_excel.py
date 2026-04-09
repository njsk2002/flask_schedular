import re
import csv
import time
import argparse
import shutil
from pathlib import Path
from collections import defaultdict, Counter

import cv2
import numpy as np
import pandas as pd
import pytesseract


# ============================================================
# Tesseract setup
# ============================================================
def setup_tesseract(user_path: str | None = None):
    """
    우선순위:
    1) --tesseract 로 받은 경로
    2) PATH에서 tesseract
    3) 일반 설치 경로
    """
    if user_path:
        p = Path(user_path)
        if p.exists():
            pytesseract.pytesseract.tesseract_cmd = str(p)
            return
        raise RuntimeError(f"tesseract not found: {user_path}")

    t = shutil.which("tesseract")
    if t:
        pytesseract.pytesseract.tesseract_cmd = t
        return

    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            pytesseract.pytesseract.tesseract_cmd = c
            return

    raise RuntimeError("tesseract.exe not found. Install Tesseract-OCR or pass --tesseract.")


# ============================================================
# Robust image IO (unicode path OK)
# ============================================================
def imread_unicode(path: Path):
    """
    cv2.imread는 한글/유니코드 경로에서 실패할 수 있어서,
    fromfile + imdecode 조합으로 안정 로딩
    """
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


# ============================================================
# Parsing
# ============================================================
DT_REGEX = re.compile(r"\b(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\.\d{3})\b")
NUM_REGEX = re.compile(r"(\d+(?:\.\d+)?)")


def parse_dt(text: str):
    text = (text or "").replace("  ", " ").strip()
    m = DT_REGEX.search(text)
    return m.group(1) if m else None


def parse_temp(text: str):
    text = (text or "").replace(",", ".").strip()
    m = NUM_REGEX.search(text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def ocr(img, psm=7, whitelist=None):
    """
    ✅ 윈도우 shlex 에러 방지:
    whitelist를 따옴표로 감싸면 (") shlex가 깨질 수 있으니,
    반드시 따옴표 없이 전달
    """
    cfg = f"--oem 3 --psm {psm}"
    if whitelist:
        wl = whitelist.replace('"', "").replace("'", "")
        cfg += f" -c tessedit_char_whitelist={wl}"
    return (pytesseract.image_to_string(img, config=cfg) or "").strip()


# ============================================================
# Preprocess variants (vote)
# ============================================================
def pre_date_v1(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    th = cv2.adaptiveThreshold(
        g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7
    )
    th = cv2.medianBlur(th, 3)
    return th


def pre_date_v2(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    g = cv2.GaussianBlur(g, (5, 5), 0)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def pre_date_v3(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    k = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    g = cv2.filter2D(g, -1, k)
    th = cv2.adaptiveThreshold(
        g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 31, 9
    )
    return th


def pre_temp_v1(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    inv = 255 - g
    _, th = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def pre_temp_v2(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    inv = 255 - g
    inv = cv2.GaussianBlur(inv, (3, 3), 0)
    th = cv2.adaptiveThreshold(
        inv, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7
    )
    return th


def pre_temp_v3(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    inv = 255 - g
    _, th = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, ker, iterations=1)
    return th


# ============================================================
# Column detection (temp column)
# ============================================================
def find_temp_col_bbox(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    inv = 255 - g
    _, th = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, ker, iterations=2)

    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None

    H, W = g.shape[:2]
    best, best_score = None, -1
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if h < H * 0.40:
            continue
        if w < W * 0.08:
            continue
        score = (x + w) / W + (h / H)
        if score > best_score:
            best_score = score
            best = (x, y, w, h)
    return best


# ============================================================
# Row split (horizontal edge projection)
# ============================================================
def split_rows(col_bgr):
    g = cv2.cvtColor(col_bgr, cv2.COLOR_BGR2GRAY)
    dy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    proj = np.abs(dy).mean(axis=1)

    k = 9
    proj_s = np.convolve(proj, np.ones(k) / k, mode="same")

    H = g.shape[0]
    thr = np.quantile(proj_s, 0.92)
    idx = np.where(proj_s >= thr)[0]

    if len(idx) < 10:
        approx = max(40, H // 18)
        rows = []
        y = 0
        while y < H:
            y1 = min(H, y + approx)
            if y1 - y >= 28:
                rows.append((y, y1))
            y = y1
        return rows

    cuts = [0]
    last = -999
    for y in idx:
        if y - last > 6:
            cuts.append(int(y))
        last = y
    cuts.append(H)
    cuts = sorted(set(cuts))

    rows = []
    for i in range(len(cuts) - 1):
        y0, y1 = cuts[i], cuts[i + 1]
        if y1 - y0 >= 28:
            rows.append((y0, y1))

    if len(rows) < 8:
        approx = max(40, H // 18)
        rows = []
        y = 0
        while y < H:
            y1 = min(H, y + approx)
            if y1 - y >= 28:
                rows.append((y, y1))
            y = y1

    return rows


# ============================================================
# OCR one row with voting
# ============================================================
def ocr_row(date_cell_bgr, temp_cell_bgr, temp_min=None, temp_max=None):
    dt_candidates = []
    for pre in (pre_date_v1, pre_date_v2, pre_date_v3):
        img = pre(date_cell_bgr)
        txt = ocr(img, psm=7, whitelist="0123456789/:. ")
        dt = parse_dt(txt)
        if dt:
            dt_candidates.append(dt)

    dt = None
    if dt_candidates:
        dt = Counter(dt_candidates).most_common(1)[0][0]

    tv_candidates = []
    for pre in (pre_temp_v1, pre_temp_v2, pre_temp_v3):
        img = pre(temp_cell_bgr)
        txt = ocr(img, psm=7, whitelist="0123456789.,")
        tv = parse_temp(txt)
        if tv is None:
            continue
        if temp_min is not None and tv < temp_min:
            continue
        if temp_max is not None and tv > temp_max:
            continue
        tv_candidates.append(round(tv, 2))

    tv = None
    if tv_candidates:
        most = Counter(tv_candidates).most_common()
        top_cnt = most[0][1]
        top_vals = [v for v, c in most if c == top_cnt]
        tv = top_vals[0] if len(top_vals) == 1 else sorted(tv_candidates)[len(tv_candidates) // 2]

    return dt, tv


# ============================================================
# Extract pairs from one image
# ============================================================
def extract_pairs_from_image(img_path: Path, temp_min=None, temp_max=None):
    bgr = imread_unicode(img_path)
    if bgr is None:
        return []

    H, W = bgr.shape[:2]
    bbox = find_temp_col_bbox(bgr)
    if bbox is None:
        return []

    tx, ty, tw, th = bbox

    pad_x = int(tw * 0.05)
    pad_y = int(th * 0.02)

    tx0 = max(0, tx - pad_x)
    tx1 = min(W, tx + tw + pad_x)
    ty0 = max(0, ty - pad_y)
    ty1 = min(H, ty + th + pad_y)

    temp_col = bgr[ty0:ty1, tx0:tx1]

    dx0 = int(W * 0.03)
    dx1 = max(dx0 + 220, tx0)
    date_col = bgr[ty0:ty1, dx0:dx1]

    rows = split_rows(temp_col)

    out = []
    for y0, y1 in rows:
        if y1 - y0 < 28:
            continue

        t_cell = temp_col[y0:y1, :]
        d_cell = date_col[y0:y1, :]

        dt, tv = ocr_row(d_cell, t_cell, temp_min=temp_min, temp_max=temp_max)
        if dt and (tv is not None):
            out.append((dt, float(tv)))

    return out


# ============================================================
# Read frames_index.csv (auto delimiter)
# ============================================================
def read_frames_csv(csv_path: Path):
    """
    frames_index.csv가 콤마/탭/세미콜론 등으로 저장돼도 읽히게 처리.
    기대 컬럼: full_path, sharpness, write_ok (있으면 사용)
    """
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    # 1) 먼저 sniffer로 구분자 감지 시도
    try:
        sample = csv_path.read_text(encoding="utf-8-sig", errors="ignore")[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"])
        sep = dialect.delimiter
        df = pd.read_csv(csv_path, sep=sep, engine="python", encoding="utf-8-sig")
    except Exception:
        # 2) fallback: pandas가 최대한 추측
        df = pd.read_csv(csv_path, sep=None, engine="python", encoding="utf-8-sig")

    # 컬럼 이름 유연하게 처리
    cols = {c.lower().strip(): c for c in df.columns}
    path_col = cols.get("full_path") or cols.get("path") or cols.get("file") or None
    sharp_col = cols.get("sharpness") or cols.get("sharp") or None
    ok_col = cols.get("write_ok") or cols.get("ok") or None

    if path_col is None:
        raise RuntimeError(f"CSV must contain 'full_path' column. columns={list(df.columns)}")

    items = []
    for _, row in df.iterrows():
        if ok_col is not None:
            v = str(row.get(ok_col, "")).strip().lower()
            if v in ("false", "0", "no", "n"):
                continue

        p = str(row.get(path_col, "")).strip()
        if not p:
            continue

        sharp = 0.0
        if sharp_col is not None:
            try:
                sharp = float(row.get(sharp_col, 0.0))
            except Exception:
                sharp = 0.0

        img = Path(p)
        if img.exists():
            items.append((sharp, img))

    return items


# ============================================================
# Dedupe by datetime
# ============================================================
def dedupe(pairs):
    bucket = defaultdict(list)
    for dt, tv in pairs:
        bucket[dt].append(round(float(tv), 2))

    out = []
    for dt, arr in bucket.items():
        c = Counter(arr).most_common()
        top_cnt = c[0][1]
        top_vals = [v for v, cnt in c if cnt == top_cnt]
        if len(top_vals) == 1:
            out.append((dt, top_vals[0]))
        else:
            s = sorted(arr)
            out.append((dt, s[len(s) // 2]))

    out.sort(key=lambda x: x[0])
    return out


# ============================================================
# Pipeline
# ============================================================
def run(csv_path: Path, out_xlsx: Path, topk=0, min_sharp=0.0, temp_min=None, temp_max=None, verbose=True):
    t0 = time.time()

    print("[STEP] Load frames_index.csv ...")
    frames = read_frames_csv(csv_path)
    print(f"[INFO] frames found: {len(frames)}")

    frames = [(s, p) for (s, p) in frames if s >= min_sharp]
    frames.sort(key=lambda x: x[0], reverse=True)
    if topk and topk > 0:
        frames = frames[:topk]

    total = len(frames)
    print(f"[STEP] Frames selected: {total} (topk={topk}, min_sharp={min_sharp})")

    all_pairs = []
    ok_frames = 0
    skip_frames = 0

    for i, (s, img_path) in enumerate(frames, 1):
        t_frame = time.time()
        status = "OK"
        got = 0
        reason = ""

        try:
            pairs = extract_pairs_from_image(img_path, temp_min=temp_min, temp_max=temp_max)
            got = len(pairs)
            if got:
                ok_frames += 1
                all_pairs.extend(pairs)
                status = "OK"
            else:
                skip_frames += 1
                status = "EMPTY"   # bbox 못찾거나 OCR 실패 등
        except Exception as e:
            skip_frames += 1
            status = "ERR"
            got = 0
            reason = str(e)

        dt_ms = (time.time() - t_frame) * 1000.0

        # ✅ 1장당 1줄 진행 로그
        if verbose:
            msg = (
                f"[FRAME] {i}/{total} {status} "
                f"sharp={s:.1f} pairs={got} raw_pairs={len(all_pairs)} "
                f"{dt_ms:.0f}ms  {img_path}"
            )
            print(msg)

            # 에러 이유는 너무 길면 지저분하니 ERR일 때만 짧게 1줄
            if status == "ERR" and reason:
                short = reason.replace("\n", " ")
                if len(short) > 160:
                    short = short[:160] + "..."
                print(f"        reason: {short}")

    print("[STEP] Dedupe by datetime ...")
    final_pairs = dedupe(all_pairs)
    print(f"[INFO] dedupe result rows: {len(final_pairs)} (raw_pairs={len(all_pairs)})")

    print("[STEP] Save Excel ...")
    df = pd.DataFrame(final_pairs, columns=["datetime", "temp"])
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(out_xlsx, index=False)

    t1 = time.time()
    print(f"[DONE] saved: {out_xlsx}")
    print(f"[DONE] elapsed: {t1 - t0:.1f}s  ok_frames={ok_frames}  skip_frames={skip_frames}")

    return len(frames), len(all_pairs), len(final_pairs)




def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="frames_index.csv path")
    ap.add_argument("--out", required=True, help="output xlsx path")
    ap.add_argument("--topk", type=int, default=250, help="use top-K sharp frames (0=all)")
    ap.add_argument("--min_sharp", type=float, default=0.0, help="sharpness threshold")
    ap.add_argument("--temp_min", type=float, default=None, help="optional temp lower bound")
    ap.add_argument("--temp_max", type=float, default=None, help="optional temp upper bound")
    ap.add_argument("--tesseract", default=None, help="tesseract.exe full path (optional)")
    ap.add_argument("--quiet", action="store_true", help="less logs")
    return ap.parse_args()


def main():
    args = parse_args()
    setup_tesseract(args.tesseract)

    frames_used, raw_pairs, final_rows = run(
        csv_path=Path(args.csv),
        out_xlsx=Path(args.out),
        topk=args.topk,
        min_sharp=args.min_sharp,
        temp_min=args.temp_min,
        temp_max=args.temp_max,
        verbose=(not args.quiet),
    )

    print(f"[OK] frames_used={frames_used}")
    print(f"[OK] raw_pairs={raw_pairs}")
    print(f"[OK] final_rows(after dedupe)={final_rows}")
    print(f"[OK] saved: {args.out}")


if __name__ == "__main__":
    main()
