# 🗺️ Antigravity V3.2 — The Operational Map (System Blueprint)

Welcome to the definitive source of truth for **Antigravity V3.2**. This document maps out the system's inner workings, data flows, and the "Logic" powering our automated, highly parallelized, and fault-tolerant AI auditing pipeline.

> [!NOTE]
> This map is designed as a deep-dive reference for human architects. It moves from the high-level orchestration down to the low-level synchronization mechanics to ensure systemic transparency.

---

## 1. ⚙️ The Parallel Orchestrator (The 4-Thread Engine)

In V3.2, generating a report is a fast, parallel process. We employ a **4-Thread `ThreadPoolExecutor`** that fires requests to Google Gemini simultaneously. Each thread handles one section of the audit with a specialized system instruction prompt.

### Model Assignment & Rationale
All four threads use the same model — **`gemini-3.5-flash`** — with section-specific system instructions (`_SECTION_INSTRUCTIONS` dict in `ai_engine.py`):

1. **Thread 1: The Executive Summary (`summary`)**
   - **Model:** `gemini-3.5-flash` (Default) / `gemini-3.1-flash-lite` (Fallback)
   - **Max Tokens:** 4,096
   - **Rationale:** Writing a cohesive, professional Arabic prose paragraph requires deep synthesis logic. The system instruction enforces formal administrative Arabic style with no Markdown formatting.

2. **Thread 2: Task Evaluation (`tasks`)**
   - **Model:** `gemini-3.5-flash` (Default) / `gemini-3.1-flash-lite` (Fallback)
   - **Max Tokens:** 8,192 (higher limit to accommodate JSON for all tasks)
   - **Rationale:** Produces a structured JSON array analyzing each task. Higher token limit ensures the complete array is generated even for offices with 11 tasks.

3. **Thread 3: The Plan Audit (`audit`)**
   - **Model:** `gemini-3.5-flash` (Default) / `gemini-3.1-flash-lite` (Fallback)
   - **Max Tokens:** 4,096
   - **Rationale:** Cross-references actual accomplishment data with the original PDF plan text (`plan_text[:6000]`). Gemini's large context window handles the plan-vs-actuals comparison effectively.

4. **Thread 4: Challenges & Bottlenecks (`challenges`)**
   - **Model:** `gemini-3.5-flash` (Default) / `gemini-3.1-flash-lite` (Fallback)
   - **Max Tokens:** 4,096
   - **Rationale:** Dedicated analyzer for unifying administrative challenges, classifying priorities (high/medium/low), and integrating general challenges + additional notes into actionable insights.

> [!TIP]
> **Why Parallelize?** By routing specific sections to separate threads asynchronously with dedicated system prompts, generation time drops significantly compared to sequential processing, multiplying throughput linearly.

---

## 2. 🦺 The Failover Logic (The Three-Tier Life Jacket)

API limits (Error 429) and network unavailabilities (Error 503) are inevitable in batch-processing. Antigravity V3.2 employs a dynamic, self-healing **Three-Tier Failover** mechanism.

### How It Works (All Threads — Uniform Logic)
Every thread uses the same fallback chain, implemented in `call_gemini_with_fallback()`:

```
┌─────────────────────────────────────────────────┐
│  Tier 1: Default Model (gemini-3.5-flash)       │
│  → Success → Return result immediately          │
│  → 429/503/ResourceExhausted → Go to Tier 2     │
│  → 400/401/403 (permanent) → Raise exception    │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────▼───────────────────────┐
│  Tier 2: Fallback Model (gemini-3.1-flash-lite) │
│  → Success → Return result immediately          │
│  → 429/503 (repeated) → Go to Tier 3            │
│  → Other errors → Raise exception               │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────▼───────────────────────┐
│  Tier 3: Infinite Retry Loop                    │
│  → Wait 30 seconds                              │
│  → Retry Fallback Model                         │
│  → Success → Return result                      │
│  → 429 again → Wait 30 more seconds → Retry     │
│  (Loops until success or non-transient error)    │
└─────────────────────────────────────────────────┘
```

### Input Sanitization
Before every API call, `sanitize(text)` cleans the input:
- Strips control characters (`0x00-0x08`, `0x0b`, `0x0c`, `0x0e-0x1f`, `0x7f`)
- Removes UTF-16 surrogate pairs (`0xD800-0xDFFF`)
- Removes private-use Unicode characters (`0xE000-0xF8FF`)

---

## 3. 🧩 The Data Synchronization (The Dictionary Mapping)

