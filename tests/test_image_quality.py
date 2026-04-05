"""Tests for image quality assessment: sharpness, contrast, brightness, scoring."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.image_quality import (
    BLUR_THRESHOLD,
    BRIGHTNESS_HIGH,
    BRIGHTNESS_LOW,
    CONTRAST_LOW,
    ImageQualityReport,
    assess_quality,
)


# ── ImageQualityReport dataclass ─────────────────────────────────────


class TestImageQualityReport:
    def test_acceptable_when_no_issues(self):
        report = ImageQualityReport(
            sharpness=100.0, contrast=50.0, mean_brightness=128.0,
            is_blurry=False, is_low_contrast=False,
            is_overexposed=False, is_underexposed=False,
        )
        assert report.is_acceptable is True
        assert report.issues == []

    def test_not_acceptable_when_blurry(self):
        report = ImageQualityReport(
            sharpness=20.0, contrast=50.0, mean_brightness=128.0,
            is_blurry=True, is_low_contrast=False,
            is_overexposed=False, is_underexposed=False,
        )
        assert report.is_acceptable is False
        assert any("blurry" in i for i in report.issues)

    def test_not_acceptable_when_low_contrast(self):
        report = ImageQualityReport(
            sharpness=100.0, contrast=10.0, mean_brightness=128.0,
            is_blurry=False, is_low_contrast=True,
            is_overexposed=False, is_underexposed=False,
        )
        assert report.is_acceptable is False
        assert any("contrast" in i for i in report.issues)

    def test_not_acceptable_when_overexposed(self):
        report = ImageQualityReport(
            sharpness=100.0, contrast=50.0, mean_brightness=250.0,
            is_blurry=False, is_low_contrast=False,
            is_overexposed=True, is_underexposed=False,
        )
        assert report.is_acceptable is False
        assert any("bright" in i for i in report.issues)

    def test_not_acceptable_when_underexposed(self):
        report = ImageQualityReport(
            sharpness=100.0, contrast=50.0, mean_brightness=20.0,
            is_blurry=False, is_low_contrast=False,
            is_overexposed=False, is_underexposed=True,
        )
        assert report.is_acceptable is False
        assert any("dark" in i for i in report.issues)

    def test_multiple_issues_reported(self):
        report = ImageQualityReport(
            sharpness=10.0, contrast=5.0, mean_brightness=250.0,
            is_blurry=True, is_low_contrast=True,
            is_overexposed=True, is_underexposed=False,
        )
        assert len(report.issues) == 3

    def test_frozen_dataclass(self):
        report = ImageQualityReport(
            sharpness=100.0, contrast=50.0, mean_brightness=128.0,
            is_blurry=False, is_low_contrast=False,
            is_overexposed=False, is_underexposed=False,
        )
        with pytest.raises(AttributeError):
            report.sharpness = 999.0  # type: ignore[misc]


# ── Quality score computation ─────────────────────────────────────────


class TestQualityScore:
    def test_perfect_image_scores_high(self):
        report = ImageQualityReport(
            sharpness=BLUR_THRESHOLD * 2, contrast=CONTRAST_LOW * 2,
            mean_brightness=128.0,
            is_blurry=False, is_low_contrast=False,
            is_overexposed=False, is_underexposed=False,
        )
        assert report.quality_score == 100.0

    def test_borderline_sharpness_and_contrast(self):
        report = ImageQualityReport(
            sharpness=BLUR_THRESHOLD, contrast=CONTRAST_LOW,
            mean_brightness=128.0,
            is_blurry=False, is_low_contrast=False,
            is_overexposed=False, is_underexposed=False,
        )
        assert report.quality_score == 50.0

    def test_brightness_penalty_applied(self):
        normal = ImageQualityReport(
            sharpness=BLUR_THRESHOLD, contrast=CONTRAST_LOW,
            mean_brightness=128.0,
            is_blurry=False, is_low_contrast=False,
            is_overexposed=False, is_underexposed=False,
        )
        dark = ImageQualityReport(
            sharpness=BLUR_THRESHOLD, contrast=CONTRAST_LOW,
            mean_brightness=20.0,
            is_blurry=False, is_low_contrast=False,
            is_overexposed=False, is_underexposed=True,
        )
        assert dark.quality_score == normal.quality_score - 25.0

    def test_score_clamped_to_zero(self):
        report = ImageQualityReport(
            sharpness=0.0, contrast=0.0, mean_brightness=10.0,
            is_blurry=True, is_low_contrast=True,
            is_overexposed=False, is_underexposed=True,
        )
        assert report.quality_score == 0.0

    def test_score_clamped_to_hundred(self):
        report = ImageQualityReport(
            sharpness=BLUR_THRESHOLD * 100, contrast=CONTRAST_LOW * 100,
            mean_brightness=128.0,
            is_blurry=False, is_low_contrast=False,
            is_overexposed=False, is_underexposed=False,
        )
        assert report.quality_score == 100.0


# ── assess_quality integration ────────────────────────────────────────


class TestAssessQuality:
    def _make_image(self, array: np.ndarray) -> Image.Image:
        return Image.fromarray(array.astype(np.uint8), mode="L")

    def test_sharp_high_contrast_image(self):
        """Checkerboard pattern: high sharpness, high contrast, mid brightness."""
        pattern = np.zeros((100, 100), dtype=np.uint8)
        pattern[::2, ::2] = 255
        pattern[1::2, 1::2] = 255
        report = assess_quality(self._make_image(pattern))
        assert report.sharpness > BLUR_THRESHOLD
        assert report.contrast > CONTRAST_LOW
        assert not report.is_blurry
        assert not report.is_low_contrast
        assert report.is_acceptable

    def test_uniform_gray_image(self):
        """Solid gray: zero sharpness, zero contrast."""
        gray = np.full((100, 100), 128, dtype=np.uint8)
        report = assess_quality(self._make_image(gray))
        assert report.sharpness == 0.0
        assert report.contrast == 0.0
        assert report.is_blurry
        assert report.is_low_contrast
        assert not report.is_acceptable

    def test_very_dark_image(self):
        """Nearly black: underexposed."""
        dark = np.full((100, 100), 10, dtype=np.uint8)
        report = assess_quality(self._make_image(dark))
        assert report.mean_brightness < BRIGHTNESS_LOW
        assert report.is_underexposed
        assert not report.is_overexposed

    def test_very_bright_image(self):
        """Nearly white: overexposed."""
        bright = np.full((100, 100), 250, dtype=np.uint8)
        report = assess_quality(self._make_image(bright))
        assert report.mean_brightness > BRIGHTNESS_HIGH
        assert report.is_overexposed
        assert not report.is_underexposed

    def test_rgb_image_converted(self):
        """RGB input is correctly converted to grayscale for assessment."""
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb[::2, ::2] = [255, 255, 255]
        rgb[1::2, 1::2] = [255, 255, 255]
        image = Image.fromarray(rgb, mode="RGB")
        report = assess_quality(image)
        assert report.sharpness > 0
        assert isinstance(report.contrast, float)

    def test_small_image(self):
        """Minimum viable image (1x1 pixel)."""
        tiny = np.array([[128]], dtype=np.uint8)
        report = assess_quality(self._make_image(tiny))
        assert isinstance(report.quality_score, float)
        assert report.mean_brightness == 128.0
