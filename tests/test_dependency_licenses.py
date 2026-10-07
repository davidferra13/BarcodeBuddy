"""BarcodeBuddy is licensed to customers under closed, no-resale terms.

A strong copyleft library (AGPL or GPL) shipped inside it would conflict with
those terms, which is why PDF handling moved from PyMuPDF to PDFium and
ReportLab. These checks stop it from coming back.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED_MODULES = {"fitz", "pymupdf"}
BANNED_PACKAGES = ("pymupdf", "pymupdfb", "pymupdf-fonts")


def _requirement_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            for stop in "<>=!~[; ":
                line = line.split(stop, 1)[0]
            names.add(line.strip().lower().replace("_", "-"))
    return names


def test_no_copyleft_pdf_library_is_installed():
    for name in ("requirements.txt", "constraints.txt"):
        assert not _requirement_names(ROOT / name) & set(BANNED_PACKAGES), name


def test_no_shipped_code_imports_a_copyleft_pdf_library():
    files = [ROOT / "main.py", ROOT / "stats.py", *sorted((ROOT / "app").rglob("*.py")),
             *sorted((ROOT / "scripts").glob("*.py"))]
    offenders = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            if any(module.split(".")[0] in BANNED_MODULES for module in modules):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == []


def test_third_party_notices_list_no_strong_copyleft_license():
    text = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| ") and not line.startswith("| Library") and not line.startswith("| ---")]
    assert rows, "the notices table is empty"
    for row in rows:
        assert "AFFERO" not in row.upper() and "AGPL" not in row.upper(), row
        assert " GPL" not in row.upper().replace("LGPL", ""), row
