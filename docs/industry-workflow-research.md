# Industry Workflow Research

## Scope

This note summarizes how the people closest to this problem currently handle it:

- frontline users who scan or attach documents
- developers who build or wire the ingestion layer
- owners and operations leaders who buy or configure the wider workflow
- packaging, manufacturing, and industrial supply companies that live with the retrieval and dispute costs

Problem statement:

Scanned paperwork needs to land on the correct PO, receipt, shipment, delivery, or related business record without manual renaming, document loss, or ambiguous attachment.

Research date: April 3-4, 2026.

## Research Method

I cross-checked the problem from multiple angles:

- operator-facing scan and attach documentation
- scan software and hot-folder automation documentation
- open-source ingestion platform documentation
- barcode library packaging and deployment documentation
- enterprise document automation product documentation
- packaging, manufacturing, and industrial supply case studies
- Danpack public-site context already captured elsewhere in this repo

The goal was not to collect generic document-management advice. The goal was to isolate what people are actually doing today around scanned packing slips, POD documents, receiving paperwork, and related supply-chain records.

## What Frontline Users Actually Do Today

### 1. They still scan to folders or scan directly into transaction systems

Current operator-facing tools still center on two patterns:

- scan directly into an ERP or accounting transaction and attach the file there
- scan to a predefined folder and let an import rule or downstream system consume it

Red Wing documents direct scanning and attaching to purchase orders, receipts, vendor invoices, sales orders, and customer invoices. NAPS2 documents desktop scanning profiles that auto-save to a fixed path, either one file per page or one file per scan, and can split files by Patch-T pages.

Why this matters:

- the first-mile problem is still real
- one file per scan versus one file per page is a high-impact operator choice
- Barcode Buddy should keep assuming a file-based intake, because that is how many operators actually work

### 2. Shipping and POD workflows are increasingly mobile, but paper scan-back still exists

MHC's ePOD product shows where mature shipping workflows are going: signatures, photos, GPS, timestamps, and immediate digital return to the office. But the same materials also make clear why paper POD handling still matters: proof of delivery is crucial for disputes, audits, and customer communication.

Why this matters:

- `shipping_pod` should remain a separate workflow
- rescans and corrected paperwork are normal in this lane
- if Danpack eventually moves to mobile POD, Barcode Buddy still remains useful for paper-originated edge cases and backfile cleanup, but it should not pretend to be the mobile system

### 3. Scan profile details are operational, not cosmetic

NAPS2's current profile settings surface the knobs operators actually use:

- WIA versus TWAIN
- feeder versus duplex
- color versus grayscale
- DPI
- auto-save path
- one file per scan versus one file per page
- Patch-T splitting
- blank-page exclusion

Why this matters:

- upstream scan-profile guidance belongs in this repo's operating docs
- false blank-page removal, one-file-per-page, and TIFF defaults are not abstract risks; they are common operator-side failure sources

## What Developers Actually Do Today

### 1. They still build around consume folders and background consumers

Paperless-ngx remains a strong example of the current developer pattern:

- watch a consumption directory
- expose duplicate policy
- expose recursive folder behavior
- expose barcode engine choice
- expose pre-consume and post-consume scripts
- expose polling when file notifications are unreliable

Paperless explicitly documents that if filesystem notifications do not work, polling should be enabled instead. It also exposes barcode settings such as engine choice, barcode DPI, max pages, TIFF support, and double-sided collation helpers.

Why this matters:

- Barcode Buddy's polling design is not behind the market; it is aligned with how real ingestion systems survive unreliable networked filesystems
- the current product should keep treating hot-folder intake as a first-class deployment model
- the next builder should not replace polling with file events just because file events look cleaner on paper

### 2. Native barcode libraries are common, and packaging still matters

The official `zxing-cpp` Python package is production-stable, ships current wheels for Windows, macOS, and manylinux, and still documents a source-build path when no wheel is available. This matches what developers do in practice: use a native barcode library for speed and accuracy, then deal with wheel and build-environment realities as part of deployment.

Why this matters:

- the current dependency choice remains sound
- if future deployment targets Alpine or unusual Python or runtime combinations, packaging becomes part of the product decision
- this is a place to use judgment rather than widen scope now; no dependency swap is justified today

### 3. Developers do not solve the whole business problem in one service

The platforms and case studies repeatedly separate these layers:

