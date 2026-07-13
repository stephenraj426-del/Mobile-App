from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


def project_root() -> Path:
    # backend/production_lipsync/file_utils.py -> backend
    # (Fixed: this used to be parents[2], which is correct only if this file
    # lived at backend/src/production_lipsync/file_utils.py. pyproject.toml's
    # `where=["."]` means the package that actually gets installed is the
    # top-level backend/production_lipsync/, one level shallower -- parents[2]
    # was resolving to the folder ABOVE backend/, breaking every relative
    # path in config/languages.json. If you ever move this package back under
    # src/, this needs to become parents[2] again.)
    return Path(__file__).resolve().parents[1]


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_empty_dir(path: str | Path) -> Path:
    path = Path(path)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def resolve_backend_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return project_root() / p


def copy_file(src: str | Path, dst: str | Path) -> Path:
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def assert_file_exists(path: str | Path, label: str) -> Path:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path
