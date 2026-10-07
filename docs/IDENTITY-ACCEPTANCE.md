# Barcode Buddy: who it is for, and proof it does their job

Run 2026-10-07 11:52 UTC on revision `3554d9a`. Every line below was executed against the real product in a fresh workspace: the real processor filing generated scans, the full web app answering real requests, and for the installer, the web app and filing service running as separate programs.

**Score: 134 of 143 proven.** 1 failed. 8 could not be proven on this machine.

| Who | Proven | Failed | Not provable here |
| --- | --- | --- | --- |
| Scanner operator / warehouse clerk | 13 of 13 | 0 | 0 |
| Receiving dock worker | 11 of 12 | 1 | 0 |
| Shipping / proof-of-delivery clerk | 7 of 7 | 0 | 0 |
| Quality and compliance lead | 8 of 8 | 0 | 0 |
| Inventory manager | 18 of 18 | 0 | 0 |
| Floor worker on a phone or tablet | 10 of 12 | 0 | 2 |
| Department lead / manager | 12 of 12 | 0 | 0 |
| Office admin / customer service | 4 of 4 | 0 | 0 |
| Operations owner / executive | 9 of 9 | 0 | 0 |
| System admin | 21 of 22 | 0 | 1 |
| Installer / IT implementer | 16 of 19 | 0 | 3 |
| Buyer signing off the purchase | 5 of 7 | 0 | 2 |

## Scanner operator / warehouse clerk

Feeds paperwork through the scanner and expects it to file itself.

- [x] A PDF scan with a barcode files itself as the barcode value, in this year's and month's folder
- [x] A JPG scan is converted to a PDF and filed
- [x] A PNG scan is converted to a PDF and filed
- [x] A two-page TIFF from the scanner is filed as a two-page PDF
- [x] A page fed 90 degrees the wrong way round still files
- [x] A page fed 180 degrees the wrong way round still files
- [x] A page fed 270 degrees the wrong way round still files
- [x] A multi-page scan whose barcode is on page 2 still files, with every page kept
- [x] A page with no barcode goes to the rejected folder with the reason beside it, original untouched
- [x] A file that is not really a scan (renamed to .pdf) is rejected, not filed
- [x] A zero-byte file from a failed scan is rejected with a reason
- [x] Nothing is left behind in the scan folder or the in-progress folder after processing
- [x] With the service running, a scan dropped in the folder disappears and files itself within seconds, hands off

Would also want, and this product does not do it:
- Scanning a stack of different documents as one file and having it split itself
- Filing paperwork that has no barcode on it (no OCR, no handwriting)

## Receiving dock worker

Scans packing slips against purchase orders and books stock in.

- [x] A packing slip files under its purchase order number
- [x] A slip whose only barcode is not a PO number is rejected instead of being filed under the wrong name
- [x] Scanning the same PO twice flags the second copy and leaves the first filed copy untouched
- [x] A slip carrying two different PO barcodes is held for a person, never guessed
- [x] A slip with the same PO barcode printed twice still files normally
- [x] A slip with a vendor barcode and a PO barcode files under the PO, ignoring the vendor code
- [x] Scanning an item's barcode pulls up the item
- [x] Typing the SKU pulls up the same item
- [x] Booking a delivery in adds to the count and records the PO number
- [x] The item's history shows the receipt with amount, running total and PO
- [x] The item's barcode label downloads as an image and scans back to the same item
- [ ] **FAILED** A dock worker can scan an item that the inventory manager set up
  - AssertionError: HTTP 404: an ordinary user cannot see an item a manager created (line 174)

Would also want, and this product does not do it:
- Attaching the filed slip to the purchase order inside the ERP
- Receiving against an expected-deliveries list

## Shipping / proof-of-delivery clerk

Files signed delivery receipts and books stock out.

- [x] A delivery receipt files under its shipment number
- [x] Rescanning the signed copy keeps both versions side by side, neither overwritten
- [x] A receiving slip dropped in the shipping folder by mistake is rejected, not filed as a delivery
- [x] Booking a shipment out reduces the count and records the shipment number
- [x] The system refuses to ship more than is on hand
- [x] A damaged or returned unit is recorded with its own reason
- [x] A list of scanned barcodes becomes a titled PDF manifest, with item details filled in and unknown codes kept

Would also want, and this product does not do it:
- Checking that the delivery receipt was actually signed
- Attaching the receipt to the shipment record in the ERP

## Quality and compliance lead

Files certificates and needs a record nobody can quietly change.

- [x] A certificate files under its quality record number
- [x] A second certificate with the same record number is flagged, never silently replacing the first
- [x] Every rejected document across all three workflows carries a written reason
- [x] The processing log records every document with workflow, machine, config version and error code
- [x] The activity record can be filtered by kind of action and by date
- [x] Nobody, not even the owner, can delete or edit the activity record through the app
- [x] The full stock ledger exports to a spreadsheet with every movement and its reason
- [x] A correction adds a new ledger line and never alters an earlier one

