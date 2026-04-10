from __future__ import annotations

import threading
import time
from typing import Any, Dict


class RepositorySchedulerCache:
    _lock = threading.RLock()
    _runs: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def set_run(cls, key: str, status: str, detail: Dict[str, Any] | None = None) -> None:
        with cls._lock:
            cls._runs[str(key)] = {
                "status": str(status),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "detail": detail or {},
            }

    @classmethod
    def get_all_runs(cls) -> Dict[str, Dict[str, Any]]:
        with cls._lock:
            return dict(cls._runs)
