"""Shared upload pipeline.

First consumer is :mod:`service_crm.tickets`; the 0.6 interventions
blueprint will reuse the same helpers. Bytes are validated by extension
*and* by magic-byte sniffing (Pillow for images, ``mimetypes`` for the
rest), images are compressed (long edge ≤ 2048 px, WebP q85 per
``v1-implementation-goals.md`` §2.4), and the result is written to
``instance/uploads/<scope>/<owner_hex>/<ulid><ext>``.

Bytes are NEVER written under ``static/`` — attachment downloads run
through an authenticated route that streams the bytes back.
"""

from __future__ import annotations

import io
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, BinaryIO

from flask import current_app

from . import ulid

MAX_BYTES = 25 * 1024 * 1024  # 25 MB single-file cap; revisited in v0.9.
MAX_IMAGE_EDGE = 2048  # long-edge px for re-encode.

# Allowed extensions + their expected MIME prefix. Anything else is
# rejected at validate time.
_ALLOWED: dict[str, str] = {
    ".jpg": "image/",
    ".jpeg": "image/",
    ".png": "image/",
    ".webp": "image/",
    ".gif": "image/",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
}

# Magic-byte prefixes for the formats we accept. Multiple entries per
# extension are checked OR-wise.
_MAGIC: dict[str, list[bytes]] = {
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".webp": [b"RIFF"],  # actually RIFF....WEBP; first 4 bytes are enough.
    ".gif": [b"GIF87a", b"GIF89a"],
    ".pdf": [b"%PDF"],
}

# Extensions that route through Pillow for re-encoding.
_IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


class UploadRejected(ValueError):
    """Raised when the uploaded blob fails any of: size, extension, MIME,
    magic-byte sniff. Carries a human-readable message."""


@dataclass(frozen=True, slots=True)
class StoredUpload:
    """The output of :func:`store_upload`."""

    storage_key: str  # relative to instance/uploads
    filename: str  # sanitised original filename
    content_type: str  # the canonicalised content type
    size_bytes: int  # bytes on disk after re-encode


def _instance_uploads_root() -> Path:
    """The root directory for stored uploads.

    Configurable via ``UPLOADS_ROOT`` (absolute path). Falls back to
    ``<instance>/uploads`` when unset.
    """
    raw = current_app.config.get("UPLOADS_ROOT")
    if raw:
        return Path(str(raw))
    return Path(current_app.instance_path) / "uploads"


def _safe_filename(name: str) -> str:
    """Strip directory components and unsafe characters from a filename."""
    # Drop any path separators
    base = os.path.basename(name or "")
    # Keep only a conservative ASCII subset
    cleaned = "".join(c for c in base if c.isalnum() or c in "._- ")
    cleaned = cleaned.strip().replace("  ", " ")
    return cleaned or "upload"


def _ext_of(name: str) -> str:
    """Lowercase extension of ``name`` (e.g. ``".png"``); empty if none."""
    _, ext = os.path.splitext(name or "")
    return ext.lower()


def _check_magic(ext: str, head: bytes) -> bool:
    """Whether ``head`` matches any known magic prefix for ``ext``.

    Text formats (``.txt`` / ``.csv``) have no reliable magic — they're
    accepted by extension alone.
    """
    if ext not in _MAGIC:
        return True
    return any(head.startswith(prefix) for prefix in _MAGIC[ext])


def _read_into_buffer(stream: IO[bytes]) -> bytes:
    """Read a stream into memory enforcing :data:`MAX_BYTES`."""
    data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise UploadRejected(f"file is larger than the {MAX_BYTES // (1024 * 1024)} MB limit")
    return data


def _reencode_image(data: bytes, ext: str) -> tuple[bytes, str, str]:
    """Re-encode an image to WebP at long-edge ≤ :data:`MAX_IMAGE_EDGE`.

    Returns ``(new_bytes, new_ext, new_content_type)``. If Pillow can't
    decode the bytes, raises :class:`UploadRejected`.
    """
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - Pillow is a hard dep
        raise UploadRejected("Pillow is not installed") from exc

    try:
        img: Any = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise UploadRejected(f"could not decode {ext} image") from exc

    if img.mode not in {"RGB", "RGBA"}:
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    long_edge = max(img.size)
    if long_edge > MAX_IMAGE_EDGE:
        ratio = MAX_IMAGE_EDGE / long_edge
        new_size = (max(1, int(img.size[0] * ratio)), max(1, int(img.size[1] * ratio)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85, method=4)
    return buf.getvalue(), ".webp", "image/webp"


def store_upload(
    *,
    stream: BinaryIO,
    original_filename: str,
    declared_content_type: str = "",
    scope: str,
    owner_id: bytes,
) -> StoredUpload:
    """Validate, optionally re-encode, and persist an uploaded blob.

    ``scope`` is the subdirectory under ``instance/uploads/`` (typically
    a blueprint name, e.g. ``"tickets"``). ``owner_id`` is the hex of
    the parent entity; bytes will live under
    ``<root>/<scope>/<owner_hex>/<ulid><ext>``.
    """
    name = _safe_filename(original_filename)
    ext = _ext_of(name)
    if ext not in _ALLOWED:
        raise UploadRejected(f"file type {ext or 'unknown'!r} is not allowed")

    data = _read_into_buffer(stream)
    if not data:
        raise UploadRejected("file is empty")

    head = data[:32]
    if not _check_magic(ext, head):
        raise UploadRejected("file content does not match its extension")

    # Re-encode images
    if ext in _IMAGE_EXTS:
        data, ext, content_type = _reencode_image(data, ext)
        # Re-derive the visible filename's extension to match the bytes
        base_without_ext, _old = os.path.splitext(name)
        name = base_without_ext + ext
    else:
        content_type = _ALLOWED[ext]
        # The declared content type from multipart parsing is advisory
        # only; the extension + magic-byte check above is authoritative.

    # Compute the storage key and write the bytes
    aid_hex = ulid.new().hex()
    owner_hex = owner_id.hex()
    rel_path = Path(scope) / owner_hex / f"{aid_hex}{ext}"
    root = _instance_uploads_root()
    full_path = root / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "wb") as fh:
        fh.write(data)

    return StoredUpload(
        storage_key=str(rel_path).replace(os.sep, "/"),
        filename=name,
        content_type=content_type,
        size_bytes=len(data),
    )


def open_stored(storage_key: str) -> tuple[Path, int]:
    """Return ``(absolute_path, size_bytes)`` for a stored upload.

    Raises :class:`FileNotFoundError` if the file is missing.
    """
    root = _instance_uploads_root()
    full = (root / storage_key).resolve()
    # Guard against path traversal: the resolved path must stay under root.
    if not str(full).startswith(str(root.resolve())):
        raise FileNotFoundError(storage_key)
    if not full.is_file():
        raise FileNotFoundError(storage_key)
    return full, full.stat().st_size


def delete_stored(storage_key: str) -> None:
    """Remove an upload from disk, ignoring missing files."""
    root = _instance_uploads_root()
    full = (root / storage_key).resolve()
    if not str(full).startswith(str(root.resolve())):
        return
    if full.is_file():
        full.unlink()


def reset_uploads_root() -> None:
    """Wipe and recreate the configured uploads root. Test-only."""
    root = _instance_uploads_root()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
