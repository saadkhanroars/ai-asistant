"""
backend_api.py — FastAPI server for modern desktop UI.

Exposes all desktop assistant functionality as REST endpoints:
  - Chat with AI
  - Search indexed files
  - Execute actions (open apps, files, settings)
  - Manage index (rebuild, refresh)
  - Get system stats

This layer sits between the existing Python backend and the Electron UI.
Zero changes to existing logic — only wrapping it in REST endpoints.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import existing backend modules
from ai import ask_ai, has_api_key
from indexer import ensure_index, rebuild_index, show_indexed_folders
from incremental_indexer import incremental_refresh
from memory import SessionMemory
from router import handle_request
from search_engine import load_index_cache, search_index
from normalize import NormalizedQuery, normalize_input
from watcher import start_background_watcher, stop_background_watcher

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ChatRequest(BaseModel):
    """Chat message from UI."""
    message: str
    conversation_id: str | None = None  # For future multi-session support

class ChatResponse(BaseModel):
    """Chat response to UI."""
    response: str
    thinking: bool = False
    conversation_id: str

class SearchRequest(BaseModel):
    """File/app search from UI."""
    query: str

class SearchResult(BaseModel):
    """Single search result."""
    name: str
    path: str
    kind: str  # folder, app, document, video, etc.
    item_type: str
    mtime: float

class SearchResponse(BaseModel):
    """Search results list."""
    results: list[SearchResult]
    total_indexed: int
    candidates: int
    elapsed_ms: float

class ActionRequest(BaseModel):
    """Execute action (open app, file, etc)."""
    command: str

class ActionResponse(BaseModel):
    """Action result."""
    success: bool
    message: str
    action_type: str  # 'open_app', 'open_file', 'search', 'settings', etc.

class IndexStats(BaseModel):
    """Index statistics."""
    item_count: int
    last_built: str
    status: str  # 'ready', 'building', 'error'
    watcher_mode: str  # 'watchdog', 'polling', 'off'

class SettingsResponse(BaseModel):
    """App settings."""
    ai_enabled: bool
    indexed_folders: list[str]
    theme: str  # 'dark', 'light'
    auto_launch: bool

class RebuildIndexRequest(BaseModel):
    """Trigger index rebuild."""
    full_rebuild: bool = False

# ============================================================================
# GLOBAL STATE
# ============================================================================

# Session memory for chat context
_session_memory = SessionMemory()
_watcher_mode = "off"
_is_indexing = False

# ============================================================================
# APP SETUP
# ============================================================================

app = FastAPI(
    title="Desktop AI Assistant API",
    description="REST API for modern desktop AI assistant UI",
    version="1.0.0",
)

# CORS middleware for Electron frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH & INITIALIZATION
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize backend on server startup."""
    global _watcher_mode
    try:
        ensure_index()
        load_index_cache()
        _watcher_mode = start_background_watcher()
        print(f"✅ Backend initialized. Watcher mode: {_watcher_mode}")
    except Exception as err:
        print(f"❌ Startup error: {err}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown."""
    stop_background_watcher()
    print("👋 Backend shutdown")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "ai_enabled": "yes" if has_api_key() else "no",
        "watcher": _watcher_mode,
    }


