"""Identity acceptance: every kind of person who uses Barcode Buddy, and every
job they do with it, executed against the real product in a fresh workspace.

Each line of the checklist is a real action: the real processor files real
generated scans, the full web application answers real HTTP requests with its
auth and CSRF middleware in place, and the installer checks start the web app
and the ingestion service as separate operating-system processes.

Nothing here touches an installed customer runtime. A line that cannot be
proven on this host is recorded as BLOCKED with the reason; it never passes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(REPO))

import httpx
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from starlette.testclient import TestClient

from app import database
from app.barcode_generator import generate_barcode_image
from app.config import Settings, ensure_runtime_directories, load_settings

PASS, FAIL, BLOCKED = "PASS", "FAIL", "BLOCKED"


def pdf_pages(path_or_bytes) -> int:
    """Page count of a PDF, read with PDFium (BSD/Apache licensed)."""
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else Path(path_or_bytes).read_bytes()
    document = pdfium.PdfDocument(data)
    try:
        return len(document)
    finally:
        document.close()


def pdf_text(data: bytes) -> str:
    document = pdfium.PdfDocument(data)
    try:
        parts = []
        for index in range(len(document)):
            page = document[index]
            textpage = page.get_textpage()
            parts.append(textpage.get_text_bounded())
            textpage.close()
            page.close()
        return "".join(parts)
    finally:
        document.close()


def pdf_first_page_image(path: Path, dpi: int) -> Image.Image:
    document = pdfium.PdfDocument(Path(path).read_bytes())
    try:
        page = document[0]
        bitmap = page.render(scale=dpi / 72)
        image = bitmap.to_pil().convert("RGB")
        bitmap.close()
        page.close()
        return image
    finally:
        document.close()
JSON_HEADERS = {"Content-Type": "application/json"}
HTML = {"accept": "text/html"}


# ---------------------------------------------------------------- catalogue

IDENTITIES: list[tuple[str, str, str]] = [
    ("scanner_operator", "Scanner operator / warehouse clerk",
     "Feeds paperwork through the scanner and expects it to file itself."),
    ("receiving", "Receiving dock worker",
     "Scans packing slips against purchase orders and books stock in."),
    ("shipping", "Shipping / proof-of-delivery clerk",
     "Files signed delivery receipts and books stock out."),
    ("quality", "Quality and compliance lead",
     "Files certificates and needs a record nobody can quietly change."),
    ("inventory_manager", "Inventory manager",
     "Owns the item list, labels, counts, imports, alerts and stock reports."),
    ("floor_phone", "Floor worker on a phone or tablet",
     "Looks items up and does counts standing in the aisle."),
    ("team_lead", "Department lead / manager",
     "Runs a team, hands out tasks and looks across people's stock."),
    ("office_retrieval", "Office admin / customer service",
     "Pulls a filed document when a customer or vendor asks for it."),
    ("owner_exec", "Operations owner / executive",
     "Wants to know what happened today and whether the system is healthy."),
    ("system_admin", "System admin",
     "Controls who gets in, what they can do, and what was changed by whom."),
    ("installer", "Installer / IT implementer",
     "Puts it on a Windows machine, proves it, backs it up and recovers it."),
    ("buyer", "Buyer signing off the purchase",
     "Needs the delivered product to match the written offer, no more, no less."),
]

# Things each identity commonly wants that this product does not do.
# They are outside the written offer and are never counted as passes.
NOT_PROVIDED: dict[str, list[str]] = {
    "scanner_operator": [
        "Scanning a stack of different documents as one file and having it split itself",
        "Filing paperwork that has no barcode on it (no OCR, no handwriting)",
    ],
    "receiving": [
        "Attaching the filed slip to the purchase order inside the ERP",
        "Receiving against an expected-deliveries list",
    ],
    "shipping": [
        "Checking that the delivery receipt was actually signed",
        "Attaching the receipt to the shipment record in the ERP",
    ],
    "quality": [
        "Notes, sign-offs and attachments on an individual scan record",
        "A list of certificates that are due but have not been scanned yet",
    ],
    "inventory_manager": [
        "Purchase orders, supplier records and automatic reordering",
        "Multi-site stock transfers",
    ],
    "floor_phone": [
        "A native phone app for scanning paperwork into the filing folder",
        "Camera scanning in Firefox (Chrome and Edge only)",
    ],
    "team_lead": [
        "Shift, daily and quarterly workload reports",
        "A queue of overdue scans by assignee",
    ],
    "office_retrieval": [
        "Searching filed documents inside the web app (retrieval is by folder and file name)",
        "Searching by words printed on the document",
    ],
    "owner_exec": [
        "Tomorrow's workload forecast",
        "Quarter-over-quarter reporting",
    ],
    "system_admin": [
        "Single sign-on with the company directory",
        "Two-factor login",
    ],
    "installer": [
        "Shipping logs to an outside log system",
        "Config overrides by environment variable (only the secret key)",
    ],
    "buyer": [
        "Multi-site deployment under one purchase",
        "Custom features for one customer",
    ],
}


@dataclass
class Result:
    identity: str
    check_id: str
    text: str
    state: str
    detail: str = ""


@dataclass
class Run:
    results: list[Result] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)

    def _next_id(self, identity: str) -> str:
        self.counters[identity] = self.counters.get(identity, 0) + 1
        return f"{identity}-{self.counters[identity]:02d}"

    def check(self, identity: str, text: str, fn: Callable[[], Any]) -> bool:
        check_id = self._next_id(identity)
        try:
            observed = fn()
            detail = "" if observed is None else str(observed)[:300]
            self.results.append(Result(identity, check_id, text, PASS, detail))
            print(f"  PASS    {check_id}  {text}", flush=True)
            return True
        except Exception as exc:  # a failed line must never stop the run
            tail = traceback.extract_tb(exc.__traceback__)[-1]
            detail = f"{type(exc).__name__}: {str(exc)[:500]} (line {tail.lineno})"
            self.results.append(Result(identity, check_id, text, FAIL, detail))
            print(f"  FAIL    {check_id}  {text}\n            {detail}", flush=True)
            return False

    def blocked(self, identity: str, text: str, why: str) -> None:
        check_id = self._next_id(identity)
        self.results.append(Result(identity, check_id, text, BLOCKED, why))
        print(f"  BLOCKED {check_id}  {text}\n            {why}", flush=True)


def need(condition: Any, detail: Any = "") -> None:
    if not condition:
        raise AssertionError(str(detail)[:500])


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# ---------------------------------------------------------------- fixtures

def slip_page(barcodes: list[tuple[str, str]], rotate: int = 0) -> Image.Image:
    """A letter-size page that looks like a slip: header, ruled lines, barcodes."""
    page = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(page)
    draw.rectangle([100, 100, 1600, 170], fill=(25, 25, 25))
    draw.text((120, 200), "PACKING SLIP / DELIVERY RECEIPT", fill=(0, 0, 0))
    for row in range(14):
        top = 1100 + row * 60
        draw.line([100, top, 1600, top], fill=(150, 150, 150), width=2)
        draw.text((120, top + 15), f"LINE {row + 1:02d}   QTY 10   EACH", fill=(60, 60, 60))
    y = 320
    for value, fmt in barcodes:
        code = generate_barcode_image(value, format=fmt, scale=4).convert("RGB")
        page.paste(code, (220, y))
        y += code.height + 160
    if rotate:
        page = page.rotate(rotate, expand=True, fillcolor="white")
    return page


def save_pdf(pages: list[Image.Image], destination: Path) -> Path:
    pages[0].save(destination, "PDF", resolution=200.0, save_all=True, append_images=pages[1:])
    return destination


def save_image(page: Image.Image, destination: Path) -> Path:
    if destination.suffix.lower() in {".jpg", ".jpeg"}:
        page.save(destination, "JPEG", quality=88)
    else:
        page.save(destination)
    return destination


def workflow_settings(root: Path, key: str, pattern: str, duplicates: str) -> Settings:
    base = root / key
    settings = Settings(
        input_path=base / "input", processing_path=base / "processing",
        output_path=base / "output", rejected_path=base / "rejected", log_path=base / "logs",
        barcode_types=("code128", "auto"), barcode_value_patterns=(pattern,),
        scan_all_pages=True, duplicate_handling=duplicates, file_stability_delay_ms=500,
        max_pages_scan=50, poll_interval_ms=200, server_host="127.0.0.1",
        workflow_key=key, secret_key="identity-acceptance-secret-0123456789abcdef",
    )
    ensure_runtime_directories(settings)
    return settings


def outputs_for(settings: Settings, barcode: str) -> list[Path]:
    return sorted(p for p in settings.output_path.rglob("*.pdf") if p.name.startswith(barcode))


def sidecar_for(rejected: Path) -> Path:
    for candidate in (rejected.with_suffix(".meta.json"), Path(str(rejected) + ".meta.json")):
        if candidate.is_file():
            return candidate
    raise AssertionError(f"no sidecar beside {rejected.name}")


# ---------------------------------------------------------------- filing

def filing_checks(run: Run, root: Path) -> dict[str, Any]:
    """Scanner operator, receiving, shipping and quality: the paperwork side."""
    from app.processor import BarcodeBuddyService

    fixtures = root / "fixtures"
    fixtures.mkdir()
    receiving = workflow_settings(root, "receiving", r"^PO-[0-9]+$", "reject")
    shipping = workflow_settings(root, "shipping_pod", r"^SHP-[0-9]+$", "timestamp")
    quality = workflow_settings(root, "quality_compliance", r"^QC-[0-9]+$", "reject")
    now = datetime.now()
    dated = Path(f"{now:%Y}") / f"{now:%m}"

    def feed(service: Any, settings: Settings, source: Path, name: str | None = None) -> Any:
        target = settings.input_path / (name or source.name)
        shutil.copyfile(source, target)
        return service.process_file(target)

    def filed(settings: Settings, result: Any, barcode: str) -> Path:
        need(result.status == "success", f"status={result.status} reason={result.reason}")
        need(result.barcode == barcode, f"barcode={result.barcode}")
        expected = settings.output_path / dated / f"{barcode}.pdf"
        need(result.output_path is not None and result.output_path.is_file(), "no output file")
        need(result.output_path.resolve() == expected.resolve(),
             f"filed at {result.output_path}, expected {expected}")
        return result.output_path

    def rejected(result: Any, reason: str | tuple[str, ...], source: Path) -> Path:
        reasons = (reason,) if isinstance(reason, str) else reason
        need(result.status == "failure", f"status={result.status}")
        need(result.reason in reasons, f"reason={result.reason}, expected one of {reasons}")
        need(result.rejected_path is not None and result.rejected_path.is_file(), "nothing in rejected")
        need(sha256(result.rejected_path) == sha256(source), "rejected copy differs from the original scan")
        meta = json.loads(sidecar_for(result.rejected_path).read_text(encoding="utf-8"))
        need(meta.get("reason") == result.reason, f"sidecar reason={meta.get('reason')}")
        return result.rejected_path

    # --- scanner operator ---------------------------------------------------
    op = "scanner_operator"
    svc = BarcodeBuddyService(receiving)
    state: dict[str, Any] = {"receiving": receiving, "shipping": shipping, "quality": quality}
    try:
        pdf = save_pdf([slip_page([("PO-100001", "Code128")])], fixtures / "scan-pdf.pdf")
        run.check(op, "A PDF scan with a barcode files itself as the barcode value, in this year's and month's folder",
                  lambda: filed(receiving, feed(svc, receiving, pdf), "PO-100001"))
        jpg = save_image(slip_page([("PO-100002", "Code128")]), fixtures / "scan-jpg.jpg")

        def jpg_becomes_pdf() -> str:
            out = filed(receiving, feed(svc, receiving, jpg), "PO-100002")
            pages = pdf_pages(out)
            need(pages == 1, pages)
            return out.name
        run.check(op, "A JPG scan is converted to a PDF and filed", jpg_becomes_pdf)
        png = save_image(slip_page([("PO-100003", "Code128")]), fixtures / "scan-png.png")
        run.check(op, "A PNG scan is converted to a PDF and filed",
                  lambda: filed(receiving, feed(svc, receiving, png), "PO-100003").name)

        tiff = fixtures / "scan-tiff.tiff"
        first, second = slip_page([("PO-100004", "Code128")]), slip_page([])
        first.save(tiff, "TIFF", save_all=True, append_images=[second], compression="tiff_lzw")

        def tiff_keeps_pages() -> str:
            out = filed(receiving, feed(svc, receiving, tiff), "PO-100004")
            pages = pdf_pages(out)
            need(pages == 2, f"pages={pages}")
            return "2 pages kept"
        run.check(op, "A two-page TIFF from the scanner is filed as a two-page PDF", tiff_keeps_pages)

        for index, angle in enumerate((90, 180, 270)):
            value = f"PO-10001{index}"
            turned = save_pdf([slip_page([(value, "Code128")], rotate=angle)], fixtures / f"scan-rot{angle}.pdf")
            run.check(op, f"A page fed {angle} degrees the wrong way round still files",
                      lambda t=turned, v=value: filed(receiving, feed(svc, receiving, t), v).name)

        back_page = save_pdf([slip_page([]), slip_page([("PO-100020", "Code128")])], fixtures / "scan-page2.pdf")

        def page_two() -> str:
            out = filed(receiving, feed(svc, receiving, back_page), "PO-100020")
            pages = pdf_pages(out)
            need(pages == 2, f"pages={pages}")
            return "found on page 2, both pages kept"
        run.check(op, "A multi-page scan whose barcode is on page 2 still files, with every page kept", page_two)

        blank = save_pdf([slip_page([])], fixtures / "scan-blank.pdf")
        run.check(op, "A page with no barcode goes to the rejected folder with the reason beside it, original untouched",
                  lambda: rejected(feed(svc, receiving, blank), "BARCODE_NOT_FOUND", blank).name)
        fake = fixtures / "notes.pdf"
        fake.write_bytes(b"these are meeting notes, not a scan\r\n" * 200)
        run.check(op, "A file that is not really a scan (renamed to .pdf) is rejected, not filed",
                  lambda: rejected(feed(svc, receiving, fake), ("UNSUPPORTED_FORMAT", "CORRUPT_FILE"), fake).name)
        empty = fixtures / "empty.pdf"
        empty.write_bytes(b"")

        def empty_rejected() -> str:
            result = feed(svc, receiving, empty)
            need(result.status == "failure" and result.reason in {"EMPTY_FILE", "CORRUPT_FILE", "UNSUPPORTED_FORMAT"},
                 f"{result.status}/{result.reason}")
            return result.reason
        run.check(op, "A zero-byte file from a failed scan is rejected with a reason", empty_rejected)
        run.check(op, "Nothing is left behind in the scan folder or the in-progress folder after processing",
                  lambda: need(not [p for p in receiving.input_path.iterdir() if p.is_file()]
                               and not [p for p in receiving.processing_path.iterdir() if p.is_file()],
                               "files stranded"))

        # --- receiving ---------------------------------------------------------
        rc = "receiving"
        slip = save_pdf([slip_page([("PO-200001", "Code128")])], fixtures / "slip-po.pdf")
        first_out: dict[str, Any] = {}

        def slip_files() -> str:
            out = filed(receiving, feed(svc, receiving, slip), "PO-200001")
            first_out["path"], first_out["hash"] = out, sha256(out)
            return str(out.relative_to(receiving.output_path))
        run.check(rc, "A packing slip files under its purchase order number", slip_files)
        wrong = save_pdf([slip_page([("VENDOR-77-A", "Code128")])], fixtures / "slip-vendor-code.pdf")
        run.check(rc, "A slip whose only barcode is not a PO number is rejected instead of being filed under the wrong name",
                  lambda: rejected(feed(svc, receiving, wrong), "INVALID_BARCODE_FORMAT", wrong).name)

        def duplicate_po() -> str:
            result = feed(svc, receiving, slip, "slip-po-again.pdf")
            rejected(result, "DUPLICATE_FILE", slip)
            need(sha256(first_out["path"]) == first_out["hash"], "the first filed copy changed")
            need(len(outputs_for(receiving, "PO-200001")) == 1, "more than one filed copy")
            return "second copy flagged, first copy unchanged"
        run.check(rc, "Scanning the same PO twice flags the second copy and leaves the first filed copy untouched", duplicate_po)
        two_pos = save_pdf([slip_page([("PO-200002", "Code128"), ("PO-200003", "Code128")])], fixtures / "slip-two-pos.pdf")
        run.check(rc, "A slip carrying two different PO barcodes is held for a person, never guessed",
                  lambda: rejected(feed(svc, receiving, two_pos), "AMBIGUOUS_BARCODE", two_pos).name)
        same_twice = save_pdf([slip_page([("PO-200004", "Code128"), ("PO-200004", "Code128")])], fixtures / "slip-same-twice.pdf")
        run.check(rc, "A slip with the same PO barcode printed twice still files normally",
                  lambda: filed(receiving, feed(svc, receiving, same_twice), "PO-200004").name)
        mixed = save_pdf([slip_page([("PO-200005", "Code128")]), slip_page([("PO-200006", "Code128")])], fixtures / "two-slips-one-file.pdf")
        run.check("buyer", "Two different documents scanned into one file are held for a person, never filed under one of the two numbers (splitting is excluded from the offer)",
                  lambda: rejected(feed(svc, receiving, mixed), "AMBIGUOUS_BARCODE", mixed).name)
        vendor_plus_po = save_pdf([slip_page([("VENDOR-77-A", "Code128"), ("PO-200007", "Code128")])], fixtures / "slip-vendor-and-po.pdf")
        run.check(rc, "A slip with a vendor barcode and a PO barcode files under the PO, ignoring the vendor code",
                  lambda: filed(receiving, feed(svc, receiving, vendor_plus_po), "PO-200007").name)

        # --- shipping ----------------------------------------------------------
        sh = "shipping"
        ship_svc = BarcodeBuddyService(shipping)
        try:
            pod = save_pdf([slip_page([("SHP-300001", "Code128")])], fixtures / "pod.pdf")
            run.check(sh, "A delivery receipt files under its shipment number",
                      lambda: filed(shipping, feed(ship_svc, shipping, pod), "SHP-300001").name)

            def rescan_kept() -> str:
                before = sha256(outputs_for(shipping, "SHP-300001")[0])
                result = feed(ship_svc, shipping, pod, "pod-signed-rescan.pdf")
                need(result.status == "success", f"{result.status}/{result.reason}")
                copies = outputs_for(shipping, "SHP-300001")
                need(len(copies) == 2, f"{len(copies)} copies filed")
                need(before in {sha256(c) for c in copies}, "original copy was altered")
                return ", ".join(c.name for c in copies)
            run.check(sh, "Rescanning the signed copy keeps both versions side by side, neither overwritten", rescan_kept)
            not_shipment = save_pdf([slip_page([("PO-200001", "Code128")])], fixtures / "pod-wrong-folder.pdf")
            run.check(sh, "A receiving slip dropped in the shipping folder by mistake is rejected, not filed as a delivery",
                      lambda: rejected(feed(ship_svc, shipping, not_shipment), "INVALID_BARCODE_FORMAT", not_shipment).name)
        finally:
            ship_svc.stop()

        # --- quality -----------------------------------------------------------
        qa = "quality"
        qa_svc = BarcodeBuddyService(quality)
        try:
            cert = save_pdf([slip_page([("QC-400001", "Code128")]), slip_page([])], fixtures / "cert.pdf")
            run.check(qa, "A certificate files under its quality record number",
                      lambda: filed(quality, feed(qa_svc, quality, cert), "QC-400001").name)
            run.check(qa, "A second certificate with the same record number is flagged, never silently replacing the first",
                      lambda: rejected(feed(qa_svc, quality, cert, "cert-again.pdf"), "DUPLICATE_FILE", cert).name)
        finally:
            qa_svc.stop()

        def every_rejection_explained() -> str:
            count = 0
            for settings in (receiving, shipping, quality):
                for item in settings.rejected_path.iterdir():
                    if item.is_file() and not item.name.endswith(".meta.json"):
                        meta = json.loads(sidecar_for(item).read_text(encoding="utf-8"))
                        need(meta.get("reason"), f"{item.name} has no reason")
                        count += 1
            need(count >= 6, f"only {count} rejections seen")
            return f"{count} rejected files, every one has a written reason"
        run.check(qa, "Every rejected document across all three workflows carries a written reason", every_rejection_explained)

        def log_is_traceable() -> str:
            lines = [json.loads(line) for line in receiving.log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            need(len(lines) >= 10, f"{len(lines)} log lines")
            for entry in lines:
                for key in ("schema_version", "workflow", "host", "config_version"):
                    need(key in entry, f"log line missing {key}: {entry}")
            need(any(e.get("error_code") == "BARCODE_NOT_FOUND" for e in lines), "no error_code recorded")
            return f"{len(lines)} log entries, each with workflow, host and config version"
        run.check(qa, "The processing log records every document with workflow, machine, config version and error code", log_is_traceable)
    finally:
        svc.stop()
    return state


# ---------------------------------------------------------------- web app

def rows(payload: Any, *keys: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    for key in keys:
        if isinstance(payload.get(key), list):
            return payload[key]
    for value in payload.values():
        if isinstance(value, list):
            return value
    raise AssertionError(f"no list in {str(payload)[:200]}")


def one(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, payload)
    need(isinstance(value, dict), f"no {key} in {str(payload)[:200]}")
    return value


def ok(response: Any, *codes: int) -> Any:
    expected = codes or (200,)
    need(response.status_code in expected,
         f"HTTP {response.status_code}, expected {expected}: {response.text[:300]}")
    return response


def web_checks(run: Run, root: Path, state: dict[str, Any]) -> None:
    import zxingcpp
    from app.alerts import check_stock_alerts
    from app.auth import create_reset_token
    from app.auth_routes import _reset_rate_limiter
    from app.stats import create_stats_app

    receiving: Settings = state["receiving"]
    app = create_stats_app(receiving)
    people: dict[str, dict[str, Any]] = {}

    def new_client() -> TestClient:
        return TestClient(app, follow_redirects=False)

    def signup(name: str, email: str, password: str = "floorpass123") -> Any:
        _reset_rate_limiter()
        client = new_client()
        response = client.post("/auth/api/signup", json={
            "email": email, "password": password, "display_name": name.title()})
        if response.status_code == 200:
            people[name] = {"c": client, "email": email, "password": password, "user": response.json()["user"]}
        return response

    def login(name: str, password: str | None = None) -> Any:
        _reset_rate_limiter()
        person = people[name]
        client = new_client()
        response = client.post("/auth/api/login", json={
            "email": person["email"], "password": password or person["password"]})
        if response.status_code == 200:
            person["c"] = client
            if password:
                person["password"] = password
        return response

    def c(name: str) -> TestClient:
        return people[name]["c"]

    def uid(name: str) -> str:
        return people[name]["user"]["id"]

    def with_db(fn: Callable[[Any], Any]) -> Any:
        generator = database.get_db()
        db = next(generator)
        try:
            return fn(db)
        finally:
            generator.close()

    try:
        # --- system admin: getting people in ----------------------------------
        ad = "system_admin"
        run.check(ad, "On a brand new install, an anonymous visitor is refused before anyone has an account",
                  lambda: ok(new_client().get("/api/inventory"), 401).status_code)
        run.check(ad, "The first person to sign up becomes the owner",
                  lambda: need(ok(signup("owner", "owner@warehouse.example")).json()["user"]["role"] == "owner"))
        run.check(ad, "The next person to sign up is an ordinary user, not an admin",
                  lambda: need(ok(signup("dock", "dock@warehouse.example")).json()["user"]["role"] == "user"))
        for name in ("admin", "invmgr", "lead", "viewer", "leaver", "office"):
            signup(name, f"{name}@warehouse.example")
        need(len(people) == 8, f"setup failed, only {sorted(people)} exist")

        def set_role(target: str, role: str, actor: str = "owner") -> Any:
            return c(actor).put(f"/admin/api/users/{uid(target)}/role", json={"role": role})

        def promote_all() -> str:
            ok(set_role("admin", "admin"))
            ok(set_role("invmgr", "manager"))
            ok(set_role("lead", "manager"))
            for name in ("admin", "invmgr", "lead"):
                ok(login(name))
                need(ok(c(name).get("/auth/api/me")).json()["user"]["role"] in {"admin", "manager"})
            return "admin, two managers"
        run.check(ad, "The owner can make someone an admin and make others managers", promote_all)
        run.check(ad, "An admin cannot create another admin; only the owner can",
                  lambda: ok(set_role("viewer", "admin", actor="admin"), 403).status_code)
        run.check(ad, "An ordinary user is kept out of the admin area",
                  lambda: ok(c("dock").get("/admin/api/users"), 403).status_code)
        run.check(ad, "A manager is kept out of the admin area",
                  lambda: ok(c("lead").get("/admin/api/users"), 403).status_code)

        def close_and_reopen_signup() -> str:
            ok(c("admin").put("/admin/api/settings/signup", json={"open_signup": False}))
            refused = signup("stranger", "stranger@elsewhere.example")
            need(refused.status_code == 403, f"signup returned {refused.status_code} while closed")
            ok(c("admin").put("/admin/api/settings/signup", json={"open_signup": True}))
            need(ok(c("admin").get("/admin/api/settings")).json()["open_signup"] is True)
            return "closed: refused; reopened"
        run.check(ad, "Closing signup stops strangers creating accounts; reopening it works", close_and_reopen_signup)

        def deactivate_cuts_access() -> str:
            ok(c("leaver").get("/auth/api/me"))
            ok(c("admin").put(f"/admin/api/users/{uid('leaver')}/active", json={"is_active": False}))
            ok(c("leaver").get("/auth/api/me"), 401)
            need(login("leaver").status_code in {401, 403}, "deactivated user could log in again")
            return "session dead at once, login refused"
        run.check(ad, "Deactivating someone who left cuts their access immediately, even if they are still logged in", deactivate_cuts_access)

        def reactivate() -> str:
            ok(c("admin").put(f"/admin/api/users/{uid('leaver')}/active", json={"is_active": True}))
            ok(login("leaver"))
            return "back in"
        run.check(ad, "Reactivating them lets them log in again", reactivate)

        def admin_resets_password() -> str:
            ok(c("admin").put(f"/admin/api/users/{uid('leaver')}/password", json={"new_password": "freshstart456"}))
            need(login("leaver").status_code == 401, "old password still works")
            ok(login("leaver", "freshstart456"))
            return "old password dead, new one works"
        run.check(ad, "An admin can reset a locked-out person's password; the old one stops working", admin_resets_password)

        def owner_protected() -> str:
            owner_id = uid("owner")
            ok(c("admin").put(f"/admin/api/users/{owner_id}/role", json={"role": "user"}), 403)
            ok(c("admin").put(f"/admin/api/users/{owner_id}/active", json={"is_active": False}), 403)
            ok(c("admin").delete(f"/admin/api/users/{owner_id}", headers=JSON_HEADERS), 403)
            return "demote, deactivate and delete all refused"
        run.check(ad, "No admin can demote, deactivate or delete the owner", owner_protected)

        def delete_user() -> str:
            ok(c("admin").delete(f"/admin/api/users/{uid('leaver')}", headers=JSON_HEADERS))
            emails = [u["email"] for u in rows(ok(c("admin").get("/admin/api/users")).json(), "users")]
            need("leaver@warehouse.example" not in emails, emails)
            return "gone from the user list"
        run.check(ad, "An admin can remove an account entirely", delete_user)

        def audit_trail() -> str:
            entries = rows(ok(c("admin").get("/admin/api/audit-log")).json(), "entries")
            actions = {e.get("action") for e in entries}
            need("role_change" in actions, actions)
            need(len(actions) >= 3, actions)
            return ", ".join(sorted(a for a in actions if a))
        run.check(ad, "Every role change, deactivation, password reset and deletion is in the admin audit log", audit_trail)
        run.check(ad, "An ordinary user cannot read the admin audit log",
                  lambda: ok(c("dock").get("/admin/api/audit-log"), 403).status_code)

        def short_password() -> int:
            _reset_rate_limiter()
            response = new_client().post("/auth/api/signup", json={
                "email": "weak@warehouse.example", "password": "short", "display_name": "Weak"})
            need(response.status_code in {400, 422}, response.status_code)
            return response.status_code
        run.check(ad, "Passwords shorter than eight characters are refused", short_password)

        def forged_form() -> int:
            response = c("dock").post("/api/inventory", data={"name": "Forged", "sku": "FORGED-1"})
            need(response.status_code == 403, response.status_code)
            return response.status_code
        run.check(ad, "A forged web form posted from another site is refused", forged_form)

        def reset_token_single_use() -> str:
            _reset_rate_limiter()
            ok(new_client().post("/auth/api/reset-request", json={"email": "nobody@warehouse.example"}))
            token = with_db(lambda db: create_reset_token(
                db.query(database.User).filter(database.User.email == people["office"]["email"]).first(), db))
            _reset_rate_limiter()
            ok(new_client().post("/auth/api/reset-confirm", json={"token": token, "new_password": "officepass789"}))
            again = new_client().post("/auth/api/reset-confirm", json={"token": token, "new_password": "anotherone789"})
            need(again.status_code == 400, f"reused token returned {again.status_code}")
            ok(login("office", "officepass789"))
            return "reset link works once, then is dead"
        run.check(ad, "A password reset link works once and cannot be reused; asking for one never reveals who has an account", reset_token_single_use)

        def brute_force() -> str:
            _reset_rate_limiter()
            guesser = new_client()
            codes = [guesser.post("/auth/api/login", json={"email": "owner@warehouse.example", "password": f"guess{i}xxxx"}).status_code
                     for i in range(11)]
            _reset_rate_limiter()
            need(codes[-1] == 429 and 200 not in codes, codes)
            return "locked out after 10 wrong guesses in a minute"
        run.check(ad, "Guessing passwords gets a login locked out after ten tries", brute_force)

        def ai_gated() -> str:
            page = c("dock").get("/ai/settings", headers=HTML)
            need(page.status_code != 200, "an ordinary user opened the AI provider settings")
            saved = c("dock").post("/ai/api/config", json={"mode": "cloud"})
            need(saved.status_code in {401, 403}, f"ordinary user config save returned {saved.status_code}")
            ok(c("owner").get("/ai/privacy", headers=HTML))
            return "settings owner-only, privacy page readable"
        run.check(ad, "Only the owner can set up the AI helper or its keys; everyone can read what data it sees", ai_gated)

        def ai_honest_when_off() -> str:
            response = c("dock").post("/ai/api/chat", json={"message": "what is low on stock?"})
            body = response.text.lower()
            need(response.status_code != 200 or "error" in body or "not configured" in body or "setup" in body,
                 f"chat answered with no AI configured: {response.text[:200]}")
            return f"HTTP {response.status_code}, no invented answer"
        run.check(ad, "With no AI set up, the chat says so plainly instead of making up an answer", ai_honest_when_off)

        # --- inventory manager ---------------------------------------------------
        im = "inventory_manager"
        inv = c("invmgr")
        items: dict[str, dict[str, Any]] = {}

        def create(client: TestClient, **body: Any) -> dict[str, Any]:
            return one(ok(client.post("/api/inventory", json=body), 201).json(), "item")

        def create_first() -> str:
            items["box"] = create(inv, name="Corrugated Box 12x12", sku="BOX-1212", quantity=500, unit="each",
                                  location="Aisle 3", category="Packaging", min_quantity=50, cost=1.25)
            need(items["box"]["barcode_value"], "no barcode assigned")
            return items["box"]["barcode_value"]
        run.check(im, "Creating an item gives it a barcode automatically", create_first)

        def every_label_type() -> str:
            formats = rows(ok(inv.get("/api/barcode/formats")).json(), "formats")
            names = [f["value"] if isinstance(f, dict) and "value" in f else (f.get("name") if isinstance(f, dict) else f) for f in formats]
            made = []
            for label, value in (("Code128", "LBL-C128-1"), ("QRCode", "LBL-QR-1"), ("Code39", "LBLC391"),
                                 ("DataMatrix", "LBL-DM-1"), ("EAN13", "5901234123457")):
                image = ok(inv.get("/api/barcode/preview.png", params={"value": value, "format": label}))
                need(image.content[:8] == b"\x89PNG\r\n\x1a\n", f"{label} preview is not a PNG")
                decoded = zxingcpp.read_barcodes(Image.open(io.BytesIO(image.content)))
                need(decoded and decoded[0].text == value, f"{label} label reads back as {[d.text for d in decoded]}")
                made.append(label)
            return f"{', '.join(made)} print and scan back correctly ({len(names)} formats offered)"
        run.check(im, "Labels can be made as Code 128, QR, Code 39, Data Matrix and EAN-13, and each one scans back to the right value", every_label_type)
        run.check(im, "A second item with an existing SKU is refused instead of creating a duplicate",
                  lambda: ok(inv.post("/api/inventory", json={"name": "Dup", "sku": "BOX-1212"}), 409).status_code)

        def edit_item() -> str:
            edited = one(ok(inv.put(f"/api/inventory/{items['box']['id']}", json={
                "name": "Corrugated Box 12x12x8", "location": "Aisle 4"})).json(), "item")
            need(edited["name"] == "Corrugated Box 12x12x8" and edited["location"] == "Aisle 4", edited)
            return "name and location changed"
        run.check(im, "An item's details can be edited", edit_item)

        def no_negative_edit() -> str:
            before = ok(inv.get(f"/api/inventory/{items['box']['id']}")).json()
            refused = inv.put(f"/api/inventory/{items['box']['id']}", json={"quantity": -5})
            need(refused.status_code in {400, 422}, f"a negative quantity was accepted: HTTP {refused.status_code}")
            after = ok(inv.get(f"/api/inventory/{items['box']['id']}")).json()
            need(one(after, "item")["quantity"] == one(before, "item")["quantity"], "the count changed")
            need(len(rows(after, "transactions")) == len(rows(before, "transactions")), "a history line was written")
            return "refused; count and history untouched"
        run.check(im, "Typing a negative quantity into an item's edit form is refused, and the count and history stay as they were", no_negative_edit)

        csv_text = ("name,sku,quantity,unit,location,category,cost,min_quantity,barcode_value\n"
                    "Bubble Wrap Roll,BW-100,200,roll,Aisle 1,Packaging,3.50,20,\n"
                    "Packing Tape,TAPE-01,1000,roll,Aisle 1,Supplies,0.75,100,TAPE-SCAN-001\n"
                    "Stretch Film,FILM-18,40,roll,Aisle 2,Packaging,12.00,10,\n"
                    "Edge Protector,EDGE-36,900,each,Aisle 2,Supplies,0.20,0,\n")

        def import_csv() -> str:
            result = ok(inv.post("/api/inventory/import/csv", files={"file": ("stock.csv", csv_text.encode(), "text/csv")})).json()
            need(result["created"] == 4 and result["errors"] == [], result)
            return "4 items created from the spreadsheet"
        run.check(im, "A spreadsheet of items imports in one go", import_csv)

        def reimport_updates() -> str:
            changed = csv_text.replace("Bubble Wrap Roll,BW-100,200", "Bubble Wrap Roll,BW-100,260")
            result = ok(inv.post("/api/inventory/import/csv", files={"file": ("stock.csv", changed.encode(), "text/csv")})).json()
            listing = rows(ok(inv.get("/api/inventory", params={"limit": 100})).json(), "items")
            need(len(listing) == 5, f"{len(listing)} items after re-import, expected 5")
            wrap = next(i for i in listing if i["sku"] == "BW-100")
            need(wrap["quantity"] == 260, f"quantity {wrap['quantity']}")
            return f"no duplicates, quantity updated ({result})"
        run.check(im, "Importing the spreadsheet again updates existing items by SKU instead of duplicating them", reimport_updates)

        def import_json() -> str:
            payload = json.dumps([{"name": "Pallet Label", "sku": "LBL-PAL", "quantity": 300, "category": "Labels"}]).encode()
            result = ok(inv.post("/api/inventory/import/json", files={"file": ("stock.json", payload, "application/json")})).json()
            need(result.get("created") == 1, result)
            return "1 item created"
        run.check(im, "Items can also be imported from a JSON file", import_json)

        def find_things() -> str:
            by_name = rows(ok(inv.get("/api/inventory", params={"q": "tape"})).json(), "items")
            need([i["sku"] for i in by_name] == ["TAPE-01"], by_name)
            by_cat = rows(ok(inv.get("/api/inventory", params={"category": "Supplies"})).json(), "items")
            need({i["sku"] for i in by_cat} == {"TAPE-01", "EDGE-36"}, by_cat)
            by_loc = rows(ok(inv.get("/api/inventory", params={"location": "Aisle 2"})).json(), "items")
            need({i["sku"] for i in by_loc} == {"FILM-18", "EDGE-36"}, by_loc)
            ordered = rows(ok(inv.get("/api/inventory", params={"sort": "quantity", "order": "asc", "limit": 100})).json(), "items")
            quantities = [i["quantity"] for i in ordered]
            need(quantities == sorted(quantities), quantities)
            return "search, category filter, location filter and sort all correct"
        run.check(im, "The item list can be searched by name, filtered by category and location, and sorted by quantity", find_things)

        def summary_bar() -> str:
            summary = ok(inv.get("/api/inventory/summary")).json()
            need("6" in json.dumps(summary), summary)
            cats = rows(ok(inv.get("/api/inventory/categories")).json(), "categories")
            locs = rows(ok(inv.get("/api/inventory/locations")).json(), "locations")
            need({"Packaging", "Supplies", "Labels"} <= set(cats), cats)
            need({"Aisle 1", "Aisle 2", "Aisle 4"} <= set(locs), locs)
            return f"{len(cats)} categories, {len(locs)} locations"
        run.check(im, "The summary shows how many items, categories and locations there are", summary_bar)

        def exports() -> str:
            table = list(csv.reader(io.StringIO(ok(inv.get("/api/inventory/export/csv")).text)))
            need(len(table) == 7, f"{len(table) - 1} rows exported, expected 6")
            as_json = ok(inv.get("/api/inventory/export/json")).json()
            need(len(rows(as_json, "items")) == 6, "json export count")
            filtered = list(csv.reader(io.StringIO(ok(inv.get("/api/inventory/export/csv/filtered", params={"category": "Supplies"})).text)))
            need(len(filtered) == 3, f"{len(filtered) - 1} filtered rows, expected 2")
            return "CSV 6 rows, JSON 6 items, filtered CSV 2 rows"
        run.check(im, "Stock exports to CSV and JSON, and can be exported for one category only", exports)

        def low_stock_alert() -> str:
            film = next(i for i in rows(ok(inv.get("/api/inventory", params={"q": "FILM-18"})).json(), "items"))
            items["film"] = film
            ok(inv.post(f"/api/inventory/{film['id']}/adjust", json={"quantity_change": -35, "reason": "sold", "notes": "big order"}))
            with_db(check_stock_alerts)
            alerts = rows(ok(inv.get("/api/alerts")).json(), "alerts")
            need(any("Stretch Film" in json.dumps(a) for a in alerts), f"no alert for Stretch Film in {alerts}")
            count = ok(inv.get("/api/alerts/count")).json()
            need(any(isinstance(v, int) and v >= 1 for v in count.values()), count)
            return f"alert raised at 5 left against a minimum of 10; badge {count}"
        run.check(im, "When an item drops below its minimum, a low-stock alert appears and the alert badge counts it", low_stock_alert)

        def alert_lifecycle() -> str:
            alerts = rows(ok(inv.get("/api/alerts")).json(), "alerts")
            ids = [a["id"] for a in alerts]
            ok(inv.post("/api/alerts/read", json={"alert_ids": ids[:1]}))
            ok(inv.post("/api/alerts/dismiss", json={"alert_ids": ids[:1]}))
            ok(inv.post("/api/alerts/dismiss-all", headers=JSON_HEADERS))
            count = ok(inv.get("/api/alerts/count")).json()
            need(all(v == 0 for v in count.values() if isinstance(v, int)), count)
            return "read, dismissed, dismiss-all; badge back to zero"
        run.check(im, "Alerts can be marked read, dismissed one at a time, or all cleared", alert_lifecycle)

        def alert_settings() -> str:
            ok(inv.put("/api/alerts/config", json={"alert_type": "low_stock", "enabled": True, "webhook_url": ""}))
            config = ok(inv.get("/api/alerts/config")).json()
            need("low_stock" in json.dumps(config), config)
            return "low-stock alerting on"
        run.check(im, "Low-stock alerting can be switched on and off per person", alert_settings)

        def reports() -> str:
            for path in ("/api/analytics/valuation", "/api/analytics/velocity", "/api/analytics/stock-health", "/api/analytics/transactions"):
                need(ok(inv.get(path)).json(), f"{path} empty")
            health = json.dumps(ok(inv.get("/api/analytics/stock-health")).json())
            need("Stretch Film" in health, "low item missing from stock health")
            value = json.dumps(ok(inv.get("/api/analytics/valuation")).json())
            need("Packaging" in value and "Supplies" in value, "valuation missing categories")
            return "valuation by category, top movers, stock health, transaction trends"
        run.check(im, "Stock reports show value by category and location, fastest movers, and what is low or out", reports)

        def calendar() -> str:
            today = datetime.now(timezone.utc).date()
            month = ok(inv.get("/api/calendar", params={"year": today.year, "month": today.month})).json()
            need(month, "empty month")
            day = ok(inv.get("/api/calendar/day", params={"date": today.isoformat()})).json()
            need("Stretch Film" in json.dumps(day), f"today's movement missing: {str(day)[:200]}")
            return "month view and today's movements"
        run.check(im, "The calendar shows which days had stock movement and what moved on a given day", calendar)

        def bulk_move() -> str:
            targets = [i["id"] for i in rows(ok(inv.get("/api/inventory", params={"location": "Aisle 1"})).json(), "items")]
            ok(inv.post("/api/inventory/bulk/update", json={"item_ids": targets, "location": "Mezzanine"}))
            moved = rows(ok(inv.get("/api/inventory", params={"location": "Mezzanine"})).json(), "items")
            need(len(moved) == len(targets) == 2, f"{len(moved)} moved of {len(targets)}")
            return "2 items moved to a new location at once"
        run.check(im, "Several items can be moved to a new location in one action", bulk_move)

        def archive_then_delete() -> str:
            label = next(i for i in rows(ok(inv.get("/api/inventory", params={"q": "LBL-PAL"})).json(), "items"))
            archived = one(ok(inv.put(f"/api/inventory/{label['id']}", json={"status": "archived"})).json(), "item")
            need(archived["status"] == "archived", archived)
            ok(inv.get("/api/scan/lookup", params={"code": "LBL-PAL"}), 404)
            edge = next(i for i in rows(ok(inv.get("/api/inventory", params={"q": "EDGE-36"})).json(), "items"))
            ok(inv.post("/api/inventory/bulk/delete", json={"item_ids": [edge["id"]]}))
            ok(inv.delete(f"/api/inventory/{label['id']}", headers=JSON_HEADERS))
            left = rows(ok(inv.get("/api/inventory", params={"limit": 100})).json(), "items")
            need({i["sku"] for i in left} == {"BOX-1212", "BW-100", "TAPE-01", "FILM-18"}, [i["sku"] for i in left])
            return "archived item stops scanning; bulk delete and single delete both work"
        run.check(im, "A discontinued item can be archived (it stops scanning), and items can be deleted singly or in bulk", archive_then_delete)

        def isolation() -> str:
            mine = rows(ok(c("dock").get("/api/inventory")).json(), "items")
            need(mine == [], f"dock worker sees {len(mine)} of the manager's items")
            ok(c("dock").get(f"/api/inventory/{items['box']['id']}"), 404)
            return "another user's list is empty and direct links 404"
        run.check(im, "One person's item list is private from ordinary users", isolation)

        # --- receiving: the stock side -------------------------------------------
        rc = "receiving"
        dock = c("dock")

        def dock_item() -> str:
            items["dock"] = create(dock, name="Kraft Mailer 10x13", sku="MAIL-1013", quantity=100, location="Dock 2", category="Packaging")
            found = one(ok(dock.get("/api/scan/lookup", params={"code": items["dock"]["barcode_value"]})).json(), "item")
            need(found["id"] == items["dock"]["id"], found)
            return "found by its barcode"
        run.check(rc, "Scanning an item's barcode pulls up the item", dock_item)
        run.check(rc, "Typing the SKU pulls up the same item",
                  lambda: need(one(ok(dock.get("/api/scan/lookup", params={"code": "MAIL-1013"})).json(), "item")["id"] == items["dock"]["id"]))

        def receive_stock() -> str:
            result = ok(dock.post(f"/api/inventory/{items['dock']['id']}/adjust", json={
                "quantity_change": 250, "reason": "received", "notes": "PO-200001"})).json()
            need(one(result, "item")["quantity"] == 350, result)
            return "100 + 250 received = 350"
        run.check(rc, "Booking a delivery in adds to the count and records the PO number", receive_stock)

        def history_shows_receipt() -> str:
            detail = ok(dock.get(f"/api/inventory/{items['dock']['id']}")).json()
            txns = rows(detail, "transactions")
            receipt = next(t for t in txns if t.get("reason") == "received" and t.get("quantity_change") == 250)
            need(receipt.get("quantity_after") == 350 and "PO-200001" in (receipt.get("notes") or ""), receipt)
            return f"{len(txns)} history lines; receipt shows +250 to 350 with the PO"
        run.check(rc, "The item's history shows the receipt with amount, running total and PO", history_shows_receipt)

        def label_scans_back() -> str:
            image = ok(dock.get(f"/api/inventory/{items['dock']['id']}/barcode.png"))
            decoded = zxingcpp.read_barcodes(Image.open(io.BytesIO(image.content)))
            need(decoded and decoded[0].text == items["dock"]["barcode_value"], [d.text for d in decoded])
            return "downloaded label reads back to the item's barcode"
        run.check(rc, "The item's barcode label downloads as an image and scans back to the same item", label_scans_back)

        def shared_stock() -> str:
            response = dock.get("/api/scan/lookup", params={"code": items["box"]["barcode_value"]})
            need(response.status_code == 200, f"HTTP {response.status_code}: an ordinary user cannot see an item a manager created")
            return "found"
        run.check(rc, "A dock worker can scan an item that the inventory manager set up", shared_stock)

        # --- shipping: the stock side --------------------------------------------
        sh = "shipping"

        def ship_out() -> str:
            result = ok(dock.post(f"/api/inventory/{items['dock']['id']}/adjust", json={
                "quantity_change": -40, "reason": "sold", "notes": "SHP-300001"})).json()
            need(one(result, "item")["quantity"] == 310, result)
            return "350 - 40 shipped = 310"
        run.check(sh, "Booking a shipment out reduces the count and records the shipment number", ship_out)
        run.check(sh, "The system refuses to ship more than is on hand",
                  lambda: ok(dock.post(f"/api/inventory/{items['dock']['id']}/adjust", json={
                      "quantity_change": -9999, "reason": "sold"}), 400).status_code)
        run.check(sh, "A damaged or returned unit is recorded with its own reason",
                  lambda: [ok(dock.post(f"/api/inventory/{items['dock']['id']}/adjust", json={
                      "quantity_change": change, "reason": reason, "notes": "pallet 4"})).status_code
                      for change, reason in ((-2, "damaged"), (1, "returned"))])

        def manifest_pdf() -> str:
            codes = [items["dock"]["barcode_value"], "UNKNOWN-CODE-9"]
            enriched = ok(dock.post("/api/scan-to-pdf/enrich", json={"codes": codes})).json()
            text = json.dumps(enriched)
            need("Kraft Mailer 10x13" in text and "UNKNOWN-CODE-9" in text, text[:300])
            entries = [{"code": items["dock"]["barcode_value"], "name": "Kraft Mailer 10x13", "sku": "MAIL-1013", "location": "Dock 2"},
                       {"code": "UNKNOWN-CODE-9"}]
            pdf = ok(dock.post("/api/scan-to-pdf/generate", json={"title": "Truck 7 manifest", "entries": entries}))
            need(pdf.content[:5] == b"%PDF-", "not a PDF")
            page_text = pdf_text(pdf.content)
            need("Truck 7 manifest" in page_text and "MAIL-1013" in page_text and "UNKNOWN-CODE-9" in page_text, page_text[:300])
            return "PDF lists known item with its details and keeps the unknown code"
        run.check(sh, "A list of scanned barcodes becomes a titled PDF manifest, with item details filled in and unknown codes kept", manifest_pdf)

        # --- system admin: the optional AI helper, against a local model if one is running
        ai_line = "With a local AI model switched on by the owner, the helper answers a stock question with the real number from inventory"
        ollama_url = os.environ.get("BB_ACCEPTANCE_OLLAMA_URL", "http://127.0.0.1:11434")
        try:
            tagged = httpx.get(ollama_url + "/api/tags", timeout=5).json().get("models", [])
            capable = [m["name"] for m in tagged if "tools" in (m.get("capabilities") or [])
                       and "embedding" not in (m.get("capabilities") or [])]
        except Exception:
            capable = []
        preferred = [name for name in ("qwen3.5:4b", "granite4.2:8b", "granite4.2:3b") if name in capable]
        model = (preferred or capable or [None])[0]
        if model is None:
            run.blocked(ad, ai_line, f"No local AI model with tool support is reachable at {ollama_url}. The product works with AI off; this line needs a model on the machine.")
        else:
            def ai_answers() -> str:
                boss = c("owner")
                for step, data in (("choose_mode", {"mode": "local"}), ("ollama_url", {"url": ollama_url}),
                                   ("ollama_model", {"chat_model": model}), ("complete", {})):
                    ok(boss.post("/ai/api/setup-step", json={"step": step, "data": data}))
                on_hand = one(ok(dock.get(f"/api/inventory/{items['dock']['id']}")).json(), "item")["quantity"]
                reply = ok(dock.post("/ai/api/chat", json={
                    "message": "Look up SKU MAIL-1013 in inventory. How many units are on hand right now? Reply with the number."})).json()
                need(not reply.get("error"), f"AI error: {reply.get('error')}")
                answer = reply["message"]["content"]
                need(str(on_hand) in answer.replace(",", ""), f"expected {on_hand} in the answer, got: {answer[:300]}")
                return f"{model} answered with the real count of {on_hand}"
            run.check(ad, ai_line, ai_answers)

        # --- floor worker on a phone ---------------------------------------------
        fp = "floor_phone"
        pages = ["/", "/inventory", "/inventory/new", "/inventory/import", "/inventory/bulk", "/scan", "/scan-to-pdf",
                 "/calendar", "/analytics", "/alerts", "/activity", "/team", "/feedback", "/auth/profile",
                 f"/inventory/{items['dock']['id']}"]

        def login_page_phone() -> str:
            body = ok(new_client().get("/auth/login", headers=HTML)).text
            need('name="viewport"' in body and "width=device-width" in body, "login page has no phone viewport")
            return "login page declares a phone-width layout"
        run.check(fp, "The login page is laid out for a phone screen", login_page_phone)

        def open_page(path: str) -> Any:
            response = dock.get(path, headers=HTML)
            if response.status_code in {301, 302, 303, 307, 308}:
                response = dock.get(response.headers["location"], headers=HTML)
            return response

        def every_page_loads() -> str:
            for path in pages:
                ok(open_page(path))
            return f"{len(pages)} pages opened"
        run.check(fp, "Every screen an ordinary worker can reach opens without an error", every_page_loads)

        def every_page_phone() -> str:
            missing = [p for p in pages if "width=device-width" not in open_page(p).text]
            need(not missing, f"no phone viewport on: {missing}")
            return f"{len(pages)} pages declare a phone-width layout"
        run.check(fp, "Every one of those screens is laid out for a phone", every_page_phone)
        run.blocked(fp, "Pointing the phone camera at a barcode reads it live",
                    "Needs a physical phone camera in Chrome or Edge. The server side of the same lookup is proven above.")

        label_png = dock.get(f"/api/inventory/{items['dock']['id']}/barcode.png").content

        def photo_decodes() -> str:
            response = ok(dock.post("/api/scan-to-pdf/decode", files={"file": ("label.png", label_png, "image/png")}))
            need(items["dock"]["barcode_value"] in response.text, response.text[:300])
            return "barcode read from an uploaded photo of the label"
        run.check(fp, "A photo of a label, uploaded from the phone, is read and matched", photo_decodes)

        def sheet_decodes() -> str:
            sheet = slip_page([("COUNT-0001", "Code128"), ("COUNT-0002", "Code128"), ("COUNT-0003", "Code128")])
            buffer = io.BytesIO()
            sheet.save(buffer, "PNG")
            response = ok(dock.post("/api/scan-to-pdf/decode", files={"file": ("shelf.png", buffer.getvalue(), "image/png")}))
            found = [code for code in ("COUNT-0001", "COUNT-0002", "COUNT-0003") if code in response.text]
            need(len(found) == 3, f"only {found} read from the photo")
            return "3 labels read from one photo"
        run.check(fp, "One photo of a shelf with several labels reads all of them for a count", sheet_decodes)
        run.check(fp, "Scanning something that is not in the system says so cleanly instead of erroring",
                  lambda: ok(dock.get("/api/scan/lookup", params={"code": "NOT-A-REAL-CODE"}), 404).status_code)

        def expired_goes_to_login() -> str:
            response = new_client().get("/inventory", headers=HTML)
            need(response.status_code in {302, 303, 307} and "/auth/login" in response.headers.get("location", ""),
                 f"HTTP {response.status_code} to {response.headers.get('location')}")
            return "sent to the login page"
        run.check(fp, "When the login has expired, the worker is sent to the login page, not shown an error", expired_goes_to_login)

        def own_profile() -> str:
            ok(dock.put("/auth/api/me/profile", json={"display_name": "Dock Two"}))
            need(ok(dock.get("/auth/api/me")).json()["user"]["display_name"] == "Dock Two")
            ok(dock.put("/auth/api/me/password", json={"current_password": people["dock"]["password"], "new_password": "newdockpass88"}))
            need(login("dock").status_code == 401, "old password still works")
            ok(login("dock", "newdockpass88"))
            return "name changed; password changed and old one refused"
        run.check(fp, "A worker can change their own display name and password", own_profile)
        dock = c("dock")

        def feedback() -> str:
            ok(dock.post("/api/feedback", json={"feedback_type": "bug", "message": "Label printer prints off-centre on dock 2"}))
            saved = [p for p in receiving.log_path.rglob("feedback*.jsonl")]
            need(saved and "off-centre" in saved[0].read_text(encoding="utf-8"), "feedback was not written to disk")
            return "saved on the local machine"
        run.check(fp, "A worker can report a problem from inside the app and it is saved", feedback)

        def logout() -> str:
            leaving = new_client()
            _reset_rate_limiter()
            ok(leaving.post("/auth/api/login", json={"email": people["dock"]["email"], "password": people["dock"]["password"]}))
            ok(leaving.get("/auth/api/me"))
            leaving.post("/auth/api/logout", headers=JSON_HEADERS)
            ok(leaving.get("/auth/api/me"), 401)
            return "logged out; the old session no longer works"
        run.check(fp, "Logging out on a shared device really ends the session", logout)

        # --- department lead -------------------------------------------------------
        tl = "team_lead"
        lead = c("lead")
        team: dict[str, Any] = {}

        def create_team() -> str:
            team.update(one(ok(lead.post("/team/api/teams", json={"name": "Receiving", "description": "Dock crew"}), 200, 201).json(), "team"))
            return team["name"]
        run.check(tl, "A manager can create a team", create_team)
        run.check(tl, "An ordinary user cannot create a team",
                  lambda: ok(dock.post("/team/api/teams", json={"name": "Rogue"}), 403).status_code)
        members: dict[str, str] = {}

        def add_members() -> str:
            for name, role in (("dock", "member"), ("viewer", "viewer")):
                ok(lead.post(f"/team/api/teams/{team['id']}/members", json={"user_id": uid(name), "team_role": role}), 200, 201)
            detail = one(ok(lead.get(f"/team/api/teams/{team['id']}")).json(), "team")
            for member in detail["members"]:
                members[member["user_id"]] = member["id"]
            need(uid("dock") in members and uid("viewer") in members, detail)
            return f"{len(members)} people on the team"
        run.check(tl, "The lead can add people to the team as member or viewer", add_members)
        task: dict[str, Any] = {}

        def create_task() -> str:
            task.update(one(ok(lead.post(f"/team/api/teams/{team['id']}/tasks", json={
                "title": "Count aisle 3", "description": "Full count before Friday", "assigned_to": uid("dock"),
                "priority": "high", "due_date": "2030-01-15"}), 200, 201).json(), "task"))
            need(task["title"] == "Count aisle 3", task)
            return "task with assignee, priority and due date"
        run.check(tl, "The lead can hand out a task with an owner, a priority and a due date", create_task)
        run.check(tl, "A task cannot be assigned to someone who is not on the team",
                  lambda: need(lead.post(f"/team/api/teams/{team['id']}/tasks", json={
                      "title": "Wrong person", "assigned_to": uid("office")}).status_code in {400, 403, 404, 422}))

        def member_updates_own() -> str:
            updated = one(ok(c("dock").put(f"/team/api/teams/{team['id']}/tasks/{task['id']}", json={"status": "in_progress"})).json(), "task")
            need(updated["status"] == "in_progress", updated)
            return "status moved to in progress"
        run.check(tl, "The person a task is assigned to can update its status", member_updates_own)
        run.check(tl, "A viewer can see the team but cannot change its tasks",
                  lambda: [ok(c("viewer").get(f"/team/api/teams/{team['id']}")).status_code,
                           ok(c("viewer").put(f"/team/api/teams/{team['id']}/tasks/{task['id']}", json={"status": "done"}), 403).status_code])
        run.check(tl, "Someone who is not on the team cannot open it",
                  lambda: need(c("office").get(f"/team/api/teams/{team['id']}").status_code in {403, 404}))

        def change_and_remove_member() -> str:
            ok(lead.put(f"/team/api/teams/{team['id']}/members/{members[uid('viewer')]}", json={"team_role": "member"}))
            ok(lead.delete(f"/team/api/teams/{team['id']}/members/{members[uid('viewer')]}", headers=JSON_HEADERS))
            need(c("viewer").get(f"/team/api/teams/{team['id']}").status_code in {403, 404}, "removed member still has access")
            return "role changed, then removed and access gone"
        run.check(tl, "The lead can change someone's team role and remove them, which ends their access", change_and_remove_member)

        def sees_reports_stock() -> str:
            listing = rows(ok(lead.get("/api/inventory", params={"view_user": uid("dock")})).json(), "items")
            need([i["sku"] for i in listing] == ["MAIL-1013"], listing)
            return "manager can read a team member's item list"
        run.check(tl, "A manager can look at a team member's stock", sees_reports_stock)

        def tidy_team() -> str:
            ok(lead.delete(f"/team/api/teams/{team['id']}/tasks/{task['id']}", headers=JSON_HEADERS))
            ok(lead.put(f"/team/api/teams/{team['id']}", json={"name": "Receiving and Returns", "description": "Dock crew"}))
            return "task deleted, team renamed"
        run.check(tl, "The lead can delete a task and rename the team", tidy_team)

        def close_team() -> str:
            ok(lead.delete(f"/team/api/teams/{team['id']}", headers=JSON_HEADERS), 403)
            ok(c("admin").delete(f"/team/api/teams/{team['id']}", headers=JSON_HEADERS))
            need(c("admin").get(f"/team/api/teams/{team['id']}").status_code == 404, "deleted team still opens")
            return "manager refused; admin closed it"
        run.check(tl, "Closing a whole team down is reserved for an admin, so a manager cannot wipe a team by mistake", close_team)

        # --- quality: the record ---------------------------------------------------
        qa = "quality"
        admin = c("admin")

        def activity_filters() -> str:
            everything = rows(ok(admin.get("/api/activity", params={"limit": 200})).json(), "entries", "activities", "items")
            need(len(everything) >= 15, f"only {len(everything)} activity entries")
            inventory_only = rows(ok(admin.get("/api/activity", params={"category": "inventory", "limit": 200})).json(), "entries", "activities", "items")
            need(inventory_only and all(e.get("category") == "inventory" for e in inventory_only), "category filter leaked")
            today = datetime.now(timezone.utc).date().isoformat()
            ok(admin.get("/api/activity", params={"date_from": today, "date_to": today}))
            return f"{len(everything)} entries; {len(inventory_only)} inventory entries when filtered"
        run.check(qa, "The activity record can be filtered by kind of action and by date", activity_filters)

        def nobody_can_rewrite() -> str:
            codes = {
                "delete": admin.delete("/api/activity", headers=JSON_HEADERS).status_code,
                "put": admin.put("/api/activity", json={}).status_code,
                "owner delete": c("owner").delete("/api/activity", headers=JSON_HEADERS).status_code,
            }
            need(all(code in {404, 405} for code in codes.values()), codes)
            return "no way to delete or edit entries, even for the owner"
        run.check(qa, "Nobody, not even the owner, can delete or edit the activity record through the app", nobody_can_rewrite)

        def ledger_export() -> str:
            table = list(csv.reader(io.StringIO(ok(c("dock").get("/api/inventory/export/transactions")).text)))
            need(len(table) >= 5, f"{len(table) - 1} ledger rows")
            flat = " ".join(" ".join(row) for row in table)
            need("received" in flat and "sold" in flat and "damaged" in flat, "reasons missing from the ledger")
            return f"{len(table) - 1} ledger rows with reasons"
        run.check(qa, "The full stock ledger exports to a spreadsheet with every movement and its reason", ledger_export)

        def history_never_overwritten() -> str:
            before = rows(ok(c("dock").get(f"/api/inventory/{items['dock']['id']}")).json(), "transactions")
            ok(c("dock").post(f"/api/inventory/{items['dock']['id']}/adjust", json={"quantity_change": -1, "reason": "adjusted", "notes": "recount"}))
            after = rows(ok(c("dock").get(f"/api/inventory/{items['dock']['id']}")).json(), "transactions")
            need(len(after) == len(before) + 1, f"{len(before)} then {len(after)}")
            old_ids = {t["id"] for t in before}
            kept = [t for t in after if t["id"] in old_ids]
            need(sorted(kept, key=lambda t: t["id"]) == sorted(before, key=lambda t: t["id"]), "an earlier ledger line changed")
            return "a correction adds a line; earlier lines are unchanged"
        run.check(qa, "A correction adds a new ledger line and never alters an earlier one", history_never_overwritten)

        # --- office retrieval ------------------------------------------------------
        of = "office_retrieval"
        now = datetime.now()

        def find_by_number() -> str:
            expected = receiving.output_path / f"{now:%Y}" / f"{now:%m}" / "PO-200001.pdf"
            need(expected.is_file(), f"{expected} not there")
            pages = pdf_pages(expected)
            need(pages == 1, pages)
            image = pdf_first_page_image(expected, 200)
            values = {d.text for d in zxingcpp.read_barcodes(image)}
            need("PO-200001" in values, f"barcode on the filed copy reads {values}")
            return f"{expected.relative_to(receiving.output_path)} opens and still shows its barcode"
        run.check(of, "Knowing only the PO number, the filed PDF is at year / month / PO number, it opens, and it is the right document", find_by_number)

        def recent_on_dashboard() -> str:
            stats = json.dumps(ok(c("office").get("/api/stats")).json())
            need("PO-200007" in stats, "most recent filed document is not on the dashboard")
            return "recently filed documents are listed with their numbers"
        run.check(of, "The dashboard lists recently filed documents by number, so the office can confirm a scan arrived", recent_on_dashboard)

        def rejected_findable() -> str:
            sidecars = sorted(receiving.rejected_path.glob("*.meta.json"))
            reasons = {json.loads(s.read_text(encoding="utf-8")).get("reason") for s in sidecars}
            need({"BARCODE_NOT_FOUND", "DUPLICATE_FILE", "AMBIGUOUS_BARCODE", "INVALID_BARCODE_FORMAT"} <= reasons, reasons)
            stats = json.dumps(ok(c("office").get("/api/stats")).json())
            need("BARCODE_NOT_FOUND" in stats, "failure reasons are not on the dashboard")
            return f"{len(sidecars)} rejected scans, each with its reason; reasons also on the dashboard"
        run.check(of, "A scan that did not file can be found in the rejected folder with the reason, without calling IT", rejected_findable)

        def daily_report() -> str:
            report = Path(ok(c("office").post("/api/reports/daily", headers=JSON_HEADERS)).json()["path"])
            need(report.is_file() and report.stat().st_size > 500, f"{report} missing or empty")
            return f"{report.name} written"
        run.check(of, "A daily summary report can be produced on demand", daily_report)

        # --- operations owner --------------------------------------------------------
        ow = "owner_exec"
        owner = c("owner")

        def dashboard_numbers() -> str:
            docs = ok(owner.get("/api/stats")).json()["documents"]
            log = [json.loads(line) for line in receiving.log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            done = [e for e in log if e.get("status") in {"success", "failure"} and e.get("stage") != "service"]
            need(docs["succeeded"] >= 11 and docs["failed"] >= 7, docs)
            need(docs["succeeded"] + docs["failed"] <= len(done) + 1, f"dashboard {docs} vs {len(done)} log outcomes")
            return f"{docs['succeeded']} filed, {docs['failed']} rejected, matching what was scanned"
        run.check(ow, "The dashboard's filed and rejected counts match what was actually scanned", dashboard_numbers)
        run.check(ow, "The dashboard page itself opens for the owner",
                  lambda: need("Barcode" in ok(owner.get("/", headers=HTML)).text))

        def backlog_visible() -> str:
            waiting = receiving.input_path / "waiting.pdf"
            shutil.copyfile(root / "fixtures" / "scan-blank.pdf", waiting)
            try:
                queue = ok(owner.get("/api/queue")).json()
                need(queue["queues"]["input_backlog_count"] == 1, queue)
            finally:
                waiting.unlink()
            return "one waiting scan shown as a backlog of 1"
        run.check(ow, "If scans are piling up unprocessed, the backlog count shows it", backlog_visible)

        def health_follows_worker() -> str:
            from app.contracts import SERVICE_EVENT_STARTUP
            from app.processor import BarcodeBuddyService
            from app.runtime_lock import ServiceLock
            down = new_client().get("/health")
            need(down.status_code == 503, f"health says {down.status_code} with the filing service stopped")
            service = BarcodeBuddyService(receiving)
            lock = ServiceLock(receiving.log_path / ".service.lock", metadata={"workflow": receiving.workflow_key})
            lock.acquire()
            worker = threading.Thread(target=lambda: (service.log_service_event(SERVICE_EVENT_STARTUP), service.run_forever()), daemon=True)
            worker.start()
            try:
                deadline = time.time() + 30
                while time.time() < deadline and new_client().get("/health").status_code != 200:
                    time.sleep(0.5)
                up = new_client().get("/health")
                need(up.status_code == 200 and up.json()["status"] == "healthy", up.text)
                dropped = receiving.input_path / "hot-folder.pdf"
                save_pdf([slip_page([("PO-500001", "Code128")])], root / "fixtures" / "hot-folder.pdf")
                shutil.copyfile(root / "fixtures" / "hot-folder.pdf", dropped)
                started = time.time()
                while time.time() - started < 30 and not outputs_for(receiving, "PO-500001"):
                    time.sleep(0.25)
                elapsed = time.time() - started
                need(outputs_for(receiving, "PO-500001") and not dropped.exists(), "dropped scan was not picked up within 30 s")
                state["hot_folder_seconds"] = round(elapsed, 1)
            finally:
                service.stop()
                worker.join(timeout=20)
                lock.release()
            return f"503 when stopped, healthy when running; a dropped scan filed itself in {state['hot_folder_seconds']} s"
        run.check(ow, "The health check is red when the filing service is stopped and green when it is running", health_follows_worker)
        run.check("scanner_operator", "With the service running, a scan dropped in the folder disappears and files itself within seconds, hands off",
                  lambda: need(state.get("hot_folder_seconds") is not None and state["hot_folder_seconds"] < 30,
                               "hot folder was not proven") or f"{state['hot_folder_seconds']} s")

        def ops_feeds() -> str:
            for path in ("/api/health-score", "/api/hourly", "/api/achievements"):
                ok(owner.get(path))
            metrics = ok(owner.get("/metrics")).text
            need("barcode_buddy_documents_succeeded_total" in metrics, "metric missing")
            return "health score, hourly throughput and monitoring metrics all answer"
        run.check(ow, "Hourly throughput, a health score and monitoring metrics are available", ops_feeds)

        def end_of_day() -> str:
            stats = ok(owner.get("/api/activity/stats")).json()
            need(any(isinstance(v, int) and v >= 15 for v in stats.values()) or "today" in json.dumps(stats), stats)
            recent = rows(ok(owner.get("/api/activity/recent")).json(), "entries", "activities", "items")
            need(len(recent) >= 5, len(recent))
            return "today's totals by kind of action, plus the latest events"
        run.check(ow, "An end-of-day view shows how much happened today and the most recent actions", end_of_day)
        run.check(ow, "A read-only status page can be shown on a wall screen",
                  lambda: need(len(ok(owner.get("/client", headers=HTML)).text) > 1000))

        def owner_sees_all_stock() -> str:
            listing = rows(ok(owner.get("/api/inventory", params={"view_user": uid("invmgr"), "limit": 100})).json(), "items")
            need(len(listing) >= 3, f"owner sees {len(listing)} of the manager's items")
            return f"owner can read the manager's {len(listing)} items"
        run.check(ow, "The owner can look at anyone's stock", owner_sees_all_stock)

        def hand_over() -> str:
            ok(c("admin").post("/admin/api/transfer-ownership", json={"target_user_id": uid("dock")}), 403)
            result = ok(owner.post("/admin/api/transfer-ownership", json={"target_user_id": uid("admin")})).json()
            need(one(result, "user")["role"] == "owner", result)
            return "only the owner can hand over; the new owner is in place"
        run.check(ow, "The owner can hand the system over to someone else, and nobody else can do that", hand_over)
    finally:
        scheduler = getattr(app.state, "alert_scheduler", None)
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                pass
        database.shutdown_db()


# ---------------------------------------------------------------- installer

def wait_for(predicate: Callable[[], bool], seconds: float, step: float = 0.5) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(step)
    return False


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def find_browser() -> str | None:
    candidates = [os.environ.get("BB_ACCEPTANCE_BROWSER", ""),
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                  shutil.which("chromium") or "", shutil.which("google-chrome") or ""]
    return next((path for path in candidates if path and Path(path).is_file()), None)


def measure_phone_widths(browser: str, base: str, session: httpx.Client, work: Path) -> str:
    """Seed a little stock, then load every screen in a 375 px frame inside a
    real headless browser and read back how wide each page actually laid out."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    first_id = None
    for name, sku, quantity, minimum in (("Corrugated Box 12x12x8", "PH-BOX-1212", 500, 50),
                                         ("Stretch Film 18 in", "PH-FILM-18", 5, 10),
                                         ("Kraft Mailer 10x13", "PH-MAIL-1013", 0, 25)):
        created = session.post("/api/inventory", json={"name": name, "sku": sku, "quantity": quantity, "location": "Aisle 3",
                                                       "category": "Packaging", "min_quantity": minimum, "cost": 1.5})
        need(created.status_code == 201, created.text[:200])
        first_id = first_id or created.json()["item"]["id"]
    session.post(f"/api/inventory/{first_id}/adjust", json={"quantity_change": 250, "reason": "received", "notes": "PO-200001"})
    paths = ["/auth/login", "/", "/inventory", f"/inventory/{first_id}", "/inventory/new", "/inventory/bulk", "/scan",
             "/scan-to-pdf", "/calendar", "/analytics", "/alerts", "/activity", "/team", "/feedback", "/auth/profile"]
    cookie = "; ".join(f"{key}={value}" for key, value in session.cookies.items())
    control = "/__too_wide"  # a deliberately overflowing page: proves the measurement can see overflow
    control_page = (b"<!doctype html><html><head><meta name='viewport' content='width=device-width'></head>"
                    b"<body><div style='width:900px;height:20px'>control</div></body></html>")
    frames = f"<iframe data-p='{control}' src='{control}' style='width:375px;height:812px;border:0'></iframe>" + "".join(f"<iframe data-p='{p}' src='{p}' style='width:375px;height:812px;border:0'></iframe>" for p in paths)
    harness = ("<!doctype html><html><head><title>pending</title></head><body>" + frames + "<script>"
               "window.addEventListener('load',function(){setTimeout(function(){var out=[];"
               "document.querySelectorAll('iframe').forEach(function(f){var w=-1;try{var d=f.contentDocument;"
               "w=Math.max(d.documentElement.scrollWidth,d.body?d.body.scrollWidth:0);}catch(e){}"
               "out.push(f.getAttribute('data-p')+'='+w);});document.title='WIDTHS '+out.join(' ');},3000);});"
               "</script></body></html>").encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/__harness":
                status, kind, body = 200, "text/html", harness
            elif self.path == control:
                status, kind, body = 200, "text/html", control_page
            else:
                upstream = httpx.get(base + self.path, timeout=60,
                                     headers={"Cookie": cookie, "Accept": self.headers.get("Accept", "*/*")})
                status, kind, body = upstream.status_code, upstream.headers.get("content-type", "text/html"), upstream.content
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    work.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", "--window-size=1400,900",
             f"--user-data-dir={work / 'profile'}", "--virtual-time-budget=20000", "--dump-dom",
             f"http://127.0.0.1:{server.server_address[1]}/__harness"],
            capture_output=True, text=True, timeout=300, encoding="utf-8", errors="ignore")
    finally:
        server.shutdown()
    marker = result.stdout.find("<title>WIDTHS ")
    need(marker >= 0, f"browser did not report widths: {result.stdout[:200]} {result.stderr[-200:]}")
    report = result.stdout[marker + len("<title>WIDTHS "):result.stdout.find("</title>", marker)]
    widths = dict(entry.rsplit("=", 1) for entry in report.split())
    need(int(widths.pop(control, "0")) > 375, "the overflow control page was not detected, so the measurement proves nothing")
    need(set(widths) == set(paths), f"measured {sorted(widths)}")
    wrong = {path: width for path, width in widths.items() if int(width) != 375}
    need(not wrong, f"screens not exactly phone width (-1 means it did not load): {wrong}")
    return f"{len(widths)} screens measured, every one exactly 375 px wide"


