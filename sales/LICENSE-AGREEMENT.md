# BarcodeBuddy Software License and Installation Agreement

DRAFT TEMPLATE. Not legal advice. Have a lawyer review it before the first signature.

## Before anyone signs this (for David, delete this section from the copy you send)

1. Fill in the Licensor's legal name. Decide which company sells software. Do not assume it is the same company that runs the chef business.
2. Confirm the license fee and the optional support price on the Order Form.
3. Resolve the PDF library license. BarcodeBuddy reads PDFs with PyMuPDF, which is published under the GNU AGPL or a paid commercial license from Artifex. Shipping it inside a closed, no-resale license may conflict with the AGPL. Before the first sale, either buy the commercial PyMuPDF license, or have the PDF reading moved to a permissively licensed library, or take legal advice that the current setup is fine. Every other library BarcodeBuddy installs is under a permissive license (MIT, BSD, Apache 2.0 or similar).
4. Have a lawyer in the buyer's state read sections 7 to 10.

---

This Agreement is between **[Licensor legal name]** ("Licensor") and the customer named on the signed Order Form ("Customer"). It takes effect on the date both parties sign the Order Form.

## 1. Definitions

- **Software**: the BarcodeBuddy program files, scripts and documentation delivered to Customer, in the version listed on the Order Form, plus any updates Licensor delivers under a support plan.
- **Site**: the one physical location listed on the Order Form.
- **Licensed Workflow**: each document workflow listed on the Order Form, for example receiving paperwork.
- **Customer Data**: everything Customer puts into or gets out of the Software: scanned documents, filed PDFs, rejected files, the database, configuration files, logs and backups.

## 2. License

Licensor grants Customer a perpetual, non-exclusive, non-transferable license to install and use the Software at the Site for the Licensed Workflows, for Customer's own internal business operations.

Customer may:

- install the Software on the computers it controls at the Site;
- make copies needed for backup, recovery and testing;
- change configuration files, barcode rules, folder locations and user accounts;
- read the program files and change them for its own internal use. Licensor does not support or warrant parts Customer has changed.

## 3. What Customer may not do

Customer may not sell, resell, rent, lease, sublicense, publish or give the Software to anyone else; run the Software as a service for other companies; use it at another location or for another workflow without a further license; or remove copyright or license notices. If Customer is sold or reorganized, it may transfer this license to the successor business at the same Site with written notice to Licensor.

## 4. Ownership

Licensor owns the Software and all rights in it, and may license the same Software to other customers. This Agreement does not assign any intellectual property to Customer.

Customer owns its installed copy's Customer Data. Licensor claims no rights in Customer Data and gets no access to it unless Customer grants access for support, and then only for that support.

## 5. Delivery and acceptance

Licensor installs the Software and configures each Licensed Workflow as described on the Order Form. Customer supplies the redacted sample documents and the correct record number for each. The installation is accepted when the agreed samples produce the agreed results through the installed Software and Customer confirms it in writing. Acceptance does not cover documents, scanners or workflows that were not tested.

## 6. Fees

Customer pays the license and installation fee shown on the Order Form on the schedule shown there. Fees do not include taxes, travel outside the Site's region or hardware. The license is fully paid once the fee is paid in full.

## 7. Support (optional)

For 30 days after acceptance, Licensor fixes defects in the accepted Licensed Workflow at no extra charge.

After that, support is optional and is bought separately as shown on the Order Form. Support covers defect fixes and updates for the licensed version line and help by phone or email during business hours. New features, new workflows, new sites and work on Customer-changed files are quoted separately.

**Ending support never ends the license.** Customer may keep running the version it has for as long as it wants.

## 8. Data, security and AI features

The Software runs on Customer's own computer. By default it serves its web screens only on that computer, and it does not send Customer Data anywhere. It sends data outside Customer's network only through features Customer turns on itself: a cloud AI provider, an alert webhook address, or a public tunnel. Customer is responsible for that computer, its network, its access controls and its backups; the Software includes backup and restore tools for that purpose.

Optional AI features are off by default. If Customer turns on a cloud AI provider, the text Customer sends goes to that provider under Customer's own account and that provider's terms. If Customer sets an alert webhook, alert details go to the address Customer chose.

## 9. Warranty

Licensor warrants that, at acceptance, the Software performs the accepted Licensed Workflow as tested. Customer's remedy for a breach of this warranty is repair under section 7, or if Licensor cannot repair it within a reasonable time, a refund of the license fee in exchange for removing the Software.

Except for that warranty, the Software is provided as is. Licensor does not warrant that it is error free or that it will read every barcode, scan or document. Customer should keep its original paper or scans until it has checked the filed copies.

## 10. Limitation of liability

Neither party is liable for indirect, incidental, special or consequential damages, or for lost profits or lost data. Each party's total liability under this Agreement is limited to the fees Customer paid under it. These limits do not apply to a breach of section 3.

## 11. Third-party components

The Software uses open-source libraries that are installed under their own licenses. Those licenses govern those libraries. They are listed in THIRD-PARTY-NOTICES.md, delivered with the Software.

## 12. Termination

Licensor may end the license only if Customer breaks section 3 and does not cure the breach within 30 days of written notice. Customer may end the license at any time by removing the Software. Sections 4, 9, 10 and 13 survive.

## 13. General

This Agreement and the Order Form are the whole agreement about the Software. Changes must be in writing and signed by both parties. The law of **[State]** governs. If any part is unenforceable, the rest still applies.

## Signatures

Licensor: ______________________   Name and title: ______________________   Date: __________

Customer: ______________________   Name and title: ______________________   Date: __________
