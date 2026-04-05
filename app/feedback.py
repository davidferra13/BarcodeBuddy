"""In-app feedback widget: bug reports, feature requests, and questions.

Submissions are appended to ``data/logs/feedback.jsonl`` (append-only,
consistent with the project's data-safety rules).  No external service
required — the developer pulls the file during maintenance.
"""

from __future__ import annotations

import html as html_mod
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import __version__
from app.activity import log_activity
from app.auth import require_user
from app.database import User, get_db
from app.layout import render_shell

router = APIRouter(tags=["feedback"])

_E = html_mod.escape

_FEEDBACK_TYPES = ("bug", "feature", "question")


class FeedbackSubmission(BaseModel):
    feedback_type: str = Field(..., pattern="^(bug|feature|question)$")
    message: str = Field(..., min_length=1, max_length=2000)
    page_url: str = Field(default="", max_length=500)


def _feedback_file() -> Path:
    """Return the path to the feedback JSONL file."""
    return Path(os.environ.get("BB_LOG_PATH", "data/logs")) / "feedback.jsonl"


def _append_feedback(entry: dict) -> None:
    """Append a single feedback entry to the JSONL file (fsync for durability)."""
    path = _feedback_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True))
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


@router.post("/api/feedback")
def submit_feedback(
    body: FeedbackSubmission,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_version": __version__,
        "feedback_type": body.feedback_type,
        "message": body.message,
        "page_url": body.page_url,
        "user_email": user.email,
        "user_display_name": user.display_name,
    }
    _append_feedback(entry)
    log_activity(
        db,
        user=user,
        action="feedback_submitted",
        category="system",
        summary=f"{body.feedback_type}: {body.message[:80]}",
    )
    return JSONResponse(content={"ok": True, "message": "Thank you for your feedback."})


@router.get("/feedback", response_class=HTMLResponse)
def feedback_page(user: User = Depends(require_user)) -> HTMLResponse:
    body = """
<style>
  .fb-form { max-width:560px; margin:0 auto; }
  .fb-type-row { display:flex; gap:10px; margin-bottom:18px; }
  .fb-type-btn {
    flex:1; padding:14px 10px; border-radius:10px; border:2px solid var(--line);
    background:var(--paper); color:var(--text); cursor:pointer; text-align:center;
    font-size:14px; font-weight:600; transition: border-color .2s, background .2s;
  }
  .fb-type-btn:hover { border-color:var(--accent); }
  .fb-type-btn.active { border-color:var(--accent); background:rgba(136,85,41,.08); }
  .fb-type-btn .fb-icon { font-size:22px; display:block; margin-bottom:6px; }
  .fb-textarea {
    width:100%; min-height:140px; padding:14px; border-radius:10px;
    border:1px solid var(--line); background:var(--paper); color:var(--text);
    font-size:14px; font-family:inherit; resize:vertical; margin-bottom:16px;
  }
  .fb-textarea:focus { outline:none; border-color:var(--accent); }
  .fb-submit {
    width:100%; padding:14px; border-radius:10px; border:none;
    background:var(--accent); color:#fff; font-size:15px; font-weight:700;
    cursor:pointer; transition: opacity .2s;
  }
  .fb-submit:hover { opacity:.9; }
  .fb-submit:disabled { opacity:.5; cursor:not-allowed; }
  .fb-success {
    text-align:center; padding:40px 20px; display:none;
  }
  .fb-success .fb-check { font-size:48px; margin-bottom:12px; }
  .fb-success h3 { color:var(--text); margin-bottom:8px; }
  .fb-success p { color:var(--muted); font-size:14px; }
  .fb-hint { font-size:12px; color:var(--muted); margin-bottom:16px; }
</style>

<div class="page-header">
  <div>
    <p class="page-desc" style="margin-bottom:0">Report a bug, request a feature, or ask a question.</p>
  </div>
</div>

<div class="fb-form" id="fb-form">
  <div class="fb-type-row">
    <button type="button" class="fb-type-btn" data-type="bug" onclick="setType(this)">
      <span class="fb-icon">&#128027;</span>Bug Report
    </button>
    <button type="button" class="fb-type-btn" data-type="feature" onclick="setType(this)">
      <span class="fb-icon">&#128161;</span>Feature Request
    </button>
    <button type="button" class="fb-type-btn" data-type="question" onclick="setType(this)">
      <span class="fb-icon">&#10067;</span>Question
    </button>
  </div>

  <textarea class="fb-textarea" id="fb-msg" placeholder="Describe the issue, idea, or question..."
    maxlength="2000"></textarea>
  <div class="fb-hint"><span id="fb-charcount">0</span> / 2000 characters</div>

  <button class="fb-submit" id="fb-submit" onclick="submitFeedback()" disabled>Send Feedback</button>
</div>

<div class="fb-success" id="fb-success">
  <div class="fb-check">&#9989;</div>
  <h3>Feedback Sent</h3>
  <p>Your message has been recorded. Thank you.</p>
  <button class="fb-submit" style="max-width:200px;margin:20px auto 0;display:block"
    onclick="resetForm()">Send Another</button>
</div>
"""

    js = """<script>
let fbType = '';
function setType(btn) {
  document.querySelectorAll('.fb-type-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  fbType = btn.dataset.type;
  checkReady();
}
function checkReady() {
  const msg = document.getElementById('fb-msg').value.trim();
  document.getElementById('fb-submit').disabled = !fbType || !msg;
}
document.getElementById('fb-msg').addEventListener('input', function() {
  document.getElementById('fb-charcount').textContent = this.value.length;
  checkReady();
});
async function submitFeedback() {
  const btn = document.getElementById('fb-submit');
  btn.disabled = true;
  btn.textContent = 'Sending...';
  try {
    const r = await fetch('/api/feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        feedback_type: fbType,
        message: document.getElementById('fb-msg').value.trim(),
        page_url: document.referrer || window.location.href
      })
    });
    if (r.ok) {
      document.getElementById('fb-form').style.display = 'none';
      document.getElementById('fb-success').style.display = 'block';
    } else {
      const d = await r.json();
      toast(d.detail || d.error || 'Something went wrong. Please try again.', 'error');
      btn.disabled = false;
      btn.textContent = 'Send Feedback';
    }
  } catch(e) {
    toast('Network error. Please check your connection and try again.', 'error');
    btn.disabled = false;
    btn.textContent = 'Send Feedback';
  }
}
function resetForm() {
  document.getElementById('fb-form').style.display = 'block';
  document.getElementById('fb-success').style.display = 'none';
  document.getElementById('fb-msg').value = '';
  document.getElementById('fb-charcount').textContent = '0';
  document.querySelectorAll('.fb-type-btn').forEach(b => b.classList.remove('active'));
  fbType = '';
  document.getElementById('fb-submit').disabled = true;
  document.getElementById('fb-submit').textContent = 'Send Feedback';
}
</script>"""

    return HTMLResponse(content=render_shell(
        title="Help & Feedback",
        active_nav="feedback",
        body_html=body,
        body_js=js,
        display_name=user.display_name,
        role=user.role,
    ))
