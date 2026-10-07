# Install one customer workflow

Use Windows and Python 3.12. Keep the application on a local disk; scanner devices write completed files into the configured input folder.

From the installed product directory, run:

```powershell
.\provision-customer.ps1 -WorkflowKey receiving -ConfigPath ".\config.customer.json" -RuntimeRoot ".\data\customer" -BarcodePattern '^PO-[0-9]+$' -DuplicateHandling reject -InstallDependencies
```

The pattern above is an example. Confirm the buyer's actual routing identifiers from redacted samples before setting it. Each file must represent one business document. Mixed-document splitting is outside this offer.

Provisioning creates a unique secret and validates the workflow directories. Preserve config.customer.json privately; never commit it or reuse another customer's secret.

Start the worker and web application in separate terminals:

```powershell
.\.venv\Scripts\python.exe main.py --config ".\config.customer.json"
.\.venv\Scripts\python.exe stats.py --config ".\config.customer.json" --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:8080 locally, create the installation owner account, and close open signup from owner settings before adding users. Keep LAN/public exposure off unless specifically approved and configured for the customer.

Run sample acceptance before enabling scanner intake. See ACCEPTANCE.md. A successful synthetic reference test is not acceptance of the buyer's paperwork.
