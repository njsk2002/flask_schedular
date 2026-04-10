from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
class _RunContext:
    job_id: int | None
    device_id: str
    template_code: str
    job_name: str
    upcoming_start_date: date | None = None
    upcoming_end_date: date | None = None


class GroupwareService:
    def __init__(
        self,
        *,
        device_id: str = "E06",
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

    def _load_login_module(self):
        base = Path(__file__).resolve().parents[1] / "test" / "bb_groupware"
        fp = base / "login.py"
        if not fp.exists():
            raise FileNotFoundError(f"groupware sample not found: {fp}")

        base_str = str(base)
        if base_str not in sys.path:
            sys.path.insert(0, base_str)

        spec = importlib.util.spec_from_file_location("pybo_groupware_sample_login", str(fp))
        if spec is None or spec.loader is None:
            raise RuntimeError("failed to load groupware sample")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _credentials(self) -> Dict[str, str]:
        def _cfg(name: str, default: str = "") -> str:
            if has_app_context():
                return str(current_app.config.get(name, default) or "").strip()
            return ""

        ci = (os.getenv("GROUPWARE_CI") or _cfg("GROUPWARE_CI")).strip()
        ui = (os.getenv("GROUPWARE_UI") or _cfg("GROUPWARE_UI")).strip()
        pw = (os.getenv("GROUPWARE_PW") or _cfg("GROUPWARE_PW")).strip()
        xcn = (os.getenv("GROUPWARE_XCN") or _cfg("GROUPWARE_XCN")).strip()
        if not ci or not ui or not pw:
            raise RuntimeError("GROUPWARE_CI/GROUPWARE_UI/GROUPWARE_PW is required")
        return {"ci": ci, "ui": ui, "pw": pw, "xcn": xcn}

    def _weekday_kr(self, d: date) -> str:
        return ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]

    def _resolve_context(self, auto_job: Any | None) -> _RunContext:
        if auto_job is None:
            return _RunContext(
                job_id=None,
                device_id=self.default_device_id,
                template_code="groupware_e06_v1",
                job_name="groupware-default",
                upcoming_start_date=None,
                upcoming_end_date=None,
            )

        return _RunContext(
            job_id=int(auto_job.id),
            device_id=str(auto_job.target_device_id or self.default_device_id),
            template_code=str(auto_job.template_code or "groupware_e06_v1"),
            job_name=str(auto_job.job_name or f"groupware-{auto_job.id}"),
            upcoming_start_date=getattr(auto_job, "upcoming_start_date", None),
            upcoming_end_date=getattr(auto_job, "upcoming_end_date", None),
        )

    def _resolve_upcoming_range(self, ctx: _RunContext, base_date: date) -> tuple[date, date]:
        start = ctx.upcoming_start_date or (base_date + timedelta(days=1))
        end = ctx.upcoming_end_date or (base_date + timedelta(days=8))
        if end < start:
            start, end = end, start
        return start, end

    def _collect_months(self, dates: List[date]) -> List[tuple[int, int]]:
        month_keys = {(d.year, d.month) for d in dates}
        return sorted(month_keys)

    def _fetch_schedule(self, target_date: date, upcoming_start: date, upcoming_end: date) -> Dict[str, Any]:
        mod = self._load_login_module()
        cred = self._credentials()

        sess = mod.login_and_get_session(
            ci=cred["ci"],
            ui=cred["ui"],
            pw=cred["pw"],
            xcn=cred["xcn"],
        )

        cal = mod.BBCalendarFetcher(sess)

        dates: List[date] = [target_date]
        cur = upcoming_start
        while cur <= upcoming_end:
            dates.append(cur)
            cur += timedelta(days=1)

        month_event_map: Dict[tuple[int, int], Dict[str, Any]] = {}
        for year, month in self._collect_months(dates):
            cal.fetch_month(year, month)
            cal.parse_yL_from_html()
            cal.parse_events(year, month)
            month_event_map[(year, month)] = cal.get_month(year, month)

        def _events_for(d: date) -> List[Dict[str, str]]:
            m = month_event_map.get((d.year, d.month), {})
            rows = m.get(d.isoformat(), []) or []
            out = []
            for row in rows:
                title = " ".join(str(row.get("title") or "").split()).strip()
                if title:
                    out.append({"title": title})
            return out

        today_events = _events_for(target_date)

        upcoming_events = []
        cursor = upcoming_start
        while cursor <= upcoming_end:
            upcoming_events.append(
                {
                    "date": cursor.isoformat(),
                    "weekday": self._weekday_kr(cursor),
                    "events": _events_for(cursor),
                }
            )
            cursor += timedelta(days=1)

        return {
            "base_date": target_date.isoformat(),
            "upcoming_start": upcoming_start.isoformat(),
            "upcoming_end": upcoming_end.isoformat(),
            "today_events": today_events,
            "upcoming_events": upcoming_events,
        }

    def _build_payload(self, data: Dict[str, Any], run_at: datetime, ctx: _RunContext) -> Dict[str, Any]:
        return {
            "type": "groupware",
            "title": "그룹웨어 일정",
            "base_date": data.get("base_date"),
            "generated_at": run_at.strftime("%Y-%m-%d %H:%M:%S"),
            "today_events": data.get("today_events") or [],
            "upcoming_events": data.get("upcoming_events") or [],
            # render_service 하위 호환
            "week_events": data.get("upcoming_events") or [],
            "footer": f"장치 {ctx.device_id} | Revision {RevisionService.get_display_revision()}",
        }

    def _fallback_send_latest(self, ctx: _RunContext) -> Dict[str, Any] | None:
        hist = BulletinRenderHistoryRepository.latest_success(ctx.job_id, ctx.device_id)
        if not hist:
            return None

        result = BulletinRenderResultVO(
            device_id=ctx.device_id,
            job_type="groupware",
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
            "job": "groupware",
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
        auto_job: Any | None = None,
        schedule_item: Any | None = None,
    ) -> Dict[str, Any]:
        now = run_at or datetime.now()
        ctx = self._resolve_context(auto_job)
        upcoming_start, upcoming_end = self._resolve_upcoming_range(ctx, now.date())

        self._log(
            "info",
            "[groupware] run start",
            now=now.strftime("%Y-%m-%d %H:%M:%S"),
            force=force,
            job_id=ctx.job_id,
            device_id=ctx.device_id,
            template_code=ctx.template_code,
            job_name=ctx.job_name,
            schedule=getattr(schedule_item, "run_time", None),
            upcoming_start=upcoming_start.isoformat(),
            upcoming_end=upcoming_end.isoformat(),
        )

        try:
            schedule_data = self._fetch_schedule(now.date(), upcoming_start, upcoming_end)
            self._log(
                "info",
                "[groupware] fetch success",
                today_count=len(schedule_data.get("today_events") or []),
                upcoming_days=len(schedule_data.get("upcoming_events") or []),
            )
        except Exception as e:
            self._log("warning", "[groupware] fetch failed", err=str(e), device_id=ctx.device_id)
            fb = self._fallback_send_latest(ctx)
            if fb is not None:
                self._log("warning", "[groupware] fallback_send_latest used", result=fb)
                db.session.commit()
                return fb
            return {
                "ok": False,
                "job": "groupware",
                "device_id": ctx.device_id,
                "error": str(e),
                "schedule": getattr(schedule_item, "run_time", None),
            }

        try:
            payload = self._build_payload(schedule_data, now, ctx)
            content_hash = BulletinRenderHistoryRepository.make_content_hash(
                {
                    "base_date": payload.get("base_date"),
                    "today_events": payload.get("today_events"),
                    "upcoming_events": payload.get("upcoming_events"),
                }
            )

            self._log(
                "info",
                "[groupware] payload built",
                content_hash=content_hash,
                today_count=len(payload.get("today_events") or []),
                upcoming_days=len(payload.get("upcoming_events") or []),
            )

            if not force:
                if BulletinRenderHistoryRepository.has_same_hash(
                    job_id=ctx.job_id,
                    device_id=ctx.device_id,
                    content_hash=content_hash,
                    render_date=now.date(),
                ):
                    self._log(
                        "info",
                        "[groupware] no change detected",
                        job_id=ctx.job_id,
                        device_id=ctx.device_id,
                        content_hash=content_hash,
                        render_date=now.date().isoformat(),
                    )

                    if ctx.job_id is not None:
                        BulletinAutoJobRepository.touch_run_result(ctx.job_id, success=True)
                    db.session.commit()
                    return {
                        "ok": True,
                        "job": "groupware",
                        "device_id": ctx.device_id,
                        "changed": False,
                        "reason": "no_change",
                        "content_hash": content_hash,
                    }

            revision_name = RevisionService.get_display_revision()
            render_result = self.render_service.render_from_layout(
                payload=payload,
                device_id=ctx.device_id,
                job_type="groupware",
                template_code=ctx.template_code,
                content_hash=content_hash,
                revision_name=revision_name,
                source_summary={
                    "base_date": payload.get("base_date"),
                    "today_count": len(payload.get("today_events") or []),
                    "upcoming_days": len(payload.get("upcoming_events") or []),
                },
            )

            self._log(
                "info",
                "[groupware] render success",
                png_path=render_result.png_path,
                bin_path=render_result.bin_path,
                meta_path=render_result.meta_path,
                revision_name=revision_name,
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
                    "upcoming_start": schedule_data.get("upcoming_start"),
                    "upcoming_end": schedule_data.get("upcoming_end"),
                },
            )

            send_result = self.send_service.send(render_result)

            self._log(
                "info",
                "[groupware] send result",
                history_id=int(history.id),
                send_ok=bool(send_result.get("ok")),
                send_result=send_result,
            )

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
                "job": "groupware",
                "device_id": ctx.device_id,
                "changed": True,
                "history_id": int(history.id),
                "content_hash": content_hash,
                "today_count": len(payload.get("today_events") or []),
                "upcoming_days": len(payload.get("upcoming_events") or []),
                "render": render_result.to_dict(),
                "transfer": send_result,
            }
        except Exception as e:
            db.session.rollback()
            self._log("exception", "[groupware] run failed", err=str(e), device_id=ctx.device_id)
            return {
                "ok": False,
                "job": "groupware",
                "device_id": ctx.device_id,
                "error": str(e),
            }
