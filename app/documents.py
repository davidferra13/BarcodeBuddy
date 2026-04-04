from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path
from typing import Iterator

import fitz
from PIL import Image, ImageOps
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
PDF_SUFFIXES = {".pdf"}
SUPPORTED_SUFFIXES = IMAGE_SUFFIXES | PDF_SUFFIXES
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE_PREFIX = b"\xff\xd8\xff"
PDF_SIGNATURE = b"%PDF-"
SIGNATURE_READ_BYTES = 16


class DocumentError(Exception):
    """Base document processing error."""


class UnsupportedFileTypeError(DocumentError):
    """Raised when the input file is not a supported type."""


class FileLockedError(DocumentError):
    """Raised when exclusive access cannot be obtained for a file."""


def is_supported_input(path: Path) -> bool:
    try:
        _probe_input_type(path)
    except (DocumentError, OSError):
        return False
    return True


def ensure_exclusive_access(path: Path, retries: int, interval_seconds: float) -> None:
    @retry(
        stop=stop_after_attempt(retries),
        wait=wait_fixed(interval_seconds),
        retry=retry_if_exception_type(OSError),
        reraise=True,
    )
    def _try_lock() -> None:
        try:
            with path.open("rb") as handle:
                _lock_handle(handle)
                _unlock_handle(handle)
        except FileNotFoundError:
            raise
        except OSError:
            raise

    try:
        _try_lock()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise FileLockedError(f"Unable to acquire exclusive access to {path.name}") from exc


def get_page_count(path: Path) -> int:
    input_type = _probe_input_type(path)
    if input_type in {"jpeg", "png"}:
        return 1
    if input_type == "pdf":
        try:
            document = fitz.open(path)
            if document.page_count < 1:
                raise DocumentError("PDF has no pages.")
            return document.page_count
        except Exception as exc:
            if isinstance(exc, DocumentError):
                raise
            raise DocumentError(f"Unable to read PDF page count for {path.name}") from exc
        finally:
            if "document" in locals():
                document.close()
    raise UnsupportedFileTypeError(f"Unsupported input type: {path.suffix}")


def iter_scan_images(path: Path, max_pages: int, render_dpi: int) -> Iterator[Image.Image]:
    input_type = _probe_input_type(path)
    if input_type in {"jpeg", "png"}:
        with Image.open(path) as image:
            yield _normalize_output_image(ImageOps.exif_transpose(image))
        return

    if input_type == "pdf":
        try:
            document = fitz.open(path)
            if document.page_count < 1:
                raise DocumentError("PDF has no pages to scan.")
            if document.page_count > max_pages:
                raise DocumentError("PDF exceeded maximum page limit.")

            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                pixmap = page.get_pixmap(dpi=render_dpi, colorspace=fitz.csGRAY, alpha=False)
                grayscale = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
                with BytesIO() as buffer:
                    grayscale.save(buffer, format="PNG")
                    buffer.seek(0)
                    with Image.open(buffer) as png_image:
                        yield png_image.copy()
            return
        except Exception as exc:
            if isinstance(exc, DocumentError):
                raise
            raise DocumentError(f"Unable to render PDF pages for {path.name}") from exc
        finally:
            if "document" in locals():
                document.close()

    raise UnsupportedFileTypeError(f"Unsupported input type: {path.suffix}")


def save_processing_file_as_pdf(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    input_type = _probe_input_type(source_path)
    temp_path = destination_path.with_name(f"{destination_path.name}.tmp")

    if temp_path.exists():
        temp_path.unlink(missing_ok=True)

    try:
        if input_type == "pdf":
            shutil.copy2(str(source_path), str(temp_path))
            temp_path.replace(destination_path)
            source_path.unlink(missing_ok=True)
            return

        if input_type not in {"jpeg", "png"}:
            raise UnsupportedFileTypeError(f"Unsupported input type: {source_path.suffix}")

        with Image.open(source_path) as image:
            normalized = _normalize_output_image(ImageOps.exif_transpose(image))
            normalized.save(temp_path, "PDF")
        temp_path.replace(destination_path)
        source_path.unlink(missing_ok=True)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def move_file(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(destination_path))


def _probe_input_type(path: Path) -> str:
    expected_type = _expected_input_type(path.suffix.lower())
    if expected_type is None:
        raise UnsupportedFileTypeError(f"Unsupported input type: {path.suffix}")

    try:
        with path.open("rb") as handle:
            signature = handle.read(SIGNATURE_READ_BYTES)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise DocumentError(f"Unable to inspect input type for {path.name}") from exc

    actual_type = _detect_input_type(signature)
    if actual_type is None or actual_type != expected_type:
        raise UnsupportedFileTypeError(
            f"Unsupported or mismatched input type: {path.suffix}"
        )
    return actual_type


def _expected_input_type(suffix: str) -> str | None:
    if suffix in PDF_SUFFIXES:
        return "pdf"
    if suffix == ".png":
        return "png"
    if suffix in {".jpg", ".jpeg"}:
        return "jpeg"
    return None


def _detect_input_type(signature: bytes) -> str | None:
    if signature.startswith(PDF_SIGNATURE):
        return "pdf"
    if signature.startswith(PNG_SIGNATURE):
        return "png"
    if signature.startswith(JPEG_SIGNATURE_PREFIX):
        return "jpeg"
    return None


def _normalize_output_image(image: Image.Image) -> Image.Image:
    image.load()

    if image.mode in {"RGBA", "LA"}:
        background = Image.new("RGB", image.size, "white")
        alpha_channel = image.getchannel("A")
        background.paste(image.convert("RGBA"), mask=alpha_channel)
        return background

    if image.mode == "P":
        return image.convert("RGB")

    if image.mode != "RGB":
        return image.convert("RGB")

    return image.copy()


def _lock_handle(handle: object) -> None:
    if msvcrt is not None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return

    raise OSError("No exclusive locking implementation is available.")


def _unlock_handle(handle: object) -> None:
    if msvcrt is not None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
