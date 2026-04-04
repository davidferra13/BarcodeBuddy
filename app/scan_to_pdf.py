"""Scan-to-PDF: batch-scan barcodes and export a professional PDF report.

Provides three input methods:
1. Manual text entry (type/paste barcode values)
2. Camera scanning (browser BarcodeDetector API)
3. Image/document upload (decode barcodes from uploaded images or PDFs)

Session data lives client-side (localStorage). The server handles:
- Decoding barcodes from uploaded files
- Enriching barcode values with inventory data
- Generating the PDF report
"""

from __future__ import annotations

import html as html_mod
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_user
from app.database import InventoryItem, User, get_db
from app.layout import render_shell

router = APIRouter(tags=["scan-to-pdf"])

_E = html_mod.escape


# ── API: Decode barcodes from uploaded image/PDF ──────────────────

_UPLOAD_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/api/scan-to-pdf/decode")
async def decode_upload(
    file: UploadFile = File(...),
    user: User = Depends(require_user),
) -> JSONResponse:
    """Accept an image or PDF upload and return all barcodes found."""
    content = await file.read(_UPLOAD_MAX_BYTES + 1)
    if len(content) > _UPLOAD_MAX_BYTES:
        return JSONResponse(status_code=400, content={"error": "File too large. Maximum 50 MB."})

    filename = (file.filename or "upload").lower()
    results: list[dict] = []

    try:
        if filename.endswith(".pdf"):
            results = _decode_pdf(content)
        else:
            results = _decode_image(content)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": f"Failed to process file: {exc}"})

    return JSONResponse(content={
        "filename": file.filename or "upload",
        "barcodes": results,
        "count": len(results),
    })


def _decode_image(data: bytes) -> list[dict]:
    """Decode barcodes from a single image."""
    from PIL import Image
    import zxingcpp

    img = Image.open(io.BytesIO(data)).convert("RGB")
    barcodes = zxingcpp.read_barcodes(img)
    return [
        {"value": b.text, "format": b.format.name}
        for b in barcodes if b.text
    ]


