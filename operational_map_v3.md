# 🗺️ Antigravity V3.0 — The Operational Map (System Blueprint)

Welcome to the definitive source of truth for **Antigravity V3.0**. This document maps out the system's inner workings, data flows, and the "Logic" powering our automated, highly parallelized, and fault-tolerant AI auditing pipeline.

> [!NOTE]
> This map is designed as a deep-dive reference for human architects. It moves from the high-level orchestration down to the low-level synchronization mechanics to ensure systemic transparency.

---

## 1. ⚙️ The Parallel Orchestrator (The 4-Thread Engine)

In V3.0, generating a report is no longer a slow, linear process. We now employ a **4-Thread `ThreadPoolExecutor`** that fires requests to out-of-network LLMs simultaneously. Different sections of the audit require varying cognitive capabilities, so we partition the prompt logic across four localized endpoints.

### Model Assignment & Rationale
1. **Thread 1: The Executive Summary (`summary`)**
   - **Model:** `llama-3.3-70b-versatile` (Groq Engine)
   - **Rationale:** Writing a cohesive, professional Arabic prose paragraph requires immense syntheses logic and contextual depth. The 70B model handles this heavyweight NLP task effortlessly.
2. **Thread 2: Task Evaluation (`tasks`)**
   - **Model:** `llama-3.1-8b-instant` (Groq Engine)
   - **Rationale:** The evaluation requires strictly structured `JSON` generation, analyzing each task individually. The 8B model is lightning fast, highly capable of structured generation, and frees up our API limits from bloated parameter loads.
3. **Thread 3: The Plan Audit (`audit`)**
   - **Model:** `gemini-2.5-flash` (Gemini Engine)
   - **Rationale:** This thread cross-references the actual accomplishment data with the original PDF plan text. Gemini's massive context window and native document handling makes it perfect for comparing "Plan vs. Actuals".
4. **Thread 4: Challenges & Bottlenecks (`challenges`)**
   - **Model:** `gemma-4-27b-it` (Gemini Engine via Gemma)
   - **Rationale:** Gemma 4 acts as an independent analyzer dedicated to unifying administrative challenges, classifying priority levels, and integrating "Additional Notes" into actionable insights.

> [!TIP]
> **Why Parallelize?** By routing specific sections to perfectly sized models asynchronously, generation time drops from roughly ~20 seconds per office to barely ~4 seconds, multiplying throughput linearly.

---

## 2. 🦺 The Failover Logic (The Life Jacket)

API limits (Error 429) and network unavailabilities (Error 503) are inevitable in batch-processing. Antigravity V3 employs a dynamic, self-healing **"Failover Life Jacket"** mechanism.

### The Groq Key Rotation
When querying the Groq models (`summary` and `tasks`):
- Instead of using a single API key, `config.py` loads an array: `GROQ_API_KEYS`.
- If Thread 1 or 2 receives a `429 Rate Limit` from Groq, it **immediately** locks the thread, increments the index to the next API key (`_rotate_key()`), and reconstructs the client inline.
- **The Magic:** We *do not waste* a retry attempt. `attempt -= 1` ensures the engine reruns instantly on the fresh key without artificial pauses.
- If *all* keys exhaust, the system enforces a strict `Exponential Backoff` (e.g., 15s → 30s → 60s) before resetting the loop to Key 1.

### The Gemma 4 / Groq Fallback
When querying Google Gemini (`audit` and `challenges`):
- The Gemini Threads use standard exponential backoff for 429 errors.
- **The Ultimate Fallback:** If Gemini fails absolutely (e.g., Google servers are down, quota exceeded completely after 3 backoffs, or no API key is provided), the thread performs a cross-provider fallback. It instantly reroutes the Prompt natively to the `GROQ_MODEL_FALLBACK` (Llama 8B) to ensure the system never crashes mid-report.

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

1. **Extraction:** `main.py` hits the Google Sheets API via token credentials. We read up to maximum 117 columns containing Office ID, PDF URL, and up to 11 dynamic tasks.
2. **Parsing:** `data_parser.py` slices the row into 10-column chunks, cleaning raw text and standardizing it into an `OfficeData` dictionary.
3. **Orchestration:** `ai_engine.py` generates the Prompts and fires them simultaneously into the `ThreadPoolExecutor`.
4. **LLM Execution:** Threads hit Groq/Gemini APIs asynchronously. Life jacket mechanics handle any immediate 429 throttling.
5. **Report Assembly:** `report_generator.py` ingests the resolved futures. It builds the Word Document headers, loops through the mapped tasks, and prints the AI insight paragraphs smoothly aligned using RTL styling.
6. **Upload:** A local Word Document is dumped into `/reports`. The Drive API authenticates, seeks the proper month folder inside `نظام_المتابعة_الدورية`, and streams the Document payload into Google Drive.

---

## 5. 🗂️ Configuration Management

The system adheres to strict modularity. Here's what manages what:

- **`config.py` (The Heart):** A single source of truth for variables. Holds OAuth Scopes, Column Index IDs (so we never hardcode `[114]` elsewhere), Model endpoints, API Keys (loaded natively via `.env`), and Folder IDs. 
- **`data_parser.py` (The Funnel):** Contains the static logic mapping Sheet array positions -> clean Python Dictionaries. It calculates sub-statistics required for prompts.
- **`ai_engine.py` (The Brains):** Houses the `ParallelOrchestrator`, the strict AI Personas (`_SYSTEM_INSTRUCTION` or `_SECTION_INSTRUCTIONS`), prompt structures, backoff loops, and Key Rotation locking classes.
- **`report_generator.py` (The Muscles):** Deals exclusively with Microsoft `.docx` logic. Handles the 5-Tier Dictionary matching, font-sizing, borders, Right-To-Left alignments, and color codes (RGB).
- **`main.py` (The Conductor):** Sets up the CLI progress bar, iterates sequentially across the `rows` fetched from Google Sheets, controls inter-row mandatory waits (10s throttle), and initiates the Google Drive Upload payload for the finalized reports.
