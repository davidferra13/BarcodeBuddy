---
name: feature-closeout
description: Feature close-out - compilation check, test suite, commit, push. Run when user asks to close out a feature.
disable-model-invocation: true
---

# Feature Close-Out

Run these in order. Stop and report any failure before continuing.

1. `py -m compileall app tests main.py stats.py -q` - must exit 0
2. `py -3.12 -B -m pytest tests/ -x -q` - must pass
3. `git add` relevant files + `git commit` with a clear message
4. `git push origin <current-branch>` - push to GitHub
5. Confirm branch is clean and ready

Do **NOT** merge to `main` or deploy to production. Only push the feature branch.
