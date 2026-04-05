"""Tests for document processing: type detection, page counts, PDF conversion, file locking."""

from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.documents import (
    DocumentError,
    FileLockedError,
    UnsupportedFileTypeError,
    ensure_exclusive_access,
    get_page_count,
    is_supported_input,
    iter_scan_images,
    move_file,
    save_processing_file_as_pdf,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_png(tmp_path: Path, name: str = "test.png", size: tuple = (100, 100)) -> Path:
    path = tmp_path / name
    Image.new("RGB", size, "red").save(path, "PNG")
    return path


def _make_jpeg(tmp_path: Path, name: str = "test.jpg") -> Path:
    path = tmp_path / name
    Image.new("RGB", (100, 100), "blue").save(path, "JPEG")
    return path


def _make_pdf(tmp_path: Path, name: str = "test.pdf") -> Path:
    import fitz
    path = tmp_path / name
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((50, 100), "Hello")
    doc.save(str(path))
    doc.close()
    return path


def _make_fake_file(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


# ── is_supported_input ────────────────────────────────────────────────


class TestIsSupportedInput:
    def test_png_supported(self, tmp_path):
        assert is_supported_input(_make_png(tmp_path)) is True

    def test_jpeg_supported(self, tmp_path):
        assert is_supported_input(_make_jpeg(tmp_path)) is True

    def test_pdf_supported(self, tmp_path):
        assert is_supported_input(_make_pdf(tmp_path)) is True

    def test_txt_not_supported(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_text("hello")
        assert is_supported_input(path) is False

    def test_wrong_signature_not_supported(self, tmp_path):
        """A .png file with JPEG content is rejected (signature mismatch)."""
        path = _make_fake_file(tmp_path, "fake.png", b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        assert is_supported_input(path) is False

    def test_nonexistent_file(self, tmp_path):
        assert is_supported_input(tmp_path / "missing.png") is False


# ── get_page_count ────────────────────────────────────────────────────


class TestGetPageCount:
    def test_png_is_one_page(self, tmp_path):
        assert get_page_count(_make_png(tmp_path)) == 1

    def test_jpeg_is_one_page(self, tmp_path):
        assert get_page_count(_make_jpeg(tmp_path)) == 1

    def test_pdf_page_count(self, tmp_path):
        assert get_page_count(_make_pdf(tmp_path)) >= 1

    def test_multi_page_pdf(self, tmp_path):
        import fitz
        path = tmp_path / "multi.pdf"
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text((50, 100), f"Page {i + 1}")
        doc.save(str(path))
        doc.close()
        assert get_page_count(path) == 3

    def test_unsupported_format_raises(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_text("not an image")
        with pytest.raises(UnsupportedFileTypeError):
            get_page_count(path)


# ── iter_scan_images ──────────────────────────────────────────────────


class TestIterScanImages:
    def test_png_yields_one_image(self, tmp_path):
        images = list(iter_scan_images(_make_png(tmp_path), max_pages=10, render_dpi=72))
        assert len(images) == 1
        assert isinstance(images[0], Image.Image)

    def test_jpeg_yields_one_image(self, tmp_path):
        images = list(iter_scan_images(_make_jpeg(tmp_path), max_pages=10, render_dpi=72))
        assert len(images) == 1

    def test_pdf_yields_pages(self, tmp_path):
        import fitz
        path = tmp_path / "two.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.new_page()
        doc.save(str(path))
        doc.close()
        images = list(iter_scan_images(path, max_pages=10, render_dpi=72))
        assert len(images) == 2

    def test_pdf_max_pages_enforced(self, tmp_path):
        import fitz
        path = tmp_path / "big.pdf"
        doc = fitz.open()
        for _ in range(5):
            doc.new_page()
        doc.save(str(path))
        doc.close()
        with pytest.raises(DocumentError, match="maximum page limit"):
            list(iter_scan_images(path, max_pages=3, render_dpi=72))

    def test_unsupported_raises(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_text("nope")
        with pytest.raises(UnsupportedFileTypeError):
            list(iter_scan_images(path, max_pages=10, render_dpi=72))


# ── save_processing_file_as_pdf ───────────────────────────────────────


class TestSaveProcessingFileAsPdf:
    def test_png_to_pdf(self, tmp_path):
        src = _make_png(tmp_path, "input.png")
        dst = tmp_path / "output" / "result.pdf"
        save_processing_file_as_pdf(src, dst)
        assert dst.exists()
        assert dst.stat().st_size > 0
        assert not src.exists()  # source removed

    def test_jpeg_to_pdf(self, tmp_path):
        src = _make_jpeg(tmp_path, "input.jpg")
        dst = tmp_path / "output" / "result.pdf"
        save_processing_file_as_pdf(src, dst)
        assert dst.exists()
        assert not src.exists()

    def test_pdf_copied(self, tmp_path):
        src = _make_pdf(tmp_path, "input.pdf")
        original_size = src.stat().st_size
        dst = tmp_path / "output" / "result.pdf"
        save_processing_file_as_pdf(src, dst)
        assert dst.exists()
        assert dst.stat().st_size == original_size
        assert not src.exists()

    def test_rgba_image_converted(self, tmp_path):
        """RGBA images are flattened to RGB before PDF conversion."""
        src = tmp_path / "rgba.png"
        Image.new("RGBA", (50, 50), (255, 0, 0, 128)).save(src, "PNG")
        dst = tmp_path / "out.pdf"
        save_processing_file_as_pdf(src, dst)
        assert dst.exists()

    def test_palette_image_converted(self, tmp_path):
        """Palette mode images are converted to RGB."""
        src = tmp_path / "palette.png"
        Image.new("P", (50, 50)).save(src, "PNG")
        dst = tmp_path / "out.pdf"
        save_processing_file_as_pdf(src, dst)
        assert dst.exists()


# ── move_file ─────────────────────────────────────────────────────────


class TestMoveFile:
    def test_move_creates_destination_dir(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("data")
        dst = tmp_path / "sub" / "dir" / "b.txt"
        move_file(src, dst)
        assert dst.exists()
        assert dst.read_text() == "data"
        assert not src.exists()


# ── ensure_exclusive_access ───────────────────────────────────────────


class TestEnsureExclusiveAccess:
    def test_unlocked_file_succeeds(self, tmp_path):
        path = _make_png(tmp_path)
        ensure_exclusive_access(path, retries=1, interval_seconds=0.01)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ensure_exclusive_access(tmp_path / "gone.png", retries=1, interval_seconds=0.01)
