# pybo/service/eink_render_service.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, Tuple

from flask import current_app
from PIL import Image

from .file_management import (
    get_translation_service,
    apply_editor_layout_to_image,
    save_meta_bundle,
    inject_approval_runtime_into_snapshot,
    inject_user_photo1_into_snapshot,
    _normalize_layout_snapshot,
)

try:
    from ..repository.repository_eink import RepositoryEINK
except Exception:
    RepositoryEINK = None


class EinkRenderService:
    """
    - DocumentInfo.layout_snapshot_json 기반으로
      approval_process/{doc_id}/ 번들을 '현 상태/현 스냅샷' 기준으로 재렌더하여 덮어쓴다.
    - 승인/반려 시 결재칸 표시(서명/완료/반려)가 preview_merged.png와 onelayer.*에 반영되게 한다.
    - stored_path는 "폴더 경로"여도 동작해야 한다.
    """
    # 작성한 파일의 절대 경로를 얻음. /approval_process/74/   stored_path는 "폴더 경로
    @staticmethod
    def _resolve_doc_dir_from_stored_path(stored_path: str) -> str:
        """
        stored_path가
        - 폴더(…/approval_process/74/)일 수도 있고
        - 파일(…/approval_process/74/onelayer.bmp)일 수도 있으므로
        doc_dir(폴더)를 안전하게 얻는다.
        """
        p = (stored_path or "").strip().strip('"').strip("'")
        if not p:
            return ""

        p = os.path.normpath(p)

        # 1) 존재하는 디렉토리면 그대로
        if os.path.isdir(p):
            return p

        # 2) 존재하는 파일이면 dirname
        if os.path.isfile(p):
            return os.path.dirname(p)

        # 3) 존재하지 않더라도, 확장자 있으면 파일로 보고 dirname
        _, ext = os.path.splitext(p)
        if ext:
            return os.path.dirname(p)

        # 4) 그 외는 "폴더"로 간주
        return p

    @staticmethod
    def _bundle_paths_from_doc_dir(doc_dir: str) -> Tuple[str, str, str, str, str]:
        """
        approval_process/{doc_id}/ 구조 고정:
          - preview_base.png
          - preview_merged.png
          - onelayer.bmp
          - onelayer.bin
          - onelayer_meta.json
        """
        preview_base = os.path.join(doc_dir, "preview_base.png")
        preview_merged = os.path.join(doc_dir, "preview_merged.png")
        onelayer_bmp = os.path.join(doc_dir, "onelayer.bmp")
        onelayer_bin = os.path.join(doc_dir, "onelayer.bin")
        onelayer_meta = os.path.join(doc_dir, "onelayer_meta.json")
        return preview_base, preview_merged, onelayer_bmp, onelayer_bin, onelayer_meta

    @staticmethod
    def _load_base_canvas_from_doc_dir(doc_dir: str) -> Image.Image:
        """
        base 캔버스 우선순위:
          1) preview_base.png (최우선)
          2) preview_merged.png (있으면)
          3) onelayer.bmp (있으면)
        """
        preview_base, preview_merged, onelayer_bmp, _, _ = EinkRenderService._bundle_paths_from_doc_dir(doc_dir)

        if os.path.isfile(preview_base):
            return Image.open(preview_base).convert("RGB")

        if os.path.isfile(preview_merged):
            return Image.open(preview_merged).convert("RGB")

        if os.path.isfile(onelayer_bmp):
            return Image.open(onelayer_bmp).convert("RGB")

        raise FileNotFoundError(f"base canvas not found in doc_dir={doc_dir}")

    # ----------------------------
    # 핵심: layout_snapshot 안전 로더
    # ----------------------------
    @staticmethod
    def _loads_json_maybe(v: Any) -> dict:
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return {}
            try:
                obj = json.loads(s)
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _load_layout_snapshot(doc: Any, doc_dir: str) -> dict:
        """
        우선순위:
          1) doc.layout_snapshot_json (dict 또는 JSON string)
          2) doc_dir/layout_snapshot.json 파일
        """
        snap = EinkRenderService._loads_json_maybe(getattr(doc, "layout_snapshot_json", None))

        # 2) 파일 폴백
        if not snap:
            fp = os.path.join(doc_dir, "layout_snapshot.json")
            if os.path.isfile(fp):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        obj = json.load(f)
                    if isinstance(obj, dict):
                        snap = obj
                except Exception:
                    pass

        return snap or {}

    @staticmethod
    def _has_any_layers(layout_snapshot: dict) -> bool:
        """
        스냅샷이 비어있을 때 preview_merged/onelayer를 덮어써버리면 '모든 레이어가 사라진' 현상이 발생하므로,
        최소한 레이어 존재 여부를 확인하고 없으면 중단한다.
        """
        if not layout_snapshot:
            return False

        # 구 구조
        if isinstance(layout_snapshot.get("editor_layers"), list) and len(layout_snapshot["editor_layers"]) > 0:
            return True

        # 신 구조 (layers_json / layers)
        layers_raw = layout_snapshot.get("layers_json") or layout_snapshot.get("layers")
        if isinstance(layers_raw, dict) and isinstance(layers_raw.get("layers"), list) and len(layers_raw["layers"]) > 0:
            return True
        if isinstance(layers_raw, list) and len(layers_raw) > 0:
            return True

        return False

    @staticmethod
    def rerender_bundle_for_doc(doc_id: int) -> Dict[str, Any]:
        if RepositoryEINK is None:
            raise RuntimeError("RepositoryEINK not available")

        doc = RepositoryEINK.get_upload(int(doc_id))
        if not doc:
            raise FileNotFoundError(f"DocumentInfo not found: {doc_id}")

        doc_dir = EinkRenderService._resolve_doc_dir_from_stored_path(getattr(doc, "stored_path", "") or "")
        if not doc_dir:
            raise FileNotFoundError("doc.stored_path is empty or invalid")
        if not os.path.isdir(doc_dir):
            raise FileNotFoundError(f"doc_dir not found: {doc_dir}")

        preview_base, preview_merged, onelayer_bmp, onelayer_bin, onelayer_meta = (
            EinkRenderService._bundle_paths_from_doc_dir(doc_dir)
        )

        # 1) snapshot 로드(문자열 JSON 파싱 + 파일 폴백)
        layout_snapshot = EinkRenderService._load_layout_snapshot(doc, doc_dir)
        # dict 보장
        layout_snapshot = _normalize_layout_snapshot(layout_snapshot)

        w = int(getattr(doc, "width", 1200) or 1200)
        h = int(getattr(doc, "height", 1600) or 1600)
        mode = (getattr(doc, "mode", None) or "BWRYBG").upper()

        current_app.logger.debug(
            "[rerender] doc_id=%s doc_dir=%r w=%s h=%s mode=%s status=%s stored_path=%r",
            int(doc.id), doc_dir, w, h, mode, getattr(doc, "status", None), getattr(doc, "stored_path", None)
        )
        try:
            current_app.logger.debug("[rerender] layout_snapshot loaded. keys=%s", list(layout_snapshot.keys())[:20])
        except Exception:
            pass

        # 2) 레이어 존재 검사(없으면 overwrite 중단)
        if not EinkRenderService._has_any_layers(layout_snapshot):
            current_app.logger.debug("[rerender] NO LAYERS in snapshot -> abort overwrite to protect bundle")
            return {
                "ok": False,
                "doc_id": int(doc.id),
                "doc_dir": doc_dir,
                "reason": "layout_snapshot has no layers (editor_layers/layers_json). refused to overwrite preview_merged/onelayer.",
            }

        # 3) base canvas 로드
        base_im = EinkRenderService._load_base_canvas_from_doc_dir(doc_dir)

        if base_im.size != (w, h):
            base_im = base_im.resize((w, h))

        current_app.logger.debug("[rerender] base_canvas size=%s mode=%s", base_im.size, base_im.mode)

        # 4) ✅ 결재할 때마다 DB 상태를 snapshot에 주입
        runtime_map = RepositoryEINK.get_approval_runtime_map(int(doc_id))
        changed_status = inject_approval_runtime_into_snapshot(layout_snapshot, runtime_map)

        current_app.logger.debug(
            "[rerender] approval runtime injected doc_id=%s changed=%s keys=%s",
            doc_id, changed_status, sorted(list(runtime_map.keys()))
        )

        # 5) ✅ 결재할 때마다 User.photo_1 최신값을 snapshot에 주입(서명 변경 대응)
        changed_photo = inject_user_photo1_into_snapshot(layout_snapshot)
        current_app.logger.debug("[rerender] photo_1 injected changed=%s", changed_photo)

        # 6) merged 렌더링
        merged_rgb = apply_editor_layout_to_image(base_im, w, h, layout_snapshot)

        # 6-1) preview_merged.png 저장
        try:
            merged_rgb.save(preview_merged, "PNG")
            current_app.logger.debug("[rerender] preview_merged updated: %r", preview_merged)
        except Exception:
            current_app.logger.debug("[rerender] preview_merged save failed", exc_info=True)

        # 7) quantize for device palette
        svc = get_translation_service()
        if mode == "BWRY":
            final_im = svc.quantize_to_BWRY(merged_rgb)
            fmt = "BWRY"
        elif mode in ("BWRYBG", "SPECTRA6", "COLOR6"):
            final_im = svc.quantize_to_BWRYBG(merged_rgb)
            fmt = "BWRYBG"
        else:
            final_im = svc.quantize_to_BW(merged_rgb)
            fmt = "BW"

        # 8) meta 유지용(assignees 등)
        assignees = {}
        try:
            md = doc.metadata_json if isinstance(doc.metadata_json, dict) else {}
            assignees = md.get("assignees") or {}
        except Exception:
            assignees = {}

        current_app.logger.debug(
            "[rerender] write onelayer.* bmp=%r bin=%r meta=%r",
            onelayer_bmp, onelayer_bin, onelayer_meta
        )

        # 9) onelayer.bmp/bin/onelayer_meta.json 덮어쓰기
        payload, meta = save_meta_bundle(
            final_im,
            fmt,
            (w, h),
            onelayer_bmp,
            onelayer_bin,
            onelayer_meta,
            getattr(doc, "device_id", "") or "",
            getattr(doc, "target_dir", "in_review") or "in_review",
            bool(getattr(doc, "need_approval", True)),
            bool((getattr(doc, "status", "") or "").lower() == "approved"),
            getattr(doc, "route_id", None),
            assignees,
            doc_id=int(doc.id),
            upload_row_id=int(doc.id),
        )

        return {
            "ok": True,
            "doc_id": int(doc.id),
            "doc_dir": doc_dir,
            "preview_base": preview_base if os.path.isfile(preview_base) else None,
            "preview_merged": preview_merged if os.path.isfile(preview_merged) else None,
            "onelayer_bmp": onelayer_bmp,
            "onelayer_bin": onelayer_bin,
            "onelayer_meta": onelayer_meta,
            "mode": fmt,
            "target_dir": getattr(doc, "target_dir", None),
            "status": getattr(doc, "status", None),
            "injected": {
                "status_changed": int(changed_status),
                "photo_changed": int(changed_photo),
            },
        }
