"""
vanna_setup.py
Builds and returns a configured Vanna 2.0 Agent.

Components wired:
  - OpenAILlmService  (pointing at Groq's OpenAI-compatible endpoint)
  - SqliteRunner      (clinic.db)
  - ValidatedRunSqlTool  (RunSqlTool + SQL safety guard)
  - VisualizeDataTool
  - SaveQuestionToolArgsTool
  - SearchSavedCorrectToolUsesTool
  - DemoAgentMemory   (in-RAM; re-seeded on every app startup)
  - DefaultUserResolver
"""

import os
import re
import logging
from typing import Type

from dotenv import load_dotenv

from vanna import Agent, AgentConfig, ToolRegistry, User
from vanna.core.user.resolver import UserResolver
from vanna.core.user.request_context import RequestContext
from vanna.core.tool import Tool, ToolContext, ToolResult
from vanna.components import UiComponent, NotificationComponent, ComponentType, SimpleTextComponent
from vanna.capabilities.sql_runner import RunSqlToolArgs
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import SaveQuestionToolArgsTool, SearchSavedCorrectToolUsesTool
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.openai import OpenAILlmService

load_dotenv()
logger = logging.getLogger(__name__)

# ── SQL safety guard ──────────────────────────────────────────────────────────

# Keywords that must never appear in an allowed query
_BANNED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|"
    r"EXEC|EXECUTE|GRANT|REVOKE|SHUTDOWN|ATTACH|DETACH|PRAGMA|xp_|sp_)\b",
    re.IGNORECASE,
)

# System table access patterns
_SYSTEM_TABLES = re.compile(
    r"\bsqlite_master\b|\bsqlite_sequence\b|\bsqlite_stat",
    re.IGNORECASE,
)

# Allowed lead tokens for a statement
_ALLOWED_LEAD = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

# Simple semicolon-based multi-statement detector (after stripping string literals)
_MULTI_STMT = re.compile(r";.+", re.DOTALL)


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Return (is_safe, error_message).
    is_safe=True means the query may be executed.
    """
    stripped = sql.strip()
    if not stripped:
        return False, "Empty SQL query."

    # Must start with SELECT or WITH
    if not _ALLOWED_LEAD.match(stripped):
        first_word = stripped.split()[0].upper()
        return False, f"Only SELECT queries are allowed. Got: {first_word}"

    # No banned keywords anywhere
    m = _BANNED_KEYWORDS.search(stripped)
    if m:
        return False, f"Forbidden keyword detected: {m.group().upper()}"

    # No system table access
    if _SYSTEM_TABLES.search(stripped):
        return False, "Access to system tables is not allowed."

    # WITH must resolve to a trailing SELECT
    if stripped.upper().startswith("WITH"):
        # Remove everything up to the last closing paren before the final SELECT
        last_select = stripped.upper().rfind("SELECT")
        if last_select == -1:
            return False, "WITH expression must end in a SELECT statement."

    return True, ""


class ValidatedRunSqlTool(RunSqlTool):
    """RunSqlTool that validates SQL before execution."""

    def get_args_schema(self) -> Type[RunSqlToolArgs]:
        return RunSqlToolArgs

    async def execute(self, context: ToolContext, args: RunSqlToolArgs) -> ToolResult:
        is_safe, reason = validate_sql(args.sql)
        if not is_safe:
            msg = f"SQL validation failed: {reason}"
            logger.warning("Blocked SQL — %s | query: %s", reason, args.sql[:200])
            return ToolResult(
                success=False,
                result_for_llm=msg,
                ui_component=UiComponent(
                    rich_component=NotificationComponent(
                        type=ComponentType.NOTIFICATION,
                        level="error",
                        message=msg,
                    ),
                    simple_component=SimpleTextComponent(text=msg),
                ),
                error=reason,
                metadata={"error_type": "sql_validation_failed"},
            )
        return await super().execute(context, args)


# ── User resolver ─────────────────────────────────────────────────────────────

class DefaultUserResolver(UserResolver):
    """Always returns the same synthetic admin user."""

    _USER = User(
        id="default-user",
        username="clinic_admin",
        permissions=["admin", "user"],
    )

    async def resolve_user(self, request_context: RequestContext) -> User:
        return self._USER


# ── Agent factory ─────────────────────────────────────────────────────────────

# Module-level singletons — created once and reused across requests
_agent: Agent | None = None
_memory: DemoAgentMemory | None = None


def build_agent(db_path: str | None = None) -> tuple[Agent, DemoAgentMemory]:
    """
    Build and return (agent, memory).
    Call this once at startup; the memory object is returned so seed_memory
    can populate it via save_tool_usage() directly.
    """
    global _agent, _memory

    if _agent is not None and _memory is not None:
        return _agent, _memory

    db_path = db_path or os.getenv("DATABASE_PATH", "clinic.db")
    groq_key = os.getenv("GROQ_API_KEY", "")
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    if not groq_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )

    # LLM
    llm_service = OpenAILlmService(
        model=groq_model,
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1",
    )

    # DB runner
    sqlite_runner = SqliteRunner(database_path=db_path)

    # Tool registry  (Vanna 2.0.2 uses register_local_tool, not register)
    tool_registry = ToolRegistry()
    tool_registry.register_local_tool(ValidatedRunSqlTool(sql_runner=sqlite_runner), access_groups=[])
    tool_registry.register_local_tool(VisualizeDataTool(), access_groups=[])
    tool_registry.register_local_tool(SaveQuestionToolArgsTool(), access_groups=[])
    tool_registry.register_local_tool(SearchSavedCorrectToolUsesTool(), access_groups=[])

    # Memory
    memory = DemoAgentMemory()

    # Agent
    agent = Agent(
        llm_service=llm_service,
        tool_registry=tool_registry,
        user_resolver=DefaultUserResolver(),
        agent_memory=memory,
        config=AgentConfig(
            stream_responses=False,
            include_thinking_indicators=False,
        ),
    )

    _agent = agent
    _memory = memory

    logger.info("Vanna agent built — model=%s  db=%s", groq_model, db_path)
    return agent, memory


def get_agent() -> Agent:
    """Return the singleton agent, building it on first call."""
    agent, _ = build_agent()
    return agent


def get_memory() -> DemoAgentMemory:
    """Return the singleton memory, building agent on first call."""
    _, memory = build_agent()
    return memory