def installer_checks(run: Run, root: Path) -> None:
    from app.acceptance import run_acceptance
    from app.customer_provisioning import provision_customer
    from app.release_backup import create_backup, verified_extract, verify_backup

    it = "installer"
    install = root / "install"
    config_path = install / "config.customer.json"
    port = free_port()
    box: dict[str, Any] = {}

    def provision() -> str:
        result = provision_customer(config_path=config_path, workflow_key="receiving", runtime_root=install / "runtime",
                                    server_port=port, barcode_value_patterns=(r"^PO-[0-9]+$",), duplicate_handling="reject")
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        need(raw["server_host"] == "127.0.0.1", f"host {raw['server_host']}")
        need(len(raw["secret_key"]) >= 32, "secret too short")
        need(result.settings.input_path.is_dir() and result.settings.output_path.is_dir(), "folders not created")
        box["settings"] = result.settings
        return "config written, this-machine-only by default, unique secret, folders created"
    run.check(it, "One command writes a customer's config: private to the machine by default, its own secret key, folders created", provision)
    need("settings" in box, "provisioning failed; installer checks cannot continue")
    settings: Settings = box["settings"]

    def no_overwrite() -> str:
        try:
            provision_customer(config_path=config_path, workflow_key="receiving", runtime_root=install / "runtime")
        except FileExistsError:
            return "refused"
        raise AssertionError("an existing customer config was overwritten")
    run.check(it, "Provisioning refuses to overwrite a config that already exists", no_overwrite)

    def bad_configs() -> str:
        good = json.loads(config_path.read_text(encoding="utf-8"))
        problems = {"typo": {**good, "outptu_path": "x"}, "mode": {**good, "duplicate_handling": "overwrite"},
                    "pattern": {**good, "barcode_value_patterns": ["([unclosed"]}}
        for name, body in problems.items():
            path = install / f"bad-{name}.json"
            path.write_text(json.dumps(body), encoding="utf-8")
            try:
                load_settings(path)
            except Exception:
                continue
            raise AssertionError(f"config with a bad {name} was accepted")
        return "misspelt key, unknown duplicate mode and broken pattern all refused at startup"
    run.check(it, "A config with a typo, an unknown setting or a broken barcode rule is refused at startup, not half-used", bad_configs)

    def starter_configs() -> str:
        keys = [load_settings(path).workflow_key for path in sorted((REPO / "configs").glob("config.*.example.json"))]
        need(set(keys) == {"receiving", "shipping_pod", "quality_compliance"}, keys)
        return ", ".join(keys)
    run.check(it, "Starter configs for receiving, shipping and quality all load", starter_configs)

    env = {k: v for k, v in os.environ.items() if k not in {"BB_SECRET_KEY", "BB_OWNER_EMAIL", "BB_CONFIG"}}
    env["PYTHONUNBUFFERED"] = "1"
    logs = install / "process-logs"
    logs.mkdir()
    procs: dict[str, subprocess.Popen | None] = {"web": None, "ingest": None}
    base = f"http://127.0.0.1:{port}"

    def start(kind: str) -> None:
        script = ["stats.py", "--config", str(config_path), "--host", "127.0.0.1", "--port", str(port)] if kind == "web" \
            else ["main.py", "--config", str(config_path)]
        handle = (logs / f"{kind}-{time.time_ns()}.log").open("w", encoding="utf-8")
        procs[kind] = subprocess.Popen([sys.executable, *script], cwd=REPO, env=env, stdout=handle, stderr=subprocess.STDOUT)

    def port_open() -> bool:
        with socket.socket() as sock:
            sock.settimeout(1)
            return sock.connect_ex(("127.0.0.1", port)) == 0

    try:
        def two_processes() -> str:
            start("web")
            start("ingest")
            need(wait_for(port_open, 90), "web app never opened its port")
            need(wait_for(lambda: httpx.get(base + "/health", timeout=5).status_code == 200, 60), "health never went green")
            need(procs["web"].poll() is None and procs["ingest"].poll() is None, "a process exited")
            return f"two separate processes up, health green on port {port}"
        run.check(it, "The web app and the filing service start as two separate programs from that config and report healthy", two_processes)

        def anonymous_refused() -> str:
            codes = {path: httpx.get(base + path, timeout=10).status_code
                     for path in ("/api/inventory", "/api/stats", "/metrics", "/admin/api/users", "/api/activity")}
            need(all(code == 401 for code in codes.values()), codes)
            return "five data endpoints all answer 401 to a stranger"
        run.check(it, "On the real running server, a stranger without a login gets nothing", anonymous_refused)
        session = httpx.Client(base_url=base, timeout=20)

        def first_owner() -> str:
            response = session.post("/auth/api/signup", json={
                "email": "it@customer.example", "password": "installpass123", "display_name": "IT"})
            need(response.status_code == 200 and response.json()["user"]["role"] == "owner", response.text[:200])
            need(session.get("/api/stats").status_code == 200, "owner cannot read stats")
            return "first account on the real server is the owner"
        run.check(it, "The first account created on the real running server becomes the owner", first_owner)

        def real_drop() -> str:
            source = save_pdf([slip_page([("PO-900001", "Code128")])], install / "real-drop.pdf")
            target = settings.input_path / "scan0001.pdf"
            shutil.copyfile(source, target)
            started = time.time()
            need(wait_for(lambda: bool(outputs_for(settings, "PO-900001")), 60, 0.25), "scan was not filed within 60 s")
            need(not target.exists(), "scan still sitting in the input folder")
            box["filed"] = outputs_for(settings, "PO-900001")[0]
            box["filed_hash"] = sha256(box["filed"])
            docs = session.get("/api/stats").json()["documents"]
            need(docs["succeeded"] >= 1, docs)
            return f"filed in {time.time() - started:.1f} s by the separate service; dashboard count went up"
        run.check(it, "With both programs running, a scan dropped in the folder is filed and the dashboard shows it", real_drop)

        phone_line = "In a real browser at phone width (375 px), no screen is wider than the phone, so nothing is cut off or needs sideways scrolling"
        browser = find_browser()
        if browser is None:
            run.blocked("floor_phone", phone_line, "No Chrome or Edge found on this machine to measure the screens in.")
        else:
            run.check("floor_phone", phone_line, lambda: measure_phone_widths(browser, base, session, install / "phone"))

        def second_instance_refused() -> str:
            extra = subprocess.run([sys.executable, "main.py", "--config", str(config_path)], cwd=REPO, env=env,
                                   capture_output=True, text=True, timeout=60)
            need(extra.returncode != 0, "a second filing service started on the same folder")
            return "second copy exits with an error instead of fighting over the same files"
        run.check(it, "Starting a second filing service on the same folder is refused", second_instance_refused)

        archive = install / "backups" / "customer-backup.zip"

        def backup() -> str:
            result = create_backup(config_path, archive, database_path=settings.log_path / "barcode_buddy.db", include_documents=True)
            need(result["verified"] is True and result["member_count"] >= 4, result)
            names = [m["path"] for m in result["manifest"]["members"]]
            need(any(n.startswith("documents/output/") for n in names) and "database/barcode_buddy.db" in names, names)
            return f"{result['member_count']} files, each with a checksum, taken while the system was running"
        run.check(it, "A backup of config, database, logs and filed documents can be taken while the system runs, with a checksum for every file", backup)

        def tamper_detected() -> str:
            damaged = install / "backups" / "damaged.zip"
            data = bytearray(archive.read_bytes())
            middle = len(data) // 2
            data[middle:middle + 64] = bytes(64)
            damaged.write_bytes(bytes(data))
            try:
                verify_backup(damaged)
            except Exception:
                return "damaged archive refused"
            raise AssertionError("a damaged backup passed verification")
        run.check(it, "A damaged backup is detected instead of being trusted", tamper_detected)

        def restore() -> str:
            target = install / "restored"
            result = verified_extract(archive, target)
            restored_pdf = next((target / "documents" / "output").rglob("PO-900001.pdf"))
            need(sha256(restored_pdf) == box["filed_hash"], "restored document differs from the filed one")
            need((target / "database" / "barcode_buddy.db").is_file(), "database missing from restore")
            try:
                verified_extract(archive, target)
            except FileExistsError:
                return f"{result['member_count']} files restored and verified; refuses to restore over existing files"
            raise AssertionError("restore overwrote an existing folder")
        run.check(it, "The backup restores to an empty folder, documents and database intact, and refuses to restore over existing files", restore)

        def survive_restart() -> str:
            stop_process(procs["ingest"])
            stop_process(procs["web"])
            need(wait_for(lambda: not port_open(), 20), "port still held after stop")
            stranded = settings.processing_path / "interrupted.pdf"
            shutil.copyfile(save_pdf([slip_page([("PO-900002", "Code128")])], install / "interrupted.pdf"), stranded)
            start("web")
            start("ingest")
            need(wait_for(port_open, 90), "web app did not come back")
            need(wait_for(lambda: bool(outputs_for(settings, "PO-900002")), 90, 0.5),
                 "the scan that was mid-process when the machine stopped was lost")
            need(sha256(box["filed"]) == box["filed_hash"], "an already-filed PDF changed across the restart")
            again = httpx.Client(base_url=base, timeout=20)
            login = again.post("/auth/api/login", json={"email": "it@customer.example", "password": "installpass123"})
            need(login.status_code == 200, f"login after restart returned {login.status_code}")
            return "port released on stop; interrupted scan recovered and filed; filed PDFs unchanged; accounts survive"
        run.check(it, "After a stop and restart, the scan that was mid-process is recovered and filed, filed PDFs are unchanged, and accounts still work", survive_restart)
    finally:
        stop_process(procs["ingest"])
        stop_process(procs["web"])
    run.check(it, "Stopping the programs releases the port cleanly",
              lambda: need(wait_for(lambda: not port_open(), 20), "port still held"))

    def sample_acceptance() -> str:
        samples = root / "samples"
        samples.mkdir()
        save_pdf([slip_page([("PO-700001", "Code128")])], samples / "normal.pdf")
        save_pdf([slip_page([("PO-700002", "Code128")], rotate=180)], samples / "upside-down.pdf")
        save_pdf([slip_page([])], samples / "blank.pdf")
        cases = [
            {"id": "normal", "file": "normal.pdf", "expected": {"status": "success", "barcode": "PO-700001"}},
            {"id": "upside-down", "file": "upside-down.pdf", "expected": {"status": "success", "barcode": "PO-700002"}},
            {"id": "blank", "file": "blank.pdf", "expected": {"status": "failure", "reason": "BARCODE_NOT_FOUND"}},
        ]
        manifest = samples / "manifest.json"
        manifest.write_text(json.dumps({"customer": "sample", "workflow": "receiving", "cases": cases}), encoding="utf-8")
        before = {p.name: sha256(p) for p in samples.glob("*.pdf")}
        report = run_acceptance(config_path, manifest, root / "sample-report")
        need(report["passed"] and report["summary"]["total"] == 3, report["summary"])
        need(before == {p.name: sha256(p) for p in samples.glob("*.pdf")}, "customer samples were modified")
        need((root / "sample-report" / "acceptance-report.md").is_file(), "no written report")
        return "3 of 3 expectations met, samples untouched, written report produced"
    run.check(it, "A customer's sample scans can be run against their config with a written pass/fail report, without touching the samples", sample_acceptance)

    def launcher_rules() -> str:
        result = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_windows_scripts.py", "-q", "-p", "no:cacheprovider"],
                                cwd=REPO, capture_output=True, text=True, timeout=600)
        summary = (result.stdout.strip().splitlines() or ["no output"])[-1]
        need(result.returncode == 0, summary)
        box["launcher_summary"] = summary
        return summary
    run.check(it, "The Windows launcher's safety rules hold: no public tunnel unless asked, never stops other programs' tunnels, this-machine-only by default, starts and supervises the filing service", launcher_rules)

    def powershell_probe() -> str:
        try:
            probe = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Write-Output ok"],
                                   capture_output=True, text=True, timeout=20)
            return "responds" if probe.stdout.strip() == "ok" else f"exit {probe.returncode}"
        except Exception as exc:
            return f"does not respond ({type(exc).__name__})"
    shell = powershell_probe()
    run.blocked(it, "The Windows launcher script itself runs end to end on a Windows machine",
                f"Windows PowerShell on this build machine {shell}. The launcher has to be run on a responsive Windows host; its rules are proven by test above ({box.get('launcher_summary', 'not run')}).")
    run.blocked(it, "The system starts by itself when the machine boots",
                "Registering the startup task needs an administrator approval on the machine itself, which cannot be given over a remote session.")
    run.blocked(it, "A real office scanner saving to a network folder feeds the system",
                "No customer scanner or network share has ever been available. Every scan in this run is a generated page.")