Would also want, and this product does not do it:
- Notes, sign-offs and attachments on an individual scan record
- A list of certificates that are due but have not been scanned yet

## Inventory manager

Owns the item list, labels, counts, imports, alerts and stock reports.

- [x] Creating an item gives it a barcode automatically
- [x] Labels can be made as Code 128, QR, Code 39, Data Matrix and EAN-13, and each one scans back to the right value
- [x] A second item with an existing SKU is refused instead of creating a duplicate
- [x] An item's details can be edited
- [x] A spreadsheet of items imports in one go
- [x] Importing the spreadsheet again updates existing items by SKU instead of duplicating them
- [x] Items can also be imported from a JSON file
- [x] The item list can be searched by name, filtered by category and location, and sorted by quantity
- [x] The summary shows how many items, categories and locations there are
- [x] Stock exports to CSV and JSON, and can be exported for one category only
- [x] When an item drops below its minimum, a low-stock alert appears and the alert badge counts it
- [x] Alerts can be marked read, dismissed one at a time, or all cleared
- [x] Low-stock alerting can be switched on and off per person
- [x] Stock reports show value by category and location, fastest movers, and what is low or out
- [x] The calendar shows which days had stock movement and what moved on a given day
- [x] Several items can be moved to a new location in one action
- [x] A discontinued item can be archived (it stops scanning), and items can be deleted singly or in bulk
- [x] One person's item list is private from ordinary users

Would also want, and this product does not do it:
- Purchase orders, supplier records and automatic reordering
- Multi-site stock transfers

## Floor worker on a phone or tablet

Looks items up and does counts standing in the aisle.

- [x] The login page is laid out for a phone screen
- [x] Every screen an ordinary worker can reach opens without an error
- [x] Every one of those screens is laid out for a phone
- [ ] *not provable here* Each screen looks right and is usable at phone width (375 px), checked by eye
  - Needs a real browser screenshot of each screen at 375 px. Not captured in this run.
- [ ] *not provable here* Pointing the phone camera at a barcode reads it live
  - Needs a physical phone camera in Chrome or Edge. The server side of the same lookup is proven above.
- [x] A photo of a label, uploaded from the phone, is read and matched
- [x] One photo of a shelf with several labels reads all of them for a count
- [x] Scanning something that is not in the system says so cleanly instead of erroring
- [x] When the login has expired, the worker is sent to the login page, not shown an error
- [x] A worker can change their own display name and password
- [x] A worker can report a problem from inside the app and it is saved
- [x] Logging out on a shared device really ends the session

Would also want, and this product does not do it:
- A native phone app for scanning paperwork into the filing folder
- Camera scanning in Firefox (Chrome and Edge only)

## Department lead / manager

Runs a team, hands out tasks and looks across people's stock.

- [x] A manager can create a team
- [x] An ordinary user cannot create a team
- [x] The lead can add people to the team as member or viewer
- [x] The lead can hand out a task with an owner, a priority and a due date
- [x] A task cannot be assigned to someone who is not on the team
- [x] The person a task is assigned to can update its status
- [x] A viewer can see the team but cannot change its tasks
- [x] Someone who is not on the team cannot open it
- [x] The lead can change someone's team role and remove them, which ends their access
- [x] A manager can look at a team member's stock
- [x] The lead can delete a task and rename the team
- [x] Closing a whole team down is reserved for an admin, so a manager cannot wipe a team by mistake

Would also want, and this product does not do it:
- Shift, daily and quarterly workload reports
- A queue of overdue scans by assignee

## Office admin / customer service

Pulls a filed document when a customer or vendor asks for it.

- [x] Knowing only the PO number, the filed PDF is at year / month / PO number, it opens, and it is the right document
- [x] The dashboard lists recently filed documents by number, so the office can confirm a scan arrived
- [x] A scan that did not file can be found in the rejected folder with the reason, without calling IT
- [x] A daily summary report can be produced on demand

Would also want, and this product does not do it:
- Searching filed documents inside the web app (retrieval is by folder and file name)
- Searching by words printed on the document

## Operations owner / executive

Wants to know what happened today and whether the system is healthy.

- [x] The dashboard's filed and rejected counts match what was actually scanned
- [x] The dashboard page itself opens for the owner
- [x] If scans are piling up unprocessed, the backlog count shows it
- [x] The health check is red when the filing service is stopped and green when it is running
- [x] Hourly throughput, a health score and monitoring metrics are available
- [x] An end-of-day view shows how much happened today and the most recent actions
- [x] A read-only status page can be shown on a wall screen
- [x] The owner can look at anyone's stock
- [x] The owner can hand the system over to someone else, and nobody else can do that

