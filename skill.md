# Antigravity V3.2 — System Skill Map & Development Contract
# Last Updated: 2026-06-15 | Version: 3.2

---

## 1. Current Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| AI Engine | Gemini API (gemini-3.5-flash, gemini-3.1-flash-lite) |
| Data Source | Google Sheets API (gspread) |
| File Storage | Google Drive API (OAuth2) |
| PDF Extraction | pdfplumber |
| Output Format | Word Documents (.docx) via python-docx |
| Config | .env + config.py |

---

## 2. Core Capabilities (V3.2)

### 2.1 Parallel Orchestrator (4-Thread Engine)
- The system fires **4 independent threads simultaneously** per office row using `ThreadPoolExecutor(max_workers=4)`.
- Each thread owns exactly ONE section, all using the same Gemini model with section-specific system instructions:

| Thread | Section | Model | Max Tokens | Provider |
|--------|---------|-------|------------|----------|
| 1 | `summary` | gemini-3.5-flash | 4,096 | Gemini |
| 2 | `tasks` | gemini-3.5-flash | 8,192 | Gemini |
| 3 | `audit` | gemini-3.5-flash | 4,096 | Gemini |
| 4 | `challenges` | gemini-3.5-flash | 4,096 | Gemini |

- **DO NOT** merge threads or run sections sequentially unless explicitly requested.
- **DO NOT** change model assignments without updating `config.py` first.

### 2.2 Three-Tier Failover (Gemini-Only)
The failover chain for ALL threads:
```
Default Model (gemini-3.5-flash)
  → Success: return result
  → 429/503/ResourceExhausted: Switch to Fallback Model
  → Other errors (400/401/403): BREAK immediately → raise exception

Fallback Model (gemini-3.1-flash-lite)
  → Success: return result
  → 429/503 (repeated): Wait 30 seconds → retry infinitely
  → Other errors: BREAK immediately → raise exception
```
- **INVARIANT:** `on_progress(section, bool(val.strip()))` — progress marker is `True` only when content is non-empty.
- The fallback logic is implemented in `call_gemini_with_fallback()` in `ai_engine.py`.

### 2.3 5-Tier Task Mapping Sync (The Dictionary)
`report_generator._extract_task_insights()` matches AI output to Sheet tasks via:

| Tier | Match Method |
|------|-------------|
| 1 | Exact `task_id` numeric string (`"1"`, `"2"`) |
| 2 | Arabic ordinal translation (`"الأول"` → `"1"`) |
| 3 | Exact `original_name` (lowercased) |
| 4 | Normalized name (diacritics + whitespace stripped) |
| 5 | Substring fuzzy match (task name inside AI name or vice-versa) |

- **INVARIANT:** The index structure is always `{"by_id": {}, "by_id_arabic": {}, "by_name": {}, "by_norm": {}}`. Any change to this dict shape breaks `_add_tasks_section`.
- **JSON Repair:** If AI returns truncated JSON, `rfind("}")` salvages all complete objects.

### 2.4 Cooldown & Rate Management
- Inter-row wait: `time.sleep(10)` after each office row — printed as countdown.
- Fallback retry wait: 30 seconds between infinite retry attempts on fallback model.
- Google Sheets: 3 retries (5s → 10s → 20s) on 500/503 before raising.

### 2.5 Input Sanitization
- `sanitize(text)` strips control chars, UTF-16 surrogates, and private-use Unicode before sending to Gemini.
- Applied to both `system_instruction` and `user_prompt` in `call_gemini_with_fallback()`.

### 2.6 Data Integrity Rules
- `plan_text[:6000]` — hard cap on PDF content sent to prompts. Never remove.
- `general_challenges` and `additional_notes` are injected **explicitly** at the end of every section prompt. Never omit.
- Gemini `max_output_tokens`: tasks → 8192, all others → 4096.

---

## 3. Logic Flow (V3.2)

```
main.py
  │
  ├─► sheet_reader.py    → Fetch rows (with 503 retry)
  ├─► data_parser.py     → Parse 117-column row → OfficeData dict
  ├─► pdf_handler.py     → Download + extract plan PDF text
  │
  ├─► ai_engine.py       → ParallelOrchestrator.analyze()
  │     ├─ Thread 1: _run_section("summary")    → Gemini 3.5 Flash
  │     ├─ Thread 2: _run_section("tasks")      → Gemini 3.5 Flash
  │     ├─ Thread 3: _run_section("audit")      → Gemini 3.5 Flash
  │     └─ Thread 4: _run_section("challenges") → Gemini 3.5 Flash
  │          └─► 3-Tier Fallback if any thread fails
  │
  ├─► report_generator.py → Build .docx (RTL Arabic) + PDF conversion
  │     └─► _extract_task_insights() → 5-tier mapping
  │
  └─► drive_uploader.py  → Upload to Drive (auto-create year/month folders)
```

