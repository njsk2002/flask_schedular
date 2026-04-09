# -*- coding: utf-8 -*-
import struct
import zlib
import numpy as np
from PIL import Image, ImageOps  # ← ImageOps 추가
from flask import current_app


class ImageToBytes:
    """
        E-Ink 전송 RAW 생성기 (해상도 무관)

        모드
        ----
        - BW(1bpp):
            흰=1, 검=0, MSB-first (8픽셀=1바이트)
            → 가로 8px 패딩(흰=1)  # 2025-09-11: 주석 명확화

        - BWRY(2bpp):
            2bit/pixel (W=00, Y=01, R=10, K=11)
            바이트 = (p0<<6)|(p1<<4)|(p2<<2)|p3  (좌→우, 상→하)
            → 가로 4px 패딩(흰=W 코드)

        - BWRYBG(4bpp)  # 2025-09-11: NEW (기본)
            4bit/pixel (Spectra 6: W=1, Y=2, R=3, B=5, G=6, K=0)
            2픽셀=1바이트: 상위 nibble=왼쪽 픽셀, 하위 nibble=오른쪽 픽셀
            → 가로 픽셀 수가 홀수면 마지막 1픽셀 'W'로 패딩
            → 하드웨어 정합을 위해 행 바이트 순서를 기본적으로 오른쪽→왼쪽(rtl=True)로 생성  # 2025-09-11

        - BWRYBG3(3bpp)  # 2025-09-11: NEW (옵션 경로, 혹시 필요할 때 사용)
            3bit/pixel (W=000, Y=001, R=010, B=011, G=100, K=101)
            8픽셀(24비트) → 3바이트로 패킹, 가로 8px 패딩(흰)
    """

    # ---------- 매핑 테이블 ----------
    # (기존) 4색 2bpp 매핑
    MAPPING_DEVICE = {"W": 0b00, "Y": 0b01, "R": 0b10, "K": 0b11}

    # 2025-09-11: NEW - 6색 4bpp nibble 매핑 (GDEP133C02 샘플/매크로와 일치)
    # #define BLACK 0x00 / WHITE 0x11 / YELLOW 0x22 / RED 0x33 / BLUE 0x55 / GREEN 0x66
    # → 실제 nibble 값: K=0x0, W=0x1, Y=0x2, R=0x3, B=0x5, G=0x6
    MAPPING_DEVICE_6_4BPP = {
        "K": 0x0,  # Black
        "W": 0x1,  # White
        "Y": 0x2,  # Yellow
        "R": 0x3,  # Red
        "B": 0x5,  # Blue
        "G": 0x6,  # Green
    }

    # 2025-09-11: KEEP - 6색 3bpp 기본 매핑 (옵션 경로용, 기본 사용 안 함)
    MAPPING_DEVICE_6_3BPP = {
        "W": 0b000,
        "Y": 0b001,
        "R": 0b010,
        "B": 0b011,
        "G": 0b100,
        "K": 0b101,
    }

    # 근접색 판별용 레퍼런스 RGB (6색 공통)  # 2025-09-11: 주석 정리
    COLOR_REF_6 = {
        (255, 255, 255): "W",
        (255, 255,   0): "Y",
        (255,   0,   0): "R",
        (0,     0,   0): "K",
        (0,   255,   0): "G",
        (0,     0, 255): "B",
    }

    # (기존) 4색 RGB→2bpp 매핑 기준 컬러
    COLOR_REF_4 = {
        (255, 255, 255): 0b00,  # White
        (255, 255,   0): 0b01,  # Yellow
        (255,   0,   0): 0b10,  # Red
        (0,     0,   0): 0b11,  # Black
    }
    # ---------- 내부 유틸 ----------
    @staticmethod
    def _ensure_rgb(img: Image.Image) -> Image.Image:
        return img if img.mode == "RGB" else img.convert("RGB")

    @staticmethod
    def _maybe_resize(img: Image.Image, size: tuple[int, int] | None) -> Image.Image:
        if not size:
            return img
        w, h = size
        return img if img.size == (w, h) else img.resize((w, h), Image.LANCZOS)

    # ---------- BW: 1bpp ----------
    @staticmethod
    def _pack_bw_1bpp(img: Image.Image, threshold: int | None = None) -> bytes:
        """
        - img.mode == '1' 이면: 바로 패킹
        - 그 외('L' 등) 이면: threshold 필요 → 임계 후 패킹
        """
        current_app.logger.info(f"[BW] input mode={img.mode}")
        if img.mode == "1":
            arr = np.array(img, dtype=np.uint8)     # 0 or 255
            bits = (arr != 0).astype(np.uint8)      # 흰=1, 검=0  # 2025-09-11: 주석 정리
        else:
            if threshold is None:
                raise ValueError("threshold is required when img.mode != '1'")
            g = img.convert("L")
            arr = np.array(g, dtype=np.uint8)
            bits = (arr >= threshold).astype(np.uint8)  # 흰=1, 검=0  # 2025-09-11: CHANGED(의도 일관)

        H, W = bits.shape
        pad = (-W) % 8
        if pad:
            bits = np.pad(bits, ((0, 0), (0, pad)), constant_values=1)  # 흰으로 패딩  # 2025-09-11
            W += pad

        # MSB-first 패킹 (좌→우 8비트)
        chunks = bits.reshape(H, W // 8, 8)
        weights = np.array([128, 64, 32, 16, 8, 4, 2, 1], dtype=np.uint8)
        packed = (chunks * weights).sum(axis=2).astype(np.uint8)

        payload = packed.tobytes()
        current_app.logger.info(f"[BW] {H}x{W} -> {len(payload)} bytes (expect {(H*W)//8})")
        return payload

    # ---------- BWRY: 2bpp ----------
    @staticmethod
    def _map_color_4(rgb):
        """RGB → 4색 2bpp 코드 (overflow 방지 승격)  # 2025-09-11"""
        r = int(rgb[0]); g = int(rgb[1]); b = int(rgb[2])
        diffs = {}
        for (rr, gg, bb), code in ImageToBytes.COLOR_REF_4.items():
            dr = r - rr; dg = g - gg; db = b - bb
            diffs[code] = dr*dr + dg*dg + db*db
        return min(diffs, key=diffs.get)

    @staticmethod
    def _pack_bwry_2bpp_direct(img: Image.Image) -> bytes:
        img = img.convert("RGB")
        w, h = img.size
        out = bytearray()
        acc = 0
        bitcnt = 0
        for y in range(h):
            for x in range(w):
                code = ImageToBytes._map_color_4(img.getpixel((x, y)))  # 2비트
                acc = (acc << 2) | code
                bitcnt += 2
                if bitcnt == 8:
                    out.append(acc & 0xFF)
                    acc = 0
                    bitcnt = 0
        if bitcnt:
            out.append((acc << (8 - bitcnt)) & 0xFF)
        return bytes(out)

    @staticmethod
    def _pack_bwry_2bpp_from_P(im_p: Image.Image, mapping: dict[str, int]) -> bytes:
        idx = np.array(im_p, dtype=np.uint8)      # H×W (0=K,1=R,2=Y,3=W) 가정
        lut = np.zeros(256, dtype=np.uint8)
        lut[0] = mapping["K"]
        lut[1] = mapping["R"]
        lut[2] = mapping["Y"]
        lut[3] = mapping["W"]
        codes = lut[idx]
        # 4픽셀=1바이트
        H, W = codes.shape
        pad = (-W) % 4
        if pad:
            codes = np.pad(codes, ((0, 0), (0, pad)), constant_values=mapping["W"])
            W += pad
        groups = codes.reshape(H, W // 4, 4).astype(np.uint8)
        byte_vals = ((groups[:, :, 0] << 6) |
                     (groups[:, :, 1] << 4) |
                     (groups[:, :, 2] << 2) |
                     (groups[:, :, 3]))
        return byte_vals.astype(np.uint8).tobytes()


    # ---------- BWRYBG: 6색 (공통 유틸) ----------
    @staticmethod
    def _nearest_label_6(rgb) -> str:
        """RGB → 가장 가까운 6색 라벨('W','Y','R','B','G','K')  # 2025-09-11 (overflow fix)"""
        r = int(rgb[0]); g = int(rgb[1]); b = int(rgb[2])
        best = None; best_d = None
        for (rr, gg, bb), label in ImageToBytes.COLOR_REF_6.items():
            dr = r - rr; dg = g - gg; db = b - bb
            d2 = dr*dr + dg*dg + db*db
            if best_d is None or d2 < best_d:
                best_d, best = d2, label
        return best

    # --- 4bpp 직패킹 (기본)  # 2025-09-11: NEW ---
        # --- 4bpp 직패킹 (기본)  # 2025-09-11: NEW + 2025-09-17: 옵션 확장 ---
    @staticmethod
    def _pack_bwrybg_4bpp_direct(img: Image.Image,
                                 mapping_nibble: dict[str, int] | None = None,
                                rtl: bool = False,            # ← 기본 LTR
                                swap_nibbles: bool = False,   # ← 기본: 좌=상위, 우=하위
                                flip_x: bool = False,
                                flip_y: bool = False) -> bytes:
        """
        6색을 4bpp nibble로 패킹 (2픽셀=1바이트).

        바이트 구성(기본): 상위 nibble=왼쪽 픽셀, 하위 nibble=오른쪽 픽셀.
        - swap_nibbles=True 이면 바이트 내부 닙블도 좌↔우 교환.
        - rtl=True 이면 행의 바이트 순서를 오른쪽→왼쪽으로 반전.
        - flip_x / flip_y 는 픽셀 좌표계 자체를 미리 뒤집어서 생성.

        가로 픽셀 수가 홀수면 마지막 1픽셀은 'W'로 패딩.
        """
        img = img.convert("RGB")
        if flip_x:
            img = ImageOps.mirror(img)
        if flip_y:
            img = ImageOps.flip(img)

        W, H = img.size
        mp = mapping_nibble or ImageToBytes.MAPPING_DEVICE_6_4BPP

        out = bytearray(H * ((W + 1) // 2))
        arr = np.array(img, dtype=np.uint8)  # (H,W,3)

        for y in range(H):
            row_bytes = bytearray(((W + 1) // 2))
            wi = 0
            x = 0
            while x < W:
                # 왼쪽 픽셀
                lab0 = ImageToBytes._nearest_label_6(arr[y, x])
                n0 = mp[lab0] & 0x0F
                # 오른쪽 픽셀 (없으면 W로 패딩)
                if x + 1 < W:
                    lab1 = ImageToBytes._nearest_label_6(arr[y, x + 1])
                    n1 = mp[lab1] & 0x0F
                else:
                    n1 = mp["W"] & 0x0F

                if swap_nibbles:
                    row_bytes[wi] = (n1 << 4) | n0
                else:
                    row_bytes[wi] = (n0 << 4) | n1

                wi += 1
                x += 2

            if rtl:
                row_bytes.reverse()

            start = y * ((W + 1) // 2)
            out[start:start + len(row_bytes)] = row_bytes

        return bytes(out)



    # --- 3bpp 직패킹 (옵션 경로)  # 2025-09-11: KEEP ---
    @staticmethod
    def _pack_codes_3bpp(codes_2d: np.ndarray, white_code: int = 0) -> bytes:
        """3bpp: 가로 8픽셀 그룹 → 24비트(3바이트) 패킹. 가로 8px 패딩(흰)."""
        H, W = codes_2d.shape
        pad = (-W) % 8
        if pad:
            codes_2d = np.pad(codes_2d, ((0, 0), (0, pad)), constant_values=white_code)
            W += pad

        groups = codes_2d.reshape(H, W // 8, 8).astype(np.uint8)  # (H, G, 8)
        c0 = groups[:, :, 0]; c1 = groups[:, :, 1]; c2 = groups[:, :, 2]; c3 = groups[:, :, 3]
        c4 = groups[:, :, 4]; c5 = groups[:, :, 5]; c6 = groups[:, :, 6]; c7 = groups[:, :, 7]

        b0 = ((c0 << 5) | (c1 << 2) | (c2 >> 1)) & 0xFF
        b1 = ((((c2 & 0x1) << 7) | (c3 << 4) | (c4 << 1) | (c5 >> 2))) & 0xFF
        b2 = ((((c5 & 0x3) << 6) | (c6 << 3) | c7)) & 0xFF

        out = np.stack([b0, b1, b2], axis=2).astype(np.uint8)   # (H, G, 3)
        return out.reshape(-1).tobytes()

    @staticmethod
    def _pack_bwrybg_3bpp_direct(img: Image.Image) -> bytes:
        """RGB 이미지를 6색(3bpp)으로 근접 매핑 후 패킹 (옵션 경로)"""
        img = img.convert("RGB")
        arr = np.array(img, dtype=np.uint8)  # (H,W,3)
        H, W, _ = arr.shape
        codes = np.empty((H, W), dtype=np.uint8)
        for y in range(H):
            row = arr[y]
            for x in range(W):
                # 3bpp용 코드표로 직접 기록
                label = ImageToBytes._nearest_label_6(row[x])
                codes[y, x] = ImageToBytes.MAPPING_DEVICE_6_3BPP[label]
        return ImageToBytes._pack_codes_3bpp(
            codes, white_code=ImageToBytes.MAPPING_DEVICE_6_3BPP["W"]
        )

    # ---------- 공개 API ----------
    @staticmethod
    def image_to_payload(img: Image.Image,
                         mode: str,
                         size: tuple[int, int] | None = None,
                         mapping: dict[str, int] | None = None,
                         white_thresh: int = 240,
                         sat_thresh: float = 0.25) -> bytes:
        """
        입력 이미지를 모드에 맞게 패킹한 RAW + CRC32(LE) 4바이트를 반환
        - rotate는 라우트 단계에서 처리한다고 가정  # 2025-09-11: 주석 명확화
        """
        if size and img.size != size:
            img = img.resize(size, Image.LANCZOS)

        mode_up = (mode or "BW").upper()

        if mode_up == "BW":
            raw = ImageToBytes._pack_bw_1bpp(img, threshold=white_thresh)
            current_app.logger.info(f"[BW] payload len={len(raw)}")

        elif mode_up == "BWRY":
            # 'P' 팔레트면 인덱스 기반, 아니면 RGB 근접색 기반
            if img.mode == "P":
                raw = ImageToBytes._pack_bwry_2bpp_from_P(img, mapping or ImageToBytes.MAPPING_DEVICE)
            else:
                raw = ImageToBytes._pack_bwry_2bpp_direct(img)
            current_app.logger.info(f"[BWRY] payload len={len(raw)}")

        elif mode_up in ("BWRYBG", "SPECTRA6", "COLOR6"):  # 2025-09-11: 기본 4bpp
            # GDEP133C02 데모 .h 기준: 행 반전 + 닙블 스왑이 맞는 경우가 대부분
            raw = ImageToBytes._pack_bwrybg_4bpp_direct(
                    img,
                    mapping_nibble=(mapping or ImageToBytes.MAPPING_DEVICE_6_4BPP),
                    rtl=False,           # ← 행을 뒤집지 않음 (좌→우)
                    swap_nibbles=False,  # ← 바이트 내 닙블 순서 유지(상위=왼쪽, 하위=오른쪽)
                    flip_x=False,
                    flip_y=False,
                )
            current_app.logger.info(f"[BWRYBG-4bpp] payload len={len(raw)}")


        elif mode_up in ("BWRYBG3", "SPECTRA6_3BPP"):      # 2025-09-11: 옵션 3bpp 경로
            raw = ImageToBytes._pack_bwrybg_3bpp_direct(img)
            current_app.logger.info(f"[BWRYBG-3bpp] payload len={len(raw)}")

        else:
            raise ValueError("mode must be 'BW', 'BWRY', 'BWRYBG' (or 'BWRYBG3')")

        crc = zlib.crc32(raw) & 0xFFFFFFFF
        return raw + struct.pack("<I", crc)

    @staticmethod
    def image_file_to_payload(fp: str,
                              mode: str,
                              size: tuple[int, int] | None = None,
                              mapping: dict[str, int] | None = None,
                              white_thresh: int = 240,
                              sat_thresh: float = 0.25) -> bytes:
        with Image.open(fp) as im:
            if im.mode != "P":
                im = im.convert("RGB")
            return ImageToBytes.image_to_payload(
                im, mode, size=size, mapping=mapping,
                white_thresh=white_thresh, sat_thresh=sat_thresh
            )
