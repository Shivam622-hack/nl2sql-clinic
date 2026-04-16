"""
seed_memory.py
Seeds the Vanna agent memory with 15 curated question–SQL pairs.

Can be run as a CLI script (python seed_memory.py) or imported as a module:
    from seed_memory import seed_agent_memory, SEED_EXAMPLES

DemoAgentMemory is in-RAM, so seeding is also called from main.py on startup.
"""

import asyncio
import logging
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── 15 curated pairs ──────────────────────────────────────────────────────────
# Covers every required category:
#   patient queries, doctor queries, appointment queries,
#   financial queries, time-based queries

SEED_EXAMPLES: list[dict[str, Any]] = [
    # ── Patient queries ─────────────────────────────────────────────
    {
        "question": "How many patients do we have?",
        "sql": "SELECT COUNT(*) AS total_patients FROM patients",
    },
    {
        "question": "List all patients with their city",
        "sql": (
            "SELECT first_name, last_name, city "
            "FROM patients "
            "ORDER BY last_name"
        ),
    },
    {
        "question": "Which city has the most patients?",
        "sql": (
            "SELECT city, COUNT(*) AS patient_count "
            "FROM patients "
            "GROUP BY city "
            "ORDER BY patient_count DESC "
            "LIMIT 1"
        ),
    },
    {
        "question": "List patients who visited more than 3 times",
        "sql": (
            "SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count "
            "FROM patients p "
            "JOIN appointments a ON a.patient_id = p.id "
            "GROUP BY p.id "
            "HAVING COUNT(a.id) > 3 "
            "ORDER BY visit_count DESC"
        ),
    },
    {
        "question": "Show patient registration trend by month",
        "sql": (
            "SELECT strftime('%Y-%m', registered_date) AS month, "
            "COUNT(*) AS new_patients "
            "FROM patients "
            "GROUP BY month "
            "ORDER BY month"
        ),
    },
    # ── Doctor queries ───────────────────────────────────────────────
    {
        "question": "List all doctors and their specializations",
        "sql": (
            "SELECT name, specialization, department "
            "FROM doctors "
            "ORDER BY specialization, name"
        ),
    },
    {
        "question": "Which doctor has the most appointments?",
        "sql": (
            "SELECT d.name, d.specialization, COUNT(a.id) AS appointment_count "
            "FROM doctors d "
            "JOIN appointments a ON a.doctor_id = d.id "
            "GROUP BY d.id "
            "ORDER BY appointment_count DESC "
            "LIMIT 1"
        ),
    },
    # ── Appointment queries ──────────────────────────────────────────
    {
        "question": "Show me appointments for last month",
        "sql": (
            "SELECT a.id, p.first_name, p.last_name, d.name AS doctor, "
            "a.appointment_date, a.status "
            "FROM appointments a "
            "JOIN patients p ON p.id = a.patient_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "WHERE strftime('%Y-%m', a.appointment_date) = "
            "strftime('%Y-%m', date('now', '-1 month')) "
            "ORDER BY a.appointment_date"
        ),
    },
    {
        "question": "How many cancelled appointments last quarter?",
        "sql": (
            "SELECT COUNT(*) AS cancelled_count "
            "FROM appointments "
            "WHERE status = 'Cancelled' "
            "AND appointment_date >= date('now', '-3 months')"
        ),
    },
    {
        "question": "Show monthly appointment count for the past 6 months",
        "sql": (
            "SELECT strftime('%Y-%m', appointment_date) AS month, "
            "COUNT(*) AS appointment_count "
            "FROM appointments "
            "WHERE appointment_date >= date('now', '-6 months') "
            "GROUP BY month "
            "ORDER BY month"
        ),
    },
    # ── Financial queries ────────────────────────────────────────────
    {
        "question": "What is the total revenue?",
        "sql": (
            "SELECT ROUND(SUM(cost), 2) AS total_revenue "
            "FROM treatments"
        ),
    },
    {
        "question": "Show revenue by doctor",
        "sql": (
            "SELECT d.name, d.specialization, "
            "ROUND(SUM(t.cost), 2) AS total_revenue, "
            "COUNT(t.id) AS treatments_performed "
            "FROM treatments t "
            "JOIN appointments a ON a.id = t.appointment_id "
            "JOIN doctors d ON d.id = a.doctor_id "
            "GROUP BY d.id "
            "ORDER BY total_revenue DESC"
        ),
    },
    {
        "question": "Show unpaid invoices",
        "sql": (
            "SELECT i.id, p.first_name, p.last_name, "
            "i.invoice_date, i.total_amount, i.paid_amount, i.status "
            "FROM invoices i "
            "JOIN patients p ON p.id = i.patient_id "
            "WHERE i.status IN ('Pending', 'Overdue') "
            "ORDER BY i.status, i.invoice_date"
        ),
    },
    {
        "question": "Top 5 patients by spending",
        "sql": (
            "SELECT p.first_name, p.last_name, "
            "ROUND(SUM(i.total_amount), 2) AS total_spending "
            "FROM invoices i "
            "JOIN patients p ON p.id = i.patient_id "
            "GROUP BY p.id "
            "ORDER BY total_spending DESC "
            "LIMIT 5"
        ),
    },
    # ── Time-based query ─────────────────────────────────────────────
    {
        "question": "Revenue trend by month",
        "sql": (
            "SELECT strftime('%Y-%m', a.appointment_date) AS month, "
            "ROUND(SUM(t.cost), 2) AS monthly_revenue "
            "FROM treatments t "
            "JOIN appointments a ON a.id = t.appointment_id "
            "GROUP BY month "
            "ORDER BY month"
        ),
    },
]


# ── Seeding logic ─────────────────────────────────────────────────────────────

async def _seed_async(memory, force: bool = False) -> int:
    """
    Populate memory with SEED_EXAMPLES.
    Returns number of examples actually stored.
    """
    from vanna.core.tool import ToolContext
    from vanna import User

    ctx = ToolContext(
        user=User(id="seed-script", username="seeder", permissions=["admin"]),
        conversation_id="seed",
        request_id="seed",
        agent_memory=memory,
    )

    # If not forcing, skip if memory already has items
    if not force:
        existing = await memory.get_recent_memories(ctx, limit=1)
        if existing:
            logger.info("Memory already seeded (%d+ items). Skipping.", len(SEED_EXAMPLES))
            return 0

    stored = 0
    for pair in SEED_EXAMPLES:
        await memory.save_tool_usage(
            question=pair["question"],
            tool_name="run_sql",
            args={"sql": pair["sql"]},
            context=ctx,
            success=True,
        )
        stored += 1

    logger.info("Seeded %d question-SQL pairs into agent memory.", stored)
    return stored


def seed_agent_memory(memory, force: bool = False) -> int:
    """
    Synchronous wrapper — safe to call from both CLI and FastAPI startup.
    Returns number of examples stored.
    """
    return asyncio.run(_seed_async(memory, force=force))


# ── CLI entry-point ───────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    from vanna_setup import build_agent

    _, memory = build_agent()
    count = seed_agent_memory(memory, force=True)
    print(f"Seeded {count} examples into agent memory.")
    print("Note: DemoAgentMemory is in-RAM. The API server re-seeds automatically on startup.")


if __name__ == "__main__":
    main()