# ---------------------------------------------------------------- buyer

def buyer_checks(run: Run) -> None:
    by = "buyer"

    def paperwork() -> str:
        wanted = ["sales/OFFER.md", "sales/STATEMENT-OF-WORK.md", "docs/customer/INSTALL.md", "docs/customer/OPERATIONS.md",
                  "docs/customer/SECURITY.md", "docs/customer/ADMIN-RECOVERY.md", "docs/customer/ACCEPTANCE.md"]
        missing = [name for name in wanted if not (REPO / name).is_file() or (REPO / name).stat().st_size < 200]
        need(not missing, f"missing or empty: {missing}")
        return f"{len(wanted)} documents present"
    run.check(by, "The offer, statement of work, install, operations, security, recovery and acceptance documents all exist", paperwork)

    def honest_exclusions() -> str:
        offer = (REPO / "sales" / "OFFER.md").read_text(encoding="utf-8").lower()
        for word in ("excludes", "erp", "ocr", "splitting", "one physical site", "one accepted document workflow"):
            need(word in offer, f"offer does not state: {word}")
        return "one site, one workflow; ERP, OCR and splitting stated as excluded"
    run.check(by, "The written offer states plainly what is included and what is not", honest_exclusions)

    def default_name() -> str:
        from app.branding import load_branding
        need(load_branding({}).display_name == "Barcode Buddy", load_branding({}).display_name)
        need(load_branding({"BB_ORGANIZATION_NAME": "Acme Supply"}).display_name != "Barcode Buddy", "buyer name not applied")
        return "shows Barcode Buddy by default and the buyer's own name when set"
    run.check(by, "The product carries its own name by default and the buyer's name when configured", default_name)

    def nobody_elses_name() -> str:
        import re
        neutral = re.compile(r"(\.invalid|\.example|\.test|@example\.(com|org|net)|@test\.com|@x\.com|@localhost)$")
        address = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
        shipped = [*sorted((REPO / "app").glob("*.py")), *sorted(REPO.glob("*.ps1")), REPO / "main.py", REPO / "stats.py", REPO / "config.json"]
        hits = []
        for path in shipped:
            real = [a for a in address.findall(path.read_text(encoding="utf-8", errors="ignore")) if not neutral.search(a.lower())]
            if real:
                hits.append(f"{path.name} ({len(real)})")  # file and count only; never repeat the address
        need(not hits, f"a real email address is built into the program a buyer receives: {', '.join(hits)}")
        return f"{len(shipped)} shipped files carry no real person's or company's address"
    run.check(by, "No other company's name or email is built into the program a buyer receives", nobody_elses_name)
    run.blocked(by, "The release gate passes on the exact revision being delivered",
                "The gate requires the launcher to be executed under Windows PowerShell and the sales-site integration to be committed. Both are open; see the installer lines.")
    run.blocked(by, "The buyer's own documents, from the buyer's own scanner, pass acceptance",
                "No buyer exists yet. This can only be proven on a real customer's samples.")


