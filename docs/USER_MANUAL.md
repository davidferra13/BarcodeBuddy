# BarcodeBuddy User Manual

Last updated: 2026-04-04 (audit pass).

---

## Table of Contents

- [1. Quick Start](#1-quick-start)
  - [1.1 What This System Is](#11-what-this-system-is)
  - [1.2 What It Does](#12-what-it-does)
  - [1.3 How to Access It](#13-how-to-access-it)
  - [1.4 Your First Five Minutes](#14-your-first-five-minutes)
- [2. Core Workflows](#2-core-workflows)
  - [2.1 Receiving a Shipment](#21-receiving-a-shipment)
  - [2.2 Looking Up an Item on the Floor](#22-looking-up-an-item-on-the-floor)
  - [2.3 Running a Physical Inventory Count](#23-running-a-physical-inventory-count)
  - [2.4 Handling a Stock Adjustment](#24-handling-a-stock-adjustment)
  - [2.5 Setting Up Inventory from Scratch](#25-setting-up-inventory-from-scratch)
  - [2.6 Scanning Documents into the System](#26-scanning-documents-into-the-system)
  - [2.7 Investigating a Rejected Document](#27-investigating-a-rejected-document)
  - [2.8 Responding to Low-Stock Alerts](#28-responding-to-low-stock-alerts)
  - [2.9 Onboarding a New Team Member](#29-onboarding-a-new-team-member)
  - [2.10 Running an End-of-Day Review](#210-running-an-end-of-day-review)
  - [2.11 Asking the AI for Help](#211-asking-the-ai-for-help)
  - [2.12 Generating a Scan Report](#212-generating-a-scan-report)
- [3. Feature Reference](#3-feature-reference)
  - [3.1 Dashboard](#31-dashboard)
  - [3.2 Items List](#32-items-list)
  - [3.3 Item Detail](#33-item-detail)
  - [3.4 New Item](#34-new-item)
  - [3.5 Scan Lookup](#35-scan-lookup)
  - [3.6 Scan-to-PDF](#36-scan-to-pdf)
  - [3.7 Calendar](#37-calendar)
  - [3.8 Analytics](#38-analytics)
  - [3.9 Alerts](#39-alerts)
  - [3.10 Activity Log](#310-activity-log)
  - [3.11 Teams](#311-teams)
  - [3.12 AI Chat](#312-ai-chat)
  - [3.13 AI Privacy and Data](#313-ai-privacy-and-data)
  - [3.14 AI Settings](#314-ai-settings)
  - [3.15 Admin Panel](#315-admin-panel)
  - [3.16 Bulk Import](#316-bulk-import)
  - [3.17 Bulk Export](#317-bulk-export)
- [4. Role-Based Guides](#4-role-based-guides)
  - [4.1 Warehouse Operator](#41-warehouse-operator)
  - [4.2 Inventory Manager](#42-inventory-manager)
  - [4.3 Department Lead / Manager](#43-department-lead--manager)
  - [4.4 Operations Owner / Executive](#44-operations-owner--executive)
  - [4.5 System Admin](#45-system-admin)
- [5. Admin and Setup](#5-admin-and-setup)
  - [5.1 First-Time System Setup](#51-first-time-system-setup)
  - [5.2 Configuration File](#52-configuration-file)
  - [5.3 Environment Variables](#53-environment-variables)
  - [5.4 Running the Web Application](#54-running-the-web-application)
  - [5.5 Running the Document Ingestion Service](#55-running-the-document-ingestion-service)
  - [5.6 Running Multiple Workflows](#56-running-multiple-workflows)
  - [5.7 Windows Deployment](#57-windows-deployment)
  - [5.8 Docker Deployment](#58-docker-deployment)
  - [5.9 Railway Deployment](#59-railway-deployment)
  - [5.10 Setting Up AI](#510-setting-up-ai)
  - [5.11 Setting Up Email (Password Resets)](#511-setting-up-email-password-resets)
  - [5.12 Scanner and Network Share Setup](#512-scanner-and-network-share-setup)
  - [5.13 Health Monitoring](#513-health-monitoring)
- [6. Troubleshooting](#6-troubleshooting)
- [Appendix A: Roles and Permissions Matrix](#appendix-a-roles-and-permissions-matrix)
- [Appendix B: Configuration Reference](#appendix-b-configuration-reference)
- [Appendix C: Glossary](#appendix-c-glossary)
- [Appendix D: Known Gaps](#appendix-d-known-gaps)

---

## 1. Quick Start

### 1.1 What This System Is

BarcodeBuddy is a barcode-driven document filing and inventory management system. It has two parts:

1. **A document ingestion service** that watches a folder on your computer or server. When you drop a scanned document into that folder, the service reads the barcode on the document, converts it to a PDF, and files it into the right place automatically. No renaming. No manual sorting.

2. **A web application** where you manage inventory, track stock, scan barcodes, view analytics, get alerts, collaborate with your team, and talk to an AI assistant about your operations.

These two parts run as separate programs but share the same data.

### 1.2 What It Does

For **warehouse and dock workers:** You scan a packing slip, proof-of-delivery, or invoice. Drop it in a folder. It gets filed by barcode. Done.

For **inventory managers:** You track every item with barcodes, quantities, locations, and costs. You get alerts when stock is low. You see analytics on what is moving and what is sitting.

For **managers and leads:** You organize your team, assign tasks, and see reports on throughput, failures, and stock health across the operation.

For **the person who runs it:** You manage user accounts, configure the system, set up AI, and monitor system health.

### 1.3 How to Access It

Open a web browser and go to the URL your IT team gave you. It is typically:

```text
http://your-server:8080
```

If your organization uses a Cloudflare tunnel, it may be at a custom domain like `app.yourcompany.com`.

You need an account to get in. If this is the very first time anyone is accessing the system, see [Section 5.1: First-Time System Setup](#51-first-time-system-setup).

### 1.4 Your First Five Minutes

**If you already have an account:**

1. Go to the login page. Enter your email and password.
2. You land on the **Dashboard**. This shows the operational health of the document processing system.
3. Click **Items** in the left sidebar. This is your inventory.
4. If the list is empty, you either need to create items or import them. Click **New Item** to create one, or **Import CSV** to upload a spreadsheet.
5. Click **Scan** to try looking up an item by barcode. Type a barcode value and hit Lookup.

**If nobody has used the system yet:**

1. The first person to sign up becomes the **owner** (the top-level admin).
2. You must sign up using the email address configured in the system (ask your IT person what it is).
3. Go to `/auth/signup`, enter your name, that email, and a password.
4. You now have full access. Go to **Admin Panel** to enable signup for other users.

---

## 2. Core Workflows

These are the real jobs the system handles. Each workflow walks you through the complete sequence of actions, not just isolated features.

### 2.1 Receiving a Shipment

**Situation:** A delivery truck arrives. You have packing slips that need to be scanned and filed against the correct purchase order.

**Steps:**

1. Take the packing slips to the scanner.
2. Scan each document. Your scanner should be configured to save files to the BarcodeBuddy input folder (ask IT which folder).
3. Use the "one file per scan" setting on your scanner (not "one file per page"). Save as PDF at 300 DPI or higher.
4. Drop the scanned files into the input folder. If your scanner saves directly to that folder, this happens automatically.
5. BarcodeBuddy picks up each file within a few seconds. It reads the barcode on the packing slip, converts the file to PDF, and moves it to the output folder organized by year and month. The filename becomes the barcode value.
6. If the barcode cannot be read, the file goes to the **rejected** folder. A small `.meta.json` file appears next to it explaining what went wrong. See [2.7: Investigating a Rejected Document](#27-investigating-a-rejected-document).

**What you should see:** Processed files disappear from the input folder. They show up in `output/YYYY/MM/BARCODE.pdf`. On the web dashboard, the processing count ticks up.

**If you also need to update inventory:** After receiving, go to the web app. Find the item via **Scan** (type or scan the barcode). Click the item to open its detail page. Click **Adjust Qty**, enter the quantity received, select "Received" as the reason, and add any notes.

### 2.2 Looking Up an Item on the Floor

**Situation:** You are standing in the warehouse holding an item (or its label). You need to know what it is, how many you should have, or where it belongs.

**Steps:**

1. Open BarcodeBuddy on your phone or a nearby computer. Go to **Scan** in the sidebar.
2. **Option A — Camera:** Click **Start Camera**. Point your phone or laptop camera at the barcode on the item. The system reads it automatically and shows the matching item.
3. **Option B — Type it:** Type the barcode value or SKU into the search box and press Enter.
4. The results table shows: item name, SKU, current quantity, location, category, and status.
5. Click the item name to see its full detail page, including all past quantity adjustments.

**Note:** Camera scanning requires Chrome or Edge. It does not work in Firefox.

### 2.3 Running a Physical Inventory Count

**Situation:** You need to walk the warehouse, scan items, and produce a count report.

**Steps:**

1. Go to **Scan to PDF** in the sidebar.
2. Walk through the warehouse with your phone or tablet.
3. For each item, scan its barcode using one of three methods:
   - **Camera tab:** Point your camera at the barcode. It is detected automatically and added to your list.
   - **Manual tab:** Type the barcode value and press Enter. Supports pasting multiple codes at once (one per line).
   - **Upload tab:** If you took photos of barcode labels, drag and drop the images here. Barcodes are extracted automatically.
4. As each barcode is scanned, the system looks it up in inventory and fills in the item name, SKU, location, and category. If the barcode is not in inventory, it still appears in the list with the raw barcode value.
5. When finished, enter a title for the report (e.g., "Warehouse B Count - April 4").
6. Click **Export PDF**. A professional PDF report downloads with all scanned items and their details.

**Your session is saved automatically.** If your browser closes or you navigate away, come back to Scan to PDF and your scanned items are still there. Click **Clear** when you want to start a new session.

**After the count:** If quantities are wrong, go to each item's detail page and use **Adjust Qty** with the reason "Adjusted" to correct the count.

### 2.4 Handling a Stock Adjustment

**Situation:** Stock has changed and you need to record it. Maybe you sold 10 units, received a return, found damaged goods, or corrected a count.

**Steps:**

1. Find the item: Go to **Items** and search by name, SKU, or barcode. Or go to **Scan** and look it up directly.
2. Click the item to open its detail page.
3. Click **Adjust Qty**.
4. Enter the change amount:
   - Positive number to add stock (e.g., `50` to add 50 units)
   - Negative number to remove stock (e.g., `-10` to remove 10 units)
5. Select the reason:
   - **Received** — new stock arrived
   - **Sold** — stock went out to a customer
   - **Adjusted** — correcting a count or reconciliation
   - **Damaged** — stock lost to damage
   - **Returned** — stock returned from a customer
6. Add notes if needed (e.g., "PO-2026-0042" or "damaged in transit").
7. Click **Apply**.

**What happens:** The system creates an immutable transaction record. It stores the old quantity, the change, and the new quantity. Nothing is overwritten. Every adjustment appears in the item's transaction history and in the system-wide Activity Log.

### 2.5 Setting Up Inventory from Scratch

**Situation:** You are starting fresh. You have a spreadsheet of items or you need to enter them one by one.

**Path A — Bulk import from a spreadsheet:**

1. Prepare a CSV file. The only required column is `name`. Other useful columns: `sku`, `quantity`, `location`, `category`, `cost`, `min_quantity`, `barcode_value`.
2. Go to **Import CSV** in the sidebar.
3. Click the **CSV** tab.
4. Drag and drop your file (or click to browse).
5. A preview of the first 50 rows appears. Review it.
6. Click **Import**.
7. Items are created. If any SKUs already exist, those items are updated instead of duplicated.

**Path B — Create items one at a time:**

1. Go to **New Item** in the sidebar.
2. Fill in at least the name. Everything else is optional.
3. A barcode is generated automatically (Code128 by default). You can change the format or enter a custom value.
4. If AI is set up, click the lightbulb icon next to Min Quantity, Location, or Category for a suggestion based on your existing inventory patterns.
5. Click **Create Item**.
6. Your form draft is saved in the browser. If you accidentally navigate away, come back and your data is still there.

**After setup:** Set `min_quantity` on important items so the alert system can warn you when stock is low.

### 2.6 Scanning Documents into the System

**Situation:** You need to file documents (packing slips, invoices, PODs, quality certificates) so they end up organized by barcode value.

**What you need:** The document ingestion service (`main.py`) must be running. Ask IT if it is.

**Steps:**

1. Scan your document with the scanner. Save as PDF, JPG, or PNG. Use 300 DPI or higher.
2. Place the file in the designated input folder. This varies by workflow:
   - Receiving documents go to the receiving input folder
   - Shipping/POD documents go to the shipping input folder
   - Quality/compliance documents go to the quality input folder
   - Your IT team will tell you which folder maps to which workflow
3. The file disappears from the input folder within a few seconds. That means the system picked it up.
4. Check the output folder for the result: `output/YYYY/MM/BARCODE.pdf`.

**If the file appears in the rejected folder instead**, see [2.7: Investigating a Rejected Document](#27-investigating-a-rejected-document).

**Tips for good scans:**
- Make sure the barcode on the document is fully visible and not wrinkled or smudged.
- Scan at 300 DPI or higher. Lower DPI makes barcode detection unreliable.
- Use "one file per scan" in your scanner settings, not "one file per page." Multi-page documents should stay as one file.
- If you are scanning double-sided, use the duplex setting.

### 2.7 Investigating a Rejected Document

**Situation:** A file appeared in the rejected folder instead of the output folder.

**Steps:**

1. Go to the rejected folder for your workflow.
2. Find the file. Next to it, there will be a file with the same name plus `.meta.json` at the end. For example, if your file was `scan001.pdf`, the sidecar is `scan001.pdf.meta.json`.
3. Open the `.meta.json` file in any text editor. It tells you what went wrong.

**Common rejection reasons and what to do:**

| Error in meta.json | What it means | What to do |
|---------------------|--------------|-----------|
| `NO_BARCODE` | The system scanned the document and found no barcode. | Re-scan at higher quality. Make sure the barcode is not cut off, wrinkled, or obscured. The system tries 4 rotations, so orientation is not the issue. |
| `INVALID_FORMAT` | The file is not a PDF, JPG, or PNG. The system checks the actual file content, not just the extension. | Re-scan in a supported format. Do not rename a file to trick it — it checks the file's internal header. |
| `PATTERN_MISMATCH` | A barcode was found but its value does not match the business rules configured for this workflow. | The barcode value does not look like what the system expects (e.g., it does not match the expected PO number format). Check whether this document belongs in a different workflow. |
| `DUPLICATE_REJECTED` | A document with this barcode value was already processed, and the workflow is in "reject" mode. | If the rescan was intentional (a corrected copy), the workflow may need to be in "timestamp" mode instead. Talk to IT. If it was a mistake, discard the duplicate. |
| `FILE_LOCKED` | The file was still being written when the system tried to process it. | This usually resolves itself — the system waits for files to stabilize. If it keeps happening, your scanner may be holding a lock on the file. Try a different scan-to-folder setting. |

### 2.8 Responding to Low-Stock Alerts

**Situation:** You see a red badge on the alert bell in the sidebar, or you get a webhook notification that stock is low.

**Steps:**

1. Click the alert bell in the sidebar (or go to **Alerts** in the sidebar).
2. You see a list of alerts. Each one tells you: which item, what the threshold is, and what the current quantity is.
3. Click the item name to go to its detail page.
4. Decide what to do:
   - **Order more stock:** Note the item, SKU, and location for your purchasing process.
   - **Adjust the threshold:** If the min quantity is wrong, edit the item and change `min_quantity`.
   - **Nothing:** Maybe this is expected. Dismiss the alert.
5. Back on the alerts page: **Mark as read** to acknowledge, or **Dismiss** to clear. Dismissed alerts do not come back unless the condition triggers again.

**How alerts work behind the scenes:** A background job runs every 5 minutes. It checks every item's quantity against its `min_quantity`. If quantity is at or below the threshold, an alert is created. If you have configured a webhook URL in alert settings, the alert is also POSTed to that URL.

**To set up alerts for an item:** Go to the item's detail page. Set a `min_quantity` value. That is all that is needed — the system does the rest.

### 2.9 Onboarding a New Team Member

**Situation:** A new person needs access to the system.

**If you are the owner or admin:**

1. Go to **Admin Panel** in the sidebar.
2. Check whether **Open Signup** is on. If not, toggle it on temporarily.
3. Give the new person the URL and tell them to go to `/auth/signup`.
4. They create an account with their name, email, and password. They get the "user" role by default.
5. If they need more access, change their role in the Admin Panel:
   - **Manager** — can create teams and view other users' inventory
   - **Admin** — can manage all users and system settings
6. If you want to restrict signups again, toggle Open Signup back off.

**Adding them to a team:**

1. Go to **Team** in the sidebar.
2. Open the relevant team.
3. Go to the **Members** tab.
4. Click **Add Member**. Select them from the dropdown.
5. Assign a role:
   - **Lead** — can manage other members and create/edit/delete tasks
   - **Member** — can work on tasks assigned to them
   - **Viewer** — can see the team's tasks but not change anything

### 2.10 Running an End-of-Day Review

**Situation:** You want to see what happened today across the operation before you leave.

**Steps:**

1. Start at the **Dashboard** (`/`). Check:
   - **Processing counts** — how many documents were processed today? How many succeeded vs. failed?
   - **Queue state** — is there a backlog of unprocessed files? If so, the ingestion service may have fallen behind.
   - **Service health** — is the ingestion worker running? When was its last heartbeat?

2. Go to **Activity Log** in the sidebar. Set the date range to today. Check:
   - How many inventory adjustments happened?
   - Were there any imports or exports?
   - Any unusual activity (unexpected deletions, new signups)?

3. Go to **Alerts**. Clear any alerts you have already addressed. Note any new ones for tomorrow.

4. Go to **Analytics** and check the **Stock Health** tab. Are there new out-of-stock or low-stock items since this morning?

5. Go to **Calendar**. Today's cell shows the transaction count. Click it to see the detail of what moved.

### 2.11 Asking the AI for Help

**Situation:** You have a question about your inventory or operations and you do not want to dig through screens to find the answer.

**Prerequisites:** The system owner must have completed AI setup first (see [5.10: Setting Up AI](#510-setting-up-ai)). If AI is not configured, the chat page shows an error.

**Steps:**

1. Click the **floating chat button** in the bottom-right corner of any page. Or go to **AI Chat** in the sidebar.
2. Type a question in plain English. Examples:
   - "What items are low on stock?"
   - "Show me everything in Warehouse B"
   - "What were the top 5 fastest-moving items this month?"
   - "Adjust SKU-12345 by +50 units, reason received, shipment from Acme"
   - "What is the total inventory value by category?"
   - "Summarize this week's transactions"
3. The AI responds using your actual inventory data. If it needs to look something up or make a change, it tells you which tool it is using.
4. If the AI makes a stock adjustment on your behalf, it shows up in the item's transaction history and the Activity Log, just like a manual adjustment.

**Conversations are saved.** You can have multiple threads. Switch between them or delete old ones from the chat page.

**What the AI can do:** Look up items, search by SKU, adjust stock quantities, pull analytics, view transaction history, list low-stock items, analyze categories, generate barcodes, preview and analyze CSV imports, and suggest item field values.

**What the AI cannot do:** Delete items, create new items, change system settings, manage users, or access the document ingestion service.

### 2.12 Generating a Scan Report

**Situation:** You need to produce a PDF document from a batch of barcodes — for a count report, a receiving log, a shipping manifest, or any other use.

**Steps:**

1. Go to **Scan to PDF** in the sidebar.
2. Scan barcodes using any of the three input methods:
   - **Camera:** Click the Camera tab, then Start Camera. Point at each barcode.
   - **Manual:** Click the Manual tab. Type barcodes one at a time (press Enter after each) or paste a list (one per line).
   - **Upload:** Click the Upload tab. Drag and drop images or PDFs that contain barcodes. The system extracts them automatically.
3. Each scanned barcode appears in the session table. If the barcode matches an item in your inventory, the table fills in the item name, SKU, location, and category automatically.
4. Remove any accidental scans by clicking the delete button on that row.
5. Enter a title for the report at the top (e.g., "Receiving Count - April 4, 2026").
6. Click **Export PDF**. The report downloads.

The report includes every scanned barcode, its format, the matched item details, and the scan timestamp.

---

## 3. Feature Reference

Every page in the system, what it shows, and what you can do on it.

### 3.1 Dashboard

**URL:** `/` (the homepage after login)

**What it shows:**
- Total documents processed, succeeded, and failed
- Input queue (files waiting) and processing queue (files in-flight)
- Service health status and last heartbeat from the ingestion worker
- P50, P95, P99 processing latency
- 24-hour activity summary
- Top failure reasons (most common error codes)
- Hourly throughput chart
- Quality analytics (barcode format distribution)

**What you can do:** View only. Data refreshes automatically.

### 3.2 Items List

**URL:** `/inventory`

**What it shows:** A searchable, filterable table of all inventory items.

**Summary bar:** Active items count, total units, number of categories, low stock count, out-of-stock count.

**Table columns:** Name (clickable), SKU, Quantity (color-coded: red = out of stock, yellow = low, green = healthy), Location, Category, Barcode value, Status (Active or Archived).

**What you can do:**
- Search by name, SKU, barcode, location, or tags using the search bar
- Filter by category using the dropdown
- Click any item name to open its detail page
- Export using the button in the top right

**Each user sees only their own inventory.** Managers and above can view other users' items.

### 3.3 Item Detail

**URL:** `/inventory/{item_id}`

**What it shows:**
- All item fields: name, SKU, description, quantity (large, color-coded), unit, location, category, tags, notes, cost, min quantity, status
- Barcode image (sticky panel on the right): with Download and Print buttons
- Transaction history table: every stock change with date, amount, running total, reason, and notes

**What you can do:**
- **Adjust Qty** — open a dialog to add or remove stock with a reason
- **Edit** — toggle all fields into edit mode, save or cancel
- **Delete** — permanently remove the item
- **Download barcode** — save the barcode as a PNG image
- **Print barcode** — open the browser print dialog for label printing

### 3.4 New Item

**URL:** `/inventory/new`

**Fields:**

| Field | Required | Notes |
|-------|----------|-------|
| Name | Yes | |
| SKU | No | Auto-generated if blank |
| Description | No | |
| Quantity | No | Default: 0 |
| Unit | No | e.g., "pcs", "kg", "boxes" |
| Min Quantity | No | Low-stock alert threshold. AI suggestion available. |
| Cost | No | Unit cost for valuation reports |
| Tags | No | Comma-separated |
| Location | No | AI suggestion available |
| Category | No | AI suggestion available |
| Barcode Type | No | Code128 (default), QR, EAN-13, Code39, DataMatrix |
| Barcode Value | No | Custom value or leave blank for auto-generation |
| Notes | No | |

**AI suggestion buttons** (lightbulb icon) appear next to Min Quantity, Location, and Category if AI is configured. They suggest values based on patterns in your existing inventory.

**Autosave:** Your draft is saved to browser local storage. Navigate away and come back — your data is still there.

### 3.5 Scan Lookup

**URL:** `/scan`

**Left side:**
- Text input for manual barcode/SKU lookup
- Camera scanner with device selector and start/stop button

**Right side:**
- Results table: Name, SKU, Quantity, Location, Category, Barcode, Status
- Click any result to go to that item's detail page

### 3.6 Scan-to-PDF

**URL:** `/scan-to-pdf`

**Input methods (tabs):**
- **Manual:** Type barcode values (supports pasting a list, one per line)
- **Camera:** Live camera feed with automatic barcode detection
- **Upload:** Drag-drop PNG, JPG, or PDF files; barcodes extracted automatically

**Session table:** Shows all scanned codes with: barcode value, format, matched item name, location, timestamp, and a delete button per row.

**Actions:**
- **Export PDF** — generates and downloads a report
- **Clear** — wipes the session to start fresh
- Report title field at the top

**Session persistence:** Saved in browser local storage. Survives page reloads and tab closures.

### 3.7 Calendar

**URL:** `/calendar`

A month-view grid. Each day cell shows the count of inventory transactions. Days with more activity are shaded darker.

**Navigation:** Arrow buttons to move between months.

**Click a day** to see its transactions (item name, quantity change, reason) and items created that day.

### 3.8 Analytics

**URL:** `/analytics`

Three tabs. Configurable date range (default: 30 days).

**Valuation tab:**
- Summary cards: total inventory value, active items, items with cost data, items missing cost
- Category breakdown: item count and total value per category with proportional bars
- Location breakdown: item count and total value per location with proportional bars
- Barcode format breakdown: count of items per format

**Velocity tab:**
- Top movers: items with the most transactions (by count and by volume)
- Activity bars showing relative movement

**Stock Health tab:**
- Summary cards: total items, out of stock, low stock, healthy
- Out of stock list: items at zero quantity with location
- Low stock list: items below min quantity
- Overstocked list: items significantly above expected levels

### 3.9 Alerts

**URL:** `/alerts`

**What it shows:** List of alerts triggered by stock threshold breaches.

**Each alert shows:** Item name, threshold value, current quantity, severity level, and status (unread, read, dismissed).

**Actions:**
- **Mark as read** — clears the unread badge but keeps the alert visible
- **Dismiss** — hides the alert; it does not return unless the condition triggers again
- **Dismiss all** — clears everything

**Navigation badge:** The alert bell in the sidebar shows the unread count, updating in real time.

**How alerts are generated:** A background job runs every 5 minutes and checks every item's quantity against its `min_quantity`. Breaches create alerts. If a webhook URL is configured, the alert is also sent there.

### 3.10 Activity Log

**URL:** `/activity`

An append-only audit trail of every action in the system. Nothing is ever deleted from this log.

**Categories:** inventory, auth, admin, scan, import, export, alert, system.

**Filtering:** By date range, by category, or by text search in the summary field.

**Summary stats at the top:** Today's count, this week's count, breakdown by category.

**Recent activity drawer:** Click the activity icon in the navigation to see the latest 20 events without leaving your current page.

### 3.11 Teams

**URL:** `/team`

**Left panel:** List of teams you belong to (admins see all teams). Shows team name, member count, and task count. Create Team button (managers and above).

**Right panel (when a team is selected):**

- **Team Info tab:** Name, description, edit and delete buttons
- **Members tab:** Table of members (name, email, team role, actions). Add Member button. Role dropdown (Lead, Member, Viewer). Remove button.
- **Tasks tab:** Task list with status filter buttons (To Do, In Progress, Done, Blocked). Each task shows: checkbox, title, priority badge (Low/Medium/High/Urgent), due date, assigned person. Create Task button. Click to edit.

**Team roles:**
| Role | Can do |
|------|--------|
| Lead | Manage members, create/edit/delete tasks |
| Member | Update status of tasks assigned to them |
| Viewer | Read-only |

### 3.12 AI Chat

**URL:** `/chat`

A conversational interface for querying your inventory and operations in plain English.

**Layout:** Conversation list on the left, chat messages on the right, input box at the bottom.

**What the AI can do (11 tools):**
- Look up items by name, SKU, or barcode
- Adjust stock quantities with reasons
- Pull inventory analytics and summaries
- View transaction history for any item
- List low-stock items
- Analyze categories
- Generate barcodes
- Preview and analyze CSV data
- Suggest item field values

**Conversations are saved.** Multiple conversations supported. Delete old ones from the list.

**Also accessible** via the floating chat button in the bottom-right corner of any page.

### 3.13 AI Privacy and Data

**URL:** `/ai/privacy`

Documents how user data is handled by the AI system:
- **Local mode (Ollama):** No data leaves your machine.
- **Cloud mode:** Queries and inventory context are sent to the configured provider (Anthropic or OpenAI). Their data policies apply.
- **No silent fallback:** If a provider is unavailable, the system returns an error. It never secretly switches providers.
- **API keys** are encrypted at rest.

### 3.14 AI Settings

**URL:** `/ai/settings` (owner only)

Allows the owner to reconfigure AI providers and models after the initial setup wizard. Same options as the setup wizard (provider mode, connection details, model assignments, API keys) but accessible as a standalone settings page.

### 3.15 Admin Panel

**URL:** `/admin` (admin and owner roles only)

**Stats cards:** Total users, active users, admins, regular users.

**Open Signup toggle:** Controls whether new users can self-register.

**User management table:** Name, Email, Role, Status (Active/Inactive), Created date, Actions.

**Actions per user:**
- Change role via dropdown (user, manager, admin)
- Activate / Deactivate account
- Reset password
- Delete account
- Transfer Ownership (owner only, irreversible)

**Audit log** at the bottom: Last 100 administrative actions (role changes, deactivations, ownership transfers, etc.) with actor, timestamp, and detail.

The owner account cannot be modified or deleted through this panel except via ownership transfer.

### 3.16 Bulk Import

**URL:** `/inventory/import`

**CSV tab:**
1. Drag-drop or click to upload a CSV file
2. Preview of first 50 rows
3. Click Import

**Required column:** `name`. All others optional: `sku`, `quantity`, `unit`, `location`, `category`, `cost`, `min_quantity`, `description`, `tags`, `notes`, `barcode_type`, `barcode_value`.

If a SKU already exists, the existing item is updated.

**JSON tab:** Same fields, uploaded as a JSON array of objects.

### 3.17 Bulk Export

**URL:** `/inventory/bulk` (Export tab)

1. Select format: CSV or JSON
2. Filter by: Status (active/archived/all), Category, Location
3. Live preview shows count, total quantity, and total value of matching items
4. Click Download

Also available from the Items page via the Export button.

---

## 4. Role-Based Guides

### 4.1 Warehouse Operator

**Your job in the system:** Scan documents, look up items, adjust stock.

**Pages you use daily:**
- **Scan** — look up items by barcode when you need to identify something
- **Items** — find items by name or SKU
- **Item Detail** — adjust quantities after receiving, shipping, or counting
- **Scan to PDF** — when you need to produce a count report or a receiving log

**Pages you probably do not need:**
- Admin Panel (you do not have access)
- AI Settings / AI Setup (admin only)
- Analytics (useful but not your daily concern)

**Your typical day:**
1. Receive a shipment → scan the packing slips into the input folder → adjust inventory quantities for received items
2. Ship an order → scan the POD into the input folder → adjust inventory for sold/shipped items
3. Find an item → use Scan page with camera or type the barcode
4. End of shift → check Alerts for any low-stock warnings to report to your manager

### 4.2 Inventory Manager

**Your job in the system:** Maintain accurate inventory, set up alerts, analyze stock health, run reports.

**Pages you use daily:**
- **Items** — your home base. Search, filter, review quantities.
- **Item Detail** — adjust stock, edit item data, review transaction history
- **Alerts** — respond to low-stock and overstock warnings
- **Analytics** — Stock Health tab to see what needs attention. Valuation tab for financial reporting. Velocity tab to see what is moving.
- **Calendar** — spot patterns in activity over time
- **Scan to PDF** — generate count reports during physical inventory

**Pages you use occasionally:**
- **Import CSV** — bulk loading new items or updating data
- **Bulk Export** — pulling data for reports or sharing with other systems
- **New Item** — adding items one at a time
- **AI Chat** — asking questions about your inventory without digging through screens

**Key setup tasks:**
- Set `min_quantity` on every item that matters. Without it, the alert system has nothing to check.
- Add cost data to items if you want valuation reports to be accurate.
- Assign locations and categories consistently so analytics group correctly.

### 4.3 Department Lead / Manager

**Your job in the system:** Oversee your team's work, assign tasks, review operational reports.

**Pages you use daily:**
- **Team** — check task progress, assign new work, manage membership
- **Dashboard** — see processing throughput and failures
- **Activity Log** — review what your team did today
- **Alerts** — check for unresolved stock issues

**Pages you use weekly:**
- **Analytics** — review stock health and velocity trends
- **Calendar** — look at activity patterns over the past weeks

**Manager-specific capabilities:**
- You can create teams (regular users cannot)
- You can view other users' inventory (regular users can only see their own)
- You can add and remove team members and assign them roles

### 4.4 Operations Owner / Executive

**Your job in the system:** See the big picture. Make sure the operation is healthy.

**What to look at:**
- **Dashboard** — is the document processing pipeline running? What is the failure rate? Is there a backlog?
- **Analytics → Valuation** — what is the total inventory value? How is it distributed across categories and locations?
- **Analytics → Stock Health** — how many items are out of stock or low?
- **Activity Log** — high-level view of system usage and any unusual patterns
- **Admin Panel → Audit Log** — security-relevant events (role changes, new signups, ownership transfers)

**As the owner, you also control:**
- AI configuration (setup wizard and settings)
- Ownership transfer to another person
- Everything admins can do (user management, signup settings)

### 4.5 System Admin

**Your job in the system:** Manage users, configure the platform, keep it running.

**Your responsibilities:**

1. **User management** — promote/demote roles, activate/deactivate accounts, reset passwords via Admin Panel
2. **Signup control** — toggle open signup on or off
3. **AI setup** — complete the setup wizard, configure providers and models, manage API keys (owner only, but admins often coordinate this)
4. **System health** — monitor the Dashboard and health endpoint
5. **Audit trail** — review the audit log for security-relevant actions

**For infrastructure tasks** (deployment, config files, environment variables, network shares), see [Section 5: Admin and Setup](#5-admin-and-setup).

---

## 5. Admin and Setup

This section is for the person installing, configuring, and maintaining the system.

### 5.1 First-Time System Setup

1. **Install Python** 3.10, 3.11, 3.12, or 3.13.
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **(Optional) Lock the owner email** — if you want to restrict who can claim owner on first signup:
   ```bash
   export BB_OWNER_EMAIL="owner@yourcompany.com"
   ```
   If not set, the first person to sign up becomes the owner with any email.
4. **Set a persistent JWT secret** (so sessions survive server restarts):
   ```bash
   export BB_SECRET_KEY="a-long-random-string-at-least-32-characters"
   ```
5. **Start the web application:**
   ```bash
   python stats.py
   ```
6. **Open a browser** and go to `http://localhost:8080/auth/signup`. The first user to sign up becomes the system owner.
7. **Start the ingestion service** (if you need document processing):
   ```bash
   python main.py
   ```

### 5.2 Configuration File

All configuration lives in a single JSON file. The default location is `./config.json`, overridable with `--config` or the `BB_CONFIG` environment variable.

Every key is validated on startup. Unknown keys are rejected. Invalid values cause an immediate error.

See [Appendix B: Configuration Reference](#appendix-b-configuration-reference) for the full list of keys, types, defaults, and constraints.

**Critical validation rules:**
- All five directory paths (input, processing, output, rejected, logs) must be distinct. No path can be a parent or child of another.
- All five directory paths must be on the same filesystem volume.
- `barcode_value_patterns` entries are compiled as regex on startup. A bad regex pattern causes an immediate startup failure.

### 5.3 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `BB_CONFIG` | `config.json` | Config file path (overridden by `--config` flag) |
| `BB_SECRET_KEY` | (empty) | JWT secret for session persistence. **Set this in production.** If empty, a random key is generated per startup, meaning all user sessions are invalidated on every restart. |
| `BB_OWNER_EMAIL` | (not set) | If set, the first signup must use this email. If not set, anyone can claim owner on first signup. |
| `BB_SMTP_HOST` | (empty) | SMTP server hostname for password reset emails |
| `BB_SMTP_PORT` | `587` | SMTP port |
| `BB_SMTP_USER` | (empty) | SMTP username |
| `BB_SMTP_PASSWORD` | (empty) | SMTP password |
| `BB_SMTP_USE_TLS` | `true` | Enable TLS for SMTP |
| `BB_RESET_FROM` | (empty) | "From" address for reset emails |

### 5.4 Running the Web Application

```bash
python stats.py [--config PATH] [--host HOST] [--port PORT] [--refresh-seconds N] [--history-days N] [--recent-limit N]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config` | `BB_CONFIG` or `config.json` | Config file path |
| `--host` | from config or `0.0.0.0` | Bind address |
| `--port` | from config or `8080` | Bind port |
| `--refresh-seconds` | `15` | Dashboard auto-refresh interval (minimum 5) |
| `--history-days` | `14` | Days of history on dashboard (minimum 1) |
| `--recent-limit` | `25` | Recent documents on dashboard (minimum 1) |

The database is created automatically at `{log_path}/barcode_buddy.db` using SQLite with WAL mode. All tables are created on first run.

API documentation (Swagger UI) is available at `http://your-server:8080/docs`.

### 5.5 Running the Document Ingestion Service

```bash
python main.py [--config PATH]
```

On startup, the service:
1. Loads and validates the configuration
2. Creates all required directories if they do not exist
3. Acquires an exclusive lock per workflow (prevents duplicate instances of the same workflow)
4. Recovers any in-flight files from the `processing/.journal/` directory
5. Begins watching the input folder using OS-level file notifications

**Shutdown:** Send SIGINT (Ctrl+C) or SIGTERM. The service finishes any file currently being processed before exiting.

**Lock file:** Created at `{log_path}/.service.lock` with JSON metadata (workflow, PID, config version, timestamp). If a stale lock file exists from a crashed process, the service detects and replaces it.

### 5.6 Running Multiple Workflows

For organizations with separate document types (receiving, shipping/POD, quality/compliance), run one ingestion service per workflow:

```bash
python main.py --config configs/config.receiving.json
python main.py --config configs/config.shipping-pod.json
python main.py --config configs/config.quality-compliance.json
```

Each workflow needs:
- Its own config file with a unique `workflow_key`
- Its own five directories (input, processing, output, rejected, logs)
- Its own barcode type and pattern rules
- Its own duplicate handling mode (`reject` for receiving and quality; `timestamp` for shipping/POD)

Example directory layout:

```text
D:\barcodebuddy\receiving\input
D:\barcodebuddy\receiving\processing
D:\barcodebuddy\receiving\output
D:\barcodebuddy\receiving\rejected
D:\barcodebuddy\receiving\logs

D:\barcodebuddy\shipping-pod\input
D:\barcodebuddy\shipping-pod\output
...
```

The web application (`stats.py`) only needs to run once — it is not per-workflow.

### 5.7 Windows Deployment

**Quick start with Cloudflare Tunnel:**
```powershell
powershell -ExecutionPolicy Bypass -File start-app.ps1
```

This starts the web app and a Cloudflare tunnel on port 8080. It watches both processes and restarts either if they crash. The public URL is saved to `data/logs/tunnel-url.txt`.

**Named tunnel** (permanent URL): Requires `~/.cloudflared/barcodebuddy.yml` and a DNS CNAME (e.g., `app.danpack.com`).

**Quick tunnel** (temporary URL): Works out of the box for testing.

**Autostart on login:**
```powershell
# Run as Administrator
powershell -ExecutionPolicy Bypass -File install-autostart.ps1
```

Creates a scheduled task named "BarcodeBuddy" that starts on login with automatic crash restart.

**To remove autostart:**
```powershell
Unregister-ScheduledTask -TaskName "BarcodeBuddy" -Confirm:$false
```

### 5.8 Docker Deployment

```bash
docker build -t barcodebuddy .
docker run -p 8080:8080 -v /your/data:/app/data barcodebuddy
```

The container runs as non-root (`appuser`), exposes port 8080, and includes a health check at `/health`.

**Important:** The container runs the web application only. For document ingestion, run a second container (or a host process) with `python main.py` and shared volume mounts.

### 5.9 Railway Deployment

Push the repository to Railway. The `railway.toml` file configures automatic builds with Nixpacks and health checks on `/health`.

### 5.10 Setting Up AI

The owner must complete this before anyone can use the AI chat.

1. Log in as the owner.
2. Go to **AI Setup** in the sidebar (or navigate to `/ai/setup`).
3. Choose a mode:
   - **Local** — requires Ollama running on the same machine (default URL: `http://localhost:11434`). All data stays on your network.
   - **Cloud** — requires an API key from Anthropic or OpenAI. Data is sent to the provider.
   - **Hybrid** — uses local for some tasks, cloud for others.
4. Follow the wizard steps to configure connection details, select models, and assign them to task types (chat, vision, CSV analysis, item suggestions).
5. Complete the wizard.

**After setup:** All users can access AI Chat. Settings can be changed later at `/ai/settings`.

**API keys are encrypted at rest.** They are never returned by the API — only a boolean indicating whether a key is present.

### 5.11 Setting Up Email (Password Resets)

If you want the password reset flow to send emails:

```bash
export BB_SMTP_HOST="smtp.yourcompany.com"
export BB_SMTP_PORT="587"
export BB_SMTP_USER="noreply@yourcompany.com"
export BB_SMTP_PASSWORD="your-smtp-password"
export BB_SMTP_USE_TLS="true"
export BB_RESET_FROM="noreply@yourcompany.com"
```

If these are not set, password resets are silently skipped. Users must ask an admin to reset their password manually via the Admin Panel.

For LAN-only deployments where everyone is in the same building, this is fine. Admins can reset passwords directly.

### 5.12 Scanner and Network Share Setup

**Scanner profile recommendations:**
- Output format: PDF (not TIFF — TIFF is not yet supported)
- DPI: 300 or higher
- Mode: "one file per scan" (not "one file per page")
- Destination: the BarcodeBuddy input folder for the relevant workflow
- Duplex: enabled if the scanner supports it

**Network shares (SMB):** If scanners are on different machines than the server, share only the input folders:

```text
\\server\receiving-input    → D:\barcodebuddy\receiving\input
\\server\shipping-input     → D:\barcodebuddy\shipping-pod\input
\\server\quality-input      → D:\barcodebuddy\quality-compliance\input
```

Do not share the processing, output, or rejected folders over the network. They are managed by the system.

### 5.13 Health Monitoring

**Health endpoint:** `GET /health`

Returns HTTP 200 only when:
1. The ingestion worker's heartbeat is recent
2. The service lock file exists

Use this for load balancers, Docker health checks, Kubernetes probes, or uptime monitoring.

**Prometheus metrics:** `GET /metrics` — exposes Prometheus-compatible gauges.

**Processing logs:** JSONL files at `{log_path}/processing_log.jsonl` with daily rotation. Every event includes schema version, workflow, hostname, instance ID, config version, processing stage, duration, and error code.

**Database backups:** Automatic with 14-day rolling retention at `{log_path}/barcode_buddy.{timestamp}.db`.

---

## 6. Troubleshooting

### Authentication Problems

| Problem | Cause | Fix |
|---------|-------|-----|
| Cannot sign up | Admin has closed signup | Ask an admin to re-enable it in Admin Panel |
| Cannot sign up (first user) | `BB_OWNER_EMAIL` is set and you used a different email | Use the email configured in `BB_OWNER_EMAIL`, or ask IT to unset it |
| Login fails after correct password | Rate limited (10 attempts per 60 seconds) | Wait 60 seconds and try again |
| Logged out unexpectedly | 24-hour session expired | Log in again. If it happens on every server restart, tell IT to set `BB_SECRET_KEY`. |
| Password reset email never arrives | SMTP not configured | Ask an admin to reset your password via Admin Panel |

### Document Ingestion Problems

| Problem | Cause | Fix |
|---------|-------|-----|
| Files sit in the input folder and nothing happens | Ingestion service is not running | Tell IT to start `main.py` |
| File goes to rejected folder | See the `.meta.json` sidecar for the exact reason | See [2.7: Investigating a Rejected Document](#27-investigating-a-rejected-document) |
| "No barcode found" on a document that has a barcode | Poor scan quality, barcode partially cut off, or DPI too low | Re-scan at 300 DPI or higher. Ensure the barcode is fully visible and not wrinkled. |
| Duplicate rejection on an intentional rescan | Workflow is in `reject` mode | If rescans are normal for this workflow (e.g., shipping/POD), IT should switch to `timestamp` mode |
| Lock file error on startup | Another instance of the same workflow is running | Stop the other instance first. If it crashed, the stale lock is cleaned up automatically. |

### Inventory and Web App Problems

| Problem | Cause | Fix |
|---------|-------|-----|
| Alerts not firing for an item | `min_quantity` is not set | Edit the item and set a min_quantity value |
| Camera scanning does not work | Unsupported browser | Use Chrome or Edge. Firefox does not support the BarcodeDetector API. |
| AI chat shows an error | AI is not configured | The owner needs to complete AI setup at `/ai/setup` |
| AI returns "provider unavailable" | Ollama is down or cloud API key is invalid | Check AI settings. For Ollama, make sure the Ollama service is running. For cloud, verify the API key. |
| Items list is empty but you know items exist | You are viewing your own inventory and the items belong to another user | Ask a manager or admin to check. Managers+ can view cross-user inventory. |
| Database locked errors | Multiple `stats.py` instances running against the same database | Only one instance of `stats.py` should run per database file |
| Imported CSV created duplicates | CSV rows had no `sku` column | The system uses SKU for duplicate detection during import. Without it, every row creates a new item. |

### System-Level Problems

| Problem | Cause | Fix |
|---------|-------|-----|
| All users logged out after server restart | No persistent `BB_SECRET_KEY` | Set the `BB_SECRET_KEY` environment variable to a fixed, random string of at least 32 characters |
| "Unknown config key" on startup | Config file has a typo or unsupported key | Check the config file against [Appendix B](#appendix-b-configuration-reference). Every key is validated. |
| "Paths must be on same volume" on startup | Config paths span different drives | Move all five directories (input, processing, output, rejected, logs) to the same drive |
| Startup crashes with regex error | Invalid pattern in `barcode_value_patterns` | Fix the regex syntax in your config file. Test your patterns at regex101.com first. |

---

## Appendix A: Roles and Permissions Matrix

| Capability | Owner | Admin | Manager | User |
|-----------|-------|-------|---------|------|
| View own inventory | Yes | Yes | Yes | Yes |
| Create, edit, delete own items | Yes | Yes | Yes | Yes |
| Adjust stock quantities | Yes | Yes | Yes | Yes |
| Import and export inventory | Yes | Yes | Yes | Yes |
| Barcode scan lookup | Yes | Yes | Yes | Yes |
| Scan to PDF | Yes | Yes | Yes | Yes |
| View analytics | Yes | Yes | Yes | Yes |
| View activity log | Yes | Yes | Yes | Yes |
| View and manage own alerts | Yes | Yes | Yes | Yes |
| Use AI chat | Yes | Yes | Yes | Yes |
| View calendar | Yes | Yes | Yes | Yes |
| Join teams | Yes | Yes | Yes | Yes |
| Create teams | Yes | Yes | Yes | No |
| View other users' inventory | Yes | Yes | Yes | No |
| Manage team members (as team lead) | Yes | Yes | Yes | No |
| Manage all users | Yes | Yes | No | No |
| Change user roles | Yes | Yes | No | No |
| Activate/deactivate users | Yes | Yes | No | No |
| View admin audit log | Yes | Yes | No | No |
| Toggle open signup | Yes | Yes | No | No |
| Configure AI settings | Yes | No | No | No |
| Run AI setup wizard | Yes | No | No | No |
| Transfer ownership | Yes | No | No | No |

---

## Appendix B: Configuration Reference

### Required Settings

| Key | Type | Description |
|-----|------|-------------|
| `input_path` | string | Folder where scanned documents are dropped |
| `processing_path` | string | Temporary folder for files being processed |
| `output_path` | string | Destination for successfully filed PDFs |
| `rejected_path` | string | Destination for failed files and meta sidecars |
| `log_path` | string | Processing logs, daily archives, and database |
| `barcode_types` | string[] | Barcode formats to scan for. At least one required. Values: `code128`, `qr`, `ean13`, `code39`, `datamatrix`, `auto` |
| `scan_all_pages` | bool | `true` = scan every page. `false` = first page only. |
| `duplicate_handling` | string | `"timestamp"` (keep both, append timestamp) or `"reject"` (reject the second file) |
| `file_stability_delay_ms` | int | Wait this many ms for file to stop changing before processing. Minimum: 500. |
| `max_pages_scan` | int | Maximum pages to scan per document. Minimum: 1. Default: 50. |

### Optional Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `workflow_key` | string | `"default"` | Identifier for this workflow. Lowercase alphanumeric with hyphens/underscores, max 64 chars. |
| `barcode_value_patterns` | string[] | `[]` | Regex patterns barcodes must match. Empty = accept all. |
| `poll_interval_ms` | int | `500` | Folder polling interval. Minimum: 100. |
| `barcode_scan_dpi` | int | `300` | DPI for rendering PDF pages. Minimum: 72. |
| `barcode_upscale_factor` | float | `1.0` | Image upscale factor before barcode decode. Minimum: 1.0. |
| `server_host` | string | `"0.0.0.0"` | Web server bind address. |
| `server_port` | int | `8080` | Web server bind port. Range: 1–65535. |
| `secret_key` | string | `""` | JWT secret for session persistence. Empty = random per startup. |

---

## Appendix C: Glossary

| Term | Meaning |
|------|---------|
| **Barcode value** | The text encoded in a barcode (e.g., "PO-2026-0042"). This is what the system reads and uses as the filename. |
| **Barcode type** | The encoding format: Code128, QR, EAN-13, Code39, or DataMatrix. |
| **Business-rule pattern** | A regex pattern in the config that barcodes must match. Used to filter out stray or irrelevant barcodes. |
| **Duplicate handling** | What happens when a second document has the same barcode. `timestamp` keeps both. `reject` blocks the second. |
| **Hot folder** | The input directory that the ingestion service watches for new files. |
| **Ingestion service** | The `main.py` process that automatically picks up, reads, and files scanned documents. |
| **Journal** | A crash-recovery file in `processing/.journal/` that tracks files mid-processing. If the service crashes, it uses the journal to recover. |
| **Meta sidecar** | A `.meta.json` file that appears next to a rejected document, explaining why it was rejected. |
| **Min quantity** | The stock level below which an item triggers a low-stock alert. Set per item. |
| **Owner** | The top-level account. Created during first signup. Only one exists at a time. Full system control. |
| **SKU** | Stock Keeping Unit. A unique identifier you assign to an inventory item. Used for lookups and deduplication during imports. |
| **Transaction** | An immutable record of a stock quantity change (received, sold, adjusted, damaged, returned). Cannot be edited or deleted. |
| **WAL mode** | Write-Ahead Logging. A SQLite mode that allows reads and writes to happen at the same time without locking. |
| **Workflow** | A named configuration for a specific document type (receiving, shipping_pod, quality_compliance). Each workflow runs as its own ingestion service instance. |

---

## Appendix D: Known Gaps

These are things the system does not do yet. They are documented here so you do not waste time looking for them.

| Gap | Status | Notes |
|-----|--------|-------|
| **TIFF file support** | Not started | The ingestion service accepts PDF, JPG, and PNG only. TIFF documents must be converted before scanning. |
| **Multi-document batch splitting** | Not started | If one PDF contains multiple documents (e.g., a batch of packing slips), the system treats it as a single document. You must split them before scanning. |
| **Scan Record Workbench** | Not started | A planned feature for deep-diving into a single scan record's full lifecycle (processing history, linked obligations, notes, attachments). |
| **Operations Planner** | Not started | A planned feature for multi-record planning: scan obligations, shift reports, daily close-outs, tomorrow forecasts, and workload control. |
| **Environment variable overrides for config** | Not started | Config values can only be set in the JSON file (except `BB_SECRET_KEY` which overrides `secret_key`). |
| **Admin-created accounts** | Not available | Admins cannot create accounts directly. They must enable open signup, have the person sign up, then disable signup again. |
| **Bulk item creation via UI** | Not available | You can bulk import from CSV/JSON, but there is no multi-item creation form. |
| **Firefox camera scanning** | Browser limitation | The BarcodeDetector API is not supported in Firefox. Use Chrome or Edge. |
| **Mobile app** | Does not exist | The web app works in mobile browsers but there is no native app. |
| **Email notifications for alerts** | Not available | Alerts appear in the web UI and can be sent to a webhook URL. There is no built-in email notification for stock alerts. |
