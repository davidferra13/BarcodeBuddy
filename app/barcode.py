from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re

import cv2
import numpy as np
from PIL import Image, ImageOps
import zxingcpp


FORMAT_ALIASES = {
    "aztec": zxingcpp.BarcodeFormat.Aztec,
    "codabar": zxingcpp.BarcodeFormat.Codabar,
    "code128": zxingcpp.BarcodeFormat.Code128,
    "code39": zxingcpp.BarcodeFormat.Code39,
    "code93": zxingcpp.BarcodeFormat.Code93,
    "datamatrix": zxingcpp.BarcodeFormat.DataMatrix,
    "ean13": zxingcpp.BarcodeFormat.EAN13,
    "ean8": zxingcpp.BarcodeFormat.EAN8,
    "itf": zxingcpp.BarcodeFormat.ITF,
    "pdf417": zxingcpp.BarcodeFormat.PDF417,
    "qrcode": zxingcpp.BarcodeFormat.QRCode,
    "upca": zxingcpp.BarcodeFormat.UPCA,
    "upce": zxingcpp.BarcodeFormat.UPCE,
}


@dataclass(frozen=True)
class BarcodeMatch:
    text: str
    format_name: str
    orientation_degrees: int
    matches_business_rule: bool
    bounding_box_area: float = 0.0
    scan_order_key: tuple[float, float, int] = (float("inf"), float("inf"), 0)
    page_number: int = 1


@dataclass(frozen=True)
class BarcodeCandidate:
    text: str
    format_name: str
    orientation_degrees: int
    matches_business_rule: bool
    normalized_text: str = ""
    bounding_box_area: float = 0.0
    scan_order_key: tuple[float, float, int] = (float("inf"), float("inf"), 0)
    page_number: int = 1

    def __post_init__(self) -> None:
        if not self.normalized_text:
            object.__setattr__(self, "normalized_text", self.text)

    def to_match(self) -> BarcodeMatch:
        return BarcodeMatch(
            text=self.text,
            format_name=self.format_name,
            orientation_degrees=self.orientation_degrees,
            matches_business_rule=self.matches_business_rule,
            bounding_box_area=self.bounding_box_area,
            scan_order_key=self.scan_order_key,
            page_number=self.page_number,
        )


