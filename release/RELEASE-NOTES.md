# BarcodeBuddy 3.1.0, the filing release

This is the version licensed to customers under sales/LICENSE-AGREEMENT.md.

## What the license covers

Scanned paperwork dropped into a watched folder is filed as a PDF named after the record number already printed on the page (for example a purchase order number), in a year and month folder. Anything that cannot be filed with certainty is set aside in a Rejected folder with a written reason: no barcode, a barcode that is not a record number for this workflow, more than one record number, already filed, empty, unreadable or unsupported file. The web screens show every document and its outcome, run on the customer's own PC, and are protected by owner and user accounts. Backups can be made while the system runs, checked, and restored.

Supported: Windows 10 or 11, Python 3.12, PDF, PNG, JPEG and multi-page TIFF scans, one document per file, Code 128 and the other symbologies the reader detects.

## Present in the program but not part of the licensed offer

Inventory, scan-to-PDF reports, calendar, analytics, teams, alerts and the optional AI features ship in the same program. They are not covered by the acceptance, warranty or stabilization terms of the filing license, and the optional AI and alert webhook features stay off unless the customer turns them on.

## Changes since 3.0.0

- PDF reading moved from PyMuPDF (AGPL or paid license) to PDFium, and the scan report writer to ReportLab. Every installed library is now permissively licensed (THIRD-PARTY-NOTICES.md).
- The sidebar names the product (Document Filing) when no buyer organization name is set.
- Windows stability on many-core machines: math and image libraries use a bounded number of threads by default, after memory allocation crashes on a 24-core Windows PC. Operators can still override both.

## Installing

docs/customer/INSTALL.md. Dependencies install at the exact versions in constraints.txt, the versions this release was tested with.

## Verifying this release

release/README.md. Run the gate with --product-only. sales/DEMO.md builds the demo scans and checks them through the real reader.
