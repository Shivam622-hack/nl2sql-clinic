"""
main.py
FastAPI application — NL2SQL clinic assistant.

Endpoints:
  POST /chat    Natural-language question → SQL + results + optional chart
  GET  /health  DB connectivity + memory item count

Bonuses implemented:
  ✓ Input validation   (Pydantic + length checks)
  ✓ Structured logging (JSON-compatible via structlog or stdlib)
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

load_dotenv()

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("nl2sql.api")

# ── Pydantic models ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., description="Natural language question about clinic data")

    @field_validator("question")
    @classmethod
    def question_must_be_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question must not be empty.")
        if len(v) > 500:
            raise ValueError("Question must be 500 characters or fewer.")
        return v


class ChatResponse(BaseModel):
    message: str
    sql_query: Optional[str] = None
    columns: Optional[list[str]] = None
    rows: Optional[list[list[Any]]] = None
    row_count: Optional[int] = None
    chart: Optional[dict[str, Any]] = None
    chart_type: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    database: str
    agent_memory_items: int


class ErrorResponse(BaseModel):
    message: str
    error_code: str


# ── Component parsers ─────────────────────────────────────────────────────────

def _extract_from_components(components: list) -> dict[str, Any]:
    """
    Walk the list of UiComponent objects yielded by agent.send_message and
    pull out: message text, sql_query, columns, rows, chart data.
    """
    result: dict[str, Any] = {
        "message": "",
        "sql_query": None,
        "columns": None,
        "rows": None,
        "row_count": None,
        "chart": None,
        "chart_type": None,
    }

    text_parts: list[str] = []

    for comp in components:
        rich = getattr(comp, "rich_component", None)
        simple = getattr(comp, "simple_component", None)
        if rich is None:
            continue

        ctype = type(rich).__name__

        # ── Text / narrative message ─────────────────────────────────────────
        if ctype == "RichTextComponent":
            content = getattr(rich, "content", None) or getattr(rich, "text", None)
            if content:
                text_parts.append(content.strip())

        # ── SQL results (DataFrameComponent) ────────────────────────────────
        elif ctype == "DataFrameComponent":
            columns: list[str] = getattr(rich, "columns", []) or []
            rows_raw: list[dict] = getattr(rich, "rows", []) or []
            if columns and rows_raw:
                result["columns"] = columns
                result["rows"] = [[row.get(c) for c in columns] for row in rows_raw]
                result["row_count"] = len(rows_raw)
            elif not rows_raw:
                result["columns"] = columns
                result["rows"] = []
                result["row_count"] = 0

        # ── Chart (ChartComponent) ───────────────────────────────────────────
        elif ctype == "ChartComponent":
            chart_data = getattr(rich, "data", None)
            chart_type = getattr(rich, "chart_type", None)
            if chart_data:
                result["chart"] = chart_data
                result["chart_type"] = chart_type

        # ── StatusCard often carries the final message ───────────────────────
        elif ctype == "StatusCardComponent":
            title = getattr(rich, "title", None)
            body  = getattr(rich, "body", None) or getattr(rich, "content", None)
            if body:
                text_parts.append(str(body).strip())
            elif title:
                text_parts.append(str(title).strip())

        # ── Plain notification or card ───────────────────────────────────────
        elif ctype in ("CardComponent", "NotificationComponent"):
            content = getattr(rich, "content", None) or getattr(rich, "message", None)
            if content:
                text_parts.append(str(content).strip())

        # ── Try simple_component fallback for unknown rich types ─────────────
        else:
            if simple:
                stext = getattr(simple, "text", None)
                if stext and len(stext) < 1000:
                    text_parts.append(stext.strip())

    result["message"] = "\n\n".join(t for t in text_parts if t) or "Query completed."
    return result


def _extract_sql_from_conversation(agent, conversation_id: str) -> Optional[str]:
    """
    Try to pull the generated SQL from the conversation history.
    Vanna stores assistant messages including tool calls.
    """
    try:
        store = getattr(agent, "_conversation_store", None) or getattr(agent, "conversation_store", None)
        if store is None:
            return None
        conv = asyncio.get_event_loop().run_until_complete(
            store.get_conversation(conversation_id)
        ) if store else None
        if not conv:
            return None
        for msg in reversed(getattr(conv, "messages", [])):
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                args = getattr(tc, "arguments", {}) or {}
                if "sql" in args:
                    return args["sql"]
    except Exception:
        pass
    return None


# ── Lifespan: startup seeding ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build agent and seed memory before first request."""
    logger.info('"Starting NL2SQL API — building Vanna agent…"')
    try:
        from vanna_setup import build_agent
        from seed_memory import seed_agent_memory, SEED_EXAMPLES

        agent, memory = build_agent()
        app.state.agent = agent
        app.state.memory = memory
        app.state.seed_count = len(SEED_EXAMPLES)

        # Seed memory (idempotent — skips if already populated)
        loop = asyncio.get_event_loop()
        stored = await loop.run_in_executor(None, seed_agent_memory, memory)
        if stored:
            logger.info('"Seeded %d examples into agent memory."', stored)
        else:
            logger.info('"Agent memory already populated — skipped seeding."')

        logger.info('"Vanna agent ready."')
    except Exception as exc:
        logger.error('"Agent startup failed: %s"', str(exc))
        raise

    yield  # ← application runs here

    logger.info('"Shutting down NL2SQL API."')


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NL2SQL Clinic API",
    description="Natural language to SQL over a clinic management database.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Middleware: request logging ───────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    start  = time.time()
    logger.info('"req_start","id":"%s","method":"%s","path":"%s"',
                req_id, request.method, request.url.path)
    response = await call_next(request)
    elapsed = round((time.time() - start) * 1000, 1)
    logger.info('"req_end","id":"%s","status":%d,"ms":%s',
                req_id, response.status_code, elapsed)
    return response


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception('"Unhandled exception"')
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred.", "error_code": "INTERNAL_ERROR"},
    )