def _decode_pdf(data: bytes) -> list[dict]:
    """Decode barcodes from all pages of a PDF."""
    import fitz
    from PIL import Image
    import zxingcpp

    results: list[dict] = []
    seen: set[str] = set()
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        for page_num in range(min(len(doc), 50)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            barcodes = zxingcpp.read_barcodes(img)
            for b in barcodes:
                if b.text and b.text not in seen:
                    seen.add(b.text)
                    results.append({
                        "value": b.text,
                        "format": b.format.name,
                        "page": page_num + 1,
                    })
    finally:
        doc.close()
    return results


# ── API: Enrich barcode values with inventory data ────────────────

class EnrichRequest(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=500)


@router.post("/api/scan-to-pdf/enrich")
def enrich_codes(
    body: EnrichRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Look up barcode values against the user's inventory."""
    enriched: list[dict] = []
    for code in body.codes:
        code = code.strip()
        if not code:
            continue
        item = db.query(InventoryItem).filter(
            InventoryItem.user_id == user.id,
            InventoryItem.barcode_value == code,
            InventoryItem.status == "active",
        ).first()
        if not item:
            item = db.query(InventoryItem).filter(
                InventoryItem.user_id == user.id,
                InventoryItem.sku == code,
                InventoryItem.status == "active",
            ).first()
        enriched.append({
            "code": code,
            "found": item is not None,
            "name": item.name if item else None,
            "sku": item.sku if item else None,
            "quantity": item.quantity if item else None,
            "location": item.location if item else None,
            "category": item.category if item else None,
        })
    return JSONResponse(content={"items": enriched})


# ── API: Generate PDF report ──────────────────────────────────────

class PdfEntry(BaseModel):
    code: str
    format: str = ""
    name: str = ""
    sku: str = ""
    location: str = ""
    scanned_at: str = ""


class GeneratePdfRequest(BaseModel):
    title: str = Field(default="Barcode Scan Report", max_length=200)
    entries: list[PdfEntry] = Field(min_length=1, max_length=1000)


@router.post("/api/scan-to-pdf/generate")
def generate_pdf(
    body: GeneratePdfRequest,
    user: User = Depends(require_user),
) -> Response:
    """Generate a professional PDF report from scan session data."""
    import fitz

    doc = fitz.open()
    page_width, page_height = fitz.paper_size("A4")
    margin = 50
    usable_width = page_width - 2 * margin

    # Column layout: #, Barcode Value, Format, Item Name, Location, Time
    col_widths = [
        usable_width * 0.06,   # #
        usable_width * 0.26,   # Barcode Value
        usable_width * 0.12,   # Format
        usable_width * 0.24,   # Item Name
        usable_width * 0.16,   # Location
        usable_width * 0.16,   # Time
    ]
    headers = ["#", "Barcode Value", "Format", "Item Name", "Location", "Time"]

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = body.title or "Barcode Scan Report"

    def _new_page() -> fitz.Page:
        page = doc.new_page(width=page_width, height=page_height)
        # Header bar
        page.draw_rect(fitz.Rect(0, 0, page_width, 60), color=None, fill=(0.118, 0.145, 0.188))
        page.insert_text(
            fitz.Point(margin, 38), title,
            fontsize=18, fontname="helv", color=(1, 1, 1),
        )
        page.insert_text(
            fitz.Point(page_width - margin - 150, 38), now_str,
            fontsize=9, fontname="helv", color=(0.8, 0.8, 0.8),
        )
        # Operator line
        page.insert_text(
            fitz.Point(margin, 82),
            f"Operator: {user.display_name}  |  Generated: {now_str}  |  Items: {len(body.entries)}",
            fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4),
        )
        return page

    def _draw_table_header(page: fitz.Page, y: float) -> float:
        # Header row background
        page.draw_rect(
            fitz.Rect(margin, y, margin + usable_width, y + 22),
            color=None, fill=(0.93, 0.91, 0.87),
        )
        x = margin
        for i, hdr in enumerate(headers):
            page.insert_text(
                fitz.Point(x + 4, y + 15),
                hdr, fontsize=8, fontname="helv", color=(0.3, 0.3, 0.3),
            )
            x += col_widths[i]
        return y + 22

    def _draw_row(page: fitz.Page, y: float, row_num: int, entry: PdfEntry) -> float:
        row_h = 20
        # Alternate row shading
        if row_num % 2 == 0:
            page.draw_rect(
                fitz.Rect(margin, y, margin + usable_width, y + row_h),
                color=None, fill=(0.97, 0.96, 0.94),
            )
        # Row separator
        page.draw_line(
            fitz.Point(margin, y + row_h),
            fitz.Point(margin + usable_width, y + row_h),
            color=(0.88, 0.86, 0.82), width=0.3,
        )

        x = margin
        cells = [
            str(row_num + 1),
            _truncate(entry.code, 30),
            entry.format or "—",
            _truncate(entry.name, 28) if entry.name else "—",
            _truncate(entry.location, 18) if entry.location else "—",
            entry.scanned_at[:19] if entry.scanned_at else "—",
        ]
        for i, cell in enumerate(cells):
            page.insert_text(
                fitz.Point(x + 4, y + 14),
                cell, fontsize=8, fontname="helv", color=(0.15, 0.15, 0.15),
            )
            x += col_widths[i]
        return y + row_h

    # Build pages
    page = _new_page()
    y = 100
    y = _draw_table_header(page, y)

    for idx, entry in enumerate(body.entries):
        if y + 24 > page_height - 50:
            # Footer on current page
            _draw_footer(page, page_height, doc.page_count)
            page = _new_page()
            y = 100
            y = _draw_table_header(page, y)
        y = _draw_row(page, y, idx, entry)

    # Summary section
    y += 16
    if y + 50 > page_height - 50:
        _draw_footer(page, page_height, doc.page_count)
        page = _new_page()
        y = 100

    page.draw_rect(
        fitz.Rect(margin, y, margin + usable_width, y + 36),
        color=None, fill=(0.118, 0.145, 0.188), radius=0.05,
    )
    found_count = sum(1 for e in body.entries if e.name)
    page.insert_text(
        fitz.Point(margin + 12, y + 22),
        f"Total Scanned: {len(body.entries)}    |    Matched to Inventory: {found_count}    |    Unmatched: {len(body.entries) - found_count}",
        fontsize=10, fontname="helv", color=(1, 1, 1),
    )

    _draw_footer(page, page_height, doc.page_count)

    # Output
    pdf_bytes = doc.tobytes()
    doc.close()

    safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in title).strip() or "scan-report"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{safe_title}_{timestamp}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _draw_footer(page, page_height: float, page_num: int) -> None:
    """Draw page footer with page number and branding."""
    import fitz
    page.draw_line(
        fitz.Point(50, page_height - 35),
        fitz.Point(page.rect.width - 50, page_height - 35),
        color=(0.88, 0.86, 0.82), width=0.5,
    )
    page.insert_text(
        fitz.Point(50, page_height - 20),
        f"Barcode Buddy — Scan Report  |  Page {page_num}",
        fontsize=8, fontname="helv", color=(0.6, 0.6, 0.6),
    )