Would also want, and this product does not do it:
- Tomorrow's workload forecast
- Quarter-over-quarter reporting

## System admin

Controls who gets in, what they can do, and what was changed by whom.

- [x] On a brand new install, an anonymous visitor is refused before anyone has an account
- [x] The first person to sign up becomes the owner
- [x] The next person to sign up is an ordinary user, not an admin
- [x] The owner can make someone an admin and make others managers
- [x] An admin cannot create another admin; only the owner can
- [x] An ordinary user is kept out of the admin area
- [x] A manager is kept out of the admin area
- [x] Closing signup stops strangers creating accounts; reopening it works
- [x] Deactivating someone who left cuts their access immediately, even if they are still logged in
- [x] Reactivating them lets them log in again
- [x] An admin can reset a locked-out person's password; the old one stops working
- [x] No admin can demote, deactivate or delete the owner
- [x] An admin can remove an account entirely
- [x] Every role change, deactivation, password reset and deletion is in the admin audit log
- [x] An ordinary user cannot read the admin audit log
- [x] Passwords shorter than eight characters are refused
- [x] A forged web form posted from another site is refused
- [x] A password reset link works once and cannot be reused; asking for one never reveals who has an account
- [x] Guessing passwords gets a login locked out after ten tries
- [x] Only the owner can set up the AI helper or its keys; everyone can read what data it sees
- [x] With no AI set up, the chat says so plainly instead of making up an answer
- [ ] *not provable here* The AI helper answers a stock question from real inventory
  - No AI model is configured on a fresh install, and the product must work with AI off. Needs a model chosen on the installed machine.

Would also want, and this product does not do it:
- Single sign-on with the company directory
- Two-factor login

## Installer / IT implementer

Puts it on a Windows machine, proves it, backs it up and recovers it.

- [x] One command writes a customer's config: private to the machine by default, its own secret key, folders created
- [x] Provisioning refuses to overwrite a config that already exists
- [x] A config with a typo, an unknown setting or a broken barcode rule is refused at startup, not half-used
- [x] Starter configs for receiving, shipping and quality all load
- [x] The web app and the filing service start as two separate programs from that config and report healthy
- [x] On the real running server, a stranger without a login gets nothing
- [x] The first account created on the real running server becomes the owner
- [x] With both programs running, a scan dropped in the folder is filed and the dashboard shows it
- [x] Starting a second filing service on the same folder is refused
- [x] A backup of config, database, logs and filed documents can be taken while the system runs, with a checksum for every file
- [x] A damaged backup is detected instead of being trusted
- [x] The backup restores to an empty folder, documents and database intact, and refuses to restore over existing files
- [x] After a stop and restart, the scan that was mid-process is recovered and filed, filed PDFs are unchanged, and accounts still work
- [x] Stopping the programs releases the port cleanly
- [x] A customer's sample scans can be run against their config with a written pass/fail report, without touching the samples
- [x] The Windows launcher's safety rules hold: no public tunnel unless asked, never stops other programs' tunnels, this-machine-only by default, starts and supervises the filing service
- [ ] *not provable here* The Windows launcher script itself runs end to end on a Windows machine
  - Windows PowerShell on this build machine does not respond (TimeoutExpired). The launcher has to be run on a responsive Windows host; its rules are proven by test above (10 passed, 2 skipped, 1 warning in 60.72s (0:01:00)).
- [ ] *not provable here* The system starts by itself when the machine boots
  - Registering the startup task needs an administrator approval on the machine itself, which cannot be given over a remote session.
- [ ] *not provable here* A real office scanner saving to a network folder feeds the system
  - No customer scanner or network share has ever been available. Every scan in this run is a generated page.

Would also want, and this product does not do it:
- Shipping logs to an outside log system
- Config overrides by environment variable (only the secret key)

## Buyer signing off the purchase

Needs the delivered product to match the written offer, no more, no less.

- [x] Two different documents scanned into one file are held for a person, never filed under one of the two numbers (splitting is excluded from the offer)
- [x] The offer, statement of work, install, operations, security, recovery and acceptance documents all exist
- [x] The written offer states plainly what is included and what is not
- [x] The product carries its own name by default and the buyer's name when configured
- [x] No other company's name or email is built into the program a buyer receives
- [ ] *not provable here* The release gate passes on the exact revision being delivered
  - The gate requires the launcher to be executed under Windows PowerShell and the sales-site integration to be committed. Both are open; see the installer lines.
- [ ] *not provable here* The buyer's own documents, from the buyer's own scanner, pass acceptance
  - No buyer exists yet. This can only be proven on a real customer's samples.

Would also want, and this product does not do it:
- Multi-site deployment under one purchase
- Custom features for one customer

Every scan in this run is a generated page, not a customer's document. A pass here proves the product revision, not a customer installation.
