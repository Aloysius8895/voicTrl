"""Small helpers shared by coordinator and device agent."""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
import zipfile
from pathlib import Path

CHUNK = 1 << 16


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


class PathRejected(ValueError):
    pass


def safe_join(root: Path, *parts: str) -> Path:
    """Join parts under root and refuse anything that resolves outside it
    (../, absolute paths, symlinks/junctions pointing elsewhere)."""
    root_r = Path(root).resolve()
    candidate = root_r.joinpath(*parts)
    resolved = candidate.resolve()
    if resolved != root_r and not resolved.is_relative_to(root_r):
        raise PathRejected(f"path escapes allowed root: {'/'.join(parts)}")
    return resolved


SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def check_segment(value: str) -> str:
    """IDs that become directory names must be plain ASCII segments."""
    if not SAFE_SEGMENT.match(value) or value in {".", ".."}:
        raise PathRejected(f"unsafe path segment: {value!r}")
    return value


def safe_extract_zip(zip_path: Path, dest: Path, max_total: int = 50 << 20) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = safe_join(dest, *Path(info.filename).parts)
            total += info.file_size
            if total > max_total:
                raise PathRejected("bundle too large")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                while chunk := src.read(CHUNK):
                    out.write(chunk)
            names.append(target.relative_to(dest.resolve()).as_posix())
    return names


def make_zip(src_dir: Path, out_path: Path, skip_dirs: tuple[str, ...] = (".claude", ".git", "node_modules")) -> list[str]:
    names: list[str] = []
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fn in filenames:
                p = Path(dirpath) / fn
                rel = p.relative_to(src_dir).as_posix()
                zf.write(p, rel)
                names.append(rel)
    return names


_CN_DIGITS = {"零": "0", "一": "1", "二": "2", "两": "2", "三": "3", "四": "4", "五": "5",
              "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}
_NAME_PREFIXES = ("电脑", "笔电", "笔记本", "computer", "laptop", "pc", "设备", "device")


def _base_norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    for cn, d in _CN_DIGITS.items():
        text = text.replace(cn, d)
    return re.sub(r"[\s_\-.·,，。:：'\"“”]+", "", text)


def normalize_device_name(text: str) -> str:
    """'电脑 A', 'Computer-A', 'pc-a', 'A' -> 'a'."""
    t = _base_norm(text)
    changed = True
    while changed:
        changed = False
        for p in _NAME_PREFIXES:
            if t.startswith(p) and len(t) > len(p):
                t = t[len(p):]
                changed = True
    return t


def normalize_file_query(text: str) -> str:
    """'文件 1', 'File1.md', 'file one' -> 'file1'."""
    t = unicodedata.normalize("NFKC", text).lower().strip()
    t = re.sub(r"\.(md|txt|markdown)$", "", t)
    t = t.replace("文件", "file").replace(" one", "1").replace(" two", "2")
    return _base_norm(t)
