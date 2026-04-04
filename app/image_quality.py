"""Image quality assessment using OpenCV.

Provides scan quality scoring before barcode detection so that poor-quality
inputs can be flagged with actionable rejection metadata.  All metrics use
OpenCV functions already available via the opencv-python-headless dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


# Thresholds derived from packaging industry scan quality research:
# most barcode scanners need Laplacian variance > 50 and mean brightness 40-240.
BLUR_THRESHOLD = 50.0
CONTRAST_LOW = 30.0
BRIGHTNESS_LOW = 40
BRIGHTNESS_HIGH = 240


@dataclass(frozen=True)
class ImageQualityReport:
    """Quality metrics for a scanned document image."""

    sharpness: float
    contrast: float
    mean_brightness: float
    is_blurry: bool
    is_low_contrast: bool
    is_overexposed: bool
    is_underexposed: bool

    @property
    def is_acceptable(self) -> bool:
        return not (self.is_blurry or self.is_low_contrast or self.is_overexposed or self.is_underexposed)

    @property
    def quality_score(self) -> float:
        """Composite 0-100 quality score."""
        sharpness_score = min(100.0, (self.sharpness / BLUR_THRESHOLD) * 50.0)
        contrast_score = min(100.0, (self.contrast / CONTRAST_LOW) * 50.0)
        brightness_penalty = 0.0
        if self.is_underexposed or self.is_overexposed:
            brightness_penalty = 25.0
        return max(0.0, min(100.0, (sharpness_score + contrast_score) / 2.0 - brightness_penalty))

    @property
    def issues(self) -> list[str]:
        """Human-readable list of quality issues found."""
        problems: list[str] = []
        if self.is_blurry:
            problems.append(f"blurry (sharpness {self.sharpness:.0f}, need >{BLUR_THRESHOLD:.0f})")
        if self.is_low_contrast:
            problems.append(f"low contrast ({self.contrast:.0f}, need >{CONTRAST_LOW:.0f})")
        if self.is_underexposed:
            problems.append(f"too dark (brightness {self.mean_brightness:.0f})")
        if self.is_overexposed:
            problems.append(f"too bright (brightness {self.mean_brightness:.0f})")
        return problems


def assess_quality(image: Image.Image) -> ImageQualityReport:
    """Assess scan quality of a PIL Image.

    Uses Laplacian variance for sharpness (blur detection) and standard
    deviation for contrast — both standard techniques in document imaging.
    """
    gray = np.array(image.convert("L"), dtype=np.uint8)

    # Sharpness: variance of the Laplacian (higher = sharper)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(laplacian.var())

    # Contrast: standard deviation of pixel intensities
    contrast = float(gray.std())

    # Brightness: mean pixel value
    mean_brightness = float(gray.mean())

    return ImageQualityReport(
        sharpness=sharpness,
        contrast=contrast,
        mean_brightness=mean_brightness,
        is_blurry=sharpness < BLUR_THRESHOLD,
        is_low_contrast=contrast < CONTRAST_LOW,
        is_overexposed=mean_brightness > BRIGHTNESS_HIGH,
        is_underexposed=mean_brightness < BRIGHTNESS_LOW,
    )
