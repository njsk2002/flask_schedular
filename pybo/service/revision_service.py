from __future__ import annotations

from pathlib import Path

from flask import current_app, has_app_context


class RevisionService:
    @staticmethod
    def _revision_dir() -> Path:
        if has_app_context():
            cfg = current_app.config.get("REVISION_DIR")
            if cfg:
                return Path(str(cfg))
            return Path(current_app.root_path).parent / "revision"
        return Path(__file__).resolve().parents[2] / "revision"

    @classmethod
    def get_latest_change_file(cls) -> str | None:
        rev_dir = cls._revision_dir()
        if not rev_dir.exists():
            return None
        files = sorted(rev_dir.glob("change_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        return files[0].name

    @staticmethod
    def get_current_version() -> str:
        if has_app_context():
            return str(current_app.config.get("CURRENT_REVISION", "V01.00"))
        return "V01.00"

    @classmethod
    def get_display_revision(cls) -> str:
        version = cls.get_current_version()
        latest = cls.get_latest_change_file()
        if latest:
            return f"{version} / {latest}"
        return version
