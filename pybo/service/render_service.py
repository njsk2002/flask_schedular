from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import qrcode
from PIL import Image, ImageDraw, ImageFont
from flask import current_app, has_app_context

from pybo.vo.bulletin_render_result_vo import BulletinRenderResultVO
from pybo.vo.eink_scheduler_vo import RenderBundle


class RenderService:
    def __init__(self, output_root: str | None = None, layout_root: str | None = None):
        self.output_root = Path(output_root or self._default_output_root())
        self.layout_root = Path(layout_root or self._default_layout_root())
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.layout_root.mkdir(parents=True, exist_ok=True)

    def _default_output_root(self) -> str:
        if has_app_context():
            cfg = current_app.config.get("EINK_AUTOBULLETIN_OUTPUT_ROOT")
            if cfg:
                return str(cfg)
            return str(Path(current_app.root_path) / "cache" / "auto_bulletin_outputs")
        return str(Path(__file__).resolve().parents[1] / "cache" / "auto_bulletin_outputs")

    def _default_layout_root(self) -> str:
        if has_app_context():
            cfg = current_app.config.get("EINK_LAYOUT_DIR")
            if cfg:
                return str(cfg)
            return str(Path(current_app.root_path) / "static" / "layouts" / "eink")
        return str(Path(__file__).resolve().parents[1] / "static" / "layouts" / "eink")

    def _font(self, size: int, bold: bool = False) -> ImageFont.ImageFont:
        candidates: List[str] = []
        if bold:
            candidates.extend([
                r"C:\\Windows\\Fonts\\malgunbd.ttf",
                r"C:\\Windows\\Fonts\\NanumGothicBold.ttf",
            ])
        candidates.extend([
            r"C:\\Windows\\Fonts\\malgun.ttf",
            r"C:\\Windows\\Fonts\\NanumGothic.ttf",
            r"C:\\Windows\\Fonts\\arial.ttf",
        ])
        for path in candidates:
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size=size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def _load_layout(self, template_code: str) -> Dict[str, Any]:
        code = str(template_code or "").strip()
        if not code:
            raise ValueError("template_code is required")

        if not code.endswith(".json"):
            code = f"{code}.json"

        fp = self.layout_root / code
        if not fp.exists():
            raise FileNotFoundError(f"layout not found: {fp}")

        if has_app_context():
            current_app.logger.warning(
                "[render] loading layout | template_code=%s path=%s",
                template_code,
                str(fp),
            )

        try:
            # 핵심: UTF-8 BOM 대응
            with open(fp, "r", encoding="utf-8-sig") as f:
                layout = json.load(f)

            if has_app_context():
                current_app.logger.warning(
                    "[render] layout loaded successfully | template_code=%s path=%s",
                    template_code,
                    str(fp),
                )

            return layout

        except Exception:
            if has_app_context():
                current_app.logger.exception(
                    "[render] layout load failed | template_code=%s path=%s",
                    template_code,
                    str(fp),
                )
            raise

    def _wrap_lines(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> List[str]:
        raw = " ".join(str(text or "").split())
        if not raw:
            return []
        words = raw.split(" ")
        lines: List[str] = []
        cur = ""
        for w in words:
            cand = w if not cur else f"{cur} {w}"
            if draw.textlength(cand, font=font) <= max_width:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
        if cur and len(lines) < max_lines:
            lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
        if lines and draw.textlength(lines[-1], font=font) > max_width:
            while lines[-1] and draw.textlength(lines[-1] + "...", font=font) > max_width:
                lines[-1] = lines[-1][:-1]
            lines[-1] = (lines[-1] + "...") if lines[-1] else "..."
        return lines

    def _draw_box(self, draw: ImageDraw.ImageDraw, section: Dict[str, Any], fill: str = "#FFFFFF", outline: str = "#D8DEE6") -> None:
        x, y = int(section["x"]), int(section["y"])
        w, h = int(section["w"]), int(section["h"])
        r = int(section.get("radius", 16))
        draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=fill, outline=outline, width=2)

    def _render_groupware(self, layout: Dict[str, Any], payload: Dict[str, Any]) -> Image.Image:
        canvas = layout.get("canvas") or {}
        width = int(canvas.get("width") or 1200)
        height = int(canvas.get("height") or 1600)
        bg = str(canvas.get("background") or "#F6F7F9")

        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)

        sections = layout.get("sections") or {}
        styles = layout.get("styles") or {}

        header = sections.get("header") or {"x": 32, "y": 24, "w": width - 64, "h": 120}
        self._draw_box(draw, header, fill="#111827", outline="#111827")

        title_font = self._font(int(styles.get("header_title_size") or 46), bold=True)
        sub_font = self._font(int(styles.get("header_sub_size") or 22), bold=False)
        draw.text((header["x"] + 24, header["y"] + 28), str(payload.get("title") or "오늘 일정"), fill="#FFFFFF", font=title_font)
        sub = f"기준일 {payload.get('base_date', '-')} | 생성 {payload.get('generated_at', '-')}"
        draw.text((header["x"] + 24, header["y"] + 80), sub, fill="#D1D5DB", font=sub_font)

        today_panel = sections.get("today_panel") or {"x": 32, "y": 164, "w": width - 64, "h": 630}
        week_panel = sections.get("week_panel") or {"x": 32, "y": 816, "w": width - 64, "h": 700}
        footer = sections.get("footer") or {"x": 32, "y": 1532, "w": width - 64, "h": 44}

        self._draw_box(draw, today_panel)
        self._draw_box(draw, week_panel)

        section_title_font = self._font(int(styles.get("section_title_size") or 34), bold=True)
        draw.text((today_panel["x"] + 18, today_panel["y"] + 16), "오늘 일정", fill="#111827", font=section_title_font)
        draw.text((week_panel["x"] + 18, week_panel["y"] + 16), "Upcoming Schedule", fill="#111827", font=section_title_font)

        item_font = self._font(int(styles.get("today_item_size") or 26), bold=False)
        y = today_panel["y"] + 74
        today_events = payload.get("today_events") or []
        if not today_events:
            draw.text((today_panel["x"] + 20, y), "오늘 일정 없음", fill="#6B7280", font=item_font)
        else:
            max_w = int(today_panel["w"] - 40)
            for idx, event in enumerate(today_events[:14], start=1):
                if y > today_panel["y"] + today_panel["h"] - 46:
                    break
                text = f"{idx}. {str(event.get('title') or '').strip()}"
                lines = self._wrap_lines(draw, text, item_font, max_w, 2)
                for line in lines:
                    draw.text((today_panel["x"] + 20, y), line, fill="#1F2937", font=item_font)
                    y += 34
                y += 6

        week_items = payload.get("upcoming_events") or payload.get("week_events") or []
        day_font = self._font(int(styles.get("week_day_size") or 22), bold=True)
        week_font = self._font(int(styles.get("week_item_size") or 19), bold=False)

        cols = max(1, int(styles.get("week_cols") or 2))
        gap = int(styles.get("week_gap") or 12)
        inner_w = week_panel["w"] - 28
        card_w = int((inner_w - gap * (cols - 1)) / cols)
        card_h = int(styles.get("week_card_height") or 146)

        for idx, day in enumerate(week_items[:8]):
            col = idx % cols
            row = idx // cols
            x0 = week_panel["x"] + 14 + col * (card_w + gap)
            y0 = week_panel["y"] + 62 + row * (card_h + gap)
            if y0 + card_h > week_panel["y"] + week_panel["h"] - 10:
                break
            draw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=12, fill="#F8FAFC", outline="#DDE3EC", width=2)
            label = f"{day.get('date', '')} ({day.get('weekday', '')})"
            draw.text((x0 + 10, y0 + 8), label, fill="#111827", font=day_font)

            evs = day.get("events") or []
            if not evs:
                draw.text((x0 + 10, y0 + 42), "일정 없음", fill="#6B7280", font=week_font)
                continue

            yy = y0 + 40
            for ev in evs[:4]:
                if yy > y0 + card_h - 24:
                    break
                lines = self._wrap_lines(draw, f"- {str(ev.get('title') or '').strip()}", week_font, card_w - 18, 2)
                for line in lines:
                    draw.text((x0 + 10, yy), line, fill="#374151", font=week_font)
                    yy += 23
                yy += 2

        footer_font = self._font(int(styles.get("footer_size") or 18), bold=False)
        footer_text = payload.get("footer") or "자동 게시 시스템"
        draw.text((footer["x"], footer["y"]), str(footer_text), fill="#6B7280", font=footer_font)
        return img

    def _make_qr(self, text: str, size: int) -> Image.Image:
        qr = qrcode.QRCode(version=1, box_size=4, border=1)
        qr.add_data(text or "https://example.com")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        return img.resize((size, size), Image.NEAREST)

    def _render_news(self, layout: Dict[str, Any], payload: Dict[str, Any]) -> Image.Image:
        canvas = layout.get("canvas") or {}
        width = int(canvas.get("width") or 1200)
        height = int(canvas.get("height") or 1600)
        bg = str(canvas.get("background") or "#F5F6F8")

        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)

        sections = layout.get("sections") or {}
        styles = layout.get("styles") or {}

        header = sections.get("header") or {"x": 32, "y": 24, "w": width - 64, "h": 116}
        footer = sections.get("footer") or {"x": 32, "y": 1536, "w": width - 64, "h": 40}
        article_blocks = sections.get("article_blocks") or []

        self._draw_box(draw, header, fill="#0F172A", outline="#0F172A")
        title_font = self._font(int(styles.get("header_title_size") or 40), bold=True)
        sub_font = self._font(int(styles.get("header_sub_size") or 20), bold=False)
        draw.text((header["x"] + 22, header["y"] + 24), str(payload.get("title") or "뉴스 브리핑"), fill="#FFFFFF", font=title_font)
        draw.text((header["x"] + 22, header["y"] + 74), f"실행 {payload.get('slot', '-')} | 생성 {payload.get('generated_at', '-')}", fill="#CBD5E1", font=sub_font)

        if not article_blocks:
            article_blocks = [{"x": 32, "y": 160 + i * 450, "w": width - 64, "h": 430} for i in range(3)]

        bundles = payload.get("keyword_bundles") or []
        row_font = self._font(int(styles.get("article_title_size") or 24), bold=True)
        sum_font = self._font(int(styles.get("article_summary_size") or 18), bold=False)
        key_font = self._font(int(styles.get("keyword_size") or 28), bold=True)

        for idx, block in enumerate(article_blocks[:3]):
            self._draw_box(draw, block, fill="#FFFFFF", outline="#D8DEE6")
            keyword_bundle = bundles[idx] if idx < len(bundles) else {"keyword": "키워드 없음", "articles": []}

            draw.text((block["x"] + 16, block["y"] + 12), str(keyword_bundle.get("keyword") or "-"), fill="#0F172A", font=key_font)

            articles = keyword_bundle.get("articles") or []
            start_y = block["y"] + 56
            row_h = int((block["h"] - 68) / 3)
            for aidx in range(3):
                y0 = start_y + aidx * row_h
                if aidx > 0:
                    draw.line([block["x"] + 12, y0 - 4, block["x"] + block["w"] - 12, y0 - 4], fill="#E5E7EB", width=1)

                article = articles[aidx] if aidx < len(articles) else {"title": "기사 없음", "summary": "", "url": ""}
                title = f"{aidx + 1}. {str(article.get('title') or '').strip()}"
                summary = str(article.get("summary") or "").strip()
                url = str(article.get("url") or "").strip()

                qr_size = min(96, row_h - 14)
                qr_x = block["x"] + block["w"] - qr_size - 14
                qr_y = y0 + 6
                text_w = qr_x - (block["x"] + 16) - 10

                yy = y0 + 4
                for line in self._wrap_lines(draw, title, row_font, text_w, 2):
                    draw.text((block["x"] + 16, yy), line, fill="#111827", font=row_font)
                    yy += 25

                for line in self._wrap_lines(draw, summary, sum_font, text_w, 3):
                    draw.text((block["x"] + 16, yy), line, fill="#4B5563", font=sum_font)
                    yy += 20

                qr = self._make_qr(url or "https://example.com", qr_size)
                img.paste(qr, (qr_x, qr_y))

        footer_text = payload.get("footer") or "자동 게시 시스템"
        footer_font = self._font(int(styles.get("footer_size") or 18), bold=False)
        draw.text((footer["x"], footer["y"]), str(footer_text), fill="#6B7280", font=footer_font)

        return img

    def _render_image(self, *, layout: Dict[str, Any], payload: Dict[str, Any], job_type: str) -> Image.Image:
        j = str(job_type or "").strip().lower()
        if j == "groupware":
            return self._render_groupware(layout, payload)
        if j == "news":
            return self._render_news(layout, payload)
        raise ValueError(f"unsupported job_type: {job_type}")

    def encode_binary(self, image: Image.Image, bpp: int = 4) -> bytes:
        if int(bpp) != 4:
            raise ValueError("currently only 4bpp is supported")
        gray = image.convert("L")
        w, h = gray.size
        pixels = gray.load()
        out = bytearray(((w + 1) // 2) * h)

        k = 0
        for y in range(h):
            x = 0
            while x < w:
                p0 = int(pixels[x, y] * 15 / 255) & 0x0F
                p1 = 15
                if x + 1 < w:
                    p1 = int(pixels[x + 1, y] * 15 / 255) & 0x0F
                out[k] = (p0 << 4) | p1
                k += 1
                x += 2
        return bytes(out)

    def _build_metadata(
        self,
        *,
        image: Image.Image,
        binary: bytes,
        device_id: str,
        job_type: str,
        template_code: str,
        content_hash: str,
        revision_name: str,
        source_summary: Dict[str, Any] | None,
        bpp: int = 4,
    ) -> Dict[str, Any]:
        w, h = image.size
        return {
            "width": int(w),
            "height": int(h),
            "bpp": int(bpp),
            "byte_size": int(len(binary)),
            "device_id": str(device_id),
            "job_type": str(job_type),
            "template_code": str(template_code),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content_hash": str(content_hash),
            "revision_name": str(revision_name),
            "source_summary": source_summary or {},
            "pixel_order": "left_to_right_top_to_bottom",
            "nibble_order": "high_nibble_first",
            "palette": "grayscale_16",
            "packing": "4bpp",
        }

    def render_from_layout(
        self,
        *,
        payload: Dict[str, Any],
        device_id: str,
        job_type: str,
        template_code: str,
        content_hash: str,
        revision_name: str,
        source_summary: Dict[str, Any] | None = None,
    ) -> BulletinRenderResultVO:
        layout = self._load_layout(template_code)
        image = self._render_image(layout=layout, payload=payload, job_type=job_type)

        canvas = layout.get("canvas") or {}
        bpp = int(canvas.get("bpp") or 4)
        binary = self.encode_binary(image, bpp=bpp)

        now = datetime.now()
        run_dir = (
            self.output_root
            / str(job_type)
            / str(device_id)
            / now.strftime("%Y%m%d")
            / f"{now.strftime('%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )
        run_dir.mkdir(parents=True, exist_ok=True)

        png_path = run_dir / "render.png"
        bin_path = run_dir / "render_4bpp.bin"
        meta_path = run_dir / "metadata.json"
        render_json_path = run_dir / "render_data.json"

        image.save(png_path, "PNG")
        with open(bin_path, "wb") as f:
            f.write(binary)

        metadata = self._build_metadata(
            image=image,
            binary=binary,
            device_id=device_id,
            job_type=job_type,
            template_code=template_code,
            content_hash=content_hash,
            revision_name=revision_name,
            source_summary=source_summary,
            bpp=bpp,
        )

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        with open(render_json_path, "w", encoding="utf-8") as f:
            json.dump(payload or {}, f, ensure_ascii=False, indent=2, default=str)

        return BulletinRenderResultVO(
            device_id=str(device_id),
            job_type=str(job_type),
            output_dir=str(run_dir),
            png_path=str(png_path),
            bin_path=str(bin_path),
            meta_path=str(meta_path),
            render_json_path=str(render_json_path),
            revision_name=str(revision_name),
            content_hash=str(content_hash),
            metadata=metadata,
        )

    def render_and_package(
        self,
        *,
        render_json: Dict[str, Any],
        device_id: str,
        job_name: str,
        data_hash: str,
    ) -> RenderBundle:
        job_type = str(render_json.get("type") or job_name or "groupware").strip().lower()
        template_code = "groupware_e06_v1"
        if job_type == "news":
            template_code = "news_e07_v1"

        from pybo.service.revision_service import RevisionService

        revision_label = RevisionService.get_display_revision()
        result = self.render_from_layout(
            payload=render_json,
            device_id=device_id,
            job_type=job_type,
            template_code=template_code,
            content_hash=data_hash,
            revision_name=revision_label,
            source_summary={"legacy_job_name": job_name},
        )
        return RenderBundle(
            device_id=device_id,
            job_name=job_name,
            output_dir=result.output_dir,
            render_json_path=result.render_json_path or "",
            png_path=result.png_path,
            bin_path=result.bin_path,
            meta_path=result.meta_path,
            metadata=result.metadata or {},
        )
