# Packaging And Industrial Operating Model

## Why This Exists

Custom packaging and industrial supply companies usually do not have one document-ingestion problem. They have several:

- receiving teams need vendor packing slips attached to the correct PO or receipt
- shipping and customer-service teams need POD and delivery paperwork attached to the right shipment
- quality and compliance teams may need traceability documents stored against the correct order or lot

The current research shows that companies typically solve this with multiple import rules, multiple watched folders, or separate workflows per document family instead of one universal rule set.

## Recommended Deployment Pattern

Run separate BarcodeBuddy instances with separate config files.

Suggested workflow split:

- `receiving`
- `shipping_pod`
- `quality_compliance`

Each instance should have:

- its own input folder
- its own service name or scheduled task
- its own `barcode_types`
- its own `barcode_value_patterns`
- its own duplicate policy

This keeps the runtime deterministic while matching how packaging and industrial operators actually work.

## Current Topology Constraint

The current runtime enforces five distinct managed paths per workflow:

- `input`
- `processing`
- `output`
- `rejected`
- `logs`

These paths must all live on the same filesystem volume under the current config safeguards.

That means the cleanest production pattern is:

- one same-volume root per workflow on the service host
- optionally share only the `input` subfolder over SMB to scanners or desktop scan tools

## Example Topology

```text
D:\barcodebuddy\receiving\input
D:\barcodebuddy\receiving\processing
D:\barcodebuddy\receiving\output
D:\barcodebuddy\receiving\rejected
D:\barcodebuddy\receiving\logs

D:\barcodebuddy\shipping-pod\input
D:\barcodebuddy\shipping-pod\processing
D:\barcodebuddy\shipping-pod\output
D:\barcodebuddy\shipping-pod\rejected
D:\barcodebuddy\shipping-pod\logs

D:\barcodebuddy\quality-compliance\input
D:\barcodebuddy\quality-compliance\processing
D:\barcodebuddy\quality-compliance\output
D:\barcodebuddy\quality-compliance\rejected
D:\barcodebuddy\quality-compliance\logs
```

Optional network exposure for devices:

```text
\\barcodebuddy\receiving-input -> D:\barcodebuddy\receiving\input
\\barcodebuddy\shipping-pod-input -> D:\barcodebuddy\shipping-pod\input
\\barcodebuddy\quality-compliance-input -> D:\barcodebuddy\quality-compliance\input
```

Example commands using the starter templates in `configs/`:

```text
py main.py --config configs/config.receiving.example.json
py main.py --config configs/config.shipping-pod.example.json
py main.py --config configs/config.quality-compliance.example.json
```

If these are turned into production configs, keep the workflow names the same and replace only the paths and confirmed barcode rules.

## Upstream Capture Profile Guidance

The research shows that first-mile scan profile setup is one of the biggest sources of avoidable errors.

Recommended current profile defaults:

- prefer `PDF` output
- use `300 DPI` or higher
- prefer `one file per scan`, not `one file per page`
- send each workflow to its own folder
- use duplex scanning where the hardware supports it
- keep blank-page removal conservative until validated with real paperwork

If the scanner software exposes a choice like NAPS2 does:

- use feeder or duplex when appropriate
- keep auto-save enabled to the workflow-specific `input` folder
- disable `one file per page` for the current BarcodeBuddy runtime
- use Patch-T or other separator-page splitting only if you intentionally add an upstream split layer

If the device or scan software defaults to `TIFF`, do not assume the runtime will accept it. The current runtime supports only `PDF`, `JPG`, `JPEG`, and `PNG`.

## Workflow Guidance

### Receiving

Best fit when:

- the vendor packing slip should attach to a PO, receipt, or receiving transaction
- duplicate uploads usually indicate a mistake

Recommended settings:

- narrow `barcode_types` to the actual expected formats
- set `barcode_value_patterns` to the PO or receipt format used by the ERP
- prefer `duplicate_handling` of `reject`

### Shipping Or POD

Best fit when:

- signed delivery paperwork is scanned after the fact
- rescans and corrected paperwork are common

Recommended settings:

- set `barcode_value_patterns` to the shipment or delivery identifier format
- prefer `duplicate_handling` of `timestamp`
- keep `barcode_scan_dpi` at `300` or higher if signatures or stamps reduce barcode clarity

### Quality Or Compliance

Best fit when:

- certificates, traceability sheets, or batch paperwork already include a routable barcode

Recommended settings:

- use a dedicated folder so these documents are not mixed with receiving or POD paperwork
- reject files that do not match the expected business barcode pattern

## What Not To Put In BarcodeBuddy

Do not use BarcodeBuddy as the primary ingest path for:

- emailed supplier invoices with no routing barcode
- multi-document scan batches that need document splitting
- workflows where the correct identifier must be inferred from OCR text rather than a barcode

Those belong in a different automation layer.
