# Workflow Config Templates

These files are starter templates for the three recommended BarcodeBuddy workflows:

- `config.receiving.example.json`
- `config.shipping-pod.example.json`
- `config.quality-compliance.example.json`

They intentionally leave `barcode_value_patterns` empty until Danpack provides real sample paperwork and confirmed routing identifiers.

Use them as examples, not as proof that the barcode formats are already known.

These templates use `../data/...` paths so they resolve back into the repo-level `data/` tree when loaded from the `configs/` directory.

Each template now declares an explicit `workflow_key` that the runtime emits into log events and rejection sidecars:

- `receiving`
- `shipping_pod`
- `quality_compliance`
