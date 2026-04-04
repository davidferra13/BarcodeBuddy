from __future__ import annotations

import json
import re
import socket
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from watchfiles import watch, Change

from app.barcode import BarcodeMatch, BarcodeScanner
from app.config import Settings
from app.contracts import (
    ERROR_BARCODE_NOT_FOUND,
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
    LOG_FIELD_CONFIG_VERSION,
    LOG_FIELD_ERROR_CODE,
    LOG_FIELD_HOST,
    LOG_FIELD_INSTANCE_ID,
    LOG_FIELD_SCHEMA_VERSION,
    LOG_FIELD_WORKFLOW,
    LOG_SCHEMA_VERSION,
    STAGE_OUTPUT,
    STAGE_PROCESSING,
    STAGE_SERVICE,
    STAGE_VALIDATION,
    STATUS_FAILURE,
    STATUS_SUCCESS,
    SERVICE_EVENT_HEARTBEAT,
    SERVICE_EVENT_SHUTDOWN,
    SERVICE_EVENT_STARTUP,
    normalize_error_code,
)
from app.image_quality import ImageQualityReport, assess_quality
from app.documents import (
    DocumentError,
    FileLockedError,
    UnsupportedFileTypeError,
    ensure_exclusive_access,
    get_page_count,
    iter_scan_images,
    move_file,
    save_processing_file_as_pdf,
)
from app.logging_utils import append_jsonl, get_logger, write_json_atomically


FILE_STABILITY_TIMEOUT_MS = 10_000
FILE_LOCK_RETRY_COUNT = 5
FILE_LOCK_RETRY_INTERVAL_SECONDS = 0.5
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
MAX_PROCESSING_DURATION_MS = 15_000
JOURNAL_DIR_NAME = ".journal"
HEARTBEAT_INTERVAL_SECONDS = 30

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
BARCODE_ALLOWED_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,64}$")


class ProcessingTimeoutError(Exception):
    """Raised when a single file exceeds the hard processing deadline."""


@dataclass
class FileObservation:
    size: int
    first_observed_monotonic: float
    stable_checks: int


@dataclass(frozen=True)
class ProcessingContext:
    processing_id: str
    original_filename: str
    started_at: datetime
    start_monotonic: float


@dataclass(frozen=True)
class ProcessingResult:
    processing_id: str
    status: str
    stage: str
    original_filename: str
    duration_ms: int
    reason: str | None = None
    barcode: str | None = None
    barcode_format: str | None = None
    barcode_orientation_degrees: int | None = None
    barcode_matches_business_rule: bool | None = None
    output_path: Path | None = None
    rejected_path: Path | None = None
    page_count: int | None = None
    raw_detection_count: int | None = None
    candidate_values: tuple[str, ...] | None = None
    eligible_candidate_values: tuple[str, ...] | None = None
    page_one_eligible_values: tuple[str, ...] | None = None
    quality_score: float | None = None
    quality_issues: tuple[str, ...] | None = None


@dataclass(frozen=True)
class BarcodeDetectionSummary:
    status: str
    selected_match: BarcodeMatch | None
    raw_detection_count: int
    candidate_values: tuple[str, ...]
    eligible_candidate_values: tuple[str, ...]
    page_one_eligible_values: tuple[str, ...]
    quality_report: ImageQualityReport | None = None