def _truncate(s: str, max_len: int) -> str:
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


# ── HTML Page ─────────────────────────────────────────────────────

@router.get("/scan-to-pdf", response_class=HTMLResponse)
def scan_to_pdf_page(user: User = Depends(require_user)) -> HTMLResponse:
    body = _PAGE_HTML
    js = _PAGE_JS
    css = _PAGE_CSS
    return HTMLResponse(content=render_shell(
        title="Scan to PDF",
        active_nav="scan-to-pdf",
        body_html=body,
        body_js=js,
        head_extra=css,
        display_name=user.display_name,
        role=user.role,
    ))


_PAGE_CSS = """<style>
.stp-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
.stp-input-panel { min-height: 200px; }
.stp-session-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.stp-session-table th { text-align: left; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--muted); font-weight: 600;
  padding: 8px 10px; border-bottom: 2px solid var(--line); }
.stp-session-table td { padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: middle; }
.stp-session-table tr:hover { background: rgba(0,0,0,0.015); }
.stp-badge-found { background: var(--success-bg); color: var(--success);
  padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
  border: 1px solid var(--success-border); }
.stp-badge-unknown { background: rgba(44,54,63,0.06); color: var(--muted);
  padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.stp-remove-btn { background: none; border: none; color: var(--failure); cursor: pointer;
  font-size: 16px; padding: 2px 6px; border-radius: 4px; transition: background 0.15s; }
.stp-remove-btn:hover { background: var(--failure-bg); }
.stp-count-badge { display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 22px; border-radius: 11px; font-size: 12px; font-weight: 700;
  background: var(--sidebar-accent); color: #fff; padding: 0 6px; }
.stp-dropzone { border: 2px dashed var(--line); border-radius: 12px; padding: 32px 20px;
  text-align: center; cursor: pointer; transition: all 0.2s; background: var(--paper); }
.stp-dropzone:hover, .stp-dropzone.drag-over { border-color: var(--info); background: var(--info-bg); }
.stp-tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 2px solid var(--line); }
.stp-tab { padding: 10px 20px; font-size: 13px; font-weight: 600; color: var(--muted);
  cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.15s;
  background: none; border-top: none; border-left: none; border-right: none; font-family: inherit; }
.stp-tab:hover { color: var(--text); }
.stp-tab.active { color: var(--info); border-bottom-color: var(--info); }
.stp-tab-content { display: none; }
.stp-tab-content.active { display: block; }
.stp-cam-box { background: #000; border-radius: 10px; overflow: hidden; position: relative; min-height: 240px; }
.stp-cam-box video { width: 100%; display: block; }
@media (max-width: 900px) {
  .stp-grid { grid-template-columns: 1fr; }
}
</style>"""