# ============================================================================
# CHAT ENDPOINTS
# ============================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Chat with AI assistant.
    
    Flow:
    1. Try to route as action (open app, settings, search, etc.)
    2. If not handled, send to AI
    """
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Try routing (local actions first)
    result = handle_request(message)
    if result is not None:
        # Action was handled locally
        _session_memory.add_user(message)
        _session_memory.add_assistant(result)
        return ChatResponse(
            response=result,
            thinking=False,
            conversation_id=request.conversation_id or "default",
        )

    # No local action matched — use AI
    if not has_api_key():
        return ChatResponse(
            response="AI chat is not configured (no OPENAI_API_KEY). "
                    "I can still open apps, files, and search. Try: 'open chrome' or 'search cats'.",
            thinking=False,
            conversation_id=request.conversation_id or "default",
        )

    _session_memory.add_user(message)
    try:
        response = ask_ai(_session_memory.get_messages())
        _session_memory.add_assistant(response)
        return ChatResponse(
            response=response,
            thinking=False,
            conversation_id=request.conversation_id or "default",
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"AI error: {err}")


@app.get("/api/chat/history")
async def get_chat_history() -> dict[str, Any]:
    """Get current conversation history."""
    return {
        "messages": _session_memory.get_messages(),
        "message_count": _session_memory.message_count(),
    }


@app.post("/api/chat/clear")
async def clear_chat() -> dict[str, str]:
    """Clear conversation history."""
    _session_memory.clear()
    return {"status": "cleared", "message_count": "0"}


# ============================================================================
# SEARCH ENDPOINTS
# ============================================================================

@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Search indexed files, apps, and folders.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Normalize and search
    normalized = normalize_input(query)
    parsed = NormalizedQuery(normalized=normalized, tokens=normalized.split())
    
    try:
        from search_engine import get_last_search_stats
        results = search_index(parsed)
        stats = get_last_search_stats()

        return SearchResponse(
            results=[
                SearchResult(
                    name=item.name,
                    path=item.path,
                    kind=item.kind,
                    item_type=item.item_type,
                    mtime=item.mtime,
                )
                for item in results[:20]  # Limit to top 20
            ],
            total_indexed=stats.total_indexed,
            candidates=stats.candidates,
            elapsed_ms=stats.elapsed_ms,
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Search error: {err}")


# ============================================================================
# ACTION ENDPOINTS
# ============================================================================

@app.post("/api/action", response_model=ActionResponse)
async def execute_action(request: ActionRequest) -> ActionResponse:
    """
    Execute an action (open app, file, folder, settings, search, etc.).
    This routes through the existing action handler.
    """
    command = request.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="Command cannot be empty")

    try:
        result = handle_request(command)
        
        if result is None:
            # No local action matched
            return ActionResponse(
                success=False,
                message="No action found. Try asking AI or check your command.",
                action_type="unknown",
            )

        # Determine action type from result
        action_type = _infer_action_type(command, result)
        return ActionResponse(
            success=True,
            message=result,
            action_type=action_type,
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Action error: {err}")


def _infer_action_type(command: str, result: str) -> str:
    """Guess action type from command text."""
    lower = command.lower()
    if any(word in lower for word in ["open", "launch", "play"]):
        return "open"
    if any(word in lower for word in ["search", "google", "brave"]):
        return "search"
    if any(word in lower for word in ["settings", "sound", "display"]):
        return "settings"
    if any(word in lower for word in ["close", "kill", "shut"]):
        return "close"
    if any(word in lower for word in ["index", "rebuild", "refresh"]):
        return "index"
    return "action"


# ============================================================================
# INDEX MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/index/stats", response_model=IndexStats)
async def get_index_stats() -> IndexStats:
    """
    Get current index statistics.
    """
    from database import get_index_stats
    stats = get_index_stats()
    
    return IndexStats(
        item_count=int(stats.get("item_count", 0)),
        last_built=stats.get("built_at", "never"),
        status="ready",
        watcher_mode=_watcher_mode,
    )


@app.post("/api/index/rebuild")
async def rebuild_index_endpoint(
    request: RebuildIndexRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """
    Trigger index rebuild in background.
    Full rebuild only if requested; else incremental refresh.
    """
    global _is_indexing
    
    if _is_indexing:
        raise HTTPException(status_code=409, detail="Index rebuild already in progress")

    async def rebuild_task():
        global _is_indexing
        _is_indexing = True
        try:
            if request.full_rebuild:
                result = rebuild_index()
            else:
                result = incremental_refresh()
            print(f"✅ Index rebuilt: {result}")
        finally:
            _is_indexing = False

    background_tasks.add_task(rebuild_task)
    return {
        "status": "rebuilding",
        "full_rebuild": request.full_rebuild,
        "message": "Index rebuild started in background",
    }


@app.get("/api/index/folders")
async def get_indexed_folders() -> dict[str, Any]:
    """
    List all indexed/configured folders.
    """
    return {
        "folders_info": show_indexed_folders(),
        "watcher_mode": _watcher_mode,
    }


# ============================================================================
# SETTINGS ENDPOINTS
# ============================================================================

@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """
    Get current application settings.
    """
    from search_config import all_index_roots
    
    return SettingsResponse(
        ai_enabled=has_api_key(),
        indexed_folders=list(all_index_roots()),
        theme="dark",  # Default to dark theme
        auto_launch=False,  # Future feature
    )


@app.post("/api/settings")
async def update_settings(settings: SettingsResponse) -> dict[str, str]:
    """
    Update application settings.
    Note: Limited implementation — can be expanded.
    """
    return {
        "status": "updated",
        "message": "Settings saved (limited implementation for future expansion)",
    }


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@app.get("/api/version")
async def get_version() -> dict[str, str]:
    """
    Get API version info.
    """
    return {
        "api_version": "1.0.0",
        "python_version": os.sys.version.split()[0],
    }


# ============================================================================
# MAIN & SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    print("🚀 Starting Desktop AI Assistant Backend API...")
    print("📡 Server: http://localhost:5000")
    print("📚 Docs: http://localhost:5000/docs")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=5000,
        log_level="info",
    )