class BarcodeScanner:
    def __init__(
        self,
        configured_types: tuple[str, ...],
        value_patterns: tuple[str, ...],
        upscale_factor: float,
    ) -> None:
        self.configured_types = configured_types
        self.value_patterns = tuple(re.compile(pattern) for pattern in value_patterns)
        self.upscale_factor = upscale_factor
        self.primary_formats = self._resolve_formats()
        self.allow_auto = "auto" in configured_types or not self.primary_formats

    def scan_image(self, image: Image.Image) -> BarcodeMatch | None:
        candidates = self.scan_image_candidates(image)
        if not candidates:
            return None
        return candidates[0].to_match()

    def scan_image_candidates(self, image: Image.Image) -> list[BarcodeCandidate]:
        prepared = self._prepare_image(image)

        for rotation_degrees in (0, 90, 180, 270):
            rotated = prepared if rotation_degrees == 0 else prepared.rotate(-rotation_degrees, expand=True)

            if self.primary_formats:
                candidates = self._build_candidates(
                    self._read_barcodes(rotated, self.primary_formats),
                    rotation_degrees,
                )
                if candidates:
                    return candidates

            if self.allow_auto:
                candidates = self._build_candidates(
                    self._read_barcodes(rotated, None),
                    rotation_degrees,
                )
                if candidates:
                    return candidates

        return []

    def scan_images(self, images: Iterable[Image.Image]) -> BarcodeMatch | None:
        for image in images:
            match = self.scan_image(image)
            if match is not None:
                return match
        return None

    def _prepare_image(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        cv_image = np.array(grayscale, dtype=np.uint8)

        # OpenCV advanced preprocessing pipeline
        cv_image = cv2.fastNlMeansDenoising(cv_image, h=10)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cv_image = clahe.apply(cv_image)
        cv_image = cv2.adaptiveThreshold(
            cv_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cv_image = cv2.morphologyEx(cv_image, cv2.MORPH_CLOSE, kernel)

        processed = Image.fromarray(cv_image, mode="L")

        if self.upscale_factor <= 1.0:
            return processed

        width = max(1, int(round(processed.width * self.upscale_factor)))
        height = max(1, int(round(processed.height * self.upscale_factor)))
        return processed.resize((width, height), Image.Resampling.LANCZOS)

    def _read_barcodes(
        self,
        image: Image.Image,
        formats: tuple[zxingcpp.BarcodeFormat, ...] | None,
    ) -> list[object]:
        kwargs: dict[str, object] = {}
        if formats:
            kwargs["formats"] = formats
        return list(zxingcpp.read_barcodes(image, **kwargs))

    def _build_candidates(
        self,
        results: Iterable[object],
        rotation_degrees: int,
    ) -> list[BarcodeCandidate]:
        candidates: list[BarcodeCandidate] = []
        for scan_index, result in enumerate(results):
            normalized_text = self._normalize_value(str(getattr(result, "text", "")))
            if not normalized_text:
                continue

            raw_orientation = getattr(result, "orientation", 0)
            candidate = BarcodeCandidate(
                text=normalized_text,
                format_name=self._barcode_format_name(result),
                orientation_degrees=(int(raw_orientation) + rotation_degrees) % 360,
                matches_business_rule=(
                    self._matches_business_rule(normalized_text) if self.value_patterns else True
                ),
                normalized_text=normalized_text,
                bounding_box_area=self._bounding_box_area(result),
                scan_order_key=(*self._scan_order_key(result), scan_index),
            )
            candidates.append(candidate)

        return sorted(candidates, key=self._candidate_sort_key)

    def _candidate_sort_key(
        self,
        candidate: BarcodeCandidate,
    ) -> tuple[int, float, float, float, int]:
        return (
            0 if candidate.matches_business_rule else 1,
            -candidate.bounding_box_area,
            candidate.scan_order_key[0],
            candidate.scan_order_key[1],
            candidate.scan_order_key[2],
        )

    def _matches_business_rule(self, value: str) -> bool:
        return any(pattern.fullmatch(value) for pattern in self.value_patterns)

    def _normalize_value(self, value: str) -> str:
        return "".join(character for character in value.strip() if character.isprintable())

    def _resolve_formats(self) -> tuple[zxingcpp.BarcodeFormat, ...]:
        resolved: list[zxingcpp.BarcodeFormat] = []
        for configured_type in self.configured_types:
            if configured_type == "auto":
                continue
            barcode_format = FORMAT_ALIASES.get(configured_type)
            if barcode_format is not None and barcode_format not in resolved:
                resolved.append(barcode_format)
        return tuple(resolved)

    def _barcode_format_name(self, result: object) -> str:
        raw_format = getattr(result, "format", "")
        if hasattr(raw_format, "name"):
            value = raw_format.name
        else:
            value = str(raw_format)
        return value.strip().lower().replace("-", "").replace("_", "")

    def _scan_order_key(self, result: object) -> tuple[float, float]:
        points = self._extract_points(result)
        if not points:
            return (float("inf"), float("inf"))
        min_x = min(point[0] for point in points)
        min_y = min(point[1] for point in points)
        return (min_y, min_x)

    def _bounding_box_area(self, result: object) -> float:
        points = self._extract_points(result)
        if not points:
            return 0.0
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_y = max(point[1] for point in points)
        return max(0.0, (max_x - min_x) * (max_y - min_y))

    def _extract_points(self, result: object) -> tuple[tuple[float, float], ...]:
        position = getattr(result, "position", None)
        if position is None:
            return ()

        raw_points: list[object] = []
        if isinstance(position, (list, tuple)):
            raw_points.extend(position)
        else:
            points_attr = getattr(position, "points", None)
            if isinstance(points_attr, (list, tuple)):
                raw_points.extend(points_attr)
            for attribute in (
                "top_left",
                "topRight",
                "top_right",
                "bottom_left",
                "bottomLeft",
                "bottom_right",
                "bottomRight",
            ):
                point = getattr(position, attribute, None)
                if point is not None:
                    raw_points.append(point)

        normalized_points: list[tuple[float, float]] = []
        for point in raw_points:
            x = getattr(point, "x", None)
            y = getattr(point, "y", None)
            if x is None or y is None:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    x, y = point[0], point[1]
                else:
                    continue
            normalized_points.append((float(x), float(y)))

        return tuple(normalized_points)