class BarcodeBuddyService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.scanner = BarcodeScanner(
            settings.barcode_types,
            settings.barcode_value_patterns,
            upscale_factor=settings.barcode_upscale_factor,
        )
        self.host = socket.gethostname()
        self.instance_id = str(uuid4())
        self._observations: dict[Path, FileObservation] = {}
        self._last_heartbeat_monotonic: float | None = None
        self._stop_event = threading.Event()
        self._scheduler: BackgroundScheduler | None = None
        self._log = get_logger(
            service="barcode_buddy",
            instance_id=self.instance_id,
            workflow=settings.workflow_key,
        )

    def run_forever(self) -> None:
        self._emit_heartbeat(force=True)

        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.add_job(
            self._scheduled_heartbeat,
            "interval",
            seconds=HEARTBEAT_INTERVAL_SECONDS,
            id="heartbeat",
            misfire_grace_time=HEARTBEAT_INTERVAL_SECONDS,
        )
        self._scheduler.start()

        try:
            self.process_pending_files()

            poll_interval_sec = self.settings.poll_interval_ms / 1000
            for changes in watch(
                str(self.settings.input_path),
                stop_event=self._stop_event,
                debounce=self.settings.poll_interval_ms,
                step=max(100, self.settings.poll_interval_ms // 2),
                recursive=False,
                yield_on_timeout=True,
            ):
                self.process_pending_files()
        finally:
            if self._scheduler is not None:
                self._scheduler.shutdown(wait=False)
            try:
                self.log_service_event(SERVICE_EVENT_SHUTDOWN)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()

    def _scheduled_heartbeat(self) -> None:
        try:
            self._emit_heartbeat(force=True)
        except Exception:
            pass

    def recover_processing_files(self) -> None:
        referenced_processing_paths: set[str] = set()

        for journal_path in self._list_journal_files():
            try:
                entry = json.loads(journal_path.read_text(encoding="utf-8"))
            except Exception as exc:
                self._log_recovery_event(
                    processing_id=journal_path.stem,
                    original_filename=journal_path.name,
                    status=STATUS_FAILURE,
                    reason=ERROR_RECOVERY_FAILED,
                    error=exc.__class__.__name__,
                    recovery_action="invalid_journal",
                    journal_path=journal_path,
                )
                continue

            processing_path_value = entry.get("processing_path")
            if processing_path_value:
                referenced_processing_paths.add(str(Path(processing_path_value).resolve()))
            self._recover_journal_entry(journal_path, entry)

        for processing_path in sorted(
            (path for path in self.settings.processing_path.iterdir() if path.is_file()),
            key=self._input_sort_key,
        ):
            if str(processing_path.resolve()) in referenced_processing_paths:
                continue
            self._recover_orphan_processing_file(processing_path)

    def process_pending_files(self) -> None:
        candidates = self._list_input_files()
        candidate_set = set(candidates)
        self._observations = {
            path: observation
            for path, observation in self._observations.items()
            if path in candidate_set
        }

        for input_path in candidates:
            stability = self._stability_state(input_path)
            if stability == "waiting":
                continue
            if stability == "file_locked":
                self._reject_stuck_input_file(input_path)
                continue
            self.process_file(input_path)

    def process_file(self, file_path: Path) -> ProcessingResult:
        context = self._new_context(file_path.name)
        self._observations.pop(file_path, None)

        try:
            ensure_exclusive_access(
                file_path,
                retries=FILE_LOCK_RETRY_COUNT,
                interval_seconds=FILE_LOCK_RETRY_INTERVAL_SECONDS,
            )
        except FileNotFoundError:
            result = ProcessingResult(
                processing_id=context.processing_id,
                status=STATUS_FAILURE,
                stage=STAGE_PROCESSING,
                original_filename=context.original_filename,
                duration_ms=self._elapsed_ms(context),
                reason=ERROR_FILE_MISSING,
            )
            self._log_stage(result)
            return result
        except FileLockedError:
            return self._reject_input_file(file_path, context, reason=ERROR_FILE_LOCKED)
        except Exception as exc:
            return self._reject_input_file(
                file_path,
                context,
                reason=ERROR_FILE_LOCKED,
                error=exc.__class__.__name__,
            )

        processing_path = self._build_collision_safe_path(
            self.settings.processing_path / self._sanitize_filename(file_path.name),
            when=context.started_at,
            suffix_label="processing",
        )

        try:
            move_file(file_path, processing_path)
        except FileNotFoundError:
            result = ProcessingResult(
                processing_id=context.processing_id,
                status=STATUS_FAILURE,
                stage=STAGE_PROCESSING,
                original_filename=context.original_filename,
                duration_ms=self._elapsed_ms(context),
                reason=ERROR_FILE_MISSING,
            )
            self._log_stage(result)
            return result
        except Exception as exc:
            return self._reject_input_file(
                file_path,
                context,
                reason=ERROR_FILE_LOCKED,
                error=exc.__class__.__name__,
            )

        try:
            self._write_journal(
                context,
                processing_path=processing_path,
                state="claimed",
                stage=STAGE_PROCESSING,
            )
        except Exception as exc:
            return self._reject_file(
                processing_path=processing_path,
                context=context,
                reason=ERROR_UNEXPECTED_ERROR,
                stage=STAGE_PROCESSING,
                error=exc.__class__.__name__,
            )

        try:
            return self._process_processing_file(processing_path, context)
        except Exception as exc:
            if not processing_path.exists():
                raise
            return self._reject_file(
                processing_path=processing_path,
                context=context,
                reason=ERROR_UNEXPECTED_ERROR,
                stage=STAGE_PROCESSING,
                error=exc.__class__.__name__,
            )

    def _process_processing_file(
        self,
        processing_path: Path,
        context: ProcessingContext,
    ) -> ProcessingResult:
        try:
            self._ensure_within_timeout(context)
            file_size = processing_path.stat().st_size
            if file_size == 0:
                return self._reject_file(processing_path, context, ERROR_EMPTY_FILE, STAGE_PROCESSING)
            if file_size > MAX_FILE_SIZE_BYTES:
                return self._reject_file(
                    processing_path,
                    context,
                    ERROR_FILE_TOO_LARGE,
                    STAGE_PROCESSING,
                )

            page_count = get_page_count(processing_path)
            if page_count > self.settings.max_pages_scan:
                return self._reject_file(
                    processing_path,
                    context,
                    ERROR_PROCESSING_TIMEOUT,
                    STAGE_PROCESSING,
                    page_count=page_count,
                )

            detection = self._detect_barcode(processing_path, context)
            qr = detection.quality_report
            quality_score = qr.quality_score if qr is not None else None
            quality_issues = tuple(qr.issues) if qr is not None and qr.issues else None
            if detection.status == "not_found":
                return self._reject_file(
                    processing_path,
                    context,
                    ERROR_BARCODE_NOT_FOUND,
                    STAGE_PROCESSING,
                    page_count=page_count,
                    raw_detection_count=detection.raw_detection_count,
                    candidate_values=detection.candidate_values,
                    eligible_candidate_values=detection.eligible_candidate_values,
                    page_one_eligible_values=detection.page_one_eligible_values,
                    quality_score=quality_score,
                    quality_issues=quality_issues,
                )
            barcode = detection.selected_match
            if barcode is None:
                return self._reject_file(
                    processing_path,
                    context,
                    ERROR_BARCODE_NOT_FOUND,
                    STAGE_PROCESSING,
                    page_count=page_count,
                    raw_detection_count=detection.raw_detection_count,
                    candidate_values=detection.candidate_values,
                    eligible_candidate_values=detection.eligible_candidate_values,
                    page_one_eligible_values=detection.page_one_eligible_values,
                    quality_score=quality_score,
                    quality_issues=quality_issues,
                )

            processing_result = ProcessingResult(
                processing_id=context.processing_id,
                status=STATUS_SUCCESS,
                stage=STAGE_PROCESSING,
                original_filename=context.original_filename,
                duration_ms=self._elapsed_ms(context),
                barcode=barcode.text,
                barcode_format=barcode.format_name,
                barcode_orientation_degrees=barcode.orientation_degrees,
                barcode_matches_business_rule=barcode.matches_business_rule,
                page_count=page_count,
                raw_detection_count=detection.raw_detection_count,
                candidate_values=detection.candidate_values or None,
                eligible_candidate_values=detection.eligible_candidate_values or None,
                page_one_eligible_values=detection.page_one_eligible_values or None,
                quality_score=quality_score,
                quality_issues=quality_issues,
            )
            self._log_stage(processing_result)

            normalized_barcode = self._normalize_barcode_text(barcode.text)
            if not barcode.matches_business_rule:
                return self._reject_file(
                    processing_path,
                    context,
                    ERROR_INVALID_BARCODE_FORMAT,
                    STAGE_VALIDATION,
                    barcode=normalized_barcode,
                    barcode_format=barcode.format_name,
                    barcode_orientation_degrees=barcode.orientation_degrees,
                    barcode_matches_business_rule=barcode.matches_business_rule,
                    page_count=page_count,
                    raw_detection_count=detection.raw_detection_count,
                    candidate_values=detection.candidate_values,
                    eligible_candidate_values=detection.eligible_candidate_values,
                    page_one_eligible_values=detection.page_one_eligible_values,
                    quality_score=quality_score,
                    quality_issues=quality_issues,
                )
            if not BARCODE_ALLOWED_PATTERN.fullmatch(normalized_barcode):
                return self._reject_file(
                    processing_path,
                    context,
                    ERROR_INVALID_BARCODE_FORMAT,
                    STAGE_VALIDATION,
                    barcode=normalized_barcode,
                    barcode_format=barcode.format_name,
                    barcode_orientation_degrees=barcode.orientation_degrees,
                    barcode_matches_business_rule=barcode.matches_business_rule,
                    page_count=page_count,
                    raw_detection_count=detection.raw_detection_count,
                    candidate_values=detection.candidate_values,
                    eligible_candidate_values=detection.eligible_candidate_values,
                    page_one_eligible_values=detection.page_one_eligible_values,
                    quality_score=quality_score,
                    quality_issues=quality_issues,
                )

            validation_result = ProcessingResult(
                processing_id=context.processing_id,
                status=STATUS_SUCCESS,
                stage=STAGE_VALIDATION,
                original_filename=context.original_filename,
                duration_ms=self._elapsed_ms(context),
                barcode=normalized_barcode,
                barcode_format=barcode.format_name,
                barcode_orientation_degrees=barcode.orientation_degrees,
                barcode_matches_business_rule=barcode.matches_business_rule,
                page_count=page_count,
                raw_detection_count=detection.raw_detection_count,
                candidate_values=detection.candidate_values or None,
                eligible_candidate_values=detection.eligible_candidate_values or None,
                page_one_eligible_values=detection.page_one_eligible_values or None,
                quality_score=quality_score,
                quality_issues=quality_issues,
            )
            self._log_stage(validation_result)

            output_path = self._build_output_path(normalized_barcode, context.started_at)
            if output_path.exists():
                if self.settings.duplicate_handling == "timestamp":
                    output_path = self._build_timestamped_output_path(
                        normalized_barcode,
                        context.started_at,
                    )
                else:
                    return self._reject_file(
                        processing_path,
                        context,
                        ERROR_DUPLICATE_FILE,
                        STAGE_OUTPUT,
                        barcode=normalized_barcode,
                        barcode_format=barcode.format_name,
                        barcode_orientation_degrees=barcode.orientation_degrees,
                        barcode_matches_business_rule=barcode.matches_business_rule,
                        page_count=page_count,
                        raw_detection_count=detection.raw_detection_count,
                        candidate_values=detection.candidate_values,
                        eligible_candidate_values=detection.eligible_candidate_values,
                        page_one_eligible_values=detection.page_one_eligible_values,
                        quality_score=quality_score,
                        quality_issues=quality_issues,
                    )

            self._write_journal(
                context,
                processing_path=processing_path,
                state="pending_output",
                stage=STAGE_OUTPUT,
                barcode=normalized_barcode,
                output_path=output_path,
            )
            self._ensure_within_timeout(context)
            save_processing_file_as_pdf(processing_path, output_path)
            self._ensure_within_timeout(context)

            result = ProcessingResult(
                processing_id=context.processing_id,
                status=STATUS_SUCCESS,
                stage=STAGE_OUTPUT,
                original_filename=context.original_filename,
                duration_ms=self._elapsed_ms(context),
                barcode=normalized_barcode,
                barcode_format=barcode.format_name,
                barcode_orientation_degrees=barcode.orientation_degrees,
                barcode_matches_business_rule=barcode.matches_business_rule,
                output_path=output_path,
                page_count=page_count,
                raw_detection_count=detection.raw_detection_count,
                candidate_values=detection.candidate_values or None,
                eligible_candidate_values=detection.eligible_candidate_values or None,
                page_one_eligible_values=detection.page_one_eligible_values or None,
                quality_score=quality_score,
                quality_issues=quality_issues,
            )
            self._log_stage(result)
            self._remove_journal(context.processing_id)
            return result
        except UnsupportedFileTypeError:
            return self._reject_file(
                processing_path,
                context,
                ERROR_UNSUPPORTED_FORMAT,
                STAGE_PROCESSING,
            )
        except ProcessingTimeoutError:
            return self._reject_file(
                processing_path,
                context,
                ERROR_PROCESSING_TIMEOUT,
                STAGE_PROCESSING,
            )
        except DocumentError:
            return self._reject_file(
                processing_path,
                context,
                ERROR_CORRUPT_FILE,
                STAGE_PROCESSING,
            )

    def _detect_barcode(
        self,
        processing_path: Path,
        context: ProcessingContext,
    ) -> BarcodeDetectionSummary:
        images = iter_scan_images(
            processing_path,
            self.settings.max_pages_scan,
            self.settings.barcode_scan_dpi,
        )
        raw_detection_count = 0
        candidate_values: list[str] = []
        eligible_candidate_values: list[str] = []
        page_one_eligible_values: list[str] = []
        seen_candidate_values: set[str] = set()
        seen_eligible_candidate_values: set[str] = set()
        seen_page_one_eligible_values: set[str] = set()
        best_match: BarcodeMatch | None = None
        quality_report: ImageQualityReport | None = None

        try:
            for page_index, image in enumerate(images, start=1):
                self._ensure_within_timeout(context)
                if page_index == 1:
                    try:
                        quality_report = assess_quality(image)
                    except Exception:
                        pass
                page_candidates = self.scanner.scan_image_candidates(image)
                self._ensure_within_timeout(context)
                raw_detection_count += len(page_candidates)

                for candidate in page_candidates:
                    page_candidate = replace(candidate, page_number=page_index)
                    candidate_match = page_candidate.to_match()
                    candidate_value = page_candidate.normalized_text

                    if best_match is None or self._barcode_match_sort_key(
                        candidate_match
                    ) < self._barcode_match_sort_key(best_match):
                        best_match = candidate_match
                    if candidate_value not in seen_candidate_values:
                        seen_candidate_values.add(candidate_value)
                        candidate_values.append(candidate_value)
                    if (
                        page_candidate.matches_business_rule
                        and candidate_value not in seen_eligible_candidate_values
                    ):
                        seen_eligible_candidate_values.add(candidate_value)
                        eligible_candidate_values.append(candidate_value)
                    if (
                        page_index == 1
                        and page_candidate.matches_business_rule
                        and candidate_value not in seen_page_one_eligible_values
                    ):
                        seen_page_one_eligible_values.add(candidate_value)
                        page_one_eligible_values.append(candidate_value)

                if not self.settings.scan_all_pages or page_index >= self.settings.max_pages_scan:
                    break
        finally:
            close_method = getattr(images, 'close', None)
            if callable(close_method):
                close_method()

        if raw_detection_count == 0:
            return BarcodeDetectionSummary(
                status='not_found',
                selected_match=None,
                raw_detection_count=raw_detection_count,
                candidate_values=(),
                eligible_candidate_values=(),
                page_one_eligible_values=(),
                quality_report=quality_report,
            )

        if not self.settings.barcode_value_patterns:
            eligible_values = tuple(candidate_values)
        else:
            eligible_values = tuple(eligible_candidate_values)

        return BarcodeDetectionSummary(
            status="found" if best_match is not None else "not_found",
            selected_match=best_match,
            raw_detection_count=raw_detection_count,
            candidate_values=tuple(candidate_values),
            eligible_candidate_values=eligible_values,
            page_one_eligible_values=tuple(page_one_eligible_values),
            quality_report=quality_report,
        )
    def _barcode_match_sort_key(
        self,
        match: BarcodeMatch,
    ) -> tuple[int, float, int, float, float, int]:
        return (
            0 if match.matches_business_rule else 1,
            -match.bounding_box_area,
            match.page_number,
            match.scan_order_key[0],
            match.scan_order_key[1],
            match.scan_order_key[2],
        )
    def _reject_stuck_input_file(self, input_path: Path) -> ProcessingResult:
        context = self._new_context(input_path.name)
        return self._reject_input_file(input_path, context, reason=ERROR_FILE_LOCKED)

    def _reject_input_file(
        self,
        input_path: Path,
        context: ProcessingContext,
        reason: str,
        error: str | None = None,
    ) -> ProcessingResult:
        rejected_path = self._build_collision_safe_path(
            self.settings.rejected_path / self._sanitize_filename(input_path.name),
            when=context.started_at,
            suffix_label="rejected",
        )

        try:
            move_file(input_path, rejected_path)
            self._write_rejection_sidecar(
                rejected_path=rejected_path,
                context=context,
                reason=reason,
                stage="processing",
            )
            result = ProcessingResult(
                processing_id=context.processing_id,
                status=STATUS_FAILURE,
                stage=STAGE_PROCESSING,
                original_filename=context.original_filename,
                duration_ms=self._elapsed_ms(context),
                reason=reason,
                rejected_path=rejected_path,
            )
            self._log_stage(result, error=error)
            return result
        except FileNotFoundError:
            result = ProcessingResult(
                processing_id=context.processing_id,
                status=STATUS_FAILURE,
                stage=STAGE_PROCESSING,
                original_filename=context.original_filename,
                duration_ms=self._elapsed_ms(context),
                reason=ERROR_FILE_MISSING,
            )
            self._log_stage(result, error=error)
            return result
        except Exception as exc:
            result = ProcessingResult(
                processing_id=context.processing_id,
                status=STATUS_FAILURE,
                stage=STAGE_PROCESSING,
                original_filename=context.original_filename,
                duration_ms=self._elapsed_ms(context),
                reason=reason,
            )
            self._log_stage(result, error=error or exc.__class__.__name__)
            return result

    def _reject_file(
        self,
        processing_path: Path,
        context: ProcessingContext,
        reason: str,
        stage: str,
        barcode: str | None = None,
        barcode_format: str | None = None,
        barcode_orientation_degrees: int | None = None,
        barcode_matches_business_rule: bool | None = None,
        page_count: int | None = None,
        raw_detection_count: int | None = None,
        candidate_values: tuple[str, ...] | None = None,
        eligible_candidate_values: tuple[str, ...] | None = None,
        page_one_eligible_values: tuple[str, ...] | None = None,
        error: str | None = None,
        quality_score: float | None = None,
        quality_issues: tuple[str, ...] | None = None,
    ) -> ProcessingResult:
        rejected_path = self._build_collision_safe_path(
            self.settings.rejected_path / self._sanitize_filename(context.original_filename),
            when=context.started_at,
            suffix_label="rejected",
        )

        try:
            self._write_journal(
                context,
                processing_path=processing_path,
                state="pending_rejection",
                stage=stage,
                barcode=barcode,
                reason=reason,
                rejected_path=rejected_path,
            )
        except Exception as exc:
            error = error or exc.__class__.__name__

        try:
            if processing_path.exists():
                move_file(processing_path, rejected_path)
            self._write_rejection_sidecar(
                rejected_path=rejected_path,
                context=context,
                reason=reason,
                stage=stage,
                barcode=barcode,
                barcode_format=barcode_format,
                barcode_orientation_degrees=barcode_orientation_degrees,
                barcode_matches_business_rule=barcode_matches_business_rule,
                page_count=page_count,
                raw_detection_count=raw_detection_count,
                candidate_values=candidate_values,
                eligible_candidate_values=eligible_candidate_values,
                page_one_eligible_values=page_one_eligible_values,
            )
        except Exception as exc:
            error = error or exc.__class__.__name__

        result = ProcessingResult(
            processing_id=context.processing_id,
            status=STATUS_FAILURE,
            stage=stage,
            original_filename=context.original_filename,
            duration_ms=self._elapsed_ms(context),
            reason=reason,
            barcode=barcode,
            barcode_format=barcode_format,
            barcode_orientation_degrees=barcode_orientation_degrees,
            barcode_matches_business_rule=barcode_matches_business_rule,
            page_count=page_count,
            raw_detection_count=raw_detection_count,
            candidate_values=candidate_values,
            eligible_candidate_values=eligible_candidate_values,
            page_one_eligible_values=page_one_eligible_values,
            rejected_path=rejected_path if rejected_path.exists() else None,
            quality_score=quality_score,
            quality_issues=quality_issues,
        )
        self._log_stage(result, error=error)
        self._remove_journal(context.processing_id)
        return result

    def _write_rejection_sidecar(
        self,
        rejected_path: Path,
        context: ProcessingContext,
        reason: str,
        stage: str,
        barcode: str | None = None,
        barcode_format: str | None = None,
        barcode_orientation_degrees: int | None = None,
        barcode_matches_business_rule: bool | None = None,
        page_count: int | None = None,
        raw_detection_count: int | None = None,
        candidate_values: tuple[str, ...] | None = None,
        eligible_candidate_values: tuple[str, ...] | None = None,
        page_one_eligible_values: tuple[str, ...] | None = None,
    ) -> None:
        meta_path = rejected_path.with_suffix(".meta.json")
        payload = {
            **self._runtime_metadata(error_code=normalize_error_code(reason)),
            "processing_id": context.processing_id,
            "reason": reason,
            "stage": stage,
            "timestamp": context.started_at.isoformat(),
            "attempts": 1,
            "original_filename": context.original_filename,
        }
        if barcode is not None:
            payload["barcode"] = barcode
        if barcode_format is not None:
            payload["barcode_format"] = barcode_format
        if barcode_orientation_degrees is not None:
            payload["barcode_orientation_degrees"] = barcode_orientation_degrees
        if barcode_matches_business_rule is not None:
            payload["barcode_matches_business_rule"] = barcode_matches_business_rule
        if page_count is not None:
            payload["pages"] = page_count
        if raw_detection_count is not None:
            payload["raw_detection_count"] = raw_detection_count
        if candidate_values is not None:
            payload["candidate_values"] = list(candidate_values)
        if eligible_candidate_values is not None:
            payload["eligible_candidate_values"] = list(eligible_candidate_values)
        if page_one_eligible_values is not None:
            payload["page_one_eligible_values"] = list(page_one_eligible_values)
        write_json_atomically(meta_path, payload)

    def _journal_dir(self) -> Path:
        return self.settings.processing_path / JOURNAL_DIR_NAME

    def _journal_path(self, processing_id: str) -> Path:
        return self._journal_dir() / f"{processing_id}.json"

    def _list_journal_files(self) -> list[Path]:
        journal_dir = self._journal_dir()
        if not journal_dir.exists():
            return []
        return sorted((path for path in journal_dir.iterdir() if path.is_file()), key=lambda path: path.name)

    def _write_journal(
        self,
        context: ProcessingContext,
        *,
        processing_path: Path,
        state: str,
        stage: str,
        barcode: str | None = None,
        reason: str | None = None,
        output_path: Path | None = None,
        rejected_path: Path | None = None,
    ) -> None:
        payload = {
            **self._runtime_metadata(error_code=normalize_error_code(reason)),
            "processing_id": context.processing_id,
            "original_filename": context.original_filename,
            "processing_path": str(processing_path.resolve()),
            "state": state,
            "stage": stage,
            "updated_at": self._now().isoformat(),
        }
        if barcode is not None:
            payload["barcode"] = barcode
        if reason is not None:
            payload["reason"] = reason
        if output_path is not None:
            payload["output_path"] = str(output_path.resolve())
        if rejected_path is not None:
            payload["rejected_path"] = str(rejected_path.resolve())
        write_json_atomically(self._journal_path(context.processing_id), payload)

    def _remove_journal(self, processing_id: str) -> None:
        self._journal_path(processing_id).unlink(missing_ok=True)

    def _recover_journal_entry(self, journal_path: Path, entry: dict[str, object]) -> None:
        processing_id = str(entry.get("processing_id") or journal_path.stem)
        original_filename = str(entry.get("original_filename") or journal_path.stem)
        journal_state = str(entry.get("state") or "claimed")
        stage = str(entry.get("stage") or STAGE_PROCESSING)
        journal_reason = str(entry.get("reason") or "").strip() or None
        processing_path = (
            Path(str(entry["processing_path"])) if entry.get("processing_path") else None
        )
        output_path = Path(str(entry["output_path"])) if entry.get("output_path") else None
        rejected_path = Path(str(entry["rejected_path"])) if entry.get("rejected_path") else None

        try:
            if processing_path is not None and processing_path.exists():
                destination = self._build_collision_safe_path(
                    self.settings.input_path / self._sanitize_filename(original_filename),
                    when=self._now(),
                    suffix_label="recovered",
                )
                move_file(processing_path, destination)
                self._log_recovery_event(
                    processing_id=processing_id,
                    original_filename=original_filename,
                    status=STATUS_SUCCESS,
                    recovery_action="requeued_processing_file",
                    journal_state=journal_state,
                    journal_path=journal_path,
                    processing_path=processing_path,
                    recovered_input_path=destination,
                )
                self._remove_journal(processing_id)
                return

            if journal_state == "pending_output" and output_path is not None and output_path.exists():
                self._log_recovery_event(
                    processing_id=processing_id,
                    original_filename=original_filename,
                    status=STATUS_SUCCESS,
                    recovery_action="finalized_output_recovery",
                    journal_state=journal_state,
                    journal_path=journal_path,
                    output_path=output_path,
                    stage=STAGE_OUTPUT,
                )
                self._remove_journal(processing_id)
                return

            if (
                journal_state == "pending_rejection"
                and rejected_path is not None
                and rejected_path.exists()
            ):
                self._log_recovery_event(
                    processing_id=processing_id,
                    original_filename=original_filename,
                    status=STATUS_SUCCESS,
                    recovery_action="finalized_rejection_recovery",
                    reason=journal_reason,
                    journal_state=journal_state,
                    journal_path=journal_path,
                    rejected_path=rejected_path,
                    stage=stage,
                )
                self._remove_journal(processing_id)
                return
        except Exception as exc:
            self._log_recovery_event(
                processing_id=processing_id,
                original_filename=original_filename,
                status=STATUS_FAILURE,
                reason=ERROR_RECOVERY_FAILED,
                error=exc.__class__.__name__,
                recovery_action="journal_recovery_failed",
                journal_state=journal_state,
                journal_path=journal_path,
                processing_path=processing_path,
                output_path=output_path,
                rejected_path=rejected_path,
                stage=stage,
            )
            return

        self._log_recovery_event(
            processing_id=processing_id,
            original_filename=original_filename,
            status=STATUS_FAILURE,
            reason=ERROR_RECOVERY_FAILED,
            recovery_action="unresolved_journal",
            journal_state=journal_state,
            journal_path=journal_path,
            processing_path=processing_path,
            output_path=output_path,
            rejected_path=rejected_path,
            stage=stage,
        )

    def _recover_orphan_processing_file(self, processing_path: Path) -> None:
        processing_id = str(uuid4())
        try:
            destination = self._build_collision_safe_path(
                self.settings.input_path / self._sanitize_filename(processing_path.name),
                when=self._now(),
                suffix_label="recovered",
            )
            move_file(processing_path, destination)
            self._log_recovery_event(
                processing_id=processing_id,
                original_filename=processing_path.name,
                status=STATUS_SUCCESS,
                recovery_action="requeued_orphan_processing_file",
                processing_path=processing_path,
                recovered_input_path=destination,
            )
        except Exception as exc:
            self._log_recovery_event(
                processing_id=processing_id,
                original_filename=processing_path.name,
                status=STATUS_FAILURE,
                reason=ERROR_RECOVERY_FAILED,
                error=exc.__class__.__name__,
                recovery_action="orphan_recovery_failed",
                processing_path=processing_path,
            )

    def _log_recovery_event(
        self,
        *,
        processing_id: str,
        original_filename: str,
        status: str,
        recovery_action: str,
        reason: str | None = None,
        error: str | None = None,
        journal_state: str | None = None,
        journal_path: Path | None = None,
        processing_path: Path | None = None,
        recovered_input_path: Path | None = None,
        output_path: Path | None = None,
        rejected_path: Path | None = None,
        stage: str = STAGE_PROCESSING,
    ) -> None:
        payload = {
            **self._runtime_metadata(error_code=normalize_error_code(reason)),
            "timestamp": self._now().isoformat(),
            "processing_id": processing_id,
            "stage": stage,
            "status": status,
            "duration_ms": 0,
            "original_filename": original_filename,
            "recovery_action": recovery_action,
        }
        if reason is not None:
            payload["reason"] = reason
        if error is not None:
            payload["error"] = error
        if journal_state is not None:
            payload["journal_state"] = journal_state
        if journal_path is not None:
            payload["journal_path"] = str(journal_path.resolve())
        if processing_path is not None:
            payload["processing_path"] = str(processing_path.resolve())
        if recovered_input_path is not None:
            payload["recovered_input_path"] = str(recovered_input_path.resolve())
        if output_path is not None:
            payload["output_path"] = str(output_path.resolve())
        if rejected_path is not None:
            payload["rejected_path"] = str(rejected_path.resolve())
        append_jsonl(self.settings.log_file, payload)

    def _list_input_files(self) -> list[Path]:
        return sorted(
            (path for path in self.settings.input_path.iterdir() if path.is_file()),
            key=self._input_sort_key,
        )

    def _input_sort_key(self, path: Path) -> tuple[float, str]:
        stat_result = path.stat()
        created = getattr(stat_result, "st_birthtime", stat_result.st_ctime)
        return (created, path.name.lower())

    def _stability_state(self, path: Path) -> str:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            self._observations.pop(path, None)
            return "waiting"

        now = time.monotonic()
        observation = self._observations.get(path)
        if observation is None:
            self._observations[path] = FileObservation(
                size=size,
                first_observed_monotonic=now,
                stable_checks=0,
            )
            return "waiting"

        observed_duration_ms = int((now - observation.first_observed_monotonic) * 1000)
        if observation.size != size:
            if observed_duration_ms >= FILE_STABILITY_TIMEOUT_MS:
                return "file_locked"
            self._observations[path] = FileObservation(
                size=size,
                first_observed_monotonic=observation.first_observed_monotonic,
                stable_checks=0,
            )
            return "waiting"

        stable_checks = observation.stable_checks + 1
        self._observations[path] = FileObservation(
            size=size,
            first_observed_monotonic=observation.first_observed_monotonic,
            stable_checks=stable_checks,
        )

        if stable_checks >= self._required_stable_checks():
            return "ready"
        if observed_duration_ms >= FILE_STABILITY_TIMEOUT_MS:
            return "file_locked"
        return "waiting"

    def _required_stable_checks(self) -> int:
        poll_interval_ms = max(1, self.settings.poll_interval_ms)
        return max(1, (self.settings.file_stability_delay_ms + poll_interval_ms - 1) // poll_interval_ms)

    def _build_output_path(self, barcode: str, when: datetime) -> Path:
        target_dir = self.settings.output_path / when.strftime("%Y") / when.strftime("%m")
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_barcode = self._sanitize_filename_component(barcode, fallback="barcode")
        return target_dir / f"{safe_barcode}.pdf"

    def _build_timestamped_output_path(self, barcode: str, when: datetime) -> Path:
        target_dir = self.settings.output_path / when.strftime("%Y") / when.strftime("%m")
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_barcode = self._sanitize_filename_component(barcode, fallback="barcode")
        timestamp = when.strftime("%Y%m%d_%H%M%S")
        candidate = target_dir / f"{safe_barcode}_{timestamp}.pdf"
        if not candidate.exists():
            return candidate

        index = 1
        while True:
            retry_candidate = target_dir / f"{safe_barcode}_{timestamp}_{index:02d}.pdf"
            if not retry_candidate.exists():
                return retry_candidate
            index += 1

    def _build_collision_safe_path(
        self,
        destination: Path,
        when: datetime,
        suffix_label: str,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            return destination

        timestamp = when.strftime("%Y%m%d_%H%M%S")
        stem = self._sanitize_filename_component(destination.stem, fallback="file")
        suffix = destination.suffix
        index = 1

        while True:
            candidate = destination.with_name(
                f"{stem}_{suffix_label}_{timestamp}_{index:02d}{suffix}"
            )
            if not candidate.exists():
                return candidate
            index += 1

    def _sanitize_filename(self, filename: str) -> str:
        sanitized = filename.replace(" ", "_")
        sanitized = INVALID_FILENAME_CHARS.sub("", sanitized)
        sanitized = sanitized.rstrip(" .")
        return sanitized or "file"

    def _sanitize_filename_component(self, value: str, fallback: str) -> str:
        sanitized = value.replace(" ", "_")
        sanitized = INVALID_FILENAME_CHARS.sub("", sanitized)
        sanitized = sanitized.rstrip(" .")
        return sanitized or fallback

    def _normalize_barcode_text(self, barcode: str) -> str:
        return "".join(character for character in barcode.strip() if character.isprintable())

    def _ensure_within_timeout(self, context: ProcessingContext) -> None:
        if self._elapsed_ms(context) > MAX_PROCESSING_DURATION_MS:
            raise ProcessingTimeoutError("File processing exceeded the hard timeout.")

    def _elapsed_ms(self, context: ProcessingContext) -> int:
        return int((time.monotonic() - context.start_monotonic) * 1000)

    def _log_stage(self, result: ProcessingResult, error: str | None = None) -> None:
        payload = {
            **self._runtime_metadata(error_code=normalize_error_code(result.reason)),
            "timestamp": self._now().isoformat(),
            "processing_id": result.processing_id,
            "stage": result.stage,
            "status": result.status,
            "duration_ms": result.duration_ms,
            "original_filename": result.original_filename,
        }
        if result.reason is not None:
            payload["reason"] = result.reason
        if result.barcode is not None:
            payload["barcode"] = result.barcode
        if result.barcode_format is not None:
            payload["barcode_format"] = result.barcode_format
        if result.barcode_orientation_degrees is not None:
            payload["barcode_orientation_degrees"] = result.barcode_orientation_degrees
        if result.barcode_matches_business_rule is not None:
            payload["barcode_matches_business_rule"] = result.barcode_matches_business_rule
        if result.page_count is not None:
            payload["pages"] = result.page_count
        if result.raw_detection_count is not None:
            payload["raw_detection_count"] = result.raw_detection_count
        if result.candidate_values is not None:
            payload["candidate_values"] = list(result.candidate_values)
        if result.eligible_candidate_values is not None:
            payload["eligible_candidate_values"] = list(result.eligible_candidate_values)
        if result.page_one_eligible_values is not None:
            payload["page_one_eligible_values"] = list(result.page_one_eligible_values)
        if result.output_path is not None:
            payload["output_path"] = str(result.output_path.resolve())
        if result.rejected_path is not None:
            payload["rejected_path"] = str(result.rejected_path.resolve())
        if result.quality_score is not None:
            payload["quality_score"] = round(result.quality_score, 1)
        if result.quality_issues is not None:
            payload["quality_issues"] = list(result.quality_issues)
        if error is not None:
            payload["error"] = error
        append_jsonl(self.settings.log_file, payload)

    def log_service_event(self, event_type: str, *, error: str | None = None) -> None:
        now = self._now()
        payload = {
            **self._runtime_metadata(error_code=None),
            "timestamp": now.isoformat(),
            "processing_id": self.instance_id,
            "stage": STAGE_SERVICE,
            "status": STATUS_SUCCESS,
            "duration_ms": 0,
            "original_filename": "(service lifecycle)",
            "event_type": event_type,
            "input_backlog_count": self._count_files(self.settings.input_path),
            "processing_count": self._count_processing_files(),
            "journal_count": len(self._list_journal_files()),
            "oldest_input_age_seconds": self._oldest_input_age_seconds(now),
        }
        if error is not None:
            payload["error"] = error
        append_jsonl(self.settings.log_file, payload)

    def _emit_heartbeat(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and self._last_heartbeat_monotonic is not None
            and now - self._last_heartbeat_monotonic < HEARTBEAT_INTERVAL_SECONDS
        ):
            return

        self.log_service_event(SERVICE_EVENT_HEARTBEAT)
        self._last_heartbeat_monotonic = now

    def _runtime_metadata(self, *, error_code: str | None) -> dict[str, str | None]:
        return {
            LOG_FIELD_SCHEMA_VERSION: LOG_SCHEMA_VERSION,
            LOG_FIELD_WORKFLOW: self.settings.workflow_key,
            LOG_FIELD_HOST: self.host,
            LOG_FIELD_INSTANCE_ID: self.instance_id,
            LOG_FIELD_CONFIG_VERSION: self.settings.config_version,
            LOG_FIELD_ERROR_CODE: error_code,
        }

    def _new_context(self, original_filename: str) -> ProcessingContext:
        return ProcessingContext(
            processing_id=str(uuid4()),
            original_filename=original_filename,
            started_at=self._now(),
            start_monotonic=time.monotonic(),
        )

    def _now(self) -> datetime:
        return datetime.now().astimezone()

    def _count_files(self, directory: Path) -> int:
        if not directory.exists():
            return 0
        return sum(1 for path in directory.iterdir() if path.is_file())

    def _count_processing_files(self) -> int:
        if not self.settings.processing_path.exists():
            return 0
        return sum(
            1
            for path in self.settings.processing_path.iterdir()
            if path.is_file()
        )

    def _oldest_input_age_seconds(self, now: datetime) -> int | None:
        if not self.settings.input_path.exists():
            return None

        oldest_timestamp: float | None = None
        for path in self.settings.input_path.iterdir():
            if not path.is_file():
                continue
            stat_result = path.stat()
            created = getattr(stat_result, "st_birthtime", stat_result.st_ctime)
            if oldest_timestamp is None or created < oldest_timestamp:
                oldest_timestamp = created

        if oldest_timestamp is None:
            return None
        return max(0, int(now.timestamp() - oldest_timestamp))