# ── Health endpoint ───────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    """Check DB connectivity and report memory item count."""
    db_path = os.getenv("DATABASE_PATH", "clinic.db")
    db_status = "disconnected"
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1")
        conn.close()
        db_status = "connected"
    except Exception as exc:
        logger.warning('"DB health check failed: %s"', str(exc))

    # Count items currently in memory
    memory = getattr(app.state, "memory", None)
    mem_count = 0
    if memory:
        try:
            from vanna import User
            from vanna.core.tool import ToolContext
            ctx = ToolContext(
                user=User(id="health", username="health", permissions=[]),
                conversation_id="health",
                request_id="health",
                agent_memory=memory,
            )
            recent = await memory.get_recent_memories(ctx, limit=1000)
            mem_count = len(recent)
        except Exception:
            mem_count = getattr(app.state, "seed_count", 0)

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        agent_memory_items=mem_count,
    )


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(body: ChatRequest):
    """
    Accept a natural-language question and return SQL + results + optional chart.
    """
    agent = getattr(app.state, "agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialised.")

    question = body.question
    conversation_id = f"chat-{uuid.uuid4().hex[:12]}"

    logger.info('"chat_request","question":"%s","conv":"%s"', question[:120], conversation_id)

    # send_message takes RequestContext; our DefaultUserResolver returns the admin user
    from vanna.core.user.request_context import RequestContext
    request_context = RequestContext(
        cookies={},
        headers={},
        metadata={"ui_features_available": []},
    )

    # Collect all yielded UiComponents
    collected: list = []
    try:
        async for component in agent.send_message(
            request_context=request_context,
            message=question,
            conversation_id=conversation_id,
        ):
            collected.append(component)
    except Exception as exc:
        logger.exception('"agent.send_message failed"')
        return JSONResponse(
            status_code=500,
            content={
                "message": f"Agent error: {str(exc)}",
                "error_code": "AGENT_ERROR",
            },
        )

    # Parse components into response shape
    extracted = _extract_from_components(collected)

    # Try to recover the SQL from component metadata if not in narrative
    # Check ToolResult metadata stored in components
    sql_query = extracted.get("sql_query")
    if not sql_query:
        for comp in collected:
            rich = getattr(comp, "rich_component", None)
            if rich is None:
                continue
            # DataFrameComponent doesn't carry SQL, but ToolResult metadata might
            # be reachable via simple_component text which contains the CSV + filename hint
            simple = getattr(comp, "simple_component", None)
            if simple:
                stext = getattr(simple, "text", "") or ""
                # RunSqlTool embeds the SQL in result_for_llm as CSV
                # We capture it from the conversation store instead
                break

        # Last resort: scan conversation store
        sql_query = _extract_sql_from_conversation(agent, conversation_id)

    extracted["sql_query"] = sql_query

    # Classify outcome
    rows = extracted.get("rows")
    row_count = extracted.get("row_count")

    if rows is not None and row_count == 0:
        extracted["message"] = "No data found for your query."

    logger.info(
        '"chat_response","conv":"%s","rows":%s,"has_chart":%s',
        conversation_id,
        row_count,
        extracted.get("chart") is not None,
    )

    return ChatResponse(**extracted)


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
