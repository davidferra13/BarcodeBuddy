"""Tests for contracts: error codes, constants, and normalization."""

from __future__ import annotations

from app.contracts import (
    ERROR_BARCODE_NOT_FOUND,
    ERROR_CODES,
    ERROR_CORRUPT_FILE,
    ERROR_DUPLICATE_FILE,
    ERROR_EMPTY_FILE,
    ERROR_FILE_LOCKED,
    ERROR_FILE_MISSING,
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_BARCODE_FORMAT,
    ERROR_PROCESSING_TIMEOUT,
    ERROR_RECOVERY_FAILED,
    ERROR_UNEXPECTED_ERROR,
    ERROR_UNSUPPORTED_FORMAT,
    LOG_SCHEMA_VERSION,
    normalize_error_code,
)


class TestErrorCodeConstants:
    """Verify the error code set is stable — downstream systems depend on these values."""

    def test_error_codes_is_frozenset(self):
        assert isinstance(ERROR_CODES, frozenset)

    def test_all_constants_in_set(self):
        expected = {
            ERROR_RECOVERY_FAILED,
            ERROR_FILE_MISSING,
            ERROR_FILE_LOCKED,
            ERROR_UNEXPECTED_ERROR,
            ERROR_EMPTY_FILE,
            ERROR_FILE_TOO_LARGE,
            ERROR_PROCESSING_TIMEOUT,
            ERROR_BARCODE_NOT_FOUND,
            ERROR_INVALID_BARCODE_FORMAT,
            ERROR_DUPLICATE_FILE,
            ERROR_UNSUPPORTED_FORMAT,
            ERROR_CORRUPT_FILE,
        }
        assert ERROR_CODES == expected

    def test_exactly_twelve_error_codes(self):
        assert len(ERROR_CODES) == 12

    def test_all_codes_are_uppercase_strings(self):
        for code in ERROR_CODES:
            assert isinstance(code, str)
            assert code == code.upper()
            assert "_" in code  # SCREAMING_SNAKE_CASE

    def test_schema_version_is_string(self):
        assert isinstance(LOG_SCHEMA_VERSION, str)
        assert LOG_SCHEMA_VERSION == "1.0"


class TestNormalizeErrorCode:
    def test_valid_code_returned_as_is(self):
        for code in ERROR_CODES:
            assert normalize_error_code(code) == code

    def test_case_insensitive(self):
        assert normalize_error_code("file_missing") == ERROR_FILE_MISSING
        assert normalize_error_code("Barcode_Not_Found") == ERROR_BARCODE_NOT_FOUND

    def test_strips_whitespace(self):
        assert normalize_error_code("  FILE_LOCKED  ") == ERROR_FILE_LOCKED

    def test_unknown_code_returns_unexpected(self):
        assert normalize_error_code("SOME_RANDOM_ERROR") == ERROR_UNEXPECTED_ERROR

    def test_none_returns_none(self):
        assert normalize_error_code(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_error_code("") is None

    def test_whitespace_only_returns_none(self):
        assert normalize_error_code("   ") is None
