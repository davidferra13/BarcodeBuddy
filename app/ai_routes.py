"""AI feature routes: setup wizard, chatbot, privacy page, settings, and utility endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.auth import SECRET_KEY, require_admin, require_owner, require_user
from app.database import AIConfig, ChatConversation, ChatMessage, User, get_db
from app.ai_provider import (
    AICompletionRequest,
    AICompletionResponse,
    AIChatMessage,
    AIRouter,
    OllamaProvider,
    CloudProvider,
    check_rate_limit,
    decrypt_api_key,
    encrypt_api_key,
    get_ai_config_dict,
    invalidate_ai_config_cache,
)
from app.ai_tools import TOOL_DEFINITIONS, build_system_prompt, execute_tool
from app.layout import render_shell

router = APIRouter(prefix="/ai", tags=["ai"])

# ─── Settings reference (injected from stats.py at startup) ──────────────
_app_settings = None


def set_app_settings(settings) -> None:
    """Called from stats.py to share the global Settings object."""
    global _app_settings
    _app_settings = settings


# ─── Request models ──────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: str = ""
    message: str

class ConfigUpdateRequest(BaseModel):
    ollama_enabled: bool | None = None
    ollama_base_url: str | None = None
    ollama_chat_model: str | None = None
    ollama_vision_model: str | None = None
    cloud_enabled: bool | None = None
    cloud_provider: str | None = None
    cloud_api_key: str | None = None
    cloud_chat_model: str | None = None
    cloud_vision_model: str | None = None
    chat_provider: str | None = None
    vision_provider: str | None = None
    csv_provider: str | None = None
    suggest_provider: str | None = None
    max_tokens_per_request: int | None = None
    max_requests_per_minute: int | None = None
    ai_enabled: bool | None = None

class SetupStepRequest(BaseModel):
    step: str
    data: dict = {}

class SuggestItemRequest(BaseModel):
    name: str
    sku: str = ""
    field: str  # "category", "location", "min_quantity"

class CsvPreviewRequest(BaseModel):
    columns: list[str]
    sample_rows: list[list[str]]

class PullModelRequest(BaseModel):
    model_name: str

class TestCloudRequest(BaseModel):
    provider: str  # "anthropic" or "openai"
    api_key: str


# ═════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════

# ─── Status ──────────────────────────────────────────────────────────────

@router.get("/api/status")
def api_status(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    if not cfg:
        return JSONResponse(content={"ai_enabled": False, "setup_completed": False})
    return JSONResponse(content=cfg.to_dict())


# ─── Config CRUD (owner only) ───────────────────────────────────────────

@router.get("/api/config")
def api_get_config(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    return JSONResponse(content=cfg.to_dict() if cfg else {})


@router.post("/api/config")
def api_update_config(
    body: ConfigUpdateRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    if not cfg:
        return JSONResponse(status_code=500, content={"error": "AI config not initialized"})

    updates = body.model_dump(exclude_none=True)
    # Handle API key encryption separately
    if "cloud_api_key" in updates:
        raw_key = updates.pop("cloud_api_key")
        if raw_key:
            cfg.cloud_api_key_encrypted = encrypt_api_key(raw_key, SECRET_KEY)
        else:
            cfg.cloud_api_key_encrypted = ""

    for k, v in updates.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)

    db.commit()
    invalidate_ai_config_cache()
    log_activity(db, user=user, action="AI Config Updated", category="admin",
                 summary="Updated AI configuration", detail={"fields": list(updates.keys())})
    return JSONResponse(content={"ok": True, "config": cfg.to_dict()})


# ─── Setup wizard endpoints ─────────────────────────────────────────────

@router.post("/api/setup-step")
def api_setup_step(
    body: SetupStepRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    step = body.step
    data = body.data

    if step == "choose_mode":
        mode = data.get("mode", "local")
        cfg.ollama_enabled = mode in ("local", "hybrid")
        cfg.cloud_enabled = mode in ("cloud", "hybrid")
        if mode == "local":
            cfg.chat_provider = "local"
            cfg.vision_provider = "local"
            cfg.csv_provider = "local"
            cfg.suggest_provider = "local"
        elif mode == "cloud":
            cfg.chat_provider = "cloud"
            cfg.vision_provider = "cloud"
            cfg.csv_provider = "cloud"
            cfg.suggest_provider = "cloud"
        else:  # hybrid
            cfg.chat_provider = "local"
            cfg.vision_provider = "cloud"
            cfg.csv_provider = "local"
            cfg.suggest_provider = "local"

    elif step == "ollama_url":
        cfg.ollama_base_url = data.get("url", "http://localhost:11434")

    elif step == "ollama_model":
        cfg.ollama_chat_model = data.get("chat_model", cfg.ollama_chat_model)
        if data.get("vision_model"):
            cfg.ollama_vision_model = data["vision_model"]

    elif step == "cloud_config":
        cfg.cloud_provider = data.get("provider", "")
        if data.get("api_key"):
            cfg.cloud_api_key_encrypted = encrypt_api_key(data["api_key"], SECRET_KEY)
        if data.get("chat_model"):
            cfg.cloud_chat_model = data["chat_model"]
        if data.get("vision_model"):
            cfg.cloud_vision_model = data["vision_model"]

    elif step == "complete":
        cfg.ai_enabled = True
        cfg.setup_completed = True
        cfg.setup_completed_at = datetime.now(timezone.utc)

    elif step == "skip":
        cfg.ai_enabled = False

    db.commit()
    invalidate_ai_config_cache()
    return JSONResponse(content={"ok": True})


@router.post("/api/check-ollama")
async def api_check_ollama(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    base_url = cfg.ollama_base_url if cfg else "http://localhost:11434"
    provider = OllamaProvider(base_url)
    result = await provider.health_check()
    return JSONResponse(content=result)


@router.post("/api/pull-model")
async def api_pull_model(
    body: PullModelRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    base_url = cfg.ollama_base_url if cfg else "http://localhost:11434"
    provider = OllamaProvider(base_url)
    result = await provider.pull_model(body.model_name)
    if not result.get("error"):
        log_activity(db, user=user, action="AI Model Downloaded", category="admin",
                     summary=f"Downloaded model: {body.model_name}")
    return JSONResponse(content=result)


@router.get("/api/models")
async def api_list_models(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    result: dict = {"ollama": [], "cloud": []}

    if cfg and cfg.ollama_enabled:
        provider = OllamaProvider(cfg.ollama_base_url)
        result["ollama"] = await provider.list_models()

    if cfg and cfg.cloud_enabled and cfg.cloud_api_key_encrypted:
        api_key = decrypt_api_key(cfg.cloud_api_key_encrypted, SECRET_KEY)
        if api_key:
            cloud = CloudProvider(cfg.cloud_provider, api_key)
            result["cloud"] = await cloud.list_models()

    return JSONResponse(content=result)


@router.post("/api/test-cloud")
async def api_test_cloud(
    body: TestCloudRequest,
    user: User = Depends(require_owner),
) -> JSONResponse:
    cloud = CloudProvider(body.provider, body.api_key)
    result = await cloud.health_check()
    return JSONResponse(content=result)


# ─── Chat API ────────────────────────────────────────────────────────────

@router.post("/api/chat")
async def api_chat(
    body: ChatRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    if not cfg or not cfg.ai_enabled:
        return JSONResponse(status_code=400, content={"error": "AI is not enabled. Ask the owner to complete AI setup."})

    if not check_rate_limit(user.id, cfg.max_requests_per_minute):
        return JSONResponse(status_code=429, content={"error": "Too many messages. Please wait a moment."})

    message_text = body.message.strip()
    if not message_text:
        return JSONResponse(status_code=400, content={"error": "Message cannot be empty."})
    if len(message_text) > 2000:
        return JSONResponse(status_code=400, content={"error": "Message too long (max 2000 characters)."})

    # Get or create conversation
    conversation = None
    if body.conversation_id:
        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == body.conversation_id,
            ChatConversation.user_id == user.id,
        ).first()
    if not conversation:
        title = message_text[:60] + ("..." if len(message_text) > 60 else "")
        conversation = ChatConversation(user_id=user.id, title=title)
        db.add(conversation)
        db.flush()

    # Save user message
    user_msg = ChatMessage(
        conversation_id=conversation.id, role="user", content=message_text,
    )
    db.add(user_msg)
    db.flush()

    # Build message history from DB
    history = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation.id,
    ).order_by(ChatMessage.created_at).all()

    messages = [AIChatMessage(role="system", content=build_system_prompt(user))]
    for msg in history:
        if msg.role in ("user", "assistant"):
            messages.append(AIChatMessage(role=msg.role, content=msg.content))

    # Execute AI with tool-calling loop (max 3 rounds)
    ai_router = AIRouter(db, SECRET_KEY)
    final_response: AICompletionResponse | None = None

    for _round in range(4):
        request = AICompletionRequest(
            messages=messages,
            tools=TOOL_DEFINITIONS if _round < 3 else None,  # no tools on last round to force text
            task_type="chat",
            max_tokens=cfg.max_tokens_per_request,
        )
        response = await ai_router.complete(request)

        if response.error:
            # Save error as assistant message
            error_content = f"I'm sorry, I couldn't process that right now. Error: {response.error}"
            db.add(ChatMessage(
                conversation_id=conversation.id, role="assistant",
                content=error_content, provider_used=response.provider, model_used=response.model_used,
            ))
            db.commit()
            return JSONResponse(content={
                "conversation_id": conversation.id,
                "message": {"role": "assistant", "content": error_content},
                "error": response.error,
            })

        if response.tool_calls:
            # Execute tool calls and append results
            messages.append(AIChatMessage(
                role="assistant", content=response.content, tool_calls=response.tool_calls,
            ))
            for tc in response.tool_calls:
                tool_result = await execute_tool(
                    tc["name"], tc.get("arguments", {}), db, user, settings=_app_settings,
                )
                messages.append(AIChatMessage(
                    role="tool", content=tool_result, tool_call_id=tc.get("id", ""),
                ))
            continue  # next round
        else:
            final_response = response
            break

    if final_response is None:
        final_response = response  # use last response from loop

    # Save assistant response
    assistant_msg = ChatMessage(
        conversation_id=conversation.id, role="assistant",
        content=final_response.content,
        tool_calls=json.dumps(final_response.tool_calls) if final_response.tool_calls else "",
        model_used=final_response.model_used,
        provider_used=final_response.provider,
    )
    db.add(assistant_msg)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()

    return JSONResponse(content={
        "conversation_id": conversation.id,
        "message": assistant_msg.to_dict(),
    })


# ─── Conversation management ────────────────────────────────────────────

@router.get("/api/conversations")
def api_list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    convos = db.query(ChatConversation).filter(
        ChatConversation.user_id == user.id,
    ).order_by(ChatConversation.updated_at.desc()).limit(limit).all()
    return JSONResponse(content={"conversations": [c.to_dict() for c in convos]})


@router.get("/api/conversations/{convo_id}")
def api_get_conversation(
    convo_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    convo = db.query(ChatConversation).filter(
        ChatConversation.id == convo_id,
        ChatConversation.user_id == user.id,
    ).first()
    if not convo:
        return JSONResponse(status_code=404, content={"error": "Conversation not found"})
    messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == convo_id,
    ).order_by(ChatMessage.created_at).all()
    return JSONResponse(content={
        "conversation": convo.to_dict(),
        "messages": [m.to_dict() for m in messages if m.role in ("user", "assistant")],
    })


@router.delete("/api/conversations/{convo_id}")
def api_delete_conversation(
    convo_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    convo = db.query(ChatConversation).filter(
        ChatConversation.id == convo_id,
        ChatConversation.user_id == user.id,
    ).first()
    if not convo:
        return JSONResponse(status_code=404, content={"error": "Conversation not found"})
    db.delete(convo)
    db.commit()
    return JSONResponse(content={"ok": True})


# ─── Item suggestion ─────────────────────────────────────────────────────

@router.post("/api/suggest-item")
async def api_suggest_item(
    body: SuggestItemRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    if not cfg or not cfg.ai_enabled:
        return JSONResponse(status_code=400, content={"error": "AI is not enabled."})

    from app.database import InventoryItem
    # Gather existing values for context
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id, InventoryItem.status == "active",
    ).all()

    if body.field == "category":
        existing = sorted(set(i.category for i in items if i.category))
        prompt = (
            f"Given an item named \"{body.name}\" with SKU \"{body.sku}\" for a packaging/industrial supply company, "
            f"and these existing categories: {existing}, "
            f"suggest the single most appropriate category. Return ONLY the category name, nothing else."
        )
    elif body.field == "location":
        existing = sorted(set(i.location for i in items if i.location))
        prompt = (
            f"Given an item named \"{body.name}\" with SKU \"{body.sku}\" for a packaging/industrial supply company, "
            f"and these existing locations: {existing}, "
            f"suggest the single most appropriate location. Return ONLY the location name, nothing else."
        )
    elif body.field == "min_quantity":
        similar = [i for i in items if i.category and i.category == body.name.split()[0] if i.min_quantity > 0]
        avg_min = int(sum(i.min_quantity for i in similar) / len(similar)) if similar else 10
        prompt = (
            f"Given an item named \"{body.name}\" for a packaging company, "
            f"similar items have an average minimum stock of {avg_min}, "
            f"suggest a reasonable minimum quantity as a single number. Return ONLY the number."
        )
    else:
        return JSONResponse(status_code=400, content={"error": f"Unknown field: {body.field}"})

    ai_router = AIRouter(db, SECRET_KEY)
    response = await ai_router.complete(AICompletionRequest(
        messages=[
            AIChatMessage(role="system", content="You are a helpful inventory assistant. Give concise single-value answers."),
            AIChatMessage(role="user", content=prompt),
        ],
        task_type="inventory_suggest",
        max_tokens=50,
        temperature=0.2,
    ))

    if response.error:
        return JSONResponse(status_code=502, content={"error": response.error})

    suggestion = response.content.strip().strip('"').strip("'")
    return JSONResponse(content={"suggestion": suggestion, "field": body.field})


# ─── CSV cleanup ─────────────────────────────────────────────────────────

@router.post("/api/csv-preview")
async def api_csv_preview(
    body: CsvPreviewRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    if not cfg or not cfg.ai_enabled:
        return JSONResponse(status_code=400, content={"error": "AI is not enabled."})

    system_columns = ["name", "sku", "description", "quantity", "unit", "location",
                      "category", "tags", "notes", "barcode_type", "barcode_value",
                      "min_quantity", "cost"]

    prompt = (
        f"I have a CSV being imported into an inventory system.\n"
        f"System columns: {system_columns}\n"
        f"CSV columns: {body.columns}\n"
        f"First rows: {body.sample_rows[:5]}\n\n"
        f"Return a JSON object mapping each CSV column to the closest system column. "
        f"Set unmapped columns to null. Example: {{\"Product Name\": \"name\", \"Stock\": \"quantity\"}}\n"
        f"Return ONLY the JSON object, no explanation."
    )

    ai_router = AIRouter(db, SECRET_KEY)
    response = await ai_router.complete(AICompletionRequest(
        messages=[
            AIChatMessage(role="system", content="You map CSV columns to system columns. Return only valid JSON."),
            AIChatMessage(role="user", content=prompt),
        ],
        task_type="csv_cleanup",
        max_tokens=300,
        temperature=0.1,
    ))

    if response.error:
        return JSONResponse(status_code=502, content={"error": response.error})

    try:
        content = response.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        mapping = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        mapping = {}

    return JSONResponse(content={"mapping": mapping})


# ─── Rejection recovery ─────────────────────────────────────────────────

@router.post("/api/recover-scan")
async def api_recover_scan(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    # This endpoint will be wired up when we add the rejected documents UI.
    # For now, return a placeholder.
    return JSONResponse(status_code=501, content={"error": "Scan recovery is not yet implemented."})


# ═════════════════════════════════════════════════════════════════════════
# HTML PAGES
# ═════════════════════════════════════════════════════════════════════════

# ─── Setup Wizard ────────────────────────────────────────────────────────

@router.get("/setup", response_class=HTMLResponse)
def page_setup(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    body_html = _render_setup_wizard_html(cfg)
    body_js = _render_setup_wizard_js()
    return HTMLResponse(render_shell(
        title="AI Setup",
        active_nav="ai-setup",
        body_html=body_html,
        body_js=body_js,
        display_name=user.display_name,
        role=user.role,
    ))


# ─── Chat Page ───────────────────────────────────────────────────────────

@router.get("/chat", response_class=HTMLResponse)
def page_chat(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    if not cfg or not cfg.ai_enabled:
        return HTMLResponse(render_shell(
            title="AI Chat",
            active_nav="ai-chat",
            body_html='<div class="empty-state"><h2>AI is not set up yet</h2><p>Ask the system owner to complete <a href="/ai/setup">AI Setup</a>.</p></div>',
            display_name=user.display_name,
            role=user.role,
        ))
    body_html = _render_chat_page_html()
    body_js = _render_chat_page_js()
    return HTMLResponse(render_shell(
        title="AI Chat",
        active_nav="ai-chat",
        body_html=body_html,
        body_js=body_js,
        display_name=user.display_name,
        role=user.role,
    ))


# ─── Privacy Page ────────────────────────────────────────────────────────

@router.get("/privacy", response_class=HTMLResponse)
def page_privacy(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    body_html = _render_privacy_page_html(cfg)
    body_js = _render_privacy_page_js()
    return HTMLResponse(render_shell(
        title="AI Privacy & Data Flow",
        active_nav="ai-privacy",
        body_html=body_html,
        body_js=body_js,
        display_name=user.display_name,
        role=user.role,
    ))


# ─── Settings Page ───────────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
def page_settings(
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    body_html = _render_settings_page_html(cfg)
    body_js = _render_settings_page_js()
    return HTMLResponse(render_shell(
        title="AI Settings",
        active_nav="ai-settings",
        body_html=body_html,
        body_js=body_js,
        display_name=user.display_name,
        role=user.role,
    ))


# ═════════════════════════════════════════════════════════════════════════
# HTML RENDERERS
# ═════════════════════════════════════════════════════════════════════════

def _render_setup_wizard_html(cfg: AIConfig | None) -> str:
    setup_done = cfg.setup_completed if cfg else False
    return f"""
