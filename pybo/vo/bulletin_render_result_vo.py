from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict


@dataclass
class BulletinRenderResultVO:
    device_id: str
    job_type: str
    output_dir: str
    png_path: str
    bin_path: str
    meta_path: str
    render_json_path: str | None = None
    revision_name: str | None = None
    content_hash: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