_PAGE_HTML = """
<p class="page-desc">Batch-scan barcodes from manual entry, camera, or document upload — then export a clean PDF report.</p>

<div class="stp-grid">
  <!-- Left: Input Methods -->
  <div>
    <div class="panel stp-input-panel">
      <div class="stp-tabs">
        <button class="stp-tab active" onclick="switchTab('manual')">Manual Entry</button>
        <button class="stp-tab" onclick="switchTab('camera')">Camera</button>
        <button class="stp-tab" onclick="switchTab('upload')">Upload File</button>
      </div>

      <!-- Manual Tab -->
      <div class="stp-tab-content active" id="tab-manual">
        <div class="search-bar" style="margin-bottom:12px">
          <input type="text" id="manual-input" placeholder="Type or paste barcode value..." style="font-size:16px;padding:10px 14px">
          <button class="btn btn-primary" onclick="addManual()" style="padding:10px 20px">Add</button>
        </div>
        <div style="font-size:12px;color:var(--muted)">Press Enter to add. Paste multiple lines to batch-add.</div>
      </div>

      <!-- Camera Tab -->
      <div class="stp-tab-content" id="tab-camera">
        <div class="stp-cam-box" id="stp-cam-box">
          <video id="stp-vid" autoplay playsinline></video>
          <div id="stp-cam-ph" style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:rgba(255,255,255,0.5)">
            <svg width="40" height="40" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1"><path d="M2 4V2h4"/><path d="M14 2h4v2"/><path d="M2 16v2h4"/><path d="M14 18h4v-2"/></svg>
            <div style="margin-top:8px;font-size:13px">Click Start to begin</div>
          </div>
        </div>
        <div style="display:flex;gap:8px;margin-top:10px;align-items:center">
          <button class="btn btn-primary btn-sm" id="stp-cam-btn" onclick="toggleStpCam()">Start Camera</button>
          <select id="stp-cam-sel" style="padding:5px 8px;border-radius:6px;border:1px solid var(--line);background:var(--paper);color:var(--text);font-size:12px;flex:1"></select>
          <span id="stp-cam-stat" style="font-size:12px;color:var(--muted)">Ready</span>
        </div>
      </div>

      <!-- Upload Tab -->
      <div class="stp-tab-content" id="tab-upload">
        <div class="stp-dropzone" id="stp-dropzone" onclick="document.getElementById('stp-file').click()">
          <input type="file" id="stp-file" accept=".png,.jpg,.jpeg,.pdf,.tiff,.bmp" style="display:none" onchange="handleUpload(this.files)">
          <svg width="36" height="36" viewBox="0 0 20 20" fill="none" stroke="var(--muted)" stroke-width="1.5" stroke-linecap="round" style="margin-bottom:8px;opacity:0.5">
            <path d="M14 2H6a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2z"/>
            <polyline points="7 10 10 7 13 10"/><line x1="10" y1="14" x2="10" y2="7"/>
          </svg>
          <div style="font-size:14px;color:var(--muted)">Drop an image or PDF here, or <strong>click to browse</strong></div>
          <div style="font-size:12px;color:var(--muted);margin-top:4px;opacity:0.7">Supports PNG, JPG, PDF — barcodes will be automatically detected</div>
        </div>
        <div id="stp-upload-status" style="margin-top:8px;font-size:13px;color:var(--muted);text-align:center"></div>
      </div>
    </div>
  </div>

  <!-- Right: Export Panel -->
  <div>
    <div class="panel">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <div class="form-section-title" style="margin:0;border:0;padding:0">
          PDF Export
        </div>
        <span class="stp-count-badge" id="stp-count">0</span>
      </div>
      <div class="fg" style="margin-bottom:12px">
        <label>Report Title</label>
        <input type="text" id="stp-title" value="Barcode Scan Report" placeholder="Report title...">
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-success" onclick="generatePdf()" id="stp-export-btn" disabled style="flex:1;padding:10px;font-size:14px">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M14 2H6a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2z"/>
            <polyline points="7 10 10 7 13 10"/><line x1="10" y1="14" x2="10" y2="7"/>
          </svg>
          Export PDF
        </button>
        <button class="btn btn-danger btn-sm" onclick="clearSession()" title="Clear all scans">Clear</button>
      </div>
    </div>
  </div>
</div>

<!-- Session Table -->
<div class="panel" style="padding:0">
  <div style="padding:16px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between">
    <div class="form-section-title" style="margin:0;border:0;padding:0">Scan Session</div>
    <div style="font-size:12px;color:var(--muted)" id="stp-session-info">No barcodes scanned yet</div>
  </div>
  <div style="overflow-x:auto">
    <table class="stp-session-table" id="stp-table">
      <thead><tr>
        <th style="width:40px">#</th><th>Barcode Value</th><th>Format</th>
        <th>Item Name</th><th>Location</th><th>Scanned</th><th style="width:50px"></th>
      </tr></thead>
      <tbody id="stp-tbody"></tbody>
    </table>
  </div>
  <div id="stp-empty" style="text-align:center;padding:40px;color:var(--muted)">
    <svg width="40" height="40" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1" style="opacity:0.3;margin-bottom:8px">
      <path d="M2 4V2h4"/><path d="M14 2h4v2"/><path d="M2 16v2h4"/><path d="M14 18h4v-2"/>
      <line x1="6" y1="6" x2="6" y2="14"/><line x1="10" y1="6" x2="10" y2="14"/><line x1="14" y1="6" x2="14" y2="14"/>
    </svg>
    <div>Add barcodes using manual entry, camera, or file upload</div>
  </div>
</div>
"""

