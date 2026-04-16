# NL2SQL Clinic Assistant

An AI-powered Natural Language to SQL system built with **Vanna 2.0**, **FastAPI**, **SQLite**, and **Groq**.  
Ask plain-English questions about a simulated clinic database and receive SQL queries, tabular results, and optional Plotly charts.

---

## LLM Provider

**Groq** — using the OpenAI-compatible API endpoint (`https://api.groq.com/openai/v1`).  
Default model: `llama-3.3-70b-versatile` (configurable via `GROQ_MODEL`).  
Get a free API key at https://console.groq.com.

---

## Quick Start

### 1. Clone / unzip the project

```bash
cd nl2sql_project
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY
```

`.env` contents:

```
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile   # optional — this is the default
DATABASE_PATH=clinic.db               # optional — this is the default
```

### 4. Create the database

```bash
python setup_database.py
```

Expected output:
```
Created 200 patients, 15 doctors, 500 appointments, 292 treatments, 300 invoices in 'clinic.db'
```

### 5. (Optional) Pre-seed agent memory from CLI

```bash
python seed_memory.py
```

> The API server also seeds memory automatically on startup, so this step is optional.

### 6. Start the API server

```bash
uvicorn main:app --port 8000
```

Or the one-liner that does everything:

```bash
pip install -r requirements.txt && python setup_database.py && python seed_memory.py && uvicorn main:app --port 8000
```

---

## API Documentation

Interactive docs available at http://localhost:8000/docs once the server is running.

### `POST /chat`

Ask a natural-language question about the clinic data.

**Request:**

```json
{
  "question": "Show revenue by doctor"
}
```

**Success response:**

```json
{
  "message": "Here is the revenue breakdown by doctor...",
  "sql_query": "SELECT d.name, ROUND(SUM(t.cost), 2) AS total_revenue ...",
  "columns": ["name", "specialization", "total_revenue"],
  "rows": [["Dr. Robert Patel", "Cardiology", 85234.10], ...],
  "row_count": 15,
  "chart": { "data": [...], "layout": {...} },
  "chart_type": "bar"
}
```

Chart fields are `null` when not applicable.

**Error response:**

```json
{
  "message": "Question must not be empty.",
  "error_code": "VALIDATION_ERROR"
}
```

| HTTP Code | `error_code`       | Cause                                 |
|-----------|-------------------|---------------------------------------|
| 422       | (Pydantic default) | Empty or overlong question (>500 chars)|
| 400       | `SQL_BLOCKED`      | Agent tried to run unsafe SQL         |
| 500       | `AGENT_ERROR`      | LLM or tool execution failure         |
| 503       | —                  | Agent not yet initialised             |

### `GET /health`

```json
{
  "status": "ok",
  "database": "connected",
  "agent_memory_items": 15
}
```

---

## Example `curl` Requests

```bash
# Health check
curl http://localhost:8000/health

# Count patients
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}'

# Top spenders
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Top 5 patients by spending"}'

# Revenue trend
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Revenue trend by month"}'
```

---

## Database Schema

```
patients     — 200 rows  — id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date
doctors      — 15 rows   — id, name, specialization, department, phone
appointments — 500 rows  — id, patient_id→patients, doctor_id→doctors, appointment_date, status, notes
treatments   — 292 rows  — id, appointment_id→appointments, treatment_name, cost, duration_minutes
invoices     — 300 rows  — id, patient_id→patients, invoice_date, total_amount, paid_amount, status
```

- **15 doctors** across 5 specializations: Dermatology, Cardiology, Orthopedics, General, Pediatrics  
- **200 patients** across 10 Indian cities  
- **500 appointments** spanning the last 12 months with skewed doctor/patient loads  
- **292 treatments** linked only to Completed appointments, costs $50–$5,000  
- **300 invoices** with Paid / Pending / Overdue statuses

---

## Project Structure

```
nl2sql_project/
├── setup_database.py   # Creates clinic.db and seeds all tables
├── seed_memory.py      # Seeds 15 Q-SQL pairs into agent memory
├── vanna_setup.py      # Vanna 2.0 Agent factory (LLM, tools, memory)
├── main.py             # FastAPI app — /chat and /health endpoints
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── RESULTS.md          # Test results for all 20 required questions
```

---

## Architecture

```
User question
     │
     ▼
FastAPI /chat
     │  Pydantic input validation
     ▼
Vanna Agent (Agent.send_message)
     │
     ├─► SearchSavedCorrectToolUsesTool   ← retrieves similar past Q→SQL from DemoAgentMemory
     │         (Groq LLM decides to call this first)
     │
     ├─► ValidatedRunSqlTool              ← SQL safety guard → SqliteRunner → clinic.db
     │         returns DataFrameComponent (rows + columns)
     │
     └─► VisualizeDataTool (optional)     ← reads CSV output → Plotly chart → ChartComponent
               (only called for trend/comparison questions)

UiComponent stream → parsed → ChatResponse JSON
```

**Key design decisions:**

- **Custom `/chat` endpoint** instead of `VannaFastAPIServer` so the response shape exactly matches the assignment spec.
- **Revenue = `SUM(treatments.cost)`** for doctor/department queries, because `invoices` has no `doctor_id` or `appointment_id` foreign key in the provided schema.
- **DemoAgentMemory** is in-RAM as required by the assignment; the API re-seeds it on every startup so memory is always populated.
- **SQL validation** happens inside `ValidatedRunSqlTool.execute()` before any DB call — blocked queries return a `ToolResult` with `success=False`, which the LLM sees and reports back without executing anything.

---

## Bonus Features Implemented

| Feature | Details |
|---|---|
| ✅ Input validation | Pydantic `field_validator` — rejects empty questions and questions > 500 chars |
| ✅ Structured logging | JSON-formatted log lines for every request, response, and agent step |
| ✅ Chart generation | Plotly charts returned for trend/comparison questions via `VisualizeDataTool` |

---

## Known Limitations

- **DemoAgentMemory** is purely in-RAM. Restarting the server loses memory; the lifespan hook re-seeds it automatically from `SEED_EXAMPLES`.
- Chart generation requires the LLM to voluntarily call `VisualizeDataTool`. For guaranteed charts, a post-processing step could be added.
- Rate limiting is not implemented (out of scope for this assignment).
