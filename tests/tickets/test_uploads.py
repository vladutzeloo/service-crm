"""Tests for the shared upload pipeline.

Exercises :func:`store_upload`, :func:`open_stored`, :func:`delete_stored`,
and :func:`reset_uploads_root`. The Pillow path is covered with a real
PNG built in-memory so we don't depend on test fixtures on disk.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from PIL import Image

from service_crm.shared import ulid, uploads


@pytest.fixture
def uploads_root(tmp_path: Path, app: Flask) -> Iterator[Path]:
    """Point uploads at a temp directory for the duration of one test.

    These tests don't use ``db_session``, so they don't enter an
    app_context themselves — we push one here so
    ``uploads._instance_uploads_root`` can read ``current_app.config``.
    """
    with app.app_context():
        app.config["UPLOADS_ROOT"] = str(tmp_path)
        uploads.reset_uploads_root()
        yield tmp_path
        app.config.pop("UPLOADS_ROOT", None)


def _png_bytes(size: tuple[int, int] = (10, 10)) -> bytes:
    img = Image.new("RGB", size, (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.integration
def test_store_upload_text(uploads_root: Path) -> None:
    owner = ulid.new()
    stream = io.BytesIO(b"hello, csv,row\n1,2,3\n")
    stored = uploads.store_upload(
        stream=stream,
        original_filename="data.csv",
        declared_content_type="text/csv",
        scope="tickets",
        owner_id=owner,
    )
    assert stored.content_type == "text/csv"
    full = uploads_root / stored.storage_key
    assert full.is_file()
    assert full.read_bytes().startswith(b"hello")


@pytest.mark.integration
def test_store_upload_image_reencodes_to_webp(uploads_root: Path) -> None:
    owner = ulid.new()
    stream = io.BytesIO(_png_bytes())
    stored = uploads.store_upload(
        stream=stream,
        original_filename="photo.png",
        scope="tickets",
        owner_id=owner,
    )
    assert stored.content_type == "image/webp"
    assert stored.filename.endswith(".webp")
    full = uploads_root / stored.storage_key
    assert full.is_file()


@pytest.mark.integration
def test_store_upload_grayscale_image_normalises_mode(uploads_root: Path) -> None:
    """A grayscale (``L`` mode) PNG triggers the convert-to-RGB branch."""
    img = Image.new("L", (4, 4), 128)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    stream = io.BytesIO(buf.getvalue())
    stored = uploads.store_upload(
        stream=stream,
        original_filename="gray.png",
        scope="tickets",
        owner_id=ulid.new(),
    )
    assert stored.content_type == "image/webp"


@pytest.mark.integration
def test_store_upload_large_image_resizes(uploads_root: Path) -> None:
    owner = ulid.new()
    stream = io.BytesIO(_png_bytes((4096, 100)))
    stored = uploads.store_upload(
        stream=stream,
        original_filename="big.png",
        scope="tickets",
        owner_id=owner,
    )
    full = uploads_root / stored.storage_key
    out = Image.open(full)
    assert max(out.size) <= uploads.MAX_IMAGE_EDGE


@pytest.mark.integration
def test_store_upload_rejects_disallowed_extension(uploads_root: Path) -> None:
    with pytest.raises(uploads.UploadRejected, match="not allowed"):
        uploads.store_upload(
            stream=io.BytesIO(b"\x00"),
            original_filename="script.exe",
            scope="tickets",
            owner_id=ulid.new(),
        )


@pytest.mark.integration
def test_store_upload_rejects_magic_mismatch(uploads_root: Path) -> None:
    with pytest.raises(uploads.UploadRejected, match="does not match"):
        uploads.store_upload(
            stream=io.BytesIO(b"not a real pdf"),
            original_filename="bad.pdf",
            scope="tickets",
            owner_id=ulid.new(),
        )


@pytest.mark.integration
def test_store_upload_rejects_empty(uploads_root: Path) -> None:
    with pytest.raises(uploads.UploadRejected, match="empty"):
        uploads.store_upload(
            stream=io.BytesIO(b""),
            original_filename="empty.txt",
            scope="tickets",
            owner_id=ulid.new(),
        )


@pytest.mark.integration
def test_store_upload_rejects_oversize(uploads_root: Path) -> None:
    huge = b"x" * (uploads.MAX_BYTES + 10)
    with pytest.raises(uploads.UploadRejected, match="larger than"):
        uploads.store_upload(
            stream=io.BytesIO(huge),
            original_filename="huge.txt",
            scope="tickets",
            owner_id=ulid.new(),
        )


@pytest.mark.integration
def test_store_upload_rejects_corrupt_image(uploads_root: Path) -> None:
    fake = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
    with pytest.raises(uploads.UploadRejected, match="decode"):
        uploads.store_upload(
            stream=io.BytesIO(fake),
            original_filename="corrupt.png",
            scope="tickets",
            owner_id=ulid.new(),
        )


@pytest.mark.integration
def test_open_stored_returns_path_and_size(uploads_root: Path) -> None:
    owner = ulid.new()
    stored = uploads.store_upload(
        stream=io.BytesIO(b"hello"),
        original_filename="ok.txt",
        scope="tickets",
        owner_id=owner,
    )
    path, size = uploads.open_stored(stored.storage_key)
    assert path.is_file()
    assert size == len(b"hello")


@pytest.mark.integration
def test_open_stored_missing_raises(uploads_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        uploads.open_stored("tickets/abc/nonexistent.txt")


@pytest.mark.integration
def test_open_stored_rejects_path_traversal(uploads_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        uploads.open_stored("../../../etc/passwd")


@pytest.mark.integration
def test_delete_stored_removes_file(uploads_root: Path) -> None:
    owner = ulid.new()
    stored = uploads.store_upload(
        stream=io.BytesIO(b"bye"),
        original_filename="bye.txt",
        scope="tickets",
        owner_id=owner,
    )
    full = uploads_root / stored.storage_key
    assert full.is_file()
    uploads.delete_stored(stored.storage_key)
    assert not full.exists()
    # Idempotent: calling again is fine.
    uploads.delete_stored(stored.storage_key)
    # Path-traversal: silently no-op.
    uploads.delete_stored("../../etc/passwd")


@pytest.mark.integration
def test_safe_filename_strips_path_components(uploads_root: Path) -> None:
    owner = ulid.new()
    stored = uploads.store_upload(
        stream=io.BytesIO(b"hi"),
        original_filename="/etc/passwd/ok.txt",
        scope="tickets",
        owner_id=owner,
    )
    assert "/" not in stored.filename
    assert "etc" not in stored.filename


@pytest.mark.integration
def test_uploads_root_falls_back_to_instance(app: Flask) -> None:
    with app.app_context():
        app.config.pop("UPLOADS_ROOT", None)
        root = uploads._instance_uploads_root()
        assert "uploads" in str(root)


@pytest.mark.integration
def test_reset_uploads_root_creates_missing_dir(tmp_path: Path, app: Flask) -> None:
    """Exercise the branch where the root does NOT yet exist."""
    new_root = tmp_path / "fresh"
    assert not new_root.exists()
    with app.app_context():
        app.config["UPLOADS_ROOT"] = str(new_root)
        uploads.reset_uploads_root()
        assert new_root.is_dir()
        app.config.pop("UPLOADS_ROOT", None)
