# Recover an installation

Keep the owner account, private customer config, application revision and SQLite path in the private handoff. Use the existing owner/admin controls for role and signup changes. Never edit password hashes or transfer ownership as a shortcut.

Create and verify a backup:

```powershell
.\.venv\Scripts\python.exe scripts/customer_backup.py create --config ".\config.customer.json" --database "C:\BarcodeBuddy\data\barcode_buddy.db" --archive "D:\Backups\receiving.zip" --include-documents
.\.venv\Scripts\python.exe scripts/customer_backup.py verify --archive "D:\Backups\receiving.zip"
```

The database path above is an example. Use the actual database path of this installation. Creation snapshots SQLite through its backup API, including committed WAL data.

Extract into a NEW directory:

```powershell
.\.venv\Scripts\python.exe scripts/customer_backup.py extract --archive "D:\Backups\receiving.zip" --destination "C:\Recovery\receiving"
```

Extraction verifies all members before publishing the restored directory and refuses an existing destination. This is a recovery staging operation, not an automatic replacement of a live installation.

Review absolute paths in the restored config before reconnecting it. Stop only this installation through its documented shutdown path, preserve the current data, and restore the verified database and configured document folders with the owner. Verify database integrity, owner login, one known filing case and retrieval before resuming scanner intake.

Restore of paperwork requires a backup made with document inclusion. Metadata-only backups do not contain those PDFs. Never call a backup complete without stating this distinction.
