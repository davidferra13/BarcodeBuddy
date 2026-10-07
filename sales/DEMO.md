# Five-minute demo

Everything shown in this demo is invented: a made-up supplier, made-up purchase orders, nine scans built by a script. No customer paperwork is used, so it can be shown to anyone.

## Set up once (about 15 minutes, on any Windows 10 or 11 PC)

Install Python 3.12 from python.org first. Then open PowerShell in the release folder and run:

```powershell
.\provision-customer.ps1 -WorkflowKey demo -ConfigPath ".\config.demo.json" -RuntimeRoot ".\data\demo" -BarcodePattern '^PO-[0-9]+$' -DuplicateHandling reject -InstallDependencies
.\.venv\Scripts\python.exe scripts\make_demo_kit.py --out "$HOME\Desktop\BarcodeBuddy demo scans"
.\.venv\Scripts\python.exe scripts\run_acceptance.py --config ".\config.demo.json" --manifest "$HOME\Desktop\BarcodeBuddy demo scans\manifest.json" --report-dir "$HOME\Desktop\BarcodeBuddy demo check"
```

The last command must end with all nine cases passing. If it does not, stop and fix that before showing anyone.

Then start the system and create the owner account:

```powershell
.\start-app.ps1 -Config ".\config.demo.json"
```

Open http://127.0.0.1:8080, choose Sign up, and create the owner account. Keep three windows ready to share:

1. The scan folder: `data\demo\demo\input`
2. The filed folder: `data\demo\demo\output`
3. The browser on Dashboard, Documents tab.

To start a later demo with empty screens, run the first command again with a new folder, for example `-RuntimeRoot ".\data\demo-2"` and `-ConfigPath ".\config.demo-2.json"`. Nothing needs to be deleted.

## The call

**0:00 Their process.** Ask before showing anything: "When a packing slip or delivery receipt comes off the dock, what happens to it? Who scans it, who renames it, and how do you find it again in three months?" Let them talk. Write down the hours per week and who does it.

**1:00 Four good scans.** Drag files 01 to 04 from the demo folder into the scan folder. Within about ten seconds they leave the scan folder. Open the filed folder: `PO-10431.pdf`, `PO-10432.pdf`, `PO-10433.pdf`, `PO-10434.pdf`, sorted by year and month.

Point out:
- The file name is the purchase order number already printed on the page. Nobody typed it.
- 02 was scanned crooked. 03 has two pages and stays one document. 04 is a photo-like JPEG that became a PDF.

**2:30 Five problem scans.** Drag files 05 to 09 in. None of them gets filed. Switch to the browser, Documents tab. Each one says why, in plain words:
- 05 and 06: No barcode found
- 07: Barcode is not a record number for this workflow (it is a carrier tracking number)
- 08: More than one record number (two orders on one page)
- 09: Already filed (the same slip scanned twice)

Say: "It never guesses. Anything it is not sure about waits in the Rejected folder for a person, with the reason written next to it."

**3:45 Who owns it.** "It runs on a PC in your building. Your documents never leave your network. You pay once, you own your install and your data, and it keeps working whether or not you buy support from me."

**4:15 The ask.** "Send me 15 to 20 copies of your real paperwork with the right PO number for each, with anything sensitive blacked out. I will run them through and show you the result before you decide anything." Use SAMPLE-REQUEST.md for what to ask for.

## If something goes wrong on the call

- A scan does not leave the scan folder within 30 seconds: the filing service is not running. Close the launcher window and run `.\start-app.ps1 -Config ".\config.demo.json"` again.
- The browser shows the sign-in page: sign in with the owner account you created.
- A good scan was rejected: open the Documents tab and read the reason. Then rerun the acceptance check from setup to see which case changed.