---

## 4. File Responsibility Map

| File | Owns | Must NOT Touch |
|------|------|---------------|
| `config.py` | All constants, model names, API keys | Business logic |
| `data_parser.py` | Column index → OfficeData mapping | AI calls, report building |
| `ai_engine.py` | LLM calls, failover, orchestration | `.docx` structure, Drive |
| `report_generator.py` | Word doc layout, task mapping | LLM model selection |
| `sheet_reader.py` | Google Sheets connection + retry | AI or file logic |
| `drive_uploader.py` | Google Drive upload/folder creation | Report content |
| `pdf_handler.py` | PDF download + text extraction | AI or report logic |
| `main.py` | Pipeline loop, progress display | Internal section logic |

---

## 5. ⚠️ THE SURGEON RULE — Development Constraints

> **This is the binding development contract for all future code edits.**

### Rule 1 — Scalpel, Not Axe
When modifying code, edit **only the targeted function or block**.
DO NOT alter stable logic in other sections (Orchestrator, Failover, or Mapping)
unless they are **explicitly named** in the user's request.

### Rule 2 — Modularity Guard
Changes to `report_generator.py` must preserve:
- The exact dict shape: `{"by_id", "by_id_arabic", "by_name", "by_norm"}`
- The `_extract_task_insights(ai_text: str) -> dict` signature
- The `_add_tasks_section(doc, office_data, ai_analysis)` interface

Changes to `ai_engine.py` must preserve:
- `analyze(office_data, plan_text, on_progress) -> dict[str, str]`
- The 4-key output: `{"summary", "tasks", "audit", "challenges"}`
- The `call_gemini_with_fallback()` section-awareness

### Rule 3 — Pre-Edit Checklist
Before ANY code modification, verify:
- [ ] Is the target function isolated from Orchestrator / Failover / Mapping?
- [ ] Will this change alter any function signature used by another file?
- [ ] Does this change affect `config.py` constants? (update them in sync)
- [ ] Is the `on_progress` True/False logic preserved?

### Rule 4 — Regression Tests (Mental Model)
After any edit, confirm these invariants hold:
1. `orchestrator.analyze()` still returns `{"summary": str, "tasks": str, "audit": str, "challenges": str}`
2. `_extract_task_insights()` still returns the 4-key dict
3. `GEMINI_MODEL_FALLBACK` is never empty string
4. `max_output_tokens` for tasks section is always ≥ 4096

### Rule 5 — Configuration Sync
If a model name or key is changed:
- Update `config.py` FIRST
- Then update any reference in `ai_engine.py`
- Never hardcode model names inside functions — always reference `cfg.*`

---

## 6. Operational Boundaries

- **DO:** Read audit data from Google Sheets.
- **DO:** Download and parse PDF plans from Drive.
- **DO:** Compare Sheet execution vs PDF plans via AI.
- **DO:** Generate Word reports and re-upload to Drive.
- **DO:** Derive report month from Sheet data, not system clock.
- **DO NOT:** Modify or write back to source Google Sheets.
- **DO NOT:** Process non-PDF plan formats (no image/Word plan support yet).
- **DO NOT:** Proceed if core env vars or credentials are missing.
- **DO NOT:** Hardcode API keys anywhere — always load from `.env`.
- **DO NOT:** Remove the `plan_text[:6000]` cap or the explicit `general_challenges` injection.

---

## 7. Expansion Slots

- `[SLOT: ALTERNATIVE_PLAN_FORMATS]` Handler for image/Word-based plans.
- `[SLOT: REPORT_DISTRIBUTION]` Automated email or Slack delivery.
- `[SLOT: BATCH_RETRY]` Persistent queue for failed Drive uploads.
- `[SLOT: WEBHOOK_NOTIFY]` POST to endpoint when a report is generated.
- `[SLOT: ADDITIONAL_GEMINI_MODEL]` Add more Gemini model tiers for granular fallback.

---

## 8. Anti-Hallucination Rules

- **Typing:** Strict Python type hints mandatory on all new functions.
- **Fallbacks:** If PDF fails → log + proceed without plan. Never crash.
- **Credentials:** No hardcoded keys. Validate at startup.
- **Errors:** All failures surface via clear console logs. No silent exceptions.
- **Month:** Always derive from Sheet column, never `datetime.now()`.
- **JSON:** Never trust raw AI output — always parse through `_extract_task_insights()`.
- **Progress:** `on_progress(section, True)` only when `val.strip()` is non-empty.