Because four separate threads return four fragmented textual outputs concurrently in random timing order, `report_generator.py` must marry the AI output securely to the exact row data before creating the Microsoft Word Document.

### How do we map unstructured JSON answers to structured Task Rows?
The AI evaluator in Thread 2 returns `[{"task_id": "1", "ai_insight": "..."}]`. However, AI hallucinations or formatting glitches can mutate the `task_id`. 
We solve this using a resilient **5-Tier Dictionary Mapping** extraction method:

1. **Numeric ID Mapping:** Tries an exact string match of the numeric ID (e.g., `"1"`).
2. **Arabic Ordinal Translation:** If the AI outputs `"الأول"` or `"مهمة 1"`, we use a translation matrix (`_ARABIC_ORDINALS`) to resolve it to `"1"`.
3. **Exact Name Match:** If the IDs fail entirely, it checks the `original_name` against the Sheets task title.
4. **Normalized Name Match:** Strips away Diacritics (تشكيل) and invisible padding for a clean string equality check.
5. **Substring Fuzzy Search:** Determines if the Sheet's task name exists *inside* the AI's provided task name or vice-versa.

> [!IMPORTANT]
> If a match fails across all 5 tiers, the system injects a `MISS` log into the CLI, leaving the insight blank in the final document rather than printing malformed code or crashing the pipeline.

---

## 4. 🔄 The Lifecycle of a Report
Mapping a single row from birth to Drive storage:

1. **Extraction:** `main.py` hits the Google Sheets API via service account credentials. We read up to maximum 117 columns containing Office ID, PDF URL, and up to 11 dynamic tasks.
2. **Parsing:** `data_parser.py` slices the row into 10-column chunks, cleaning raw text and standardizing it into an `OfficeData` dictionary.
3. **PDF Download:** `pdf_handler.py` downloads the monthly plan PDF from Google Drive directly to memory, then extracts text via `pdfplumber`. If this fails, the pipeline continues gracefully without plan comparison.
4. **Orchestration:** `ai_engine.py` generates section-specific prompts and fires them simultaneously via `ThreadPoolExecutor(max_workers=4)`.
5. **LLM Execution:** All four threads hit the Gemini API asynchronously. Three-tier fallback mechanics handle any 429 throttling automatically.
6. **Report Assembly:** `report_generator.py` ingests the resolved futures. It builds the Word Document with a cover page, 5 sections (Executive Summary, Task Details, Challenges, Plan Audit, Office Message), and proper RTL Arabic formatting.
7. **PDF Conversion:** `report_generator.py` attempts to convert the `.docx` to `.pdf` via LibreOffice headless mode. Failure is non-critical.
8. **Upload:** The Word and PDF files are uploaded to Google Drive via OAuth2 credentials into a hierarchical folder structure: `Root → Year → System → Office → Month`. Task attachments are copied directly on Drive without local download.

---

## 5. 🗂️ Configuration Management

The system adheres to strict modularity. Here's what manages what:

- **`config.py` (The Heart):** A single source of truth for variables. Holds OAuth Scopes, Column Index IDs (so we never hardcode `[114]` elsewhere), Gemini model names (`GEMINI_MODEL_DEFAULT`, `GEMINI_MODEL_FALLBACK`), API Keys (loaded natively via `.env`), and Drive Folder IDs.
- **`data_parser.py` (The Funnel):** Contains the static logic mapping Sheet array positions -> clean Python Dictionaries. It calculates sub-statistics required for prompts.
- **`ai_engine.py` (The Brains):** Houses the `ParallelOrchestrator`, the strict AI Personas (`_SYSTEM_INSTRUCTION` and `_SECTION_INSTRUCTIONS`), prompt structures, and the `call_gemini_with_fallback()` three-tier failover function.
- **`report_generator.py` (The Muscles):** Deals exclusively with Microsoft `.docx` logic. Handles the 5-Tier Dictionary matching, font-sizing, borders, Right-To-Left alignments, and color codes (institutional green `#1F4A37`, gold `#DDB557`).
- **`pdf_handler.py` (The Reader):** Handles PDF download from Google Drive and text extraction via `pdfplumber`. Designed to never raise exceptions — always returns `(text, status)` gracefully.
- **`drive_uploader.py` (The Uploader):** Manages Google Drive upload using OAuth2 user credentials (not service account) to bypass quota limits. Creates hierarchical folder structure and copies task attachments directly on Drive.
- **`main.py` (The Conductor):** Sets up the CLI progress bar, iterates sequentially across the `rows` fetched from Google Sheets, controls inter-row mandatory waits (10s throttle), and initiates the Google Drive Upload payload for the finalized reports.
