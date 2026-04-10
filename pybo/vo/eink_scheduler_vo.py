from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict


@dataclass
class RenderBundle:
    device_id: str
    job_name: str
    output_dir: str
    render_json_path: str
    png_path: str
    bin_path: str
    meta_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
