# BarcodeBuddy release verification — October 7, 2026

Owner request: keep building and finishing Barcode Buddy. Existing approved one-site/one-workflow $10,000 deterministic local Windows scope remains.

Target: C:\Users\david\Documents\BarcodeBuddy-worktrees\verified-release-20261006-2033.
Branch: feature/verified-release-20261006-2033.
Starting revision: a9e70f5dd332669781621159a902ffabf4fae593.
Native shared-task status: no .agent-command/project.json; UNMANAGED. No native identity or authority bypass.
Canonical checkout, older release worktree and BuiltToOwn peer bytes preserved.
Allowed source: app/release_gate.py; tests/test_release_gate.py; docs/customer/ACCEPTANCE.md; this digest.

Changes:
- Native release launcher gate requires both an executed parser check and executed launcher probe. Missing, skipped, duplicate or failed evidence cannot become ready.
- Real synthetic corpus now covers seven cases: one routing identifier, duplicate input, blank input, wrong/secondary identifier, two eligible identifiers on one image, a mixed two-document PDF, and repeated occurrences of one identifier.
- First-page-only scanning and the existing hard max_pages_scan rejection remain unchanged; fixtures assert their actual supported behavior.
- Acquisition proof now requires BarcodeBuddy product artifacts, validated product manifest, dedicated factory adapter tests, supplemental site verification and the same clean committed BuiltToOwn revision before and after commands.
- Dirty peer integration work is preserved without executing mutating verification there.
- Acceptance documentation explains temporary output deletion and separate disposable copy-based visual review.

Evidence:
- Initial implementation regressions: 11 failures before repair; 55 targeted tests passed afterward.
- Independent read-only review found no Critical issue and two Important findings: page-cap expectations and generic acquisition proof. Both reproduced together: 8 failed, 2 passed before fixes.
- After that fix pass: 63 focused acceptance/release/backup tests passed, one existing Starlette warning.
- Earlier full suite before the review fixes: 436 passed, 2 explicit PowerShell skips, 70 subtests. This does not establish final post-review verification.
- Final compilation passed. Final post-review full native suite: 444 passed, 2 explicit PowerShell skips, 70 subtests, one existing warning in 354.01 seconds. Exit 0. A committed-revision release receipt remains to run.
- Parser deadline 15s and native launcher deadline 45s both timed out. Independent System32 and SysWOW64 PowerShell trivial Write-Output commands each timed out at 12s. No supported shell behavior has passed; no network, power, access or host process settings changed.
- Supplied digital-double governed-route denial remains a known hardware/admission blocker; no repeated inference or direct-provider bypass was attempted.

Rulings:
- Require parser proof in addition to functional launcher proof at release. Cost if wrong: a responsive supported host is still needed before delivery; missing proof is never promoted.
- Preserve the existing hard page-count cap and first-page-only semantics. Cost if wrong: later-page conflicts remain outside configured scan scope until all-page acceptance is used.
- Replace generic acquisition success with the approved factory BarcodeBuddy contract. Cost if wrong: the product remains blocked until that explicit integration exists; no unrelated site check is called integration.

Open release gates:
1. Native PowerShell launcher/parser execution on a responsive supported Windows host.
2. BuiltToOwn Task 6 BarcodeBuddy adapter/manifest and committed factory integration. Current candidate e4a320f has peer untracked CLI/instance-store/test fixtures; it must be integrated without overwriting them.
3. Native broker is healthy with scoped_release enabled, but release-policy.json authorizes only C:/Users/david/Desktop/AGENT COMMAND, agent/command-hub, mirror-e at E:/AGENT-COMMAND-MIRROR/agent-command.git. BarcodeBuddy origin/feature branch is outside that scope. Prepare its exact push proposal; do not retarget or bypass the policy.
4. Installation-specific acceptance/recovery and scanner compatibility. Internal synthetic proof does not mean a buyer deployed.

Evidence files are private under C:\Users\david\AppData\Local\Temp with barcodebuddy-*-20261007-0409 names.
Source preservation baseline: barcodebuddy-source-before-20261007-0409.json.
No outreach, calls, payments, customer samples, public tunnel or household changes were made.
