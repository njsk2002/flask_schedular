import os
import csv
import cv2
import argparse
from pathlib import Path

# -----------------------------
# Utilities
# -----------------------------
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def laplacian_var(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def imwrite_unicode(path: Path, img) -> bool:
    """
    Windows에서 cv2.imwrite가 한글 경로에서 실패하는 경우가 많아서
    imencode + tofile로 유니코드 경로 안정 저장.
    """
    ext = path.suffix.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".bmp"]:
        path = path.with_suffix(".png")
        ext = ".png"

    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False

    ensure_dir(path.parent)
    buf.tofile(str(path))
    return True

def rotate_frame(frame, rotate: str):
    if rotate == "cw":
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotate == "ccw":
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if rotate == "180":
        return cv2.rotate(frame, cv2.ROTATE_180)
    return frame  # none

# -----------------------------
# Frame time index generators
# -----------------------------
def iter_times_by_seconds(start_sec: float, end_sec: float, step_sec: float):
    t = start_sec
    while t <= end_sec + 1e-9:
        yield t
        t += step_sec

def iter_times_by_frames(start_sec: float, end_sec: float, fps: float, every_n_frames: int):
    """
    start~end 구간을 fps 기반으로 frame index로 변환해서
    every_n_frames 간격으로 샘플링한 뒤, 다시 sec로 변환해 yield.
    """
    if every_n_frames <= 0:
        every_n_frames = 1

    start_f = int(round(start_sec * fps))
    end_f = int(round(end_sec * fps))
    for fi in range(start_f, end_f + 1, every_n_frames):
        yield fi / fps

# -----------------------------
# Core extraction
# -----------------------------
def extract_frames(
    video_path: str,
    out_dir: str,
    start_sec: float,
    end_sec: float,
    rotate: str,
    step_sec: float = None,
    every_n_frames: int = None,
    save_roi: bool = False,
    roi: tuple[int, int, int, int] = (0, 0, 0, 0),
):
    out_dir = Path(out_dir)
    full_dir = out_dir / "full"
    roi_dir = out_dir / "roi"
    ensure_dir(full_dir)
    if save_roi:
        ensure_dir(roi_dir)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if frame_count > 0 else 0.0

    start_sec = max(0.0, start_sec)
    if end_sec <= 0:
        end_sec = duration
    else:
        end_sec = min(end_sec, duration)

    # sampling plan
    if every_n_frames is not None:
        times = iter_times_by_frames(start_sec, end_sec, fps, every_n_frames)
        mode = f"frames(every={every_n_frames})"
    else:
        # default: seconds step
        step_sec = 1.0 if (step_sec is None) else max(0.01, step_sec)
        times = iter_times_by_seconds(start_sec, end_sec, step_sec)
        mode = f"seconds(step={step_sec})"

    csv_path = out_dir / "frames_index.csv"
    x, y, w, h = roi

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["t_sec", "frame_idx", "sharpness", "full_path", "roi_path", "write_ok"])

        saved = 0
        for t in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            frame = rotate_frame(frame, rotate)
            frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            sharp = laplacian_var(frame)

            t_ms = int(round(t * 1000))
            fname = f"t_{t_ms:07d}ms_f{frame_idx:06d}_sharp{sharp:.1f}.png"
            full_path = full_dir / fname

            ok_full = imwrite_unicode(full_path, frame)

            roi_path = ""
            if save_roi and w > 0 and h > 0:
                H, W = frame.shape[:2]
                x0 = max(0, min(x, W - 1))
                y0 = max(0, min(y, H - 1))
                x1 = max(0, min(x + w, W))
                y1 = max(0, min(y + h, H))
                crop = frame[y0:y1, x0:x1].copy()
                rp = roi_dir / fname
                imwrite_unicode(rp, crop)
                roi_path = str(rp)

            wr.writerow([f"{t:.3f}", frame_idx, f"{sharp:.2f}", str(full_path), roi_path, ok_full])
            saved += 1

    cap.release()
    return {
        "mode": mode,
        "fps": fps,
        "duration_sec": duration,
        "saved_rows": saved,
        "csv_path": str(csv_path),
        "full_dir": str(full_dir),
    }

# -----------------------------
# CLI
# -----------------------------
def parse_args():
    ap = argparse.ArgumentParser()

    ap.add_argument("--video", required=True, help="mp4 path")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--start", type=float, default=0.0, help="start sec")
    ap.add_argument("--end", type=float, default=-1.0, help="end sec (<=0 means end of video)")
    ap.add_argument("--rotate", default="cw", choices=["none", "cw", "ccw", "180"])

    # seconds-based sampling
    ap.add_argument("--step", type=float, default=None, help="capture every N seconds (ex: 1.0)")

    # frame-based sampling (overrides --step)
    ap.add_argument("--every", type=int, default=None, help="capture every N frames (ex: 10)")

    # optional ROI saving
    ap.add_argument("--save_roi", action="store_true")
    ap.add_argument("--roi", default="0,0,0,0", help="ROI x,y,w,h on rotated frame")

    return ap.parse_args()

def main():
    """
    실행 예시 (형이 준 그대로):
    python extract_frames.py ^
      --video "C:\\DavidFiles\\JNT_Project\\출장\\20250918_당진출장\\part1.mp4" ^
      --out   "C:\\DavidFiles\\JNT_Project\\출장\\20250918_당진출장\\cap_test" ^
      --start 0 --end 10 --step 1 --rotate cw

    프레임 기준으로 뽑고 싶으면 (예: 10프레임마다 1장):
    python extract_frames.py ^
      --video "C:\\DavidFiles\\JNT_Project\\출장\\20250918_당진출장\\part1.mp4" ^
      --out   "C:\\DavidFiles\\JNT_Project\\출장\\20250918_당진출장\\cap_test" ^
      --start 0 --end 10 --every 10 --rotate cw
    """
    args = parse_args()
    roi = tuple(int(x) for x in args.roi.split(","))

    info = extract_frames(
        video_path=args.video,
        out_dir=args.out,
        start_sec=args.start,
        end_sec=args.end,
        rotate=args.rotate,
        step_sec=args.step,
        every_n_frames=args.every,
        save_roi=args.save_roi,
        roi=roi,
    )

    print(f"[OK] mode={info['mode']}, fps={info['fps']:.2f}, duration={info['duration_sec']:.2f}s")
    print(f"[OK] saved={info['saved_rows']}, csv={info['csv_path']}")
    print(f"[OK] images={info['full_dir']}")

if __name__ == "__main__":
    main()
