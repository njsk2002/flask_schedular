from __future__ import annotations

import html
import importlib.util
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from flask import current_app, has_app_context

from pybo import db
from pybo.repository.bulletin_auto_job_repository import BulletinAutoJobRepository
from pybo.repository.bulletin_render_history_repository import BulletinRenderHistoryRepository
from pybo.service.eink_send_service import EInkSendService
from pybo.service.render_service import RenderService
from pybo.service.revision_service import RevisionService
from pybo.vo.bulletin_render_result_vo import BulletinRenderResultVO


@dataclass
class _NewsRunContext:
    job_id: int | None
    device_id: str
    template_code: str
    job_name: str
    article_count: int
    summary_length: int


class NewsService:
    DEFAULT_0700 = [
        "나스닥 다우 엔비디아",
        "이란 미국",
        "NXT 삼성전자 하이닉스",
    ]
    DEFAULT_COMMON = [
        "코스피 코스닥 삼성전자 하이닉스",
        "이란 미국",
        "환율 금",
    ]

    def __init__(
        self,
        *,
        device_id: str = "E07",
        render_service: RenderService | None = None,
        send_service: EInkSendService | None = None,
    ):
        self.default_device_id = str(device_id)
        self.render_service = render_service or RenderService()
        self.send_service = send_service or EInkSendService()

    def _log(self, level: str, msg: str, **kw: Any) -> None:
        line = msg if not kw else f"{msg} | {kw}"
        if has_app_context():
            logger = current_app.logger
        else:
            import logging

            logger = logging.getLogger(__name__)
        getattr(logger, level, logger.info)(line)

    def _resolve_slot(self, run_at: datetime, slot_label: str | None = None, schedule_item: Any | None = None) -> str:
        if slot_label:
            s = str(slot_label).strip()
            if re.match(r"^\d{2}:\d{2}$", s):
                return s
        if schedule_item is not None:
            rt = str(getattr(schedule_item, "run_time", "")).strip()
            if re.match(r"^\d{2}:\d{2}$", rt):
                return rt
        return run_at.strftime("%H:%M")

    def _credentials(self) -> tuple[str, str]:
        def _cfg(name: str, default: str = "") -> str:
            if has_app_context():
                return str(current_app.config.get(name, default) or "").strip()
            return ""

        cid = (os.getenv("NAVER_CLIENT_ID") or _cfg("NAVER_CLIENT_ID")).strip()
        secret = (os.getenv("NAVER_CLIENT_SECRET") or _cfg("NAVER_CLIENT_SECRET")).strip()
        if cid and secret:
            return cid, secret

        try:
            from pybo.service.authorization_key import Authorization

            cid2, sec2 = Authorization.naver_client()
            if cid2 and sec2:
                return str(cid2).strip(), str(sec2).strip()
        except Exception:
            pass

        raise RuntimeError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET is required")

    def _resolve_context(self, auto_job: Any | None) -> _NewsRunContext:
        if auto_job is None:
            return _NewsRunContext(
                job_id=None,
                device_id=self.default_device_id,
                template_code="news_e07_v1",
                job_name="news-default",
                article_count=3,
                summary_length=200,
            )
        return _NewsRunContext(
            job_id=int(auto_job.id),
            device_id=str(auto_job.target_device_id or self.default_device_id),
            template_code=str(auto_job.template_code or "news_e07_v1"),
            job_name=str(auto_job.job_name or f"news-{auto_job.id}"),
            article_count=max(1, int(auto_job.article_count or 3)),
            summary_length=min(500, max(50, int(auto_job.summary_length or 200))),
        )

    def _clean_html(self, text: str) -> str:
        t = re.sub(r"<[^>]+>", " ", str(text or ""))
        t = html.unescape(t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _summary(self, text: str, max_len: int) -> str:
        s = self._clean_html(text)
        if len(s) <= max_len:
            return s
        return s[:max_len].rstrip() + "..."

    def _request_news(self, keyword: str, display: int) -> Dict[str, Any]:
        cid, csec = self._credentials()

        try:
            sample_path = Path(__file__).resolve().parents[1] / "test" / "navertest.py"
            if sample_path.exists():
                spec = importlib.util.spec_from_file_location("pybo_test_navertest_runtime", str(sample_path))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "client_id"):
                        mod.client_id = cid
                    if hasattr(mod, "client_secret"):
                        mod.client_secret = csec
                    if hasattr(mod, "getNaverSearch"):
                        data = mod.getNaverSearch("news", keyword, start=1, display=display)
                        if isinstance(data, dict):
                            return data
        except Exception as e:
            self._log("warning", "[news] sample import fallback", err=str(e))

        query = urllib.parse.quote(keyword)
        url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display={display}&sort=date"
        req = urllib.request.Request(url)
        req.add_header("X-Naver-Client-Id", cid)
        req.add_header("X-Naver-Client-Secret", csec)
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
        obj = json.loads(body)
        return obj if isinstance(obj, dict) else {}

    def _resolve_keywords(self, *, ctx: _NewsRunContext, slot: str, schedule_item: Any | None) -> List[str]:
        schedule_kw = str(getattr(schedule_item, "keyword_text", "") or "").strip() if schedule_item is not None else ""
        if schedule_kw:
            return [schedule_kw]

        if ctx.job_id is not None:
            sid = int(schedule_item.id) if (schedule_item is not None and getattr(schedule_item, "id", None)) else None
            rows = BulletinAutoJobRepository.list_keywords(ctx.job_id, sid)
            kws = [str(r.keyword_text).strip() for r in rows if str(r.keyword_text or "").strip()]
            if kws:
                return kws

        if slot == "07:00":
            return list(self.DEFAULT_0700)
        return list(self.DEFAULT_COMMON)

    def _collect_articles(self, *, keyword: str, article_count: int, summary_length: int) -> Dict[str, Any]:
        data = self._request_news(keyword, display=max(article_count * 4, 12))
        items = data.get("items") or []

        rows = []
        seen = set()
        for it in items:
            url = str(it.get("originallink") or it.get("link") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)

            title = self._clean_html(it.get("title", ""))
            desc = self._clean_html(it.get("description", ""))
            rows.append(
                {
                    "title": title,
                    "summary": self._summary(desc if desc else title, summary_length),
                    "url": url,
                }
            )
            if len(rows) >= article_count:
                break

        return {"keyword": keyword, "articles": rows}

    def _build_payload(self, *, slot: str, bundles: List[Dict[str, Any]], now: datetime, ctx: _NewsRunContext) -> Dict[str, Any]:
        return {
            "type": "news",
            "title": "뉴스 브리핑",
            "slot": slot,
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "keyword_bundles": bundles,
            "footer": f"장치 {ctx.device_id} | Revision {RevisionService.get_display_revision()}",
        }

    def _fallback_send_latest(self, ctx: _NewsRunContext) -> Dict[str, Any] | None:
        hist = BulletinRenderHistoryRepository.latest_success(ctx.job_id, ctx.device_id)
        if not hist:
            return None

        result = BulletinRenderResultVO(
            device_id=ctx.device_id,
            job_type="news",
            output_dir=str(Path(hist.meta_path).parent),
            png_path=hist.png_path,
            bin_path=hist.bin_path,
            meta_path=hist.meta_path,
            revision_name=hist.revision_name,
            content_hash=hist.content_hash,
        )
        send_res = self.send_service.send(result)
        return {
            "ok": bool(send_res.get("ok")),
            "job": "news",
            "device_id": ctx.device_id,
            "fallback": True,
            "history_id": int(hist.id),
            "transfer": send_res,
        }

    def run(
        self,
        *,
        force: bool = False,
        run_at: datetime | None = None,
        slot_label: str | None = None,
        auto_job: Any | None = None,
        schedule_item: Any | None = None,
    ) -> Dict[str, Any]:
        now = run_at or datetime.now()
        ctx = self._resolve_context(auto_job)
        slot = self._resolve_slot(now, slot_label=slot_label, schedule_item=schedule_item)

        keywords = self._resolve_keywords(ctx=ctx, slot=slot, schedule_item=schedule_item)

        try:
            bundles = [
                self._collect_articles(
                    keyword=kw,
                    article_count=ctx.article_count,
                    summary_length=ctx.summary_length,
                )
                for kw in keywords
            ]
        except Exception as e:
            self._log("warning", "[news] fetch failed", err=str(e), device_id=ctx.device_id)
            fb = self._fallback_send_latest(ctx)
            if fb is not None:
                db.session.commit()
                return fb
            return {
                "ok": False,
                "job": "news",
                "device_id": ctx.device_id,
                "slot": slot,
                "error": str(e),
            }

        try:
            payload = self._build_payload(slot=slot, bundles=bundles, now=now, ctx=ctx)
            content_hash = BulletinRenderHistoryRepository.make_content_hash(
                {"slot": slot, "bundles": bundles, "article_count": ctx.article_count, "summary_length": ctx.summary_length}
            )

            if not force:
                if BulletinRenderHistoryRepository.has_same_hash(
                    job_id=ctx.job_id,
                    device_id=ctx.device_id,
                    content_hash=content_hash,
                    render_date=now.date(),
                ):
                    if ctx.job_id is not None:
                        BulletinAutoJobRepository.touch_run_result(ctx.job_id, success=True)
                    db.session.commit()
                    return {
                        "ok": True,
                        "job": "news",
                        "device_id": ctx.device_id,
                        "slot": slot,
                        "changed": False,
                        "reason": "no_change",
                        "content_hash": content_hash,
                    }

            revision_name = RevisionService.get_display_revision()
            render_result = self.render_service.render_from_layout(
                payload=payload,
                device_id=ctx.device_id,
                job_type="news",
                template_code=ctx.template_code,
                content_hash=content_hash,
                revision_name=revision_name,
                source_summary={
                    "slot": slot,
                    "keywords": keywords,
                    "article_count": sum(len(b.get("articles") or []) for b in bundles),
                },
            )

            history = BulletinRenderHistoryRepository.create_history(
                job_id=ctx.job_id,
                device_id=ctx.device_id,
                content_hash=content_hash,
                render_date=now.date(),
                png_path=render_result.png_path,
                bin_path=render_result.bin_path,
                meta_path=render_result.meta_path,
                revision_name=revision_name,
                source_summary={
                    "job_name": ctx.job_name,
                    "slot": slot,
                    "keyword_count": len(keywords),
                    "article_count": sum(len(b.get("articles") or []) for b in bundles),
                },
            )

            send_result = self.send_service.send(render_result)
            BulletinRenderHistoryRepository.update_send_result(
                int(history.id),
                ok=bool(send_result.get("ok")),
                message=(send_result.get("reason") or send_result.get("message") or ""),
            )

            if ctx.job_id is not None:
                BulletinAutoJobRepository.touch_run_result(ctx.job_id, success=bool(send_result.get("ok")))

            db.session.commit()
            return {
                "ok": bool(send_result.get("ok")),
                "job": "news",
                "device_id": ctx.device_id,
                "slot": slot,
                "changed": True,
                "history_id": int(history.id),
                "content_hash": content_hash,
                "keyword_count": len(keywords),
                "article_count": sum(len(b.get("articles") or []) for b in bundles),
                "render": render_result.to_dict(),
                "transfer": send_result,
            }
        except Exception as e:
            db.session.rollback()
            self._log("exception", "[news] run failed", err=str(e), device_id=ctx.device_id, slot=slot)
            return {
                "ok": False,
                "job": "news",
                "device_id": ctx.device_id,
                "slot": slot,
                "error": str(e),
            }
