# BarcodeBuddy User Manual

Last updated: 2026-04-04.

This manual covers every feature of BarcodeBuddy from the perspective of the person using it. It is organized by role so you can jump to the section that applies to you, then by feature so you can look up exactly what you need.

---

## Table of Contents

- [1. What Is BarcodeBuddy?](#1-what-is-barcodebuddy)
- [2. Quick Start by Role](#2-quick-start-by-role)
  - [2.1 Scanner Operator / Warehouse Clerk](#21-scanner-operator--warehouse-clerk)
  - [2.2 Inventory Manager](#22-inventory-manager)
  - [2.3 Department Lead / Manager](#23-department-lead--manager)
  - [2.4 Operations Owner / Executive](#24-operations-owner--executive)
  - [2.5 System Administrator](#25-system-administrator)
  - [2.6 IT / Infrastructure Admin](#26-it--infrastructure-admin)
- [3. Getting In — Authentication](#3-getting-in--authentication)
  - [3.1 First-Time Setup (Owner Account)](#31-first-time-setup-owner-account)
  - [3.2 Signing Up](#32-signing-up)
  - [3.3 Logging In](#33-logging-in)
  - [3.4 Resetting Your Password](#34-resetting-your-password)
  - [3.5 Sessions and Security](#35-sessions-and-security)
- [4. Navigation](#4-navigation)
- [5. Dashboard](#5-dashboard)
- [6. Inventory Management](#6-inventory-management)
  - [6.1 Viewing Your Inventory](#61-viewing-your-inventory)
  - [6.2 Creating an Item](#62-creating-an-item)
  - [6.3 Viewing Item Details](#63-viewing-item-details)
  - [6.4 Editing an Item](#64-editing-an-item)
  - [6.5 Adjusting Stock Quantity](#65-adjusting-stock-quantity)
  - [6.6 Deleting an Item](#66-deleting-an-item)
  - [6.7 Barcode Generation](#67-barcode-generation)
  - [6.8 Barcode / SKU Scan Lookup](#68-barcode--sku-scan-lookup)
  - [6.9 Camera Scanning](#69-camera-scanning)
  - [6.10 Bulk Import (CSV / JSON)](#610-bulk-import-csv--json)
  - [6.11 Bulk Export (CSV / JSON)](#611-bulk-export-csv--json)
  - [6.12 Bulk Actions](#612-bulk-actions)
- [7. Scan-to-PDF](#7-scan-to-pdf)
- [8. Calendar View](#8-calendar-view)
- [9. Analytics](#9-analytics)
  - [9.1 Valuation](#91-valuation)
  - [9.2 Velocity](#92-velocity)
  - [9.3 Stock Health](#93-stock-health)
- [10. Alerts](#10-alerts)
- [11. Activity Log](#11-activity-log)
- [12. Team Management](#12-team-management)
  - [12.1 Creating a Team](#121-creating-a-team)
  - [12.2 Managing Members](#122-managing-members)
  - [12.3 Tasks](#123-tasks)
- [13. AI Assistant](#13-ai-assistant)
  - [13.1 Setup Wizard](#131-setup-wizard)
  - [13.2 AI Chat](#132-ai-chat)
  - [13.3 AI Tools](#133-ai-tools)
  - [13.4 AI Settings](#134-ai-settings)
  - [13.5 Privacy and Data Handling](#135-privacy-and-data-handling)
- [14. Admin Panel](#14-admin-panel)
  - [14.1 User Management](#141-user-management)
  - [14.2 Role Assignments](#142-role-assignments)
  - [14.3 Open/Closed Signup](#143-openclosed-signup)
  - [14.4 Ownership Transfer](#144-ownership-transfer)
  - [14.5 Audit Log](#145-audit-log)
- [15. Document Ingestion Service](#15-document-ingestion-service)
  - [15.1 How It Works](#151-how-it-works)
  - [15.2 Supported File Formats](#152-supported-file-formats)
  - [15.3 Barcode Detection](#153-barcode-detection)
  - [15.4 What Happens to Your Files](#154-what-happens-to-your-files)
  - [15.5 Duplicate Handling](#155-duplicate-handling)
  - [15.6 Rejections](#156-rejections)
  - [15.7 Workflows](#157-workflows)
- [16. System Setup and Deployment](#16-system-setup-and-deployment)
  - [16.1 Requirements](#161-requirements)
  - [16.2 Installation](#162-installation)
  - [16.3 Configuration Reference](#163-configuration-reference)
  - [16.4 Environment Variables](#164-environment-variables)
  - [16.5 Running the Web Application](#165-running-the-web-application)
  - [16.6 Running the Ingestion Service](#166-running-the-ingestion-service)
  - [16.7 Windows Deployment](#167-windows-deployment)
  - [16.8 Docker Deployment](#168-docker-deployment)
  - [16.9 Railway Deployment](#169-railway-deployment)
  - [16.10 Running Multiple Workflows](#1610-running-multiple-workflows)
- [17. Health and Monitoring](#17-health-and-monitoring)
- [18. Troubleshooting](#18-troubleshooting)
- [19. Roles and Permissions Reference](#19-roles-and-permissions-reference)
- [20. Glossary](#20-glossary)

---

## 1. What Is BarcodeBuddy?

BarcodeBuddy is two things:

1. **A document ingestion service** — a headless hot-folder watcher that picks up scanned paperwork (packing slips, proof-of-delivery, invoices, receiving slips), reads the barcode on each document, converts it to PDF, and files it automatically by barcode value. No manual renaming. No clerk intervention.

2. **A web application** — a multi-user system for inventory management, monitoring, analytics, alerts, team collaboration, and AI-assisted operations.

The ingestion service runs as `main.py`. The web application runs as `stats.py`. They share the same configuration file and data directories but run as separate processes.

---

## 2. Quick Start by Role

Find your role below. This tells you what BarcodeBuddy does for you and where to go first.

### 2.1 Scanner Operator / Warehouse Clerk

**What you do:** Drop scanned documents into a folder. BarcodeBuddy files them automatically.

**Your workflow:**
1. Scan your document (packing slip, POD, invoice) using your desktop scanner or scan app
2. Save or send the scan to the designated input folder (your IT team will tell you which one)
3. Done. BarcodeBuddy picks it up, reads the barcode, converts it to PDF, and files it

**If something goes wrong:** The document lands in the `rejected` folder with a `.meta.json` file explaining why. Common reasons: no barcode found, unreadable file, duplicate (if reject mode is on). Tell your supervisor.

**Web app pages you'll use:**
- **Scan** (`/scan`) — look up an item by typing or scanning a barcode
- **Inventory** (`/inventory`) — view and adjust stock
- **Scan to PDF** (`/scan-to-pdf`) — scan multiple barcodes and generate a PDF report

### 2.2 Inventory Manager

**What you do:** Track stock levels, manage items, handle adjustments, monitor alerts.

**Start here:**
1. Log in at your BarcodeBuddy URL
2. Go to **Items** in the sidebar to see your inventory
3. Go to **Alerts** to see low-stock and overstock warnings
4. Go to **Analytics** for valuation, velocity, and stock health reports

**Key tasks:**
- Create items: **Items → New Item** (or sidebar "New Item")
- Adjust stock: Open any item → click **Adjust Qty** → enter change, reason, and notes
- Import stock: **Import CSV** in the sidebar → upload a CSV or JSON file
- Export stock: **Items** page → Export button (top right) or **Bulk** page → Export tab
- Generate barcodes: Every item gets a barcode automatically; download or print from the item detail page

### 2.3 Department Lead / Manager

**What you do:** Manage your team, assign tasks, review workflow-specific reports.

**Start here:**
1. Log in → go to **Team** in the sidebar
2. Create a team (requires manager role or above)
3. Add members and assign roles (lead, member, viewer)
4. Create tasks with priorities and due dates

**Monitoring:**
- **Dashboard** (`/`) — processing throughput, success/failure rates, queue state
- **Analytics** (`/analytics`) — inventory valuation, stock movement velocity, health distribution
- **Activity Log** (`/activity`) — who did what, when, with full audit trail

### 2.4 Operations Owner / Executive

**What you do:** See the big picture across all operations.

**Start here:**
1. Log in → **Dashboard** shows real-time processing state
2. **Analytics** shows inventory valuation by category and location, top movers, stock health
3. **Activity Log** shows all system activity with date range and category filters
4. **Admin Panel** shows user accounts, system settings, and the full audit log

**What you're looking for:**
- Queue backlog (dashboard) — are documents piling up?
- Failure rate (dashboard) — are scans failing more than usual?
- Low stock count (inventory summary) — are we running out of things?
- Transaction trends (analytics) — is activity increasing or decreasing?

### 2.5 System Administrator

**What you do:** Manage users, roles, system settings, and AI configuration.

**Start here:**
1. Log in as owner or admin
2. **Admin Panel** (`/admin`) — manage users, toggle open signup, view audit log
3. **AI Setup** (`/ai/setup`) — configure AI providers (owner only)
4. **AI Settings** (`/ai/settings`) — adjust models, rate limits, API keys (owner only)

**Key responsibilities:**
- Promote users to admin/manager roles via Admin Panel
- Enable or disable open signup
- Configure AI (Ollama local, Anthropic cloud, OpenAI cloud)
- Review audit log for security-relevant actions
- Transfer ownership if needed

### 2.6 IT / Infrastructure Admin

**What you do:** Install, configure, and maintain the BarcodeBuddy deployment.

**Start here:**
1. Read [Section 16: System Setup and Deployment](#16-system-setup-and-deployment)
2. Choose your deployment: Windows service, Docker, or Railway
3. Configure `config.json` with your paths and barcode settings
4. Set environment variables (`BB_OWNER_EMAIL`, `BB_SECRET_KEY`, SMTP if needed)
5. Set up scanner profiles to save to the input folder
6. Share the input folder over SMB if scanners are on a different machine

---

## 3. Getting In — Authentication

### 3.1 First-Time Setup (Owner Account)

The very first person to sign up becomes the **owner**. This signup must use the email address configured in the `BB_OWNER_EMAIL` environment variable (default: `mferragamo@danpack.com`).

1. Navigate to `http://your-server:8080/auth/signup`
2. Enter a display name, the owner email, and a password
3. You are now the owner with full system access

No other accounts can be created until you enable open signup or create accounts yourself.

### 3.2 Signing Up

After the owner account exists, additional users can sign up only if **open signup** is enabled (the owner or an admin toggles this in the Admin Panel).

1. Navigate to `/auth/signup`
2. Enter your display name, email, and password
3. You will be assigned the **user** role by default
4. An admin or the owner can promote you to **manager** or **admin** later

### 3.3 Logging In

1. Navigate to `/auth/login`
2. Enter your email and password
3. You will be redirected to the dashboard

Login is rate-limited to 10 attempts per 60 seconds per IP address. If you exceed this, wait one minute.

### 3.4 Resetting Your Password

1. On the login page, click **Forgot password?**
2. Enter your email address
3. If SMTP is configured, you will receive a reset email with a one-time link
4. Click the link and enter your new password
5. The reset token is valid for 1 hour

If SMTP is not configured (common in LAN deployments), ask your admin to reset your password via the Admin Panel.

### 3.5 Sessions and Security

- Your session lasts 24 hours. After that, you need to log in again.
- Sessions are stored as secure HTTP-only cookies (`bb_session`).
- An admin can deactivate your account, which immediately revokes all sessions.
- All login attempts, logouts, and password changes are recorded in the audit log.

---

## 4. Navigation

The web application uses a persistent **left sidebar** with the following sections:

**INVENTORY**
| Link | Page | What it does |
|------|------|-------------|
| Scan | `/scan` | Look up items by barcode or SKU (manual entry or camera) |
| Scan to PDF | `/scan-to-pdf` | Scan multiple barcodes and generate a PDF report |
| Items | `/inventory` | Full inventory list with search and filters |
| Calendar | `/calendar` | Month/day calendar of inventory activity |
| New Item | `/inventory/new` | Create a new inventory item |
| Import CSV | `/inventory/import` | Import items from CSV or JSON |

**MONITOR**
| Link | Page | What it does |
|------|------|-------------|
| Dashboard | `/` | Processing stats, queue state, health, throughput |
| Analytics | `/analytics` | Valuation, velocity, and stock health reports |
| Activity Log | `/activity` | Full audit trail of all system activity |
| Alerts | `/alerts` | Low-stock and overstock alert management |

**AI**
| Link | Page | What it does |
|------|------|-------------|
| AI Chat | `/ai/chat` | Conversational AI assistant with inventory tools |
| Privacy & Data | `/ai/privacy` | How AI handles your data |
| AI Settings | `/ai/settings` | Configure AI providers and models (owner/admin) |
| AI Setup | `/ai/setup` | First-time AI configuration wizard (owner/admin) |

**SYSTEM**
| Link | Page | What it does |
|------|------|-------------|
| Team | `/team` | Team management, members, and tasks |
| Admin Panel | `/admin` | User management, settings, audit log (admin/owner) |

The sidebar collapses to icons on narrow screens. There is also a **floating AI chat button** in the bottom-right corner for quick access to the AI assistant from any page.

The top area includes:
- **Alert bell** with unread count badge
- **Recent activity drawer** (latest 20 events)
- **User profile** at the sidebar bottom with your name, role badge, and sign-out link

---

## 5. Dashboard

**URL:** `/` (homepage after login)

The dashboard shows real-time operational state:

| Section | What it shows |
|---------|--------------|
| **Processing counts** | Total documents processed, successful, failed |
| **Queue state** | Files waiting in the input folder, files currently processing |
| **Service health** | Whether the ingestion worker is running, last heartbeat time |
| **Latency** | P50, P95, P99 processing times |
| **24-hour summary** | Activity breakdown for the last 24 hours |
| **Top failure reasons** | Most common error codes from recent failures |
| **Hourly throughput** | Documents processed per hour (chart) |
| **Quality analytics** | Average quality scores, common issues, barcode format breakdown |

All data refreshes automatically. The dashboard reads from the JSONL processing logs and the ingestion worker's heartbeat.

---

## 6. Inventory Management

### 6.1 Viewing Your Inventory

**URL:** `/inventory`

The inventory list shows all your items in a searchable, filterable table.

**Search and filter:**
- Type in the search bar to filter by name, SKU, barcode, location, or tags
- Use the category dropdown to filter by category
- Items are sorted by most recently updated

**Table columns:**
| Column | Description |
|--------|-------------|
| Name | Item name (click to open detail page) |
| SKU | Stock keeping unit identifier |
| Qty | Current quantity (color-coded: red = out of stock, yellow = low, green = healthy) |
| Location | Storage location |
| Category | Item category |
| Barcode | Barcode value |
| Status | Active or Archived |

**Summary bar** at the top shows: active items count, total units, categories, low stock count, and out-of-stock count.

Each user sees only their own inventory. Managers and above can view other users' inventory.

### 6.2 Creating an Item

**URL:** `/inventory/new`

Fill in the form:

| Field | Required | Description |
|-------|----------|-------------|
| Name | Yes | Item name |
| SKU | No | Stock keeping unit (auto-generated if left blank) |
| Description | No | Free text description |
| Quantity | No | Starting quantity (default: 0) |
| Unit | No | Unit of measure (e.g., "pcs", "kg", "boxes") |
| Min Quantity | No | Threshold for low-stock alerts |
| Cost | No | Unit cost (for valuation reports) |
| Tags | No | Comma-separated tags for filtering |
| Location | No | Storage location |
| Category | No | Category grouping |
| Barcode Type | No | Code128, QR, EAN-13, Code39, or DataMatrix (default: Code128) |
| Barcode Value | No | Custom value or leave empty for auto-generation |
| Notes | No | Additional notes |

**AI suggestions:** If AI is configured, click the lightbulb button next to Min Quantity, Location, or Category for AI-powered suggestions based on your existing inventory patterns.

**Autosave:** Your draft is saved to your browser's local storage. If you navigate away and come back, your draft will be restored.

Click **Create Item** to save. The item gets a barcode automatically.

### 6.3 Viewing Item Details

**URL:** `/inventory/{item_id}`

The detail page shows everything about one item:

**Left panel:**
- All item fields (quantity shown large and color-coded)
- Action buttons: **Adjust Qty**, **Edit**, **Delete**
- Full transaction history table (date, quantity change, running total, reason, notes)

**Right panel (sticky):**
- Barcode image (Code128 or QR depending on type)
- **Download** button — saves barcode as PNG
- **Print** button — opens print dialog for the barcode label

### 6.4 Editing an Item

On the item detail page, click **Edit**. All fields become editable. Make your changes and click **Save**. Click **Cancel** to discard.

Changes are logged in the activity log.

### 6.5 Adjusting Stock Quantity

On the item detail page, click **Adjust Qty**. A dialog appears:

| Field | Description |
|-------|-------------|
| Change | Positive number to add, negative to remove (e.g., +50 or -10) |
| Reason | Select one: Received, Sold, Adjusted, Damaged, Returned |
| Notes | Optional explanation |

Click **Apply**. The adjustment creates an immutable transaction record. The previous quantity and new quantity are both stored — nothing is overwritten.

Every adjustment appears in the transaction history on the item detail page and in the activity log.

### 6.6 Deleting an Item

On the item detail page, click **Delete**. Confirm the deletion. This permanently removes the item and its transaction history.

For bulk deletion, use the **Bulk** page.

### 6.7 Barcode Generation

Every inventory item gets a barcode automatically when created. Supported formats:

| Format | Best for |
|--------|----------|
| Code128 | General purpose, alphanumeric, most common |
| QR | Mobile scanning, holds more data |
| EAN-13 | Retail products (13-digit numeric) |
| Code39 | Legacy systems, alphanumeric |
| DataMatrix | Small labels, industrial marking |

From the item detail page:
- **Download** — saves the barcode as a PNG image file
- **Print** — opens your browser's print dialog with the barcode sized for label printing

To preview a barcode before creating an item, the system generates a live preview on the new item form.

### 6.8 Barcode / SKU Scan Lookup

**URL:** `/scan`

This page lets you look up inventory items instantly:

**Manual lookup:**
1. Type a barcode value or SKU in the text field
2. Click **Lookup** or press Enter
3. Matching items appear in the results table

The results show: name, SKU, quantity, location, category, barcode, and status. Click any item to go to its detail page.

### 6.9 Camera Scanning

On the **Scan** page (`/scan`), click **Start Camera**:

1. Select your camera device from the dropdown (if you have multiple)
2. Point the camera at a barcode
3. The browser's BarcodeDetector API reads the barcode automatically
4. The item is looked up and shown in the results

Camera scanning also works on the **Scan to PDF** page for batch operations.

**Requirements:** Camera scanning uses the browser's built-in BarcodeDetector API. This works in Chrome, Edge, and other Chromium browsers. Firefox does not support this API natively.

### 6.10 Bulk Import (CSV / JSON)

**URL:** `/inventory/import`

**CSV import:**
1. Click the **CSV** tab
2. Drag and drop your CSV file (or click to browse)
3. A preview of the first 50 rows appears
4. Review and click **Import**

**Expected CSV columns:**
| Column | Required | Notes |
|--------|----------|-------|
| name | Yes | Item name |
| sku | No | If provided, used for duplicate detection |
| quantity | No | Starting stock (default: 0) |
| unit | No | Unit of measure |
| location | No | Storage location |
| category | No | Category |
| cost | No | Unit cost |
| min_quantity | No | Low-stock threshold |
| description | No | Description |
| tags | No | Comma-separated |
| notes | No | Additional notes |
| barcode_type | No | Code128, QR, etc. |
| barcode_value | No | Custom barcode value |

**Conflict handling:** If a SKU already exists in your inventory, the import updates the existing item rather than creating a duplicate.

**JSON import:** Same fields, but as a JSON array of objects.

### 6.11 Bulk Export (CSV / JSON)

**URL:** `/inventory/bulk` → Export tab

1. Choose format: **CSV** or **JSON**
2. Optionally filter by: Status (active/archived/all), Category, Location
3. A live preview shows the count, total quantity, and total value of matching items
4. Click **Download**

You can also export directly from the Items page using the **Export** button in the top right.

### 6.12 Bulk Actions

**URL:** `/inventory/bulk`

Select multiple items and perform batch operations:
- **Bulk update:** Change location, category, or status for all selected items
- **Bulk delete:** Remove multiple items at once

---

## 7. Scan-to-PDF

**URL:** `/scan-to-pdf`

Scan-to-PDF lets you scan multiple barcodes in a session and generate a professional PDF report. This is useful for:
- Physical inventory counts
- Receiving inspections
- Shipping manifests
- Any situation where you need to scan a batch and produce a document

**Three input methods:**

| Tab | How it works |
|-----|-------------|
| **Manual** | Type barcode values (supports pasting multiple codes, one per line) |
| **Camera** | Point your camera at barcodes; they are detected and added automatically |
| **Upload** | Drag-drop or browse for PNG, JPG, PDF, TIFF, or BMP files; barcodes are extracted automatically |

**Building your session:**
1. Scan or enter barcodes using any of the three methods
2. Each barcode is automatically enriched with inventory data (item name, SKU, location, category) if a match exists
3. Your session table shows all scanned codes with their details
4. Remove any entry by clicking the delete button on that row

**Generating the report:**
1. Enter a title for your report (optional)
2. Click **Export PDF**
3. A professional PDF is generated and downloaded containing all scanned items with their details

**Session persistence:** Your scan session is saved in your browser's local storage. If you close the tab and come back, your scanned items are still there. Click **Clear** to start a new session.

---

## 8. Calendar View

**URL:** `/calendar`

The calendar shows a month-view grid of inventory activity. Each day cell shows the count of transactions that occurred.

**Using the calendar:**
1. Navigate between months using the arrow buttons
2. Click any day to see that day's details
3. The day detail shows: transactions (with item name, change, reason) and items created that day

**Color coding:** Days with higher activity are shaded more intensely so you can spot busy periods at a glance.

---

## 9. Analytics

**URL:** `/analytics`

Analytics has three tabs. All data is based on a configurable time window (default: 30 days). Adjust the date range to see different periods.

### 9.1 Valuation

Shows the financial picture of your inventory:

| Section | What it shows |
|---------|--------------|
| **Summary cards** | Total inventory value, active items, items with cost data, items missing cost |
| **Category breakdown** | Each category with its item count, total value, and proportional bar |
| **Location breakdown** | Each location with its item count, total value, and proportional bar |
| **Barcode format breakdown** | Count of items by barcode type (Code128, QR, etc.) |

### 9.2 Velocity

Shows what is moving and what is sitting:

| Section | What it shows |
|---------|--------------|
| **Top movers** | Items with the most transactions (by count and by volume) |
| **Activity bars** | Visual indication of relative movement for each item |

Use this to identify fast-selling items, frequently adjusted items, or items that never move.

### 9.3 Stock Health

Shows the health of your stock levels:

| Section | What it shows |
|---------|--------------|
| **Summary cards** | Total items, out of stock, low stock, healthy |
| **Out of stock list** | Items with zero quantity (with location and min quantity) |
| **Low stock list** | Items below their minimum quantity threshold |
| **Overstocked list** | Items significantly above expected levels |

---

## 10. Alerts

**URL:** `/alerts`

Alerts notify you when inventory items cross critical thresholds.

**Alert types:**
- **Low stock** — item quantity dropped below its minimum threshold
- **Overstock** — item quantity exceeds expected maximum

**Alert states:**
| State | Meaning |
|-------|---------|
| Unread | New alert, not yet seen |
| Read | You have seen it |
| Dismissed | You have acknowledged and cleared it |

**Actions:**
- **Mark as read** — removes the unread badge but keeps the alert visible
- **Dismiss** — hides the alert (it won't come back unless the condition triggers again)
- **Dismiss all** — clears all current alerts

**How alerts are generated:** A background job checks all items against their min/max thresholds every 5 minutes. When a threshold is breached, an alert is created. If a webhook URL is configured, the alert is also sent to that URL.

**Configuring alerts:** Set the `min_quantity` on any item (via the item detail page or during creation). The alert system uses this as the low-stock threshold.

**Navigation badge:** The alert bell in the sidebar shows the count of unread alerts. This updates in real time.

---

## 11. Activity Log

**URL:** `/activity`

The activity log is an append-only audit trail of everything that happens in the system.

**Categories:**
| Category | What it tracks |
|----------|---------------|
| `inventory` | Item create, update, delete, stock adjustments |
| `auth` | Login, logout, signup, password changes |
| `admin` | Role changes, user activation/deactivation, settings changes |
| `scan` | Barcode scan lookups |
| `import` | CSV/JSON import operations |
| `export` | CSV/JSON export operations |
| `alert` | Alert creation, dismissal |
| `system` | Background jobs, scheduler events |

**Filtering:**
- Filter by date range (start and end date)
- Filter by category (dropdown)
- Search text in the summary field

**Summary stats** at the top show: today's activity count, this week's count, and a breakdown by category.

**Recent activity drawer:** Accessible from the sidebar, shows the latest 20 events without leaving your current page.

---

## 12. Team Management

**URL:** `/team`

Teams let you organize users into groups with shared tasks and role-based access.

### 12.1 Creating a Team

Requires **manager** role or above.

1. Go to **Team** in the sidebar
2. Click **Create Team**
3. Enter a team name and description
4. Click **Create**

### 12.2 Managing Members

Team leads (and admins/owner) can manage membership.

**Adding a member:**
1. Open the team → **Members** tab
2. Click **Add Member**
3. Select a user from the dropdown
4. Assign a team role:
   - **Lead** — can manage members, create/edit/delete tasks
   - **Member** — can update their own task status
   - **Viewer** — read-only access to team tasks and info

**Changing a role:** Use the role dropdown next to any member.

**Removing a member:** Click the remove button next to their name.

### 12.3 Tasks

Team leads and above can create tasks.

**Creating a task:**
1. Open the team → **Tasks** tab
2. Click **Create Task**
3. Fill in: title, description, assigned to (team member), priority, due date
4. Click **Create**

**Task priorities:** Low, Medium, High, Urgent (color-coded badges).

**Task statuses:** To Do, In Progress, Done, Blocked.

**Filtering tasks:** Use the status filter buttons to show only tasks in a specific state.

**Updating tasks:** Click a task to edit its title, description, status, priority, assignee, or due date. Members can update the status of tasks assigned to them.

---

## 13. AI Assistant

BarcodeBuddy includes an AI assistant that can help with inventory queries, analysis, and operations using natural language.

### 13.1 Setup Wizard

**URL:** `/ai/setup` (owner only)

Before using AI, the owner must complete setup:

1. **Choose mode:**
   - **Local** — uses Ollama running on your machine (private, no data leaves your network)
   - **Cloud** — uses Anthropic (Claude) or OpenAI (GPT) cloud APIs
   - **Hybrid** — local for some tasks, cloud for others

2. **Configure Ollama** (if local/hybrid): Enter the Ollama base URL (default: `http://localhost:11434`) and select a model

3. **Configure cloud** (if cloud/hybrid): Enter your API key for Anthropic or OpenAI and select models

4. **Assign models to tasks:** Choose which model handles chat, vision, CSV analysis, and item suggestions

5. **Complete setup**

### 13.2 AI Chat

**URL:** `/ai/chat`

The chat interface lets you have conversations with the AI about your inventory and operations.

**How to use it:**
1. Type a question or instruction in the message box
2. Press Enter or click Send
3. The AI responds using your inventory data as context

**Example queries:**
- "What items are low on stock?"
- "Show me the top 5 fastest-moving items this month"
- "Adjust the quantity of SKU-12345 by +50, reason: received"
- "Generate a barcode for item ABC"
- "What's the total value of items in Warehouse B?"
- "Summarize my inventory transactions for this week"

**Conversations are persistent:** Your chat history is saved. You can have multiple conversations, switch between them, and delete old ones.

The AI assistant is also accessible via the **floating chat button** in the bottom-right corner of any page.

### 13.3 AI Tools

The AI assistant has 11 built-in tools that let it take actions on your behalf:

| Tool | What it does |
|------|-------------|
| Item lookup | Find items by name, SKU, or barcode |
| SKU lookup | Search specifically by SKU |
| Quick stock adjustment | Adjust quantity with reason and notes |
| Inventory analytics | Get summary statistics |
| Transaction history | View recent transactions for any item |
| Low stock alerts | List items below threshold |
| Category analysis | Breakdown by category |
| Barcode generation | Generate barcode image for an item |
| CSV preview | Analyze and summarize uploaded CSV data |
| Item suggestion | Suggest field values based on patterns |
| CSV analysis | Deep analysis of CSV imports |

The AI always tells you what tool it is using and what action it is taking. All AI-initiated changes are logged in the activity log.

### 13.4 AI Settings

**URL:** `/ai/settings` (owner only)

Configure:
- Ollama connection (base URL, chat model, vision model)
- Cloud provider (Anthropic or OpenAI) and API key
- Model assignments for each task type (chat, vision, CSV, suggestions)
- Rate limits (max tokens per request, max requests per minute)
- Enable/disable toggle

API keys are encrypted at rest. They are never exposed through the API — only the presence of a key is indicated.

### 13.5 Privacy and Data Handling

**URL:** `/ai/privacy`

This page documents exactly how your data is handled:

- **Local mode (Ollama):** All processing happens on your machine. No data leaves your network.
- **Cloud mode:** Your queries and relevant inventory context are sent to the cloud provider. The provider's data retention policies apply.
- **No silent fallback:** If your configured provider is unavailable, the AI returns an error. It never silently switches to a different provider.
- **User control:** You can disable cloud providers entirely and use only local AI.
- **API key security:** Cloud API keys are encrypted using the `cryptography` library before storage in the database.

---

## 14. Admin Panel

**URL:** `/admin` (admin and owner roles only)

### 14.1 User Management

The admin panel shows a table of all user accounts:

| Column | Description |
|--------|-------------|
| Name | Display name |
| Email | Account email |
| Role | owner, admin, manager, or user |
| Status | Active or Inactive |
| Created | Account creation date |
| Actions | Role change, activate/deactivate, reset password, delete |

### 14.2 Role Assignments

Change a user's role using the dropdown in the actions column. The role hierarchy:

| Role | Privilege Level | Capabilities |
|------|----------------|-------------|
| **Owner** | Highest | Everything. Only one owner exists at a time. |
| **Admin** | High | Manage all users and roles (except owner). Full system access. |
| **Manager** | Medium | Create teams. Manage team members and tasks. View cross-user inventory. |
| **User** | Standard | CRUD on own inventory. View analytics and activity. Join teams. |

You cannot change the owner's role through the admin panel. Use ownership transfer instead.

### 14.3 Open/Closed Signup

Toggle the **Open Signup** switch to control whether new users can create accounts:
- **On:** Anyone can sign up at `/auth/signup`
- **Off:** Only existing admins/owner can create accounts (by directly adding users or temporarily enabling signup)

### 14.4 Ownership Transfer

The owner can transfer ownership to another user:

1. In the Admin Panel, find the target user
2. Click **Transfer Ownership**
3. Confirm the transfer

This is irreversible. The previous owner is demoted to admin. The new owner gets full control.

### 14.5 Audit Log

The bottom of the admin panel shows the last 100 audit entries:

| Column | Description |
|--------|-------------|
| Time | When the action occurred |
| Actor | Who performed the action |
| Action | What was done (role_change, deactivate_user, transfer_ownership, etc.) |
| Detail | JSON payload with specifics |

This is separate from the Activity Log. The audit log specifically tracks administrative and security-relevant actions.

---

## 15. Document Ingestion Service

The ingestion service (`main.py`) is the headless file processor that watches a folder and automatically files scanned documents.

### 15.1 How It Works

```
[Scanner] → [Input Folder] → [BarcodeBuddy] → [Output Folder]
                                    ↓
                             [Rejected Folder]
```

1. You (or your scanner) drop a file into the **input folder**
2. BarcodeBuddy detects the new file via OS-level file watching
3. It waits for the file to stabilize (stop changing) — default: 2 seconds
4. It atomically moves the file to the **processing folder** and creates a recovery journal
5. It validates the file format (must be PDF, JPG, JPEG, or PNG)
6. It extracts barcodes using zxing-cpp with OpenCV preprocessing
7. It tries multiple rotations (0°, 90°, 180°, 270°) to find barcodes
8. If a barcode is found and passes business-rule validation, the file is converted to PDF and placed in the **output folder** organized as `YYYY/MM/barcode.pdf`
9. If no barcode is found or validation fails, the file goes to the **rejected folder** with a `.meta.json` sidecar explaining why

### 15.2 Supported File Formats

| Format | Support |
|--------|---------|
| PDF | Full support (multi-page, barcode extracted per page) |
| JPG / JPEG | Full support (converted to PDF on output) |
| PNG | Full support (converted to PDF on output) |
| TIFF | Not yet supported (planned) |

Files are validated by magic bytes (file header), not by extension. Renaming a `.txt` to `.pdf` will not fool the validator.

### 15.3 Barcode Detection

**Supported barcode types:** Configured per workflow in `config.json` under `barcode_types`. Common values: `code128`, `qr`, `ean13`, `code39`, `datamatrix`, `auto` (try all).

**Detection process:**
1. Each page is rendered at the configured DPI (default: 300)
2. OpenCV preprocessing enhances the image
3. Optionally upscaled by the configured factor
4. zxing-cpp attempts to decode barcodes
5. If nothing found, the image is rotated 90°, 180°, 270° and retried

**Barcode selection when multiple are found:**
1. Business-rule match (matches a pattern in `barcode_value_patterns`) wins
2. Then: largest bounding box
3. Then: earliest page
4. Then: scan order (top-left to bottom-right)

**Business-rule patterns:** Configure `barcode_value_patterns` in `config.json` as an array of regex strings. Only barcodes whose decoded value matches at least one pattern are accepted. If the array is empty, all barcodes are accepted.

### 15.4 What Happens to Your Files

| Outcome | Where the file goes | Details |
|---------|-------------------|---------|
| **Success** | `output/YYYY/MM/BARCODE.pdf` | PDF named after the barcode value |
| **Success (timestamp mode)** | `output/YYYY/MM/BARCODE_20260404_120000.pdf` | Timestamp appended to prevent overwrite |
| **Rejection** | `rejected/ORIGINAL_FILENAME` + `rejected/ORIGINAL_FILENAME.meta.json` | Original file preserved, sidecar explains why |

**Output organization:** Files are placed in year/month subdirectories automatically.

### 15.5 Duplicate Handling

Two modes, configured per workflow:

| Mode | Behavior | Best for |
|------|----------|----------|
| `timestamp` | Appends a timestamp to the filename; both copies are kept | Shipping/POD (rescans are normal) |
| `reject` | Second file with the same barcode is rejected | Receiving (duplicates = clerical error) |

### 15.6 Rejections

When a file is rejected, two things happen:
1. The original file is moved to the `rejected` folder (unchanged)
2. A `.meta.json` sidecar is created next to it with:
   - The original filename
   - The reason for rejection (error code and message)
   - Timestamp
   - Workflow identifier

**Common rejection reasons:**
| Error | Meaning | What to do |
|-------|---------|-----------|
| `NO_BARCODE` | No barcode found in the document | Check scan quality, ensure barcode is visible |
| `INVALID_FORMAT` | File is not PDF, JPG, or PNG | Re-scan in a supported format |
| `PATTERN_MISMATCH` | Barcode found but doesn't match business rules | Check the barcode value against your configured patterns |
| `DUPLICATE_REJECTED` | Same barcode already processed (reject mode) | Intentional rescan? Switch to timestamp mode. Mistake? Discard the duplicate. |
| `FILE_LOCKED` | File was still being written when processing started | Retry — the scanner may not have finished writing |

### 15.7 Workflows

BarcodeBuddy is designed to run one workflow per instance. The recommended workflows are:

| Workflow | Purpose | Duplicate mode |
|----------|---------|---------------|
| `receiving` | Packing slips, PO attachments | `reject` |
| `shipping_pod` | Proof-of-delivery, shipping paperwork | `timestamp` |
| `quality_compliance` | Traceability docs, certifications | `reject` |

Each workflow has its own:
- Input folder (where operators drop files)
- Output folder (where filed PDFs land)
- Rejected folder (where failures go)
- Log directory
- Configuration file
- Barcode type and pattern rules

To run multiple workflows, run multiple instances of `main.py` with different config files. See [Section 16.10](#1610-running-multiple-workflows).

---

## 16. System Setup and Deployment

### 16.1 Requirements

- **Python:** 3.10, 3.11, 3.12, or 3.13
- **OS:** Windows or Linux
- **Storage:** All managed paths (input, processing, output, rejected, logs) must be on the same filesystem volume
- **For camera scanning:** Chrome, Edge, or other Chromium browser
- **For AI (local):** Ollama installed and running
- **For AI (cloud):** Anthropic or OpenAI API key
- **For password reset emails:** SMTP server (optional)

### 16.2 Installation

```bash
# Clone the repository
git clone <repo-url>
cd BarcodeBuddy

# Install dependencies
pip install -r requirements.txt

# Copy and edit your config
cp config.json config.json  # or use a workflow template from configs/

# Set the owner email
export BB_OWNER_EMAIL="your-email@company.com"

# Start the web application
python stats.py

# Start the ingestion service (separate terminal)
python main.py
```

### 16.3 Configuration Reference

Configuration lives in a single JSON file. Every key is validated on startup — unknown keys are rejected.

**Required settings:**

| Key | Type | Description |
|-----|------|-------------|
| `input_path` | string | Folder where scanned documents are dropped |
| `processing_path` | string | Temporary folder for files being processed |
| `output_path` | string | Destination for successfully filed PDFs |
| `rejected_path` | string | Destination for failed files + meta sidecars |
| `log_path` | string | Processing logs, daily archives, and database |
| `barcode_types` | array | Barcode formats to scan for (e.g., `["code128", "auto"]`) |
| `scan_all_pages` | bool | Scan all pages (`true`) or first page only (`false`) |
| `duplicate_handling` | string | `"timestamp"` or `"reject"` |
| `file_stability_delay_ms` | int | Milliseconds to wait for file to stop changing (min: 500) |
| `max_pages_scan` | int | Maximum pages to scan per document (min: 1, default: 50) |

**Optional settings:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `workflow_key` | string | `"default"` | Identifier for this workflow (used in logs and lock files) |
| `barcode_value_patterns` | array | `[]` | Regex patterns for barcode value validation |
| `poll_interval_ms` | int | `500` | Folder polling interval in ms (min: 100) |
| `barcode_scan_dpi` | int | `300` | DPI for PDF page rendering (min: 72) |
| `barcode_upscale_factor` | float | `1.0` | Image upscale factor before decode (min: 1.0) |
| `server_host` | string | `"0.0.0.0"` | Web server bind address |
| `server_port` | int | `8080` | Web server port (1–65535) |
| `secret_key` | string | `""` | JWT secret for session persistence across restarts |

**Validation rules:**
- All five managed paths must be distinct (no overlaps)
- All five managed paths must be on the same filesystem volume
- `barcode_types` must contain at least one entry
- `barcode_value_patterns` are compiled as regex on startup — invalid patterns cause startup failure

### 16.4 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BB_CONFIG` | `config.json` | Path to config file (overridden by `--config` CLI flag) |
| `BB_SECRET_KEY` | (empty) | JWT secret key (overrides config `secret_key`) |
| `BB_OWNER_EMAIL` | `mferragamo@danpack.com` | Owner account email for first signup |
| `BB_SMTP_HOST` | (empty) | SMTP server for password reset emails |
| `BB_SMTP_PORT` | `587` | SMTP port |
| `BB_SMTP_USER` | (empty) | SMTP username |
| `BB_SMTP_PASSWORD` | (empty) | SMTP password |
| `BB_SMTP_USE_TLS` | `true` | Enable TLS for SMTP |
| `BB_RESET_FROM` | (empty) | "From" address for reset emails |

**Important:** If `BB_SECRET_KEY` is empty and config `secret_key` is empty, a random key is generated on each startup. This means all user sessions are invalidated every time the server restarts. For production, always set a persistent secret key.

**Important:** If `BB_SMTP_HOST` and `BB_RESET_FROM` are not set, password reset emails are silently skipped. This is acceptable for LAN deployments where admins can reset passwords manually.

### 16.5 Running the Web Application

```bash
python stats.py [--config PATH] [--host HOST] [--port PORT] [--refresh-seconds N] [--history-days N] [--recent-limit N]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config` | `BB_CONFIG` or `config.json` | Config file path |
| `--host` | from config | Bind address |
| `--port` | from config | Bind port |
| `--refresh-seconds` | `15` | Browser auto-refresh interval (min: 5) |
| `--history-days` | `14` | Days of activity history on dashboard (min: 1) |
| `--recent-limit` | `25` | Recent documents shown on dashboard (min: 1) |

The web app creates the database at `{log_path}/barcode_buddy.db` (SQLite with WAL mode). Tables are created automatically on first run.

API documentation is available at `http://your-server:8080/docs` (Swagger UI).

### 16.6 Running the Ingestion Service

```bash
python main.py [--config PATH]
```

The service:
1. Validates and locks the config
2. Creates all required directories
3. Acquires an exclusive lock per workflow (prevents duplicate instances)
4. Recovers any in-flight files from the journal
5. Begins watching the input folder

**Graceful shutdown:** Send SIGINT (Ctrl+C) or SIGTERM. The service finishes any in-flight file before exiting.

### 16.7 Windows Deployment

**Quick start (with Cloudflare Tunnel):**
```powershell
powershell -ExecutionPolicy Bypass -File start-app.ps1
```

This starts the web application and a Cloudflare tunnel on port 8080. It watches both processes and restarts either if they crash.

**Tunnel modes:**
- **Named tunnel:** Requires `~/.cloudflared/barcodebuddy.yml` and a DNS CNAME at `app.danpack.com`. Provides a permanent URL.
- **Quick tunnel:** Temporary URL generated by Cloudflare. Good for testing.

The public URL is saved to `data/logs/tunnel-url.txt`.

**Autostart on login:**
```powershell
# Run as Administrator
powershell -ExecutionPolicy Bypass -File install-autostart.ps1
```

This creates a Windows scheduled task named "BarcodeBuddy" that runs `start-app.ps1` at user logon with automatic crash restart.

**To remove autostart:**
```powershell
Unregister-ScheduledTask -TaskName "BarcodeBuddy" -Confirm:$false
```

### 16.8 Docker Deployment

```bash
docker build -t barcodebuddy .
docker run -p 8080:8080 -v /your/data:/app/data barcodebuddy
```

The container:
- Runs as non-root user `appuser`
- Exposes port 8080
- Health check at `/health` (30-second interval)
- Starts the web application only — the ingestion service should run separately

**For the ingestion service in Docker:** Run a second container with `python main.py` as the command and shared volume mounts for the data directories.

### 16.9 Railway Deployment

Push to Railway. The `railway.toml` configures:
- Nixpacks builder (auto-detects Python)
- Start command: `python stats.py --host 0.0.0.0 --port $PORT`
- Health check on `/health`

### 16.10 Running Multiple Workflows

For organizations with multiple document types (receiving, shipping, quality):

```bash
# Terminal 1: Receiving workflow
python main.py --config configs/config.receiving.json

# Terminal 2: Shipping/POD workflow
python main.py --config configs/config.shipping-pod.json

# Terminal 3: Quality/Compliance workflow
python main.py --config configs/config.quality-compliance.json

# Terminal 4: Web application (shared)
python stats.py
```

Each workflow instance needs:
- Its own config file
- Its own set of five directories (input, processing, output, rejected, logs)
- Its own `workflow_key`
- Its own barcode types and patterns
- Its own duplicate handling mode

**Network share setup:** Share only the input folders over SMB so scanners on other machines can drop files:
```
\\server\receiving-input    → D:\barcodebuddy\receiving\input
\\server\shipping-input     → D:\barcodebuddy\shipping-pod\input
\\server\quality-input      → D:\barcodebuddy\quality-compliance\input
```

**Scanner profile tips:**
- Set output format to PDF (not TIFF)
- Use 300 DPI or higher
- Use "one file per scan" (not "one file per page")
- Send each document type to its designated input folder
- Enable duplex scanning if your hardware supports it

---

## 17. Health and Monitoring

**Health endpoint:** `GET /health`

Returns HTTP 200 only when:
1. The ingestion worker's heartbeat is recent
2. The service lock file exists

Use this for load balancer checks, Docker health checks, Kubernetes probes, or uptime monitoring.

**Prometheus metrics:** `GET /metrics`

Exposes Prometheus-compatible gauges for integration with Grafana or other monitoring systems.

**Processing logs:** JSONL files at `{log_path}/processing_log.jsonl` with daily rotation. Every processing event includes:
- Schema version, workflow key, hostname, instance ID
- Config version (12-character SHA256 checksum)
- Processing stage, duration, and error code (if any)

**Database backups:** Automatic backups with 14-day rolling retention at `{log_path}/barcode_buddy.{timestamp}.db`.

---

## 18. Troubleshooting

| Problem | Likely cause | Solution |
|---------|-------------|----------|
| Can't sign up | Open signup is disabled | Ask an admin to enable it in the Admin Panel |
| Can't sign up (first user) | Wrong email | Use the email in `BB_OWNER_EMAIL` for the first signup |
| Login fails | Wrong credentials or rate limited | Check email/password. If rate limited, wait 60 seconds. |
| Session expired | 24-hour session timeout | Log in again |
| No password reset email | SMTP not configured | Ask admin to reset your password via Admin Panel |
| Files not being processed | Ingestion service not running | Start `main.py` in a separate terminal |
| Files going to rejected folder | No barcode / wrong format / pattern mismatch | Check the `.meta.json` sidecar for the specific reason |
| "No barcode found" rejections | Poor scan quality or barcode not visible | Re-scan at higher DPI, ensure barcode is unobstructed |
| Duplicate rejections | Same barcode already processed | Expected if using `reject` mode. Switch to `timestamp` if rescans are intentional. |
| Camera scanning not working | Browser doesn't support BarcodeDetector API | Use Chrome or Edge. Firefox is not supported. |
| AI not responding | AI not configured or provider down | Owner must complete AI setup at `/ai/setup` |
| AI returns errors | API key invalid or rate limited | Check AI settings. Verify API key. Check rate limits. |
| Lock file error on startup | Another instance already running | Stop the other instance, or check if a stale lock file exists |
| Database locked | Multiple writers | Ensure only one `stats.py` instance is running per database |
| Alerts not firing | No min_quantity set on items | Set a min_quantity on items you want to monitor |
| Server restarts log everyone out | No persistent secret key | Set `BB_SECRET_KEY` environment variable |

---

## 19. Roles and Permissions Reference

| Capability | Owner | Admin | Manager | User |
|-----------|-------|-------|---------|------|
| View own inventory | Yes | Yes | Yes | Yes |
| Create/edit/delete own items | Yes | Yes | Yes | Yes |
| Adjust stock quantities | Yes | Yes | Yes | Yes |
| Import/export inventory | Yes | Yes | Yes | Yes |
| Scan barcode lookup | Yes | Yes | Yes | Yes |
| Scan to PDF | Yes | Yes | Yes | Yes |
| View analytics | Yes | Yes | Yes | Yes |
| View activity log | Yes | Yes | Yes | Yes |
| View/manage own alerts | Yes | Yes | Yes | Yes |
| Use AI chat | Yes | Yes | Yes | Yes |
| View calendar | Yes | Yes | Yes | Yes |
| Join teams | Yes | Yes | Yes | Yes |
| Create teams | Yes | Yes | Yes | No |
| View cross-user inventory | Yes | Yes | Yes | No |
| Manage team members | Yes | Yes | As lead | No |
| Manage all users | Yes | Yes | No | No |
| Change user roles | Yes | Yes | No | No |
| Activate/deactivate users | Yes | Yes | No | No |
| View audit log | Yes | Yes | No | No |
| Toggle open signup | Yes | Yes | No | No |
| Configure AI settings | Yes | No | No | No |
| Run AI setup wizard | Yes | No | No | No |
| Transfer ownership | Yes | No | No | No |

---

## 20. Glossary

| Term | Definition |
|------|-----------|
| **Barcode value** | The decoded text content of a barcode (e.g., "PO-2026-0042") |
| **Barcode type** | The encoding format (Code128, QR, EAN-13, Code39, DataMatrix) |
| **Business-rule pattern** | A regex in `barcode_value_patterns` that barcodes must match to be accepted |
| **Duplicate handling** | How the system treats a second file with the same barcode (`timestamp` = keep both, `reject` = reject the second) |
| **Hot folder** | A directory that the ingestion service watches for new files |
| **Ingestion service** | The `main.py` process that watches the input folder and processes files |
| **Journal** | A recovery file in `processing/.journal/` that tracks in-flight files for crash recovery |
| **Meta sidecar** | A `.meta.json` file placed next to a rejected file explaining why it was rejected |
| **Owner** | The highest-privilege account, created by the first signup. Only one exists. |
| **Rejection** | When a file cannot be processed (no barcode, wrong format, pattern mismatch, duplicate in reject mode) |
| **SKU** | Stock Keeping Unit — a unique identifier for an inventory item |
| **Transaction** | An immutable record of a quantity change (received, sold, adjusted, damaged, returned) |
| **WAL mode** | Write-Ahead Logging — SQLite mode that allows concurrent reads during writes |
| **Web application** | The `stats.py` process that serves the browser-based UI |
| **Workflow** | A named configuration for a specific document type (receiving, shipping_pod, quality_compliance) |
| **Workflow key** | The identifier string in config that names the workflow |
