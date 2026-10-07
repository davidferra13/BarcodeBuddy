"""The Documents screen must say why a scan was set aside, in words, on every screen width."""
from __future__ import annotations

from app.stats import REJECTION_LABELS, _render_recent_row
from app.contracts import ERROR_CODES


def _event(**overrides):
    event = {
        "timestamp": "2026-10-07T13:04:27+00:00", "status": "success", "error_code": None,
        "original_filename": "scan.pdf", "duration_ms": 120, "reason": None, "barcode": "PO-10431",
        "barcode_format": "code128", "recovery_action": None, "pages": 1, "stage": "output",
    }
    event.update(overrides)
    return event


def test_every_error_code_has_plain_words():
    assert set(ERROR_CODES) <= set(REJECTION_LABELS)


def test_rejected_duplicate_leads_with_the_reason_not_the_barcode():
    row = _render_recent_row(_event(status="failure", error_code="DUPLICATE_FILE", original_filename="again.pdf"))
    detail_cell = row.split("</td>")[3]
    assert "Already filed" in detail_cell.split("<br>")[0]
    assert "DUPLICATE_FILE" in detail_cell and "PO-10431" in detail_cell
    file_cell = row.split("</td>")[1]
    assert "again.pdf" in file_cell and "Already filed" in file_cell


def test_rejection_without_barcode_and_success_rows():
    missing = _render_recent_row(_event(status="failure", error_code="BARCODE_NOT_FOUND", barcode=None, barcode_format=None))
    assert "No barcode found" in missing and "BARCODE_NOT_FOUND" in missing
    success = _render_recent_row(_event())
    assert "PO-10431" in success.split("</td>")[3]
    assert "Filed as PO-10431" in success.split("</td>")[1]
    assert "No barcode" not in success and "Already filed" not in success


def test_reason_text_is_escaped():
    row = _render_recent_row(_event(status="failure", error_code=None, reason="<script>x</script>", barcode=None))
    assert "<script>" not in row
