"""Build the BarcodeBuddy demo kit: invented sample scans plus an acceptance manifest.

Every document is made up. No customer names, addresses or records appear.

    python scripts/make_demo_kit.py --out demo-scans

Writes demo-scans/drop-these/ (the files to drop into the input folder on a
call) and demo-scans/manifest.json (the expected result for each file, for
scripts/run_acceptance.py). Expected results assume the demo workflow from
demo/README.md: barcode pattern ^PO-[0-9]+$ and duplicate handling "reject".
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

from app.barcode_generator import save_barcode  # noqa: E402

PAGE_SIZE = (1275, 1650)  # US Letter at 150 dpi
DEMO_PATTERN = "^PO-[0-9]+$"


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _barcode(value: str, work: Path) -> Image.Image:
    path = work / f"bc-{value}.png"
    save_barcode(value, path, format="Code128", scale=4)
    with Image.open(path) as image:
        return image.convert("RGB")


def _document(title: str, reference: str, rows: list[tuple[str, str]], work: Path,
              barcodes: tuple[str, ...] = ()) -> Image.Image:
    page = Image.new("RGB", PAGE_SIZE, "white")
    draw = ImageDraw.Draw(page)
    draw.text((90, 90), "Sample Supply Co.", font=_font(40), fill="black")
    draw.text((90, 145), "100 Example Way, Anytown", font=_font(22), fill="black")
    draw.text((90, 250), title, font=_font(52), fill="black")
    if reference:
        draw.text((90, 330), reference, font=_font(30), fill="black")
    top = 120
    for value in barcodes:
        code = _barcode(value, work)
        page.paste(code, (PAGE_SIZE[0] - code.width - 90, top))
        top += code.height + 40
    y = max(470, top + 30)
    draw.line((90, y, PAGE_SIZE[0] - 90, y), fill="black", width=2)
    draw.text((90, y + 20), "Item", font=_font(26), fill="black")
    draw.text((900, y + 20), "Qty", font=_font(26), fill="black")
    y += 70
    for item, quantity in rows:
        draw.text((90, y), item, font=_font(24), fill="black")
        draw.text((900, y), quantity, font=_font(24), fill="black")
        y += 48
    draw.line((90, y + 10, PAGE_SIZE[0] - 90, y + 10), fill="black", width=2)
    draw.text((90, PAGE_SIZE[1] - 160), "Received by: ____________________   Date: __________",
              font=_font(24), fill="black")
    return page


def _scanned(page: Image.Image, *, degrees: float = 0.0, tint: int = 0) -> Image.Image:
    """Make a clean page look like a scan: small rotation, soft blur, light grain."""
    image = page
    if degrees:
        image = image.rotate(degrees, expand=True, fillcolor="white", resample=Image.Resampling.BICUBIC)
    image = image.filter(ImageFilter.GaussianBlur(radius=0.6))
    grain = Image.effect_noise(image.size, 18).convert("RGB")
    image = Image.blend(image, grain, 0.06)
    if tint:
        overlay = Image.new("RGB", image.size, (255 - tint, 255 - tint, 255 - tint - 8))
        image = Image.blend(image, overlay, 0.25)
    return image


ITEMS = [
    ("Corrugated box 12 x 12 x 8, single wall", "200"),
    ("Stretch wrap 18 in x 1500 ft", "12"),
    ("Pallet, 48 x 40, heat treated", "6"),
    ("Packing tape 2 in x 110 yd", "36"),
]


def build_kit(out: Path) -> dict:
    """Write the demo files and manifest under ``out``. Returns the manifest."""
    drop = out / "drop-these"
    drop.mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="bb-demo-kit-") as tmp:
        work = Path(tmp)

        slip = _document("PACKING SLIP", "Purchase order PO-10431", ITEMS, work, ("PO-10431",))
        slip_path = drop / "01-packing-slip-PO-10431.pdf"
        _scanned(slip).save(slip_path, "PDF", resolution=150)
        cases.append({"id": "packing-slip", "file": "drop-these/" + slip_path.name,
                      "expected": {"status": "success", "barcode": "PO-10431"}})

        rotated = _document("PACKING SLIP", "Purchase order PO-10432", ITEMS[:3], work, ("PO-10432",))
        rotated_path = drop / "02-crooked-scan-PO-10432.png"
        _scanned(rotated, degrees=3.0).save(rotated_path)
        cases.append({"id": "crooked-scan", "file": "drop-these/" + rotated_path.name,
                      "expected": {"status": "success", "barcode": "PO-10432"}})

        receipt = _document("DELIVERY RECEIPT", "Purchase order PO-10433", ITEMS[1:], work, ("PO-10433",))
        terms = Image.new("RGB", PAGE_SIZE, "white")
        ImageDraw.Draw(terms).text((90, 120), "Page 2 of 2. Terms and conditions of delivery.",
                                   font=_font(28), fill="black")
        receipt_path = drop / "03-delivery-receipt-two-pages-PO-10433.pdf"
        first, second = _scanned(receipt), _scanned(terms)
        first.save(receipt_path, "PDF", resolution=150, save_all=True, append_images=[second])
        cases.append({"id": "two-page-receipt", "file": "drop-these/" + receipt_path.name,
                      "expected": {"status": "success", "barcode": "PO-10433"}})

        lading = _document("BILL OF LADING", "Purchase order PO-10434", ITEMS[:2], work, ("PO-10434",))
        lading_path = drop / "04-bill-of-lading-PO-10434.jpg"
        _scanned(lading, tint=18).save(lading_path, "JPEG", quality=88)
        cases.append({"id": "photo-like-jpeg", "file": "drop-these/" + lading_path.name,
                      "expected": {"status": "success", "barcode": "PO-10434"}})

        blank_path = drop / "05-blank-page.png"
        _scanned(Image.new("RGB", PAGE_SIZE, "white")).save(blank_path)
        cases.append({"id": "blank-page", "file": "drop-these/" + blank_path.name,
                      "expected": {"status": "failure", "reason": "BARCODE_NOT_FOUND"}})

        note = _document("NOTE", "", [("Call the driver about the late pallet", "")], work)
        note_path = drop / "06-note-without-barcode.png"
        _scanned(note).save(note_path)
        cases.append({"id": "no-barcode", "file": "drop-these/" + note_path.name,
                      "expected": {"status": "failure", "reason": "BARCODE_NOT_FOUND"}})

        label = _document("CARRIER LABEL", "Tracking SHIP-77120", [("1 of 1 pallets", "")], work, ("SHIP-77120",))
        label_path = drop / "07-carrier-label-wrong-kind-of-number.png"
        _scanned(label).save(label_path)
        cases.append({"id": "wrong-kind-of-number", "file": "drop-these/" + label_path.name,
                      "expected": {"status": "failure", "reason": "INVALID_BARCODE_FORMAT"}})

        both = _document("PACKING SLIP", "Two orders on one page", ITEMS[:2], work, ("PO-10435", "PO-10436"))
        both_path = drop / "08-two-orders-on-one-page.png"
        _scanned(both).save(both_path)
        cases.append({"id": "two-orders-one-page", "file": "drop-these/" + both_path.name,
                      "expected": {"status": "failure", "reason": "AMBIGUOUS_BARCODE"}})

        again_path = drop / "09-same-packing-slip-scanned-again-PO-10431.pdf"
        shutil.copy2(slip_path, again_path)
        cases.append({"id": "scanned-twice", "file": "drop-these/" + again_path.name,
                      "expected": {"status": "failure", "reason": "DUPLICATE_FILE"}})

    manifest = {"customer": "Demo kit (invented documents)", "workflow": "demo", "cases": cases}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the BarcodeBuddy demo kit.")
    parser.add_argument("--out", default="demo-scans", help="Folder to create (must be empty or new).")
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        print(f"{out} already has files in it. Choose an empty or new folder.", file=sys.stderr)
        return 2
    manifest = build_kit(out)
    print(f"Wrote {len(manifest['cases'])} demo scans to {out / 'drop-these'}")
    print(f"Expected results: {out / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
