# -*- coding: utf-8 -*-
from io import BytesIO
import zlib, struct, os
import numpy as np
from PIL import Image, ImageOps, ImageFilter

try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None


# =====================================================================
# 1) 검정(기존) 버전: FileTranslationBlackBG
# =====================================================================
class FileTranslationBlackBG:
    """
    - 업로드 파일 로딩(PDF/이미지)
    - 배치(FIT/FILL/PERCENT) + 회전
    - 팔레트/디더링 (BW/BWRY) - 일반 FS 양자화
    - 패킹(1bpp/2bpp)
    - EJOB 패키징
    """

    def __init__(self, uploads_store: dict, pdf_dpi: int = 200):
        self.uploads = uploads_store
        self.pdf_dpi = pdf_dpi

    # ---------- 내부 유틸 ----------
    @staticmethod
    def _calc_fit_fill_size(src_w, src_h, dst_w, dst_h, mode="fit", percent=100):
        if mode not in ("fit", "fill", "percent"):
            mode = "fit"
        if mode == "percent":
            scale_fit = min(dst_w / src_w, dst_h / src_h)
            scale = scale_fit * (percent / 100.0)
        elif mode == "fit":
            scale = min(dst_w / src_w, dst_h / src_h)
        else:  # fill
            scale = max(dst_w / src_w, dst_h / src_h)

        new_w = max(1, int(round(src_w * scale)))
        new_h = max(1, int(round(src_h * scale)))
        return new_w, new_h

    @classmethod
    def _place_into_canvas(cls, img, W, H, mode="fit", percent=100):
        """img(RGB) -> W×H 캔버스 중앙 배치 (fit/fill/percent) + 필요 시 중앙 크롭"""
        src_w, src_h = img.size
        new_w, new_h = cls._calc_fit_fill_size(src_w, src_h, W, H, mode, percent)

        if mode in ("fit", "percent"):
            simg = img.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGB", (W, H), (255, 255, 255))
            ox = (W - new_w) // 2
            oy = (H - new_h) // 2
            canvas.paste(simg, (ox, oy))
            return canvas
        else:
            simg = img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - W) // 2
            top  = (new_h - H) // 2
            return simg.crop((left, top, left + W, top + H))

    # ---------- 팔레트/양자화 (기존) ----------
    @staticmethod
    def quantize_to_BWRY(im_rgb: Image.Image) -> Image.Image:
        """RGB -> 4색 팔레트(P) [black, red, yellow, white] + FS 디더"""
        pal = Image.new("P", (1, 1))
        pal.putpalette(
            [0, 0, 0,  255, 0, 0,  255, 255, 0,  255, 255, 255] + [0, 0, 0] * 252
        )
        im_p = im_rgb.quantize(palette=pal, dither=Image.FLOYDSTEINBERG)
        return im_p  # P, index: 0=K,1=R,2=Y,3=W

    # ---------- 6색 팔레트 양자화 (BWRYBG) ----------  # 2025-09-11 NEW
    @staticmethod
    def quantize_to_BWRYBG(im_rgb: Image.Image, dither=True) -> Image.Image:
        """
        RGB -> 6색 제한 팔레트(RGB)
        팔레트: K(0,0,0), R(255,0,0), Y(255,255,0), W(255,255,255), G(0,255,0), B(0,0,255)
        반환: 'RGB' (팔레트 한정 색상만 포함). ImageToBytes 쪽에서 RGB→3bpp 직접 매핑.
        """
        pal = Image.new("P", (1, 1))
        # 인덱스 순서는 중요치 않음(우린 RGB 직접매퍼 사용). 단, 팔레트는 256*3 채워야 함.
        palette = [
            0, 0, 0,          # K
            255, 0, 0,        # R
            255, 255, 0,      # Y
            255, 255, 255,    # W
            0, 255, 0,        # G
            0, 0, 255,        # B
        ] + [0, 0, 0] * (256 - 6)
        pal.putpalette(palette)

        im_p = im_rgb.convert("RGB").quantize(
            palette=pal,
            dither=Image.FLOYDSTEINBERG if dither else Image.NONE
        )
        return im_p.convert("RGB")  # RGB로 돌려 ImageToBytes의 3bpp 매퍼를 태움


    # @staticmethod
    # def quantize_to_BW(im_rgb: Image.Image, threshold: int = 170) -> Image.Image:
    #     """
    #     RGB -> 1bpp 흑백 (검정=1, 흰=0).
    #     threshold보다 작은 값은 검정, 크면 흰.
    #     """
    #     g = im_rgb.convert("L")
    #     bits = (np.array(g, dtype=np.uint8) < threshold).astype(np.uint8)  # 검정=1, 흰=0

    #     # 프리뷰는 Pillow convention 때문에 반전시켜야 맞게 보임
    #     im_bin = Image.fromarray((1 - bits) * 255, mode="L").convert("1")
    #     return im_bin

    # @staticmethod
    # def quantize_to_BW(im_rgb: Image.Image, use_dither: bool = True) -> Image.Image:
    #     """
    #     사진/일반 이미지에 가장 무난한 1bpp 변환:
    #     - Grayscale("L") → 1비트("1")
    #     - 디더는 Floyd–Steinberg 기본
    #     반환: Pillow '1' (0=검정, 255=흰)
    #     """
    #     g = im_rgb.convert("L")  # 최종 해상도로 맞춘 뒤 호출할 것!
    #     # return g.convert("1", dither=Image.FLOYDSTEINBERG if use_dither else Image.NONE)
    #     return g.convert("1", dither=Image.NONE)  # 텍스트는 디더 끄기

    @staticmethod
    def quantize_to_BW(
        im_rgb: Image.Image,
        method: str = "fs",          # 'fs' | 'atkinson' | 'bayer8' | 'thresh' | 'otsu'
        threshold: int = 128,        # 'thresh' 또는 의사-밝기 보정에 사용
        gamma: float = 1.20,         # 1.0=무보정. 1.15~1.35 권장 (배경 더 하얗게)
        contrast: float = 1.10,      # 1.0=무보정. 살짝만 올려 텍스트 또렷하게
        white_boost: int = 245,      # 이 값 이상은 강제로 255(완전 흰)
        unsharp: tuple = (1.2, 160, 4),  # (radius, percent, threshold)
        serpentine: bool = True      # 오차확산 시 지그재그 스캔(패턴 줄이기)
    ) -> Image.Image:
        """
        자연스럽고 부드러운 1bpp(흑백 1비트) 양자화.
        - 전처리: Auto-contrast → Gamma → White boost → Unsharp
        - 디더링: Floyd–Steinberg(기본) / Atkinson / Bayer 8x8 / (단순)임계 / Otsu
        - 반환: Pillow '1' (검정=0, 흰=255)
        """
        import numpy as np
        from PIL import ImageOps, ImageFilter

        # ---------- 0) Grayscale ----------
        g = im_rgb.convert("L")

        # ---------- 1) 전처리 (부드럽고 또렷하게) ----------
        # 1-1) 미세한 클리핑으로 대비 펴주기
        g = ImageOps.autocontrast(g, cutoff=1)  # 상하 1% 컷 (노이즈 과증폭 방지)
        # 1-2) 감마: 배경(밝은 영역) 띄우고 잉크(어두운 영역) 살짝 눌러줌
        if gamma and abs(gamma - 1.0) > 1e-3:
            lut = [min(255, max(0, int(round(255.0 * ((i / 255.0) ** gamma))))) for i in range(256)]
            g = g.point(lut)
        # 1-3) 완전 흰 쪽으로 밀기 (노란/회색 배경 제거에 효과)
        if white_boost:
            wb = int(white_boost)
            g = g.point(lambda p, wb=wb: 255 if p >= wb else p)
        # 1-4) 텍스트/엣지 선명도
        if unsharp:
            r, p, t = unsharp
            g = g.filter(ImageFilter.UnsharpMask(radius=float(r), percent=int(p), threshold=int(t)))

        # ---------- 2) 디더링 본처리 ----------
        arr = np.asarray(g, dtype=np.float32)
        H, W = arr.shape

        def to_img1(bin_arr: np.ndarray) -> Image.Image:
            """0/255 배열 -> '1' 모드 변환."""
            return Image.fromarray(bin_arr.astype(np.uint8), mode="L").convert("1")

        if method.lower() in ("thresh", "threshold"):
            out = np.where(arr >= threshold, 255, 0).astype(np.uint8)
            return to_img1(out)

        if method.lower() == "otsu":
            # 간단 Otsu 임계 + 1비트
            hist = np.bincount(arr.astype(np.uint8).ravel(), minlength=256).astype(np.float64)
            total = arr.size
            sum_total = np.dot(np.arange(256), hist)
            sumB = 0.0; wB = 0.0; varMax = -1.0; thr = 128
            for i in range(256):
                wB += hist[i]
                if wB == 0: continue
                wF = total - wB
                if wF == 0: break
                sumB += i * hist[i]
                mB = sumB / wB
                mF = (sum_total - sumB) / wF
                varBetween = wB * wF * (mB - mF) ** 2
                if varBetween > varMax:
                    varMax = varBetween; thr = i
            out = np.where(arr >= thr, 255, 0).astype(np.uint8)
            return to_img1(out)

        if method.lower() in ("bayer", "bayer8", "ordered"):
            # 8x8 Bayer(ordered dithering): 인쇄 느낌, 균일한 텍스처
            B8 = np.array([
                [ 0,48,12,60, 3,51,15,63],
                [32,16,44,28,35,19,47,31],
                [ 8,56, 4,52,11,59, 7,55],
                [40,24,36,20,43,27,39,23],
                [ 2,50,14,62, 1,49,13,61],
                [34,18,46,30,33,17,45,29],
                [10,58, 6,54, 9,57, 5,53],
                [42,26,38,22,41,25,37,21]
            ], dtype=np.float32)
            T = (B8 + 0.5) * (255.0 / 64.0)  # 0..255
            # 타일링 비교
            out = np.empty_like(arr, dtype=np.uint8)
            for y in range(H):
                for x in range(W):
                    out[y, x] = 255 if arr[y, x] > T[y & 7, x & 7] else 0
            return to_img1(out)

        # ---- 오차 확산(Error Diffusion): FS/Atkinson ----
        # 공통 유틸
        def error_diffusion(src: np.ndarray, kernel: str = "fs", serp: bool = True) -> np.ndarray:
            a = src.copy()
            out = np.zeros_like(a, dtype=np.uint8)

            if kernel == "fs":
                # Floyd–Steinberg (1/16): [(+1,0)=7, (-1,+1)=3, (0,+1)=5, (+1,+1)=1]
                neigh = [ (1,0,7/16), (-1,1,3/16), (0,1,5/16), (1,1,1/16) ]
            elif kernel == "atkinson":
                # Atkinson (1/8)
                neigh = [ (1,0,1/8), (2,0,1/8), (-1,1,1/8), (0,1,1/8), (1,1,1/8), (0,2,1/8) ]
            else:
                neigh = [ (1,0,7/16), (-1,1,3/16), (0,1,5/16), (1,1,1/16) ]

            for y in range(H):
                if serp and (y % 2 == 1):
                    xs = range(W-1, -1, -1); s = -1
                else:
                    xs = range(0, W);       s =  1
                for x in xs:
                    old = a[y, x]
                    newv = 255.0 if old >= float(threshold) else 0.0   # 기준(기본 128)
                    out[y, x] = 255 if newv > 0 else 0
                    err = old - newv
                    # 에러 전파
                    for dx, dy, w in neigh:
                        tx = x + (dx * s)      # serpentine일 때 좌우 반전
                        ty = y + dy
                        if 0 <= tx < W and 0 <= ty < H:
                            a[ty, tx] = np.clip(a[ty, tx] + err * w, 0.0, 255.0)
            return out

        if method.lower() in ("fs", "floyd", "floyd-steinberg"):
            out = error_diffusion(arr, kernel="fs", serp=serpentine)
            return to_img1(out)

        if method.lower() in ("atkinson",):
            out = error_diffusion(arr, kernel="atkinson", serp=serpentine)
            return to_img1(out)

        # fallback: 단순 임계
        out = np.where(arr >= threshold, 255, 0).astype(np.uint8)
        return to_img1(out)



    # ---------- 패킹 ----------
    @staticmethod
    def pack_1bpp(img_bw_1bit: Image.Image) -> bytes:
        """PIL '1' -> 1bpp MSB-first (W를 8의 배수로 패드)"""
        arr = np.array(img_bw_1bit, dtype=np.uint8)  # 0 or 255
        bits = (arr == 0).astype(np.uint8)  # 검정=1, 흰색=0 로 패킹
        h, w = bits.shape
        pad = (-w) % 8
        if pad:
            bits = np.pad(bits, ((0, 0), (0, pad)), constant_values=0)
            w += pad
        bits = bits.reshape(h, w // 8, 8)
        weights = np.array([128,64,32,16,8,4,2,1], dtype=np.uint8)
        packed = (bits * weights).sum(axis=2)
        return packed.tobytes()

    @staticmethod
    def pack_BWRY_2bpp_from_P(im_p: Image.Image) -> bytes:
        """
        P(0=K,1=R,2=Y,3=W) -> 2bpp packed
          LUT: W(3)->00, Y(2)->01, R(1)->10, K(0)->11
        """
        idx = np.array(im_p, dtype=np.uint8)
        H, W = idx.shape
        lut = np.zeros(256, dtype=np.uint8)
        lut[3] = 0b00; lut[2] = 0b01; lut[1] = 0b10; lut[0] = 0b11
        two_bits = lut[idx]
        out = bytearray(); acc = 0; count = 0
        for y in range(H):
            for x in range(W):
                acc = (acc << 2) | int(two_bits[y, x])
                count += 2
                if count == 8:
                    out.append(acc & 0xFF); acc = 0; count = 0
        if count > 0:
            out.append((acc << (8 - count)) & 0xFF)
        return bytes(out)

    # ---------- EJOB ----------
    @staticmethod
    def make_ejob_payload(raw_bytes: bytes, fmt_code: int, width: int, height: int, compress: bool = True) -> bytes:
        payload = zlib.compress(raw_bytes) if compress else raw_bytes
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        header = bytearray(32)
        header[0:4] = b'EJOB'
        header[4] = 1
        struct.pack_into('<H', header, 5, width)
        struct.pack_into('<H', header, 7, height)
        header[9] = fmt_code
        header[10] = 1
        header[11] = 0
        struct.pack_into('<H', header, 12, 0)
        struct.pack_into('<I', header, 14, len(payload))
        struct.pack_into('<I', header, 18, crc)
        return bytes(header) + payload
    
    ...
    # ---------- 로딩 ----------
    def load_upload_image(self, upload_id: int, page: int = 1) -> Image.Image:
        from flask import current_app

        item = self.uploads.get(upload_id)
        if not item:
            raise FileNotFoundError("upload not found")

        path = item["path"]
        name = item.get("name", "")
        ext = (name or path).lower().split(".")[-1]

        current_app.logger.info(f"[LOAD] upload_id={upload_id}, path={path}, ext={ext}, page={page}")

        # PDF → 이미지
        if ext == "pdf":
            if not convert_from_path:
                raise RuntimeError("pdf2image not installed")
            imgs = convert_from_path(path, dpi=self.pdf_dpi,
                                    first_page=page, last_page=page)
            if not imgs:
                raise RuntimeError("PDF render fail")
            current_app.logger.info(f"[LOAD] PDF rendered: {len(imgs)} pages")
            return imgs[0].convert("RGB")

        # 이미지 파일 직접 열기
        elif ext in ("png", "jpg", "jpeg", "bmp", "gif"):
            current_app.logger.info(f"[LOAD] Opening image directly: {path}")
            return Image.open(path).convert("RGB")

        # 문서 파일 (docx, pptx, hwp, xlsx) → PDF → 이미지 변환
        elif ext in ("docx", "pptx", "hwp", "xlsx", "xls", "doc", "ppt"):
            current_app.logger.info(f"[LOAD] Converting document to image: {path}")
            return self._convert_doc_to_image(path, page)

        else:
            current_app.logger.warning(f"[LOAD] Unsupported file type: {ext}")
            raise ValueError(f"Unsupported file type: {ext}")


    def _convert_doc_to_image(self, path: str, page: int = 1) -> Image.Image:
        from flask import current_app
        import subprocess, tempfile, os

        # tmp_pdf = tempfile.mktemp(suffix=".pdf")
        base_dir = os.path.dirname(path)  # ex) ...\Temp\eink_uploads
        pdf_file = os.path.join(base_dir,os.path.splitext(os.path.basename(path))[0] + ".pdf")

        soffice_path = r"C:\Program Files\LibreOffice\program\soffice.exe"
        # current_app.logger.info(f"[DOC->PDF] Running soffice: {path} → { pdf_file }")

        subprocess.run([
            soffice_path, "--headless", "--convert-to", "pdf",
            "--outdir", base_dir, path
        ], check=True)

        current_app.logger.info(f"[DOC->PDF] Converted PDF: {pdf_file}")

        if not convert_from_path:
            raise RuntimeError("pdf2image not installed")

        imgs = convert_from_path(pdf_file, dpi=self.pdf_dpi,
                                first_page=page, last_page=page)
        if not imgs:
            raise RuntimeError("DOC render fail")

        current_app.logger.info(f"[DOC->PDF] Rendered {len(imgs)} page(s) from PDF")
        return imgs[0].convert("RGB")



    # ---------- 공개 API ----------
    def build_preview_image(self, upload_id, page, width, height, mode, scale, percent, rotate) -> Image.Image:
        im_src = self.load_upload_image(upload_id, page)
        if rotate in (90, 180, 270): im_src = im_src.rotate(rotate, expand=True)
        im_canvas = self._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
        # if mode == "BWRY":
        #     return self.quantize_to_BWRY(im_canvas).convert("RGB")
        # else:
        #     return self.quantize_to_BW(im_canvas).convert("L")

        if mode == "BWRY":
            # 보내기용: P (0=K,1=R,2=Y,3=W)
            return self.quantize_to_BWRY(im_canvas)        # mode 'P'
        elif mode == "BWRYBG":
            return self.quantize_to_BWRYBG(im_canvas)
        else:
            # 보내기용: 1bpp
            return self.quantize_to_BW(im_canvas)          # mode '1'

    def build_send_payload(self, upload_id, page, width, height, mode, scale, percent, rotate) -> bytes:
        im_src = self.load_upload_image(upload_id, page)
        if rotate in (90, 180, 270): 
            im_src = im_src.rotate(rotate, expand=True)
        im_canvas = self._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
        if mode == "BWRY":
            raw = self.pack_BWRY_2bpp_from_P(self.quantize_to_BWRY(im_canvas))
            return self.make_ejob_payload(raw, fmt_code=3, width=width, height=height, compress=True)
        else:
            raw = self.pack_1bpp(self.quantize_to_BW(im_canvas))
            return self.make_ejob_payload(raw, fmt_code=1, width=width, height=height, compress=True)


# =====================================================================
# 2) 흰 바탕 + BYR 강제 버전: FileTranslationWhiteBG
# =====================================================================
class FileTranslationWhiteBG:
    """
    - 배경(near-white)은 WHITE로 강제
    - 컬러 모드에서는 콘텐츠를 BLACK/RED/YELLOW 3색으로만 양자화 (WHITE는 배경)
    - BW 모드도 배경을 미리 화이트로 밀어낸 뒤 이분화
    - 나머지 API/패킹/EJOB 시그니처 동일
    """

    def __init__(self, uploads_store: dict, pdf_dpi: int = 200, white_thresh: int = 240, sat_thresh: float = 0.25):
        self.uploads = uploads_store
        self.pdf_dpi = pdf_dpi
        self.white_thresh = white_thresh
        self.sat_thresh = sat_thresh

    # ---------- 내부 유틸(배치 동일) ----------
    @staticmethod
    def _calc_fit_fill_size(src_w, src_h, dst_w, dst_h, mode="fit", percent=100):
        if mode not in ("fit", "fill", "percent"):
            mode = "fit"
        if mode == "percent":
            scale_fit = min(dst_w / src_w, dst_h / src_h)
            scale = scale_fit * (percent / 100.0)
        elif mode == "fit":
            scale = min(dst_w / src_w, dst_h / src_h)
        else:
            scale = max(dst_w / src_w, dst_h / src_h)
        new_w = max(1, int(round(src_w * scale)))
        new_h = max(1, int(round(src_h * scale)))
        return new_w, new_h

    @classmethod
    def _place_into_canvas(cls, img, W, H, mode="fit", percent=100):
        src_w, src_h = img.size
        new_w, new_h = cls._calc_fit_fill_size(src_w, src_h, W, H, mode, percent)
        if mode in ("fit", "percent"):
            simg = img.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGB", (W, H), (255, 255, 255))
            ox = (W - new_w) // 2
            oy = (H - new_h) // 2
            canvas.paste(simg, (ox, oy))
            return canvas
        else:
            simg = img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - W) // 2
            top  = (new_h - H) // 2
            return simg.crop((left, top, left + W, top + H))

    # ---------- 팔레트/양자화 (화이트 배경 + BYR) ----------
    def quantize_to_BWRY(self, im_rgb: Image.Image) -> Image.Image:
            """
            흰 배경 우선: V>=white_thresh 이거나 (V>=220 & S<=sat_thresh)면 WHITE.
            나머지는 BYR 최근접.
            """
            pal = Image.new("P", (1, 1))
            pal.putpalette([0,0,0, 255,0,0, 255,255,0, 255,255,255] + [0,0,0]*252)

            arr = np.asarray(im_rgb.convert("RGB"), dtype=np.uint8).astype(np.float32)
            r, g, b = arr[...,0], arr[...,1], arr[...,2]
            v = np.maximum(np.maximum(r,g), b)
            minc = np.minimum(np.minimum(r,g), b)
            s = np.where(v>0, (v-minc)/v, 0.0)

            # 화이트 마스크(밝고 채도 낮은 노란기 제거)
            white_mask = (v >= float(self.white_thresh)) | ((v >= 220.0) & (s <= float(self.sat_thresh)))

            targets = np.array([[0,0,0], [255,0,0], [255,255,0]], dtype=np.float32)  # B,R,Y
            diff = ((arr.reshape(-1,3)[:,None,:] - targets[None,:,:])**2).sum(axis=2)
            idx3 = diff.argmin(axis=1).astype(np.uint8).reshape(arr.shape[:2])  # 0..2 (B,R,Y)
            idx = np.where(white_mask, 3, idx3).astype(np.uint8)

            im_p = Image.fromarray(idx, mode="P")
            im_p.putpalette(pal.getpalette())
            return im_p

    def quantize_to_BW(self, im_rgb: Image.Image, method: str = "fs") -> Image.Image:
        """
        RGB -> 1bpp(mode '1') 흑백.
        - 배경(near-white)을 먼저 255로 승격해 화이트 고정
        - method: 'fs' | 'otsu' | 'thresh'
        """
        g = im_rgb.convert("L")
        # 배경 화이트 승격
        g = g.point(lambda p: 255 if p >= self.white_thresh else p)
        # 텍스트 샤프닝(가독성↑)
        g = g.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180, threshold=6))

        if method == "thresh":
            return g.point(lambda p: 255 if p >= 128 else 0, mode="1")
        elif method == "otsu":
            arr = np.array(g, dtype=np.uint8)
            hist = np.bincount(arr.ravel(), minlength=256).astype(np.float64)
            total = arr.size
            sum_total = np.dot(np.arange(256), hist)
            sumB = 0.0; wB = 0.0; varMax = -1.0; threshold = 128
            for i in range(256):
                wB += hist[i]
                if wB == 0: continue
                wF = total - wB
                if wF == 0: break
                sumB += i * hist[i]
                mB = sumB / wB
                mF = (sum_total - sumB) / wF
                varBetween = wB * wF * (mB - mF) ** 2
                if varBetween > varMax:
                    varMax = varBetween
                    threshold = i
            return g.point(lambda p: 255 if p >= threshold else 0, mode="1")
        else:
            return g.convert("1")

    # ---------- 패킹 (동일) ----------
    @staticmethod
    def pack_1bpp(img_bw_1bit: Image.Image) -> bytes:
        arr = np.array(img_bw_1bit, dtype=np.uint8)  # 0 or 255
        bits = (arr == 0).astype(np.uint8)  # 검정=1
        h, w = bits.shape
        pad = (-w) % 8
        if pad:
            bits = np.pad(bits, ((0,0),(0,pad)), constant_values=0)
            w += pad
        bits = bits.reshape(h, w//8, 8)
        weights = np.array([128,64,32,16,8,4,2,1], dtype=np.uint8)
        packed = (bits * weights).sum(axis=2)
        return packed.tobytes()

    @staticmethod
    def pack_BWRY_2bpp_from_P(im_p: Image.Image) -> bytes:
        idx = np.array(im_p, dtype=np.uint8)
        H, W = idx.shape
        lut = np.zeros(256, dtype=np.uint8)
        lut[3] = 0b00; lut[2] = 0b01; lut[1] = 0b10; lut[0] = 0b11
        two_bits = lut[idx]
        out = bytearray(); acc = 0; count = 0
        for y in range(H):
            for x in range(W):
                acc = (acc << 2) | int(two_bits[y, x])
                count += 2
                if count == 8:
                    out.append(acc & 0xFF); acc = 0; count = 0
        if count > 0:
            out.append((acc << (8 - count)) & 0xFF)
        return bytes(out)

    # ---------- EJOB (동일) ----------
    @staticmethod
    def make_ejob_payload(raw_bytes: bytes, fmt_code: int, width: int, height: int, compress: bool = True) -> bytes:
        payload = zlib.compress(raw_bytes) if compress else raw_bytes
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        header = bytearray(32)
        header[0:4] = b'EJOB'
        header[4] = 1
        struct.pack_into('<H', header, 5, width)
        struct.pack_into('<H', header, 7, height)
        header[9]  = fmt_code
        header[10] = 1
        header[11] = 0
        struct.pack_into('<H', header, 12, 0)
        struct.pack_into('<I', header, 14, len(payload))
        struct.pack_into('<I', header, 18, crc)
        return bytes(header) + payload

    # ---------- 로딩 ----------
    def load_upload_image(self, upload_id: int, page: int = 1) -> Image.Image:
        item = self.uploads.get(upload_id)
        if not item:
            raise FileNotFoundError("upload not found")

        path = item["path"]
        name = item.get("name", "")
        ext = (name or path).lower().split(".")[-1]

        # PDF → 이미지
        if ext == "pdf":
            if not convert_from_path:
                raise RuntimeError("pdf2image not installed")
            imgs = convert_from_path(path, dpi=self.pdf_dpi,
                                     first_page=page, last_page=page)
            if not imgs:
                raise RuntimeError("PDF render fail")
            return imgs[0].convert("RGB")

        # 이미지 파일 직접 열기
        elif ext in ("png", "jpg", "jpeg", "bmp", "gif"):
            return Image.open(path).convert("RGB")

        # 문서 파일 (docx, pptx, hwp 등) → PDF → 이미지 변환
        elif ext in ("docx", "pptx", "hwp"):
            return self._convert_doc_to_image(path, page)

        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _convert_doc_to_image(self, path: str, page: int = 1) -> Image.Image:
        """
        문서(docx, pptx, hwp 등)를 PDF → 이미지 변환 후 PIL.Image로 반환
        """
        import subprocess, tempfile

        tmp_pdf = tempfile.mktemp(suffix=".pdf")
        tmp_png = tempfile.mktemp(suffix=".png")

        # LibreOffice headless 변환 (docx → pdf)
        subprocess.run([
            "soffice", "--headless", "--convert-to", "pdf",
            "--outdir", os.path.dirname(tmp_pdf), path
        ], check=True)

        # PDF → 이미지 (첫 페이지만)
        if not convert_from_path:
            raise RuntimeError("pdf2image not installed")

        imgs = convert_from_path(tmp_pdf, dpi=self.pdf_dpi,
                                 first_page=page, last_page=page)
        if not imgs:
            raise RuntimeError("DOC/PPT render fail")

        return imgs[0].convert("RGB")


    # ---------- 공개 API (동일 시그니처) ----------
    def build_preview_image(self, upload_id, page, width, height, mode, scale, percent, rotate) -> Image.Image:
        im_src = self.load_upload_image(upload_id, page)
        if rotate in (90, 180, 270): im_src = im_src.rotate(rotate, expand=True)
        im_canvas = self._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
        # if mode == "BWRY":
        #     return self.quantize_to_BWRY(im_canvas).convert("RGB")
        # else:
        #     return self.quantize_to_BW(im_canvas).convert("L")
        
        if mode == "BWRY":
            return self.quantize_to_BWRY(im_canvas)  # 'P'
        else:
            return self.quantize_to_BW(im_canvas)    # '1'

    def build_send_payload(self, upload_id, page, width, height, mode, scale, percent, rotate) -> bytes:
        im_src = self.load_upload_image(upload_id, page)
        if rotate in (90, 180, 270): im_src = im_src.rotate(rotate, expand=True)
        im_canvas = self._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
        if mode == "BWRY":
            raw = self.pack_BWRY_2bpp_from_P(self.quantize_to_BWRY(im_canvas))
            return self.make_ejob_payload(raw, fmt_code=3, width=width, height=height, compress=True)
        else:
            raw = self.pack_1bpp(self.quantize_to_BW(im_canvas))
            return self.make_ejob_payload(raw, fmt_code=1, width=width, height=height, compress=True)