- first-mile capture
- document ingestion
- indexing and matching
- downstream approval or exception handling
- retrieval and audit

Why this matters:

- Barcode Buddy should stay the first-mile deterministic routing layer
- it should not collapse into OCR-first invoice automation, general DMS, or a CAD repository
- a downstream handoff contract is more valuable than trying to absorb the whole back office

## What Owners, Entrepreneurs, And Companies Actually Optimize For

### 1. They buy outcomes, not scanners

The business-facing case studies consistently center on:

- faster retrieval
- less manual document chasing
- lower dispute resolution time
- fewer lost documents
- better exception visibility
- improved cash flow
- reduced paper storage

Packaging Specialties describes digitizing multiple parts of the business for cost reduction and better customer service. A.B. Martin Roofing scans packing slips into DocuWare so invoice, PO, and shipping copy can be reviewed together when discrepancies happen. Elit reports more than 4,000 delivery slips and outgoing invoices daily and ties document automation directly to lower missing returns and better cash flow. Ludwig Industriebedarf moved from a separate archiving process to real-time background archiving.

Why this matters:

- Barcode Buddy should keep framing itself as retrieval and routing infrastructure, not as "scanner software"
- the value proposition is speed, certainty, and fewer disputes, not document beautification

### 2. The real workflow is often a 3-way or multi-document match

DocuWare's current 3-way match guidance is explicit:

- the invoice, PO, and packing slip all need the same order number
- exceptions route into approval flows when the match fails

This is important because Barcode Buddy is not the whole AP or receiving solution. It is the deterministic first-mile step that makes the packing slip or POD available under the right key so the larger workflow can work.

Why this matters:

- the product should not over-promise invoice automation or AP approval
- but it should make downstream matching easier by preserving routable filenames, sidecars, and logs

## What Packaging And Industrial Supply Companies Specifically Show

### 1. They have multiple document families, not one

The current case studies and Danpack public context support a consistent split:

- receiving paperwork
- shipping or POD paperwork
- vendor and AP paperwork
- quality and compliance documents
- engineering and product-support files

Those do not behave the same operationally.

### 2. Adjacent systems are broader than Barcode Buddy's scope

M.H. EBY uses DocuWare not only for invoices and approvals but also to store drawings and parts information tied to manufacturing work orders. That is a real and valuable use case, but it is broader than Barcode Buddy's barcode-first ingest scope.

Why this matters:

- engineering drawings, CAD files, and general document retrieval are adjacent, not core
- do not let the current product drift into becoming "the whole company document system"

### 3. Paper still matters even when email and ERP integration exist

A.B. Martin and Ludwig both show mixed-source reality:

- invoices may arrive by email
- paper copies are still scanned in
- packing slips and shipping copies still matter when discrepancies arise

Why this matters:

- Barcode Buddy should stay strict about what belongs in the barcode pipeline
- but the builder should assume the company lives in a mixed paper-plus-email-plus-ERP world

## Cross-Checked Workflow Map

Across end users, developers, and owners, the workflow keeps resolving to the same structure:

1. Capture
   - MFP scan-to-folder
   - desktop scan tool auto-save
   - mobile POD
   - email inboxes for invoices
2. First-mile routing
   - folder rule
   - barcode rule
   - patch page
   - manual attach
   - OCR or IDP in broader systems
3. Business binding
   - PO
   - receipt
   - shipment
   - delivery
   - customer or job record
4. Exception handling
   - manual correction
   - approval queue
   - reject or report screen
5. Retrieval and audit
   - customer service
   - AP
   - receiving
   - compliance
   - disputes

Barcode Buddy belongs in step 2.

## Where Real Workflows Break

Cross-checked failure modes:

- the wrong transaction or PO is selected during manual attachment
- scan software saves one file per page when downstream expects one file per document
- scan software outputs TIFF by default while downstream only expects PDF or common image formats
- duplex collation or blank-page removal changes the evidence unexpectedly
- a watched folder receives files that are still being written or still locked
- a document contains several barcodes and the wrong one is chosen
- receiving, POD, and non-barcoded AP paperwork are mixed in one queue
- documents are searchable only by manual naming or cabinet retrieval
- paper or email copies exist in parallel, making status unclear
- downstream systems know how to do approval or 3-way match, but still depend on the first-mile document landing under the right key

## What Is Missing In Many Current Setups