<style>
  .wizard {{ max-width: 720px; margin: 0 auto; }}
  .wizard-step {{ display: none; }}
  .wizard-step.active {{ display: block; }}
  .step-indicator {{ display: flex; gap: 8px; margin-bottom: 32px; }}
  .step-dot {{ width: 12px; height: 12px; border-radius: 50%; background: var(--border); transition: background .2s; }}
  .step-dot.active {{ background: var(--accent); }}
  .step-dot.done {{ background: #22c55e; }}
  .mode-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 24px 0; }}
  .mode-card {{ border: 2px solid var(--border); border-radius: 12px; padding: 20px; cursor: pointer;
                transition: all .2s; text-align: center; }}
  .mode-card:hover {{ border-color: var(--accent); background: rgba(99,102,241,.05); }}
  .mode-card.selected {{ border-color: var(--accent); background: rgba(99,102,241,.1); }}
  .mode-card h3 {{ margin: 0 0 8px; font-size: 1.1rem; }}
  .mode-card p {{ margin: 0; font-size: .85rem; color: var(--muted); }}
  .mode-card .badge {{ display: inline-block; font-size: .7rem; padding: 2px 8px; border-radius: 99px;
                       background: var(--accent); color: #fff; margin-top: 8px; }}
  .wizard h2 {{ margin: 0 0 8px; }}
  .wizard .subtitle {{ color: var(--muted); margin: 0 0 24px; font-size: .9rem; }}
  .wizard-actions {{ display: flex; gap: 12px; margin-top: 32px; }}
  .wizard-actions .btn {{ padding: 10px 24px; border-radius: 8px; border: none; cursor: pointer;
                          font-size: .95rem; font-weight: 600; }}
  .btn-primary {{ background: var(--accent); color: #fff; }}
  .btn-primary:disabled {{ opacity: .5; cursor: not-allowed; }}
  .btn-secondary {{ background: var(--surface); color: var(--text); border: 1px solid var(--border) !important; }}
  .check-result {{ margin: 16px 0; padding: 12px 16px; border-radius: 8px; display: none; }}
  .check-ok {{ background: rgba(34,197,94,.1); color: #16a34a; display: block; }}
  .check-fail {{ background: rgba(239,68,68,.1); color: #dc2626; display: block; }}
  .model-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0; }}
  .model-card {{ border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
  .model-card h4 {{ margin: 0 0 4px; }}
  .model-card p {{ margin: 0 0 12px; font-size: .83rem; color: var(--muted); }}
  .model-card .progress {{ height: 6px; background: var(--border); border-radius: 3px; margin-top: 8px; display: none; }}
  .model-card .progress-bar {{ height: 100%; background: var(--accent); border-radius: 3px; width: 0%; transition: width .3s; }}
  .input-group {{ margin: 12px 0; }}
  .input-group label {{ display: block; font-size: .85rem; font-weight: 600; margin-bottom: 4px; }}
  .input-group input, .input-group select {{ width: 100%; padding: 8px 12px; border: 1px solid var(--border);
                                             border-radius: 6px; font-size: .9rem; background: var(--surface); color: var(--text); }}
  .feature-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 20px 0; }}
  .feature-card {{ text-align: center; padding: 20px 12px; border: 1px solid var(--border); border-radius: 10px; }}
  .feature-card .icon {{ font-size: 2rem; margin-bottom: 8px; }}
  .feature-card h4 {{ margin: 0 0 6px; font-size: .95rem; }}
  .feature-card p {{ margin: 0; font-size: .8rem; color: var(--muted); }}
  .summary-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin: 16px 0; }}
  .summary-row {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border); }}
  .summary-row:last-child {{ border: none; }}
  .adv-toggle {{ font-size: .83rem; color: var(--accent); cursor: pointer; margin-top: 8px; display: inline-block; }}
  .adv-content {{ display: none; margin-top: 12px; }}
  .adv-content.show {{ display: block; }}
</style>

<div class="wizard" id="wizard">
  <div class="step-indicator" id="stepDots"></div>

  <!-- Step 1: Why AI? -->
  <div class="wizard-step active" data-step="1">
    <h2>Add AI to BarcodeBuddy</h2>
    <p class="subtitle">AI gives you a smarter way to work with your data. Here's what it can do:</p>
    <div class="feature-cards">
      <div class="feature-card">
        <div class="icon">&#128172;</div>
        <h4>Ask Questions</h4>
        <p>Chat with your data. "What's my lowest stock?" "How many scans failed today?"</p>
      </div>
      <div class="feature-card">
        <div class="icon">&#128269;</div>
        <h4>Recover Failed Scans</h4>
        <p>When a barcode can't be read, AI can try to read the document for you.</p>
      </div>
      <div class="feature-card">
        <div class="icon">&#9889;</div>
        <h4>Smart Suggestions</h4>
        <p>Auto-fill categories, locations, and reorder points when adding items.</p>
      </div>
    </div>
    <div class="wizard-actions">
      <button class="btn btn-primary" onclick="wizardNext()">Let's Set It Up</button>
      <button class="btn btn-secondary" onclick="wizardSkip()">Skip for Now</button>
    </div>
  </div>

  <!-- Step 2: Choose Mode -->
  <div class="wizard-step" data-step="2">
    <h2>Choose How AI Runs</h2>
    <p class="subtitle">Pick what works best for your organization. You can change this later.</p>
    <div class="mode-cards">
      <div class="mode-card" data-mode="local" onclick="selectMode(this)">
        <h3>&#127968; Local Only</h3>
        <p>Everything stays on your server. Free to run. Requires downloading a model (~2-4 GB).</p>
        <span class="badge" style="background:#22c55e">Most Private</span>
      </div>
      <div class="mode-card" data-mode="cloud" onclick="selectMode(this)">
        <h3>&#9729;&#65039; Cloud Only</h3>
        <p>Uses Claude or ChatGPT. Faster and smarter for complex tasks. Data is sent to the provider.</p>
      </div>
      <div class="mode-card" data-mode="hybrid" onclick="selectMode(this)">
        <h3>&#128256; Hybrid</h3>
        <p>Local for everyday questions. Cloud for advanced tasks like reading documents.</p>
        <span class="badge">Recommended</span>
      </div>
    </div>
    <div class="wizard-actions">
      <button class="btn btn-secondary" onclick="wizardBack()">Back</button>
      <button class="btn btn-primary" id="modeNextBtn" disabled onclick="wizardNext()">Next</button>
    </div>
  </div>

  <!-- Step 3: Ollama Setup -->
  <div class="wizard-step" data-step="3">
    <div id="ollamaSetup">
      <h2>Install Ollama</h2>
      <p class="subtitle">Ollama runs AI models on your own computer. Nothing leaves your server.</p>
      <div style="margin:20px 0;">
        <p><strong>Step 1:</strong> Download and install Ollama from the link below.</p>
        <a href="https://ollama.com/download" target="_blank" rel="noopener"
           class="btn btn-primary" style="display:inline-block;text-decoration:none;margin:8px 0;">
          Download Ollama &rarr;
        </a>
        <p style="font-size:.83rem;color:var(--muted);margin-top:8px;">
          After installing, Ollama runs in the background automatically.
        </p>
      </div>
      <div style="margin:20px 0;">
        <p><strong>Step 2:</strong> Check if Ollama is running.</p>
        <button class="btn btn-primary" id="checkOllamaBtn" onclick="checkOllama()">Check Connection</button>
        <div class="check-result" id="ollamaCheck"></div>
      </div>
      <span class="adv-toggle" onclick="toggleAdvanced()">&#9881; Advanced: Custom URL</span>
      <div class="adv-content" id="advOllama">
        <div class="input-group">
          <label>Ollama URL</label>
          <input type="text" id="ollamaUrl" value="http://localhost:11434" />
        </div>
      </div>

      <div id="modelSection" style="display:none; margin-top: 32px;">
        <h2>Download a Model</h2>
        <p class="subtitle">A model is the AI brain. Pick at least one to get started.</p>
        <div class="model-cards">
          <div class="model-card" id="model-llama3.2">
            <h4>Llama 3.2 (3B)</h4>
            <p>Great for chat and questions. ~2 GB download.</p>
            <button class="btn btn-primary" onclick="pullModel('llama3.2', this)">Download</button>
            <div class="progress"><div class="progress-bar"></div></div>
          </div>
          <div class="model-card" id="model-llava">
            <h4>LLaVA</h4>
            <p>Can read images and documents. ~4 GB. Needed for scan recovery.</p>
            <button class="btn btn-primary" onclick="pullModel('llava', this)">Download</button>
            <div class="progress"><div class="progress-bar"></div></div>
          </div>
          <div class="model-card" id="model-mistral">
            <h4>Mistral (7B)</h4>
            <p>Alternative chat model. Good balance of speed and quality.</p>
            <button class="btn btn-primary" onclick="pullModel('mistral', this)">Download</button>
            <div class="progress"><div class="progress-bar"></div></div>
          </div>
        </div>
      </div>
    </div>

    <div id="cloudSetup" style="display:none;">
      <h2>Connect a Cloud AI Provider</h2>
      <p class="subtitle">Enter your API key to use a premium AI model.</p>
      <div class="input-group">
        <label>Provider</label>
        <select id="cloudProvider" onchange="onCloudProviderChange()">
          <option value="">Select...</option>
          <option value="anthropic">Anthropic (Claude)</option>
          <option value="openai">OpenAI (ChatGPT)</option>
        </select>
      </div>
      <div class="input-group">
        <label>API Key</label>
        <div style="display:flex;gap:8px;">
          <input type="password" id="cloudApiKey" placeholder="sk-..." style="flex:1;" />
          <button class="btn btn-secondary" onclick="toggleKeyVisibility()" style="padding:8px 12px;">Show</button>
        </div>
      </div>
      <button class="btn btn-primary" id="testCloudBtn" onclick="testCloud()">Test Connection</button>
      <div class="check-result" id="cloudCheck"></div>
    </div>

    <div class="wizard-actions" style="margin-top:32px;">
      <button class="btn btn-secondary" onclick="wizardBack()">Back</button>
      <button class="btn btn-primary" id="step3NextBtn" onclick="wizardNext()">Next</button>
    </div>
  </div>

  <!-- Step 4: Complete -->
  <div class="wizard-step" data-step="4">
    <h2>You're All Set! &#127881;</h2>
    <p class="subtitle">AI is ready to use. Here's a summary of your configuration:</p>
    <div class="summary-box" id="setupSummary"></div>
    <div class="wizard-actions">
      <a href="/ai/chat" class="btn btn-primary" style="text-decoration:none;">Open AI Chat</a>
      <a href="/ai/privacy" class="btn btn-secondary" style="text-decoration:none;">View Privacy &amp; Data Flow</a>
    </div>
  </div>
</div>
"""


def _render_setup_wizard_js() -> str:
    return """<script>
let currentStep = 1;
let selectedMode = '';
let ollamaOk = false;
let cloudOk = false;
let modelsDownloaded = [];

const totalSteps = 4;

function renderDots() {
  const c = document.getElementById('stepDots');
  c.innerHTML = '';
  for (let i = 1; i <= totalSteps; i++) {
    const d = document.createElement('div');
    d.className = 'step-dot' + (i === currentStep ? ' active' : '') + (i < currentStep ? ' done' : '');
    c.appendChild(d);
  }
}

function showStep(n) {
  document.querySelectorAll('.wizard-step').forEach(s => s.classList.remove('active'));
  const el = document.querySelector(`.wizard-step[data-step="${n}"]`);
  if (el) el.classList.add('active');
  currentStep = n;
  renderDots();
}

function wizardNext() {
  if (currentStep === 2) {
    apiCall('POST', '/ai/api/setup-step', {step: 'choose_mode', data: {mode: selectedMode}});
    // Show relevant sections in step 3
    const showOllama = selectedMode === 'local' || selectedMode === 'hybrid';
    const showCloud = selectedMode === 'cloud' || selectedMode === 'hybrid';
    document.getElementById('ollamaSetup').style.display = showOllama ? 'block' : 'none';
    document.getElementById('cloudSetup').style.display = showCloud ? 'block' : 'none';
  }
  if (currentStep === 3) {
    // Save ollama/cloud config
    if (selectedMode !== 'cloud') {
      const chatModel = modelsDownloaded.includes('llama3.2') ? 'llama3.2' :
                        modelsDownloaded.includes('mistral') ? 'mistral' : modelsDownloaded[0] || 'llama3.2';
      const visionModel = modelsDownloaded.includes('llava') ? 'llava' : '';
      apiCall('POST', '/ai/api/setup-step', {step: 'ollama_url', data: {url: document.getElementById('ollamaUrl').value}});
      apiCall('POST', '/ai/api/setup-step', {step: 'ollama_model', data: {chat_model: chatModel, vision_model: visionModel}});
    }
    if (selectedMode !== 'local') {
      const provider = document.getElementById('cloudProvider').value;
      const key = document.getElementById('cloudApiKey').value;
      apiCall('POST', '/ai/api/setup-step', {step: 'cloud_config', data: {provider, api_key: key}});
    }
    // Complete setup
    apiCall('POST', '/ai/api/setup-step', {step: 'complete', data: {}});
    renderSummary();
  }
  showStep(currentStep + 1);
}

function wizardBack() { showStep(currentStep - 1); }

async function wizardSkip() {
  await apiCall('POST', '/ai/api/setup-step', {step: 'skip', data: {}});
  window.location.href = '/';
}

function selectMode(el) {
  document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  selectedMode = el.dataset.mode;
  document.getElementById('modeNextBtn').disabled = false;
}

async function checkOllama() {
  const btn = document.getElementById('checkOllamaBtn');
  const result = document.getElementById('ollamaCheck');
  btn.disabled = true; btn.textContent = 'Checking...';
  const r = await apiCall('POST', '/ai/api/check-ollama');
  btn.disabled = false; btn.textContent = 'Check Connection';
  if (r.ok && r.data.status === 'ok') {
    result.className = 'check-result check-ok';
    result.textContent = '\\u2705 Ollama is running! ' + (r.data.models || 0) + ' model(s) found.';
    ollamaOk = true;
    document.getElementById('modelSection').style.display = 'block';
  } else {
    result.className = 'check-result check-fail';
    result.textContent = '\\u274c Could not connect to Ollama. Is it installed and running?';
    ollamaOk = false;
  }
}

async function pullModel(name, btn) {
  btn.disabled = true; btn.textContent = 'Downloading...';
  const card = btn.closest('.model-card');
  const progress = card.querySelector('.progress');
  const bar = card.querySelector('.progress-bar');
  progress.style.display = 'block';
  bar.style.width = '30%';

  const r = await apiCall('POST', '/ai/api/pull-model', {model_name: name});
  bar.style.width = '100%';

  if (r.ok && !r.data.error) {
    btn.textContent = '\\u2705 Downloaded';
    btn.style.background = '#22c55e';
    if (!modelsDownloaded.includes(name)) modelsDownloaded.push(name);
  } else {
    btn.textContent = 'Failed — Retry';
    btn.disabled = false;
    btn.style.background = '#dc2626';
  }
}

function toggleAdvanced() {
  document.getElementById('advOllama').classList.toggle('show');
}

function onCloudProviderChange() {}

function toggleKeyVisibility() {
  const inp = document.getElementById('cloudApiKey');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

async function testCloud() {
  const btn = document.getElementById('testCloudBtn');
  const result = document.getElementById('cloudCheck');
  const provider = document.getElementById('cloudProvider').value;
  const key = document.getElementById('cloudApiKey').value;
  if (!provider || !key) { result.className = 'check-result check-fail'; result.textContent = 'Select a provider and enter an API key.'; return; }
  btn.disabled = true; btn.textContent = 'Testing...';
  const r = await apiCall('POST', '/ai/api/test-cloud', {provider, api_key: key});
  btn.disabled = false; btn.textContent = 'Test Connection';
  if (r.ok && r.data.status === 'ok') {
    result.className = 'check-result check-ok';
    result.textContent = '\\u2705 Connected to ' + provider + ' successfully!';
    cloudOk = true;
  } else {
    result.className = 'check-result check-fail';
    result.textContent = '\\u274c Connection failed: ' + (r.data.error || 'Unknown error');
    cloudOk = false;
  }
}

function renderSummary() {
  const box = document.getElementById('setupSummary');
  let html = '';
  html += '<div class="summary-row"><span>Mode</span><strong>' + selectedMode + '</strong></div>';
  if (selectedMode !== 'cloud') {
    html += '<div class="summary-row"><span>Local Models</span><strong>' + (modelsDownloaded.join(', ') || 'None yet') + '</strong></div>';
  }
  if (selectedMode !== 'local') {
    const prov = document.getElementById('cloudProvider').value;
    html += '<div class="summary-row"><span>Cloud Provider</span><strong>' + (prov || 'Not set') + '</strong></div>';
  }
  box.innerHTML = html;
}

renderDots();
</script>"""


# ─── Chat Page ───────────────────────────────────────────────────────────

def _render_chat_page_html() -> str:
    return """
<style>
  .chat-layout { display: flex; height: calc(100vh - 64px); }
  .chat-sidebar { width: 260px; border-right: 1px solid var(--border); display: flex; flex-direction: column;
                  background: var(--surface); }
  .chat-sidebar-header { padding: 16px; border-bottom: 1px solid var(--border); }
  .chat-sidebar-header button { width: 100%; padding: 10px; border: none; border-radius: 8px;
                                background: var(--accent); color: #fff; font-weight: 600; cursor: pointer; }
  .convo-list { flex: 1; overflow-y: auto; padding: 8px; }
  .convo-item { padding: 10px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 4px;
                font-size: .88rem; display: flex; justify-content: space-between; align-items: center; }
  .convo-item:hover { background: var(--hover); }
  .convo-item.active { background: rgba(99,102,241,.15); }
  .convo-item .title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .convo-item .delete { opacity: 0; padding: 2px 6px; border: none; background: none;
                        color: var(--muted); cursor: pointer; font-size: 1rem; }
  .convo-item:hover .delete { opacity: 1; }
  .chat-main { flex: 1; display: flex; flex-direction: column; }
  .chat-messages { flex: 1; overflow-y: auto; padding: 24px; }
  .msg { margin-bottom: 16px; display: flex; }
  .msg.user { justify-content: flex-end; }
  .msg .bubble { max-width: 70%; padding: 12px 16px; border-radius: 16px; font-size: .92rem; line-height: 1.5; }
  .msg.user .bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
  .msg.assistant .bubble { background: var(--surface); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
  .msg.assistant .bubble p { margin: 0 0 8px; }
  .msg.assistant .bubble p:last-child { margin: 0; }
  .chat-input-area { padding: 16px 24px; border-top: 1px solid var(--border); display: flex; gap: 8px; }
  .chat-input-area input { flex: 1; padding: 12px 16px; border: 1px solid var(--border); border-radius: 12px;
                           font-size: .95rem; background: var(--surface); color: var(--text); }
  .chat-input-area button { padding: 12px 24px; border: none; border-radius: 12px; background: var(--accent);
                            color: #fff; font-weight: 600; cursor: pointer; }
  .chat-input-area button:disabled { opacity: .5; cursor: not-allowed; }
  .typing-indicator { display: none; margin-bottom: 16px; }
  .typing-indicator.show { display: flex; }
  .typing-indicator .bubble { background: var(--surface); border: 1px solid var(--border); padding: 12px 20px;
                              border-radius: 16px; border-bottom-left-radius: 4px; }
  .typing-dots span { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
                      background: var(--muted); margin: 0 2px; animation: typing .8s infinite; }
  .typing-dots span:nth-child(2) { animation-delay: .15s; }
  .typing-dots span:nth-child(3) { animation-delay: .3s; }
  @keyframes typing { 0%,60%,100% { transform: translateY(0); } 30% { transform: translateY(-4px); } }
  .empty-chat { display: flex; flex-direction: column; align-items: center; justify-content: center;
                height: 100%; color: var(--muted); text-align: center; }
  .empty-chat h3 { margin: 0 0 8px; color: var(--text); }
  .empty-chat p { max-width: 400px; font-size: .9rem; }
  .suggestions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
  .suggestions button { padding: 8px 14px; border: 1px solid var(--border); border-radius: 20px;
                        background: var(--surface); color: var(--text); cursor: pointer; font-size: .83rem; }
  .suggestions button:hover { border-color: var(--accent); background: rgba(99,102,241,.05); }
  @media (max-width: 768px) {
    .chat-sidebar { display: none; }
    .msg .bubble { max-width: 90%; }
  }
</style>
<div class="chat-layout">
  <div class="chat-sidebar">
    <div class="chat-sidebar-header">
      <button onclick="newConversation()">+ New Conversation</button>
    </div>
    <div class="convo-list" id="convoList"></div>
  </div>
  <div class="chat-main">
    <div class="chat-messages" id="chatMessages">
      <div class="empty-chat" id="emptyChat">
        <h3>BarcodeBuddy AI</h3>
        <p>Ask anything about your inventory, processing stats, alerts, or activity.</p>
        <div class="suggestions">
          <button onclick="sendSuggestion(this)">What's my lowest stock item?</button>
          <button onclick="sendSuggestion(this)">How many documents failed this week?</button>
          <button onclick="sendSuggestion(this)">Show inventory summary</button>
          <button onclick="sendSuggestion(this)">Any unread alerts?</button>
        </div>
      </div>
      <div class="typing-indicator" id="typingIndicator">
        <div class="bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>
      </div>
    </div>
    <div class="chat-input-area">
      <input type="text" id="chatInput" placeholder="Ask about your inventory, stats, alerts..."
             onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMessage();}" maxlength="2000" />
      <button id="sendBtn" onclick="sendMessage()">Send</button>
    </div>
  </div>
</div>
"""


def _render_chat_page_js() -> str:
    return """<script>
let activeConvoId = '';
let sending = false;

async function loadConversations() {
  const r = await apiCall('GET', '/ai/api/conversations');
  if (!r.ok) return;
  const list = document.getElementById('convoList');
  list.innerHTML = '';
  for (const c of r.data.conversations) {
    const div = document.createElement('div');
    div.className = 'convo-item' + (c.id === activeConvoId ? ' active' : '');
    div.innerHTML = '<span class="title">' + esc(c.title) + '</span>' +
      '<button class="delete" onclick="event.stopPropagation();deleteConvo(\\'' + c.id + '\\')">&times;</button>';
    div.onclick = () => loadConversation(c.id);
    list.appendChild(div);
  }
}

async function loadConversation(id) {
  activeConvoId = id;
  const r = await apiCall('GET', '/ai/api/conversations/' + id);
  if (!r.ok) return;
  renderMessages(r.data.messages);
  loadConversations();
}

function renderMessages(messages) {
  const container = document.getElementById('chatMessages');
  const typing = document.getElementById('typingIndicator');
  const empty = document.getElementById('emptyChat');
  // Remove all message elements but keep typing and empty
  container.querySelectorAll('.msg').forEach(m => m.remove());
  empty.style.display = messages.length ? 'none' : 'flex';
  for (const m of messages) {
    const div = document.createElement('div');
    div.className = 'msg ' + m.role;
    div.innerHTML = '<div class="bubble">' + formatContent(m.content) + '</div>';
    container.insertBefore(div, typing);
  }
  container.scrollTop = container.scrollHeight;
}

function addMessage(role, content) {
  const container = document.getElementById('chatMessages');
  const typing = document.getElementById('typingIndicator');
  document.getElementById('emptyChat').style.display = 'none';
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = '<div class="bubble">' + formatContent(content) + '</div>';
  container.insertBefore(div, typing);
  container.scrollTop = container.scrollHeight;
}

function formatContent(text) {
  // Basic markdown: bold, italic, code, lists
  let s = esc(text);
  s = s.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
  s = s.replace(/\\*(.+?)\\*/g, '<em>$1</em>');
  s = s.replace(/`([^`]+)`/g, '<code style="background:var(--hover);padding:1px 4px;border-radius:3px;">$1</code>');
  s = s.replace(/\\n/g, '<br>');
  return s;
}

async function sendMessage() {
  if (sending) return;
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addMessage('user', text);
  sending = true;
  document.getElementById('sendBtn').disabled = true;
  document.getElementById('typingIndicator').classList.add('show');

  const r = await apiCall('POST', '/ai/api/chat', {conversation_id: activeConvoId, message: text});

  document.getElementById('typingIndicator').classList.remove('show');
  sending = false;
  document.getElementById('sendBtn').disabled = false;

  if (r.ok) {
    activeConvoId = r.data.conversation_id;
    addMessage('assistant', r.data.message.content);
    loadConversations();
  } else {
    addMessage('assistant', 'Error: ' + (r.data.error || 'Something went wrong.'));
  }
  input.focus();
}

function sendSuggestion(btn) {
  document.getElementById('chatInput').value = btn.textContent;
  sendMessage();
}

function newConversation() {
  activeConvoId = '';
  renderMessages([]);
  loadConversations();
  document.getElementById('chatInput').focus();
}

async function deleteConvo(id) {
  await apiCall('DELETE', '/ai/api/conversations/' + id);
  if (activeConvoId === id) { activeConvoId = ''; renderMessages([]); }
  loadConversations();
}

loadConversations();
document.getElementById('chatInput').focus();
</script>"""


# ─── Privacy Page ────────────────────────────────────────────────────────

def _render_privacy_page_html(cfg: AIConfig | None) -> str:
    ollama_enabled = cfg.ollama_enabled if cfg else False
    cloud_enabled = cfg.cloud_enabled if cfg else False
    cloud_provider = cfg.cloud_provider if cfg else ""
    ai_enabled = cfg.ai_enabled if cfg else False

    badge_text = "AI Not Configured"
    badge_color = "#6b7280"
    if ai_enabled:
        if ollama_enabled and not cloud_enabled:
            badge_text = "All AI is Local — Nothing Leaves Your Server"
            badge_color = "#22c55e"
        elif cloud_enabled and not ollama_enabled:
            badge_text = f"Cloud AI Active ({cloud_provider.title()})"
            badge_color = "#f59e0b"
        elif ollama_enabled and cloud_enabled:
            badge_text = f"Hybrid — Local + Cloud ({cloud_provider.title()})"
            badge_color = "#3b82f6"

    ollama_opacity = "1" if ollama_enabled else ".3"
    cloud_opacity = "1" if cloud_enabled else ".3"
    cloud_dash = "" if cloud_enabled else "stroke-dasharray: 6 4;"

    return f"""
<style>
  .privacy-page {{ max-width: 800px; margin: 0 auto; }}
  .status-badge {{ display: inline-block; padding: 8px 20px; border-radius: 99px; font-weight: 600;
                   font-size: .9rem; color: #fff; margin-bottom: 32px; }}
  .flow-diagram {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
                   padding: 32px; margin-bottom: 32px; text-align: center; }}
  .flow-diagram svg {{ max-width: 100%; }}
  .data-table {{ width: 100%; border-collapse: collapse; margin: 16px 0 32px; }}
  .data-table th {{ text-align: left; padding: 10px 12px; background: var(--surface); border-bottom: 2px solid var(--border);
                    font-size: .85rem; text-transform: uppercase; color: var(--muted); letter-spacing: .05em; }}
  .data-table td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: .9rem; }}
  .data-table .where {{ font-weight: 600; }}
  .section-title {{ font-size: 1.15rem; font-weight: 700; margin: 24px 0 12px; }}
  .controls-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }}
  .controls-row {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0;
                   border-bottom: 1px solid var(--border); }}
  .controls-row:last-child {{ border: none; }}
</style>

<div class="privacy-page">
  <h2>AI Privacy &amp; Data Flow</h2>
  <div class="status-badge" style="background:{badge_color};">{badge_text}</div>

  <h3 class="section-title">Where Your Data Goes</h3>
  <div class="flow-diagram">
    <svg viewBox="0 0 700 180" xmlns="http://www.w3.org/2000/svg" style="font-family:inherit;">
      <!-- Browser -->
      <rect x="10" y="60" width="140" height="60" rx="10" fill="var(--surface)" stroke="var(--border)" stroke-width="2"/>
      <text x="80" y="85" text-anchor="middle" font-size="12" fill="var(--text)" font-weight="600">Your Browser</text>
      <text x="80" y="102" text-anchor="middle" font-size="10" fill="var(--muted)">HTTPS</text>

      <!-- Arrow 1 -->
      <line x1="150" y1="90" x2="230" y2="90" stroke="var(--accent)" stroke-width="2" marker-end="url(#arrow)"/>

      <!-- Server -->
      <rect x="230" y="40" width="180" height="100" rx="10" fill="var(--accent)" fill-opacity=".1" stroke="var(--accent)" stroke-width="2"/>
      <text x="320" y="75" text-anchor="middle" font-size="12" fill="var(--text)" font-weight="700">BarcodeBuddy</text>
      <text x="320" y="93" text-anchor="middle" font-size="10" fill="var(--muted)">Your Server</text>
      <text x="320" y="110" text-anchor="middle" font-size="10" fill="var(--muted)">Database &bull; Logs</text>

      <!-- Arrow to Ollama -->
      <line x1="410" y1="70" x2="490" y2="50" stroke="var(--accent)" stroke-width="2" opacity="{ollama_opacity}" marker-end="url(#arrow)"/>

      <!-- Ollama -->
      <rect x="490" y="15" width="170" height="60" rx="10" fill="var(--surface)" stroke="#22c55e" stroke-width="2" opacity="{ollama_opacity}"/>
      <text x="575" y="40" text-anchor="middle" font-size="12" fill="var(--text)" font-weight="600" opacity="{ollama_opacity}">Ollama (Local)</text>
      <text x="575" y="57" text-anchor="middle" font-size="10" fill="#22c55e" opacity="{ollama_opacity}">Same Machine</text>

      <!-- Arrow to Cloud -->
      <line x1="410" y1="110" x2="490" y2="130" stroke="var(--accent)" stroke-width="2" opacity="{cloud_opacity}" {cloud_dash} marker-end="url(#arrow)"/>

      <!-- Cloud -->
      <rect x="490" y="105" width="170" height="60" rx="10" fill="var(--surface)" stroke="#f59e0b" stroke-width="2" opacity="{cloud_opacity}"
            {"stroke-dasharray='6 4'" if not cloud_enabled else ""}/>
      <text x="575" y="130" text-anchor="middle" font-size="12" fill="var(--text)" font-weight="600" opacity="{cloud_opacity}">Cloud API</text>
      <text x="575" y="147" text-anchor="middle" font-size="10" fill="#f59e0b" opacity="{cloud_opacity}">{"Not configured" if not cloud_enabled else cloud_provider.title()}</text>

      <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--accent)"/>
      </marker></defs>
    </svg>
  </div>

  <h3 class="section-title">What Data Is Sent to AI</h3>
  <table class="data-table">
    <thead><tr><th>Feature</th><th>What Is Sent</th><th>Where</th></tr></thead>
    <tbody>
      <tr><td>Chat questions</td><td>Your question + relevant database query results (items, counts, stats)</td>
          <td class="where">{"Local (Ollama)" if ollama_enabled else "Cloud" if cloud_enabled else "—"}</td></tr>
      <tr><td>Scan recovery</td><td>Image of a rejected document (first page only)</td>
          <td class="where">{"Cloud (" + cloud_provider.title() + ")" if cloud_enabled else "Local (Ollama)" if ollama_enabled else "—"}</td></tr>
      <tr><td>Item suggestions</td><td>Item name + existing category/location list</td>
          <td class="where">{"Local (Ollama)" if ollama_enabled else "Cloud" if cloud_enabled else "—"}</td></tr>
      <tr><td>CSV cleanup</td><td>Column headers + first 5 rows of your CSV</td>
          <td class="where">{"Local (Ollama)" if ollama_enabled else "Cloud" if cloud_enabled else "—"}</td></tr>
    </tbody>
  </table>

  <h3 class="section-title">Your Privacy Controls</h3>
  <div class="controls-box">
    <div class="controls-row">
      <span>AI Status</span>
      <strong>{"Enabled" if ai_enabled else "Disabled"}</strong>
    </div>
    <div class="controls-row">
      <span>Local AI (Ollama)</span>
      <strong style="color:{"#22c55e" if ollama_enabled else "#6b7280"};">{"Active" if ollama_enabled else "Off"}</strong>
    </div>
    <div class="controls-row">
      <span>Cloud AI</span>
      <strong style="color:{"#f59e0b" if cloud_enabled else "#6b7280"};">{"Active (" + cloud_provider.title() + ")" if cloud_enabled else "Off"}</strong>
    </div>
    <div class="controls-row">
      <span>Change settings</span>
      <a href="/ai/settings" style="color:var(--accent);font-weight:600;">AI Settings &rarr;</a>
    </div>
  </div>
</div>
"""


def _render_privacy_page_js() -> str:
    return "<script>/* Privacy page — static content, no JS needed */</script>"


# ─── Settings Page ───────────────────────────────────────────────────────

def _render_settings_page_html(cfg: AIConfig | None) -> str:
    if not cfg:
        return '<div class="empty-state"><h2>AI not initialized</h2><p>Please restart the application.</p></div>'

    return f"""
<style>
  .settings-page {{ max-width: 640px; margin: 0 auto; }}
  .setting-group {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                    padding: 20px; margin-bottom: 20px; }}
  .setting-group h3 {{ margin: 0 0 16px; font-size: 1.05rem; }}
  .setting-row {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0;
                  border-bottom: 1px solid var(--border); }}
  .setting-row:last-child {{ border: none; }}
  .setting-row label {{ font-weight: 500; font-size: .9rem; }}
  .setting-row input[type=text], .setting-row select {{ padding: 6px 10px; border: 1px solid var(--border);
                                                        border-radius: 6px; font-size: .85rem; min-width: 200px;
                                                        background: var(--bg); color: var(--text); }}
  .toggle {{ position: relative; width: 44px; height: 24px; }}
  .toggle input {{ opacity: 0; width: 0; height: 0; }}
  .toggle .slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
                     background: var(--border); border-radius: 24px; transition: .3s; }}
  .toggle .slider:before {{ content: ""; position: absolute; height: 18px; width: 18px; left: 3px; bottom: 3px;
                            background: #fff; border-radius: 50%; transition: .3s; }}
  .toggle input:checked + .slider {{ background: var(--accent); }}
  .toggle input:checked + .slider:before {{ transform: translateX(20px); }}
  .save-bar {{ display: flex; gap: 12px; margin-top: 24px; }}
  .save-bar .btn {{ padding: 10px 24px; border-radius: 8px; border: none; cursor: pointer; font-weight: 600; }}
</style>

<div class="settings-page">
  <h2>AI Settings</h2>

  <div class="setting-group">
    <h3>General</h3>
    <div class="setting-row">
      <label>AI Enabled</label>
      <label class="toggle"><input type="checkbox" id="sAiEnabled" {"checked" if cfg.ai_enabled else ""} /><span class="slider"></span></label>
    </div>
  </div>

  <div class="setting-group">
    <h3>Local AI (Ollama)</h3>
    <div class="setting-row">
      <label>Enabled</label>
      <label class="toggle"><input type="checkbox" id="sOllamaEnabled" {"checked" if cfg.ollama_enabled else ""} /><span class="slider"></span></label>
    </div>
    <div class="setting-row">
      <label>URL</label>
      <input type="text" id="sOllamaUrl" value="{cfg.ollama_base_url}" />
    </div>
    <div class="setting-row">
      <label>Chat Model</label>
      <input type="text" id="sOllamaChatModel" value="{cfg.ollama_chat_model}" />
    </div>
    <div class="setting-row">
      <label>Vision Model</label>
      <input type="text" id="sOllamaVisionModel" value="{cfg.ollama_vision_model}" />
    </div>
  </div>

  <div class="setting-group">
    <h3>Cloud AI</h3>
    <div class="setting-row">
      <label>Enabled</label>
      <label class="toggle"><input type="checkbox" id="sCloudEnabled" {"checked" if cfg.cloud_enabled else ""} /><span class="slider"></span></label>
    </div>
    <div class="setting-row">
      <label>Provider</label>
      <select id="sCloudProvider">
        <option value="" {"selected" if not cfg.cloud_provider else ""}>None</option>
        <option value="anthropic" {"selected" if cfg.cloud_provider == "anthropic" else ""}>Anthropic (Claude)</option>
        <option value="openai" {"selected" if cfg.cloud_provider == "openai" else ""}>OpenAI</option>
      </select>
    </div>
    <div class="setting-row">
      <label>API Key</label>
      <input type="password" id="sCloudApiKey" placeholder="{"••••••••" if cfg.cloud_api_key_encrypted else "Not set"}" />
    </div>
    <div class="setting-row">
      <label>Chat Model</label>
      <input type="text" id="sCloudChatModel" value="{cfg.cloud_chat_model}" />
    </div>
    <div class="setting-row">
      <label>Vision Model</label>
      <input type="text" id="sCloudVisionModel" value="{cfg.cloud_vision_model}" />
    </div>
  </div>

  <div class="setting-group">
    <h3>Task Routing</h3>
    <div class="setting-row">
      <label>Chat / Q&amp;A</label>
      <select id="sChatProv"><option value="local" {"selected" if cfg.chat_provider=="local" else ""}>Local</option><option value="cloud" {"selected" if cfg.chat_provider=="cloud" else ""}>Cloud</option></select>
    </div>
    <div class="setting-row">
      <label>Vision / Scan Recovery</label>
      <select id="sVisionProv"><option value="local" {"selected" if cfg.vision_provider=="local" else ""}>Local</option><option value="cloud" {"selected" if cfg.vision_provider=="cloud" else ""}>Cloud</option></select>
    </div>
    <div class="setting-row">
      <label>CSV Cleanup</label>
      <select id="sCsvProv"><option value="local" {"selected" if cfg.csv_provider=="local" else ""}>Local</option><option value="cloud" {"selected" if cfg.csv_provider=="cloud" else ""}>Cloud</option></select>
    </div>
    <div class="setting-row">
      <label>Item Suggestions</label>
      <select id="sSuggestProv"><option value="local" {"selected" if cfg.suggest_provider=="local" else ""}>Local</option><option value="cloud" {"selected" if cfg.suggest_provider=="cloud" else ""}>Cloud</option></select>
    </div>
  </div>

  <div class="setting-group">
    <h3>Limits</h3>
    <div class="setting-row">
      <label>Max tokens per request</label>
      <input type="text" id="sMaxTokens" value="{cfg.max_tokens_per_request}" />
    </div>
    <div class="setting-row">
      <label>Max requests per minute</label>
      <input type="text" id="sMaxRPM" value="{cfg.max_requests_per_minute}" />
    </div>
  </div>

  <div class="save-bar">
    <button class="btn btn-primary" onclick="saveSettings()">Save Changes</button>
    <a href="/ai/setup" class="btn btn-secondary" style="text-decoration:none;">Re-run Setup Wizard</a>
  </div>
</div>
"""


def _render_settings_page_js() -> str:
    return """<script>
async function saveSettings() {
  const body = {
    ai_enabled: document.getElementById('sAiEnabled').checked,
    ollama_enabled: document.getElementById('sOllamaEnabled').checked,
    ollama_base_url: document.getElementById('sOllamaUrl').value,
    ollama_chat_model: document.getElementById('sOllamaChatModel').value,
    ollama_vision_model: document.getElementById('sOllamaVisionModel').value,
    cloud_enabled: document.getElementById('sCloudEnabled').checked,
    cloud_provider: document.getElementById('sCloudProvider').value,
    cloud_chat_model: document.getElementById('sCloudChatModel').value,
    cloud_vision_model: document.getElementById('sCloudVisionModel').value,
    chat_provider: document.getElementById('sChatProv').value,
    vision_provider: document.getElementById('sVisionProv').value,
    csv_provider: document.getElementById('sCsvProv').value,
    suggest_provider: document.getElementById('sSuggestProv').value,
    max_tokens_per_request: parseInt(document.getElementById('sMaxTokens').value) || 1024,
    max_requests_per_minute: parseInt(document.getElementById('sMaxRPM').value) || 30,
  };
  const key = document.getElementById('sCloudApiKey').value;
  if (key && !key.startsWith('•')) body.cloud_api_key = key;
  const r = await apiCall('POST', '/ai/api/config', body);
  if (r.ok) { toast('Settings saved', 'success'); } else { toast('Error: ' + (r.data.error || 'Failed'), 'error'); }
}
</script>"""
