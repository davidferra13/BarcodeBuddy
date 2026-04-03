from __future__ import annotations

import unittest
from unittest.mock import patch

from PIL import Image

from app.barcode import BarcodeScanner


class _FakeFormat:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeResult:
    def __init__(
        self,
        text: str,
        *,
        points: tuple[tuple[float, float], ...],
        orientation: int = 0,
        format_name: str = "Code128",
    ) -> None:
        self.text = text
        self.position = points
        self.orientation = orientation
        self.format = _FakeFormat(format_name)


class BarcodeScannerTests(unittest.TestCase):
    def test_matching_business_rule_beats_larger_non_matching_barcode(self) -> None:
        scanner = BarcodeScanner(("code128",), (r"^PO-\d+$",), upscale_factor=1.0)
        image = Image.new("RGB", (100, 100), "white")
        results = [
            _FakeResult("SHIP-999", points=((0, 0), (40, 0), (40, 20), (0, 20))),
            _FakeResult("PO-100", points=((50, 50), (65, 50), (65, 60), (50, 60))),
        ]

        with patch.object(scanner, "_read_barcodes", return_value=results):
            match = scanner.scan_image(image)

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.text, "PO-100")
        self.assertTrue(match.matches_business_rule)

    def test_largest_area_wins_when_multiple_candidates_match(self) -> None:
        scanner = BarcodeScanner(("code128",), (), upscale_factor=1.0)
        image = Image.new("RGB", (100, 100), "white")
        results = [
            _FakeResult("BOX-001", points=((0, 0), (10, 0), (10, 10), (0, 10))),
            _FakeResult("BOX-999", points=((60, 60), (90, 60), (90, 90), (60, 90))),
        ]

        with patch.object(scanner, "_read_barcodes", return_value=results):
            match = scanner.scan_image(image)

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.text, "BOX-999")
        self.assertEqual(match.bounding_box_area, 900.0)

    def test_scan_order_breaks_area_ties(self) -> None:
        scanner = BarcodeScanner(("code128",), (), upscale_factor=1.0)
        image = Image.new("RGB", (100, 100), "white")
        results = [
            _FakeResult("BOX-TOP", points=((0, 0), (20, 0), (20, 20), (0, 20))),
            _FakeResult("BOX-LOW", points=((40, 40), (60, 40), (60, 60), (40, 60))),
        ]

        with patch.object(scanner, "_read_barcodes", return_value=results):
            match = scanner.scan_image(image)

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.text, "BOX-TOP")

    def test_rotation_retries_until_barcode_is_found(self) -> None:
        scanner = BarcodeScanner(("code128",), (), upscale_factor=1.0)
        image = Image.new("RGB", (100, 100), "white")
        result = _FakeResult(
            "ROTATED-OK",
            points=((10, 10), (30, 10), (30, 30), (10, 30)),
        )

        with patch.object(
            scanner,
            "_read_barcodes",
            side_effect=[[], [], [], [result]],
        ) as mocked_read:
            match = scanner.scan_image(image)

        self.assertEqual(mocked_read.call_count, 4)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.text, "ROTATED-OK")
        self.assertEqual(match.orientation_degrees, 270)


if __name__ == "__main__":
    unittest.main()