- workflow-specific intake profiles instead of one generic scan destination
- documented duplicate policy per workflow
- visible exception handling for warehouse or accounting staff
- a clear boundary between barcode-routable paper and OCR-heavy or non-barcoded documents
- capture-profile discipline around PDF, DPI, duplex, and one-file-per-scan behavior
- reliable first-party data about barcode formats, destination systems, and reject patterns

## Direct Product Decisions For Barcode Buddy

### Adopt now

- Keep one workflow per instance.
- Keep polling as the default intake mode.
- Keep the barcode-first scope.
- Keep explicit duplicate policy per workflow.
- Keep the local stats page and rejection sidecars for operator visibility.
- Document upstream capture guidance: prefer PDF, `300 DPI`, one file per scan, and workflow-specific folder destinations.
- Treat scan-profile setup as part of deployment quality, not as an afterthought.

### Consider next, but only with real demand

- add a downstream handoff manifest or export contract for ERP or DMS attachers
- add upstream scanner-profile templates, for example NAPS2 profile guidance
- add TIFF support only if actual Danpack devices require it
- add a separate splitter or separator-page layer if mixed scan batches are real
- add richer metrics from the existing log once the owner gives actual volume expectations

### Do not pull into core right now

- OCR-first invoice extraction
- generic AI document classification
- exposed multi-user workflow UI
- general DMS features for engineering drawings, CAD, or arbitrary company records
- destination-specific ERP logic without a confirmed target system

## Data We Still Are Not Using Or Do Not Have Yet

### High-value first-party data still missing

- actual Danpack barcode samples and confirmed regex-safe formats by workflow
- 10 to 20 real successful documents per workflow
- several real rejected or problematic documents per workflow
- scanner or MFP model list
- scan software or profile exports, including whether NAPS2 or vendor software is used
- destination systems and exact attach rules
- expected daily volume, duplicate rate, and acceptable reject rate
- whether POD is mobile-first, scan-back, or mixed
- whether any workflow still depends on TIFF

### Public or repo-adjacent data that is still underused

- Danpack testimonials, gallery categories, and compliance PDFs for richer future fixture stories
- the local stats log once real production-like intake begins
- scanner-profile artifacts from the actual deployment tools
- destination-system screenshots or SOPs that show how the routed file is consumed downstream

## Highest-Value Next Research

1. Get real Danpack samples before inventing regexes.
2. Export the exact scan profiles from the scanner software or MFP.
3. Map each workflow to its destination record and exact matching key.
4. Run the current log-based stats view for 2 to 4 weeks on representative traffic and review reject reasons.
5. Decide whether TIFF support or a pre-ingest splitter is actually needed from evidence, not assumption.

## Source Map

Operator and scanning workflow sources:

- Red Wing Software, scan and attach transaction documents:
  https://resources.redwingsoftware.com/rwssnextfiles/kbdocs/general/cp-pr-user-guide.pdf
- NAPS2 profile settings:
  https://www.naps2.com/doc/profile-settings
- MHC ePOD:
  https://www.mhcautomation.com/legacy/vanguard/proof-of-delivery/

Developer and ingestion-platform sources:

- Paperless-ngx setup:
  https://docs.paperless-ngx.com/setup/
- Paperless-ngx configuration:
  https://docs.paperless-ngx.com/configuration/
- zxing-cpp Python bindings on PyPI:
  https://pypi.org/project/zxing-cpp/

Business, packaging, and industrial workflow sources:

- DocuWare, Packaging Specialties:
  https://start.docuware.com/case-studies/packaging-specialties-inc
- DocuWare, A.B. Martin Roofing Supply:
  https://start.docuware.com/case-studies/abmartin-roofing-supply-llc
- DocuWare, Elit SRL:
  https://start.docuware.com/case-studies/elit-srl
- DocuWare, Ludwig Industriebedarf:
  https://start.docuware.com/de/case-studies/ludwig-industriebedarf-gmbh
- DocuWare, M.H. EBY:
  https://start.docuware.com/hubfs/MH%20Eby_DocuWare%20Case%20Study.pdf
- DocuWare, 3-way match FAQ:
  https://start.docuware.com/invoice-processing/user/faq/how-does-the-3-way-match-work
- DocuWare, invoice automation overview:
  https://start.docuware.com/blog/document-management/invoice-automation