_PAGE_JS = """<script>
// ── Session state (persisted to localStorage) ──
let session = JSON.parse(localStorage.getItem('stp_session') || '[]');
let stpStream = null, stpScanning = false, stpLastCode = '', stpLastTime = 0;

function saveSession() {
  localStorage.setItem('stp_session', JSON.stringify(session));
  renderTable();
}

// ── Tab switching ──
function switchTab(name) {
  document.querySelectorAll('.stp-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.stp-tab-content').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}

// ── Manual entry ──
const manualInput = document.getElementById('manual-input');
manualInput.addEventListener('keydown', e => { if (e.key === 'Enter') addManual(); });
manualInput.addEventListener('paste', e => {
  setTimeout(() => {
    const val = manualInput.value;
    if (val.includes('\\n')) {
      const lines = val.split(/\\r?\\n/).map(l => l.trim()).filter(Boolean);
      lines.forEach(l => addEntry(l, 'Manual'));
      manualInput.value = '';
    }
  }, 50);
});

function addManual() {
  const v = manualInput.value.trim();
  if (!v) return;
  addEntry(v, 'Manual');
  manualInput.value = '';
  manualInput.focus();
}

function addEntry(code, format, name, location) {
  session.push({
    code: code,
    format: format || '',
    name: name || '',
    sku: '',
    location: location || '',
    scanned_at: new Date().toISOString(),
  });
  saveSession();
  enrichLast();
  toast('Added: ' + code, 'success', 1500);
}

async function enrichLast() {
  const idx = session.length - 1;
  const entry = session[idx];
  if (!entry) return;
  try {
    const r = await apiCall('POST', '/api/scan-to-pdf/enrich', { codes: [entry.code] });
    if (r.ok && r.data.items && r.data.items[0] && r.data.items[0].found) {
      const item = r.data.items[0];
      session[idx].name = item.name || '';
      session[idx].sku = item.sku || '';
      session[idx].location = item.location || '';
      saveSession();
    }
  } catch (e) {}
}

// ── Camera scanning ──
async function toggleStpCam() {
  if (stpScanning) { stopStpCam(); return; }
  try {
    const devs = await navigator.mediaDevices.enumerateDevices();
    const cams = devs.filter(d => d.kind === 'videoinput');
    const sel = document.getElementById('stp-cam-sel');
    sel.innerHTML = cams.map((c, i) => '<option value="' + c.deviceId + '">' + (c.label || 'Camera ' + (i+1)) + '</option>').join('');
    await startStpCam(cams[0]?.deviceId);
  } catch (e) {
    document.getElementById('stp-cam-stat').textContent = 'Denied: ' + e.message;
  }
}

async function startStpCam(did) {
  const constraints = { video: { deviceId: did ? { exact: did } : undefined, facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } } };
  stpStream = await navigator.mediaDevices.getUserMedia(constraints);
  document.getElementById('stp-vid').srcObject = stpStream;
  stpScanning = true;
  document.getElementById('stp-cam-btn').textContent = 'Stop Camera';
  document.getElementById('stp-cam-ph').style.display = 'none';
  document.getElementById('stp-cam-stat').textContent = 'Scanning...';
  stpScanLoop();
}

function stopStpCam() {
  stpScanning = false;
  if (stpStream) { stpStream.getTracks().forEach(t => t.stop()); stpStream = null; }
  document.getElementById('stp-vid').srcObject = null;
  document.getElementById('stp-cam-btn').textContent = 'Start Camera';
  document.getElementById('stp-cam-ph').style.display = 'flex';
  document.getElementById('stp-cam-stat').textContent = 'Stopped';
}

async function stpScanLoop() {
  if (!stpScanning) return;
  const v = document.getElementById('stp-vid');
  if (v.readyState === v.HAVE_ENOUGH_DATA && 'BarcodeDetector' in window) {
    try {
      const det = new BarcodeDetector();
      const canvas = document.createElement('canvas');
      canvas.width = v.videoWidth; canvas.height = v.videoHeight;
      canvas.getContext('2d').drawImage(v, 0, 0);
      const barcodes = await det.detect(canvas);
      if (barcodes.length > 0 && barcodes[0].rawValue) {
        const code = barcodes[0].rawValue;
        const now = Date.now();
        if (code !== stpLastCode || now - stpLastTime > 3000) {
          stpLastCode = code;
          stpLastTime = now;
          addEntry(code, barcodes[0].format || 'Camera');
        }
      }
    } catch (e) {}
  }
  setTimeout(stpScanLoop, 400);
}

document.getElementById('stp-cam-sel').addEventListener('change', async e => {
  if (stpScanning) { stopStpCam(); await startStpCam(e.target.value); }
});

// ── File upload ──
const dropzone = document.getElementById('stp-dropzone');
dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => { e.preventDefault(); dropzone.classList.remove('drag-over'); handleUpload(e.dataTransfer.files); });

async function handleUpload(files) {
  if (!files || !files.length) return;
  const status = document.getElementById('stp-upload-status');
  status.textContent = 'Processing ' + files[0].name + '...';
  const form = new FormData();
  form.append('file', files[0]);
  try {
    const resp = await fetch('/api/scan-to-pdf/decode', { method: 'POST', body: form });
    const data = await resp.json();
    if (!resp.ok) { status.textContent = 'Error: ' + (data.error || 'Unknown'); toast(data.error || 'Upload failed', 'error'); return; }
    if (data.count === 0) { status.textContent = 'No barcodes found in ' + data.filename; toast('No barcodes found', 'warning'); return; }
    // Add all found barcodes
    for (const bc of data.barcodes) {
      session.push({
        code: bc.value,
        format: bc.format || '',
        name: '',
        sku: '',
        location: '',
        scanned_at: new Date().toISOString(),
      });
    }
    saveSession();
    // Enrich all new codes
    const codes = data.barcodes.map(b => b.value);
    try {
      const er = await apiCall('POST', '/api/scan-to-pdf/enrich', { codes });
      if (er.ok && er.data.items) {
        const startIdx = session.length - data.count;
        er.data.items.forEach((item, i) => {
          if (item.found && session[startIdx + i]) {
            session[startIdx + i].name = item.name || '';
            session[startIdx + i].sku = item.sku || '';
            session[startIdx + i].location = item.location || '';
          }
        });
        saveSession();
      }
    } catch (e) {}
    status.textContent = 'Found ' + data.count + ' barcode(s) in ' + data.filename;
    toast('Added ' + data.count + ' barcode(s) from ' + data.filename, 'success');
  } catch (e) {
    status.textContent = 'Upload failed';
    toast('Upload failed: ' + e.message, 'error');
  }
  // Reset file input so same file can be re-selected
  document.getElementById('stp-file').value = '';
}

// ── PDF generation ──
async function generatePdf() {
  if (!session.length) { toast('No barcodes to export', 'warning'); return; }
  const btn = document.getElementById('stp-export-btn');
  btn.disabled = true;
  btn.textContent = 'Generating...';
  try {
    const resp = await fetch('/api/scan-to-pdf/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: document.getElementById('stp-title').value || 'Barcode Scan Report',
        entries: session.map(s => ({
          code: s.code,
          format: s.format,
          name: s.name,
          sku: s.sku,
          location: s.location,
          scanned_at: s.scanned_at,
        })),
      }),
    });
    if (!resp.ok) { const d = await resp.json(); toast(d.error || 'PDF generation failed', 'error'); return; }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = resp.headers.get('content-disposition')?.match(/filename="(.+)"/)?.[1] || 'scan-report.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast('PDF downloaded!', 'success');
  } catch (e) {
    toast('PDF generation failed: ' + e.message, 'error');
  } finally {
    btn.disabled = session.length === 0;
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2z"/><polyline points="7 10 10 7 13 10"/><line x1="10" y1="14" x2="10" y2="7"/></svg> Export PDF';
  }
}

// ── Table rendering ──
function renderTable() {
  const tbody = document.getElementById('stp-tbody');
  const empty = document.getElementById('stp-empty');
  const count = document.getElementById('stp-count');
  const info = document.getElementById('stp-session-info');
  const exportBtn = document.getElementById('stp-export-btn');

  count.textContent = session.length;
  exportBtn.disabled = session.length === 0;

  if (!session.length) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    info.textContent = 'No barcodes scanned yet';
    return;
  }

  empty.style.display = 'none';
  const matched = session.filter(s => s.name).length;
  info.textContent = session.length + ' barcode(s) — ' + matched + ' matched to inventory';

  tbody.innerHTML = session.map((s, i) => {
    const time = s.scanned_at ? new Date(s.scanned_at).toLocaleTimeString() : '—';
    const badge = s.name
      ? '<span class="stp-badge-found">' + esc(s.name) + '</span>'
      : '<span class="stp-badge-unknown">Unknown</span>';
    return '<tr>'
      + '<td style="color:var(--muted);font-weight:600">' + (i+1) + '</td>'
      + '<td><code style="font-size:13px">' + esc(s.code) + '</code></td>'
      + '<td style="color:var(--muted);font-size:12px">' + esc(s.format || '—') + '</td>'
      + '<td>' + badge + '</td>'
      + '<td style="font-size:12px;color:var(--muted)">' + esc(s.location || '—') + '</td>'
      + '<td style="font-size:12px;color:var(--muted)">' + time + '</td>'
      + '<td><button class="stp-remove-btn" onclick="removeEntry(' + i + ')" title="Remove">&times;</button></td>'
      + '</tr>';
  }).join('');
}

function removeEntry(idx) {
  session.splice(idx, 1);
  saveSession();
}

function clearSession() {
  if (session.length && !confirm('Clear all ' + session.length + ' scanned barcodes?')) return;
  session = [];
  saveSession();
  toast('Session cleared', 'info');
}

// ── Init ──
renderTable();
</script>"""