# ---------------------------------------------------------------- report

def write_report(run: Run, output: Path, revision: str) -> dict[str, Any]:
    by_identity: dict[str, list[Result]] = {}
    for result in run.results:
        by_identity.setdefault(result.identity, []).append(result)
    total = len(run.results)
    passed = sum(1 for r in run.results if r.state == PASS)
    failed = sum(1 for r in run.results if r.state == FAIL)
    blocked = sum(1 for r in run.results if r.state == BLOCKED)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = {"schema_version": 1, "product_key": "barcodebuddy", "revision": revision, "generated_at": stamp,
               "total": total, "passed": passed, "failed": failed, "blocked": blocked,
               "all_passed": passed == total, "synthetic": True, "customer_approval": False,
               "results": [r.__dict__ for r in run.results]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "identity-acceptance.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines = ["# Barcode Buddy: who it is for, and proof it does their job", "",
             f"Run {stamp} on revision `{revision}`. Every line below was executed against the real product in a fresh workspace: "
             "the real processor filing generated scans, the full web app answering real requests, and for the installer, "
             "the web app and filing service running as separate programs.", "",
             f"**Score: {passed} of {total} proven.** {failed} failed. {blocked} could not be proven on this machine.", "",
             "| Who | Proven | Failed | Not provable here |", "| --- | --- | --- | --- |"]
    for key, title, _ in IDENTITIES:
        group = by_identity.get(key, [])
        lines.append(f"| {title} | {sum(r.state == PASS for r in group)} of {len(group)} | "
                     f"{sum(r.state == FAIL for r in group)} | {sum(r.state == BLOCKED for r in group)} |")
    mark = {PASS: "[x]", FAIL: "[ ] **FAILED**", BLOCKED: "[ ] *not provable here*"}
    for key, title, who in IDENTITIES:
        lines += ["", f"## {title}", "", who, ""]
        for result in by_identity.get(key, []):
            lines.append(f"- {mark[result.state]} {result.text}")
            if result.state != PASS:
                lines.append(f"  - {result.detail}")
        if NOT_PROVIDED.get(key):
            lines += ["", "Would also want, and this product does not do it:"]
            lines += [f"- {item}" for item in NOT_PROVIDED[key]]
    lines += ["", "Every scan in this run is a generated page, not a customer's document. "
              "A pass here proves the product revision, not a customer installation.", ""]
    (output / "identity-acceptance.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Folder for the report; must not exist yet.")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        parser.error("Refusing to write into an existing folder.")
    if database._engine is not None:
        parser.error("Refusing to run against an active database.")
    work = output / "workspace"
    work.mkdir(parents=True)
    revision = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip() or "unknown"
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    if dirty:
        revision += "+uncommitted"
    run = Run()
    for name, stage in (("filing", lambda: web_checks(run, work, filing_checks(run, work))),
                        ("installer", lambda: installer_checks(run, work)),
                        ("buyer", lambda: buyer_checks(run))):
        print(f"== {name}", flush=True)
        try:
            stage()
        except Exception as exc:
            run.results.append(Result("installer" if name == "installer" else "system_admin", f"{name}-stage",
                                      f"The {name} stage ran to the end", FAIL, f"{type(exc).__name__}: {exc}"))
            traceback.print_exc()
    summary = write_report(run, output, revision)
    print(json.dumps({k: summary[k] for k in ("total", "passed", "failed", "blocked", "all_passed")}))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
