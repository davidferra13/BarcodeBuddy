# Deployment and data ownership

The buyer controls their installed infrastructure and business data. Default web exposure is loopback-only. LAN or public access requires explicit customer approval and deployment-specific configuration. Public launch, account changes and messages are not side effects of release verification.

Generate a new installation secret per customer. Keep customer configs, databases, backups, sample manifests and documents out of Git and public assets. Protect the backup directory with the operating system's access controls and the buyer's approved encryption/backup system. The ZIP utility checks integrity; it does not encrypt the archive.

Restrict installation-folder access to operators and administrators who need it. Close open signup after owner setup. Review roles and account access when staff leave.

Sample acceptance and release receipts contain hashes and outcome metadata. Do not include raw sample contents in public proof or sales material. Diagnostic logs and private backups can contain operational identifiers and require restricted access.

Support changes preserve existing authentication and permissions. Do not enable a tunnel, change firewall rules, reset credentials or change household/network infrastructure during testing.
