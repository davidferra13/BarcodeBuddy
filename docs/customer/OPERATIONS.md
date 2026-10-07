# Operate the workflow

The scanner deposits complete PDF, PNG, JPEG or TIFF files into the input folder. Successful files become PDFs in output/YYYY/MM. Failed or ambiguous documents go to rejected with reason metadata; originals are preserved for review.

Check the dashboard queue and rejection list each workday. Investigate a stale heartbeat, growing input backlog or output disk approaching capacity. Do not treat a decoded barcode as proof that the document belongs to the expected order.

For a rejection, inspect the source and reason. Correct a scanner issue or configuration problem, make a new input copy, and verify the new result. Do not manually delete recovery journals or active processing files.

Use duplicate rejection when a duplicate must be reviewed; timestamp mode keeps rescans separately. The selected mode belongs in the accepted workflow configuration.

Schedule private backups using customer_backup.py. Include the explicit live SQLite path and --include-documents when the recovery requirement includes scanned PDFs. Back up to a different approved disk or destination. A ZIP on the same disk is not protection from disk failure.

No routine filing, duplicate handling, acceptance or backup operation requires an AI model. Optional AI features are outside the contracted document workflow.
