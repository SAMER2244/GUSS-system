<div align="center">

<img src="assets/union_logo.png" alt="GUSS Logo" width="120" />

# GUSS Periodic Monitoring System
### *Automated AI-Powered Report Pipeline for the General Union of Syrian Students*

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat&logo=supabase&logoColor=white)](https://supabase.com)
[![Gemini](https://img.shields.io/badge/Gemini-3.5_Flash-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## 📖 What Is This?

**GUSS Periodic Monitoring System** is a full-stack, AI-powered document processing pipeline designed for the internal operational offices of the [General Union of Syrian Students (GUSS)](https://guss.sy).

Each month, every executive office within the union is required to submit a structured activity report. Before this system existed, this was a manual process — collecting Word documents, chasing follow-ups, and writing summaries by hand.

**This system changes that entirely.** Office representatives fill in a guided multi-step web form. The moment they submit, the system automatically:

1. Stores the structured data in a relational database.
2. Downloads and parses the office's monthly plan PDF from secure cloud storage.
3. Fires **4 parallel Gemini AI threads** simultaneously to produce a 5-section strategic audit report.
4. Assembles a fully-formatted, RTL Arabic `.docx` report (+ PDF mirror).
5. Uploads the final report to the union's Google Drive under the correct hierarchical folder structure.

The entire process — from form submission to a ready-to-read Word report on Drive — is fully automated.

---

## 👨‍💻 Who Is This For?

This README targets **developers and technical contributors** who want to:
- Self-host the system for their own organization.
- Understand the system architecture for contribution or extension.
- Adapt the pipeline for a similar institutional use-case.

> **Not a developer?** If you're an office representative looking to submit a report, simply visit the hosted web form and follow the on-screen steps — no technical knowledge required.

---

## 🏗️ System Architecture

```
                         ┌─────────────────────────┐
                         │   React 19 Frontend       │
                         │   (Multi-Step Form Wizard)│
                         └────────────┬────────────┘
                                      │ POST /api/submit-report
                                      │ POST /api/upload-plan (PDF)
                         ┌────────────▼────────────┐
                         │   FastAPI Backend         │
                         │   (web_server.py)         │
                         │   JWT Auth + CORS         │
                         └────┬──────────┬──────────┘
                              │          │
              ┌───────────────▼──┐    ┌──▼────────────────────┐
              │  Supabase         │    │  Background Pipeline    │
              │  PostgreSQL       │    │  (per submission)       │
              │  ┌─────────────┐ │    │                         │
              │  │  offices    │ │    │  1. Fetch from DB        │
              │  │  submissions│ │    │  2. Download Plan PDF    │
              │  │  tasks      │ │    │  3. Parse text           │
              │  └─────────────┘ │    │  4. Run AI Orchestrator ─┼──► Gemini API
              │  Storage Bucket  │    │  5. Build .docx          │    (4 Threads)
              │  (monthly-plans) │    │  6. Convert to PDF       │
              └──────────────────┘    │  7. Upload to Drive      │
                                      │  8. Update DB status     │
                                      └─────────────────────────┘
```

---

## 🛠️ Technology Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Web Framework | FastAPI 0.110+ with Uvicorn |
| Language | Python 3.11 |
| Authentication | JWT via `PyJWT` stored in HttpOnly cookies |
| AI Engine | Google Gemini API (`google-genai`) |
| PDF Parsing | `pdfplumber` |
| Report Generation | `python-docx` (RTL Arabic, A4, Cairo font) |
| Google APIs | Drive v3 (OAuth2), Sheets v4 (Service Account) |
| Environment Config | `python-dotenv` + `PyYAML` (`settings.yaml`) |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 19 + Vite 8 |
| State Management | React `useState` (local) |
| Styling | Vanilla CSS with dark/light theme toggle |
| Deployment | Netlify (via `netlify.toml`) |

### Cloud Infrastructure
| Service | Purpose |
|---------|---------|
| Supabase (PostgreSQL) | Primary relational database |
| Supabase Storage | Private bucket for monthly plan PDFs |
| Google Drive | Final report archive (hierarchical folders) |
| Netlify | Frontend static hosting |

---

## 🤖 The AI Audit Engine

The core of this system is a **4-thread parallel orchestration engine** that generates audit reports with zero manual writing.

### How Parallelism Works

When a report submission is processed, `ParallelOrchestrator` in [`ai_engine.py`](ai_engine.py) spawns exactly 4 concurrent worker threads using `ThreadPoolExecutor(max_workers=4)`. Each thread owns one report section and has a specialized system instruction:

| Thread | Section | Model | Max Tokens | Purpose |
|--------|---------|-------|------------|---------|
| 1 | `summary` | `gemini-3.5-flash` | 4,096 | 7+ line executive summary prose |
| 2 | `tasks` | `gemini-3.5-flash` | **8,192** | JSON array with per-task strategic insights |
| 3 | `audit` | `gemini-3.5-flash` | 4,096 | Plan-vs-actuals compliance analysis |
| 4 | `challenges` | `gemini-3.5-flash` | 4,096 | Administrative bottlenecks & priority ranking |

> **Why 8,192 tokens for tasks?** Offices can have up to 11 tasks per month. The higher limit guarantees the JSON array is always closed and complete.

### Three-Tier Failover (Rate Limit Resilience)

All threads share the same fault-tolerance chain, implemented in `call_gemini_with_fallback()`:

```
Tier 1 → gemini-3.5-flash (Default)
   └── 429/503 transient error?
         Tier 2 → gemini-3.1-flash-lite (Fallback)
            └── 429/503 again?
                  Tier 3 → Wait 30s → Retry Tier 2 (loops until success)
                  └── Non-transient error (400/403)? → Raise exception immediately
```

### 5-Tier Task Matching

The AI returns a JSON array referencing tasks by ID or name. Since LLMs occasionally hallucinate IDs, the report generator matches AI insights to actual DB tasks through 5 progressive fallback strategies:

1. **Numeric task_id** — exact string match (`"1"`, `"2"`)
2. **Arabic ordinal** — translates `"الأول"` → `"1"` via a lookup matrix
3. **Exact name match** — case-insensitive
4. **Normalized name** — strips Arabic diacritics (تشكيل) and whitespace
5. **Fuzzy substring** — checks if the DB task name is a substring of the AI-provided name or vice-versa

If all 5 tiers miss, the insight is left blank in the document and a `MISS` warning is logged — the pipeline **never crashes** due to a matching failure.

---

## 🗄️ Database Schema

The database runs on **Supabase (PostgreSQL)**. The schema is defined in [`migrations/001_create_tables.sql`](migrations/001_create_tables.sql).

```
offices
  ├── id          SERIAL PK
  └── name        TEXT UNIQUE NOT NULL          -- e.g. "المكتب الإعلامي"

submissions
  ├── id                SERIAL PK
  ├── office_id         FK → offices(id)
  ├── submitter_name    TEXT NOT NULL
  ├── submitter_phone   TEXT
  ├── month             INTEGER (1–12)
  ├── year              INTEGER
  ├── has_plan          BOOLEAN
  ├── plan_file_path    TEXT                    -- Supabase Storage path
  ├── general_challenges TEXT
  ├── additional_notes  TEXT
  ├── status            TEXT  (pending | processed | failed)
  ├── drive_report_link TEXT                    -- filled after processing
  └── UNIQUE (office_id, month, year)          -- prevents duplicate submissions

tasks
  ├── id                    SERIAL PK
  ├── submission_id         FK → submissions(id) ON DELETE CASCADE
  ├── task_order            INTEGER
  ├── manager_name          TEXT NOT NULL
  ├── manager_phone         TEXT
  ├── task_name             TEXT NOT NULL
  ├── task_description      TEXT
  ├── task_type             TEXT  (ضمن الخطة | خارج الخطة)
  ├── execution_mechanism   TEXT
  ├── task_status           TEXT  (مكتملة | قيد التنفيذ | ملغاة)
  └── issues                TEXT

answers  -- Reserved EAV table for future extensibility (currently empty)
```

**Row Level Security (RLS)** is enabled on all tables:
- Public `INSERT` allowed on `submissions` and `tasks` (the form is unauthenticated).
- `SELECT`/`UPDATE`/`DELETE` require the `service_role` key (backend only).

> **Note on Offices:** The 12 initial offices are seeded in [`migrations/002_seed_offices.sql`](migrations/002_seed_offices.sql). This list may evolve as the organization grows — to add or rename offices, run a direct `INSERT` into the `offices` table in Supabase.

---

## 📁 Project Structure

```
GUSS/
├── frontend/                   # React 19 + Vite form wizard
│   ├── src/
│   │   ├── App.jsx             # Main app with step routing & submission logic
│   │   ├── components/
│   │   │   ├── WelcomeStep.jsx
│   │   │   ├── BasicInfoStep.jsx  # Office selector, month/year, PDF upload
│   │   │   ├── TasksStep.jsx
│   │   │   ├── ClosingStep.jsx
│   │   │   └── SuccessScreen.jsx
│   │   └── index.css
│   └── vite.config.js
│
├── routes/
│   ├── submissions.py          # Public API: submit report, upload PDF, list offices
│   └── dashboard.py           # Admin-only API: CRUD for submissions
│
├── migrations/
│   ├── 001_create_tables.sql   # Full schema with RLS policies
│   ├── 002_seed_offices.sql    # Initial 12 offices
│   ├── 003_storage_bucket.sql  # Supabase Storage bucket (monthly-plans)
│   └── 004_add_drive_link.sql  # Adds drive_report_link column
│
├── ai_engine.py                # ParallelOrchestrator + Gemini failover logic
├── report_generator.py         # .docx builder (RTL Arabic, 5-section layout)
├── pdf_handler.py              # PDF download (Drive or HTTP) + pdfplumber extraction
├── drive_uploader.py           # Google Drive OAuth2 uploader + folder hierarchy
├── supabase_adapter.py         # Converts Supabase rows to legacy pipeline format
├── data_parser.py              # Task statistics + OfficeData type alias
├── web_server.py               # FastAPI app, JWT auth, background pipeline runner
├── database.py                 # Supabase singleton client
├── models.py                   # Pydantic request/response models
├── config.py                   # Central config (loaded from .env + settings.yaml)
├── logger.py                   # Rotating file + console logger
├── exceptions.py               # Custom exception hierarchy
├── retry.py                    # Generic retry decorator
├── settings.yaml               # Runtime-configurable settings (AI models, colors, etc.)
├── environment.yml             # Conda environment definition
├── requirements.txt            # pip dependencies
└── .env.example                # Template for required environment variables
```

---

## ⚙️ Local Setup (Full Guide)

### Prerequisites

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Python 3.11+
- Node.js 18+ and npm
- A [Supabase](https://supabase.com) project (free tier works)
- A Google Cloud project with Drive API and Sheets API enabled
- A [Google AI Studio](https://aistudio.google.com) API key for Gemini
- LibreOffice installed (for PDF conversion) — optional but recommended

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/SAMER2244/GUSS-system.git
cd GUSS-system
```

---

### Step 2 — Set Up the Python Environment

```bash
conda env create -f environment.yml
conda activate ai_env
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

### Step 3 — Configure Environment Variables

Copy the example file and fill in real values:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# ── Gemini API ─────────────────────────────────────────────────
GEMINI_API_KEY=your-gemini-api-key-here

# ── Supabase ───────────────────────────────────────────────────
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here

# ── CORS (frontend URL) ────────────────────────────────────────
# Local dev: http://localhost:5173 | Production: https://your-app.netlify.app
ALLOWED_ORIGIN=http://localhost:5173
```

---

### Step 4 — Set Up Supabase

Run all migration files in order inside the **Supabase SQL Editor**:

```sql
-- 1. Create tables (offices, submissions, tasks, answers) + RLS policies
-- Copy and run: migrations/001_create_tables.sql

-- 2. Seed the initial 12 offices
-- Copy and run: migrations/002_seed_offices.sql

-- 3. Create the private storage bucket for monthly plan PDFs
-- Copy and run: migrations/003_storage_bucket.sql

-- 4. Add the drive_report_link column
-- Copy and run: migrations/004_add_drive_link.sql
```

> **Adding or renaming offices later?**
> ```sql
> INSERT INTO offices (name) VALUES ('اسم المكتب الجديد') ON CONFLICT (name) DO NOTHING;
> ```

---

### Step 5 — Configure Google APIs

#### 5a. Service Account (for Google Drive read access from the PDF handler)

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Credentials**.
2. Create a **Service Account** and download the JSON key.
3. Place the file at the project root as `credentials.json`.
4. Share your Google Drive folder with the service account email.

#### 5b. OAuth2 Desktop Client (for Drive upload)

1. In the same console, create an **OAuth 2.0 Client ID** → **Desktop App**.
2. Download the JSON and save it as `oauth_client.json` at the project root.
3. On first run, the system will open a browser window for authorization. A `token.json` will be saved automatically for future runs.

> **Important:** Both `credentials.json`, `oauth_client.json`, and `token.json` are listed in `.gitignore` and will **never** be committed.

---

### Step 6 — Start the Backend

```bash
python web_server.py
```

The API will be live at: `http://localhost:8000`

Interactive API docs (Swagger UI) available at: `http://localhost:8000/docs`

---

### Step 7 — Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The form wizard will be available at: `http://localhost:5173`

Create a `frontend/.env` (or `frontend/.env.local`) with:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

---

## 🔑 Configuration Reference

All runtime-tunable settings live in `settings.yaml`. Changes take effect on next server start — no code edits needed.

| Setting | Path | Default | Description |
|---------|------|---------|-------------|
| Default AI model | `ai.default_model` | `gemini-3.5-flash` | Primary Gemini model for all threads |
| Fallback AI model | `ai.fallback_model` | `gemini-3.1-flash-lite` | Used when primary hits rate limits |
| Fallback wait | `ai.fallback_wait_seconds` | `30` | Seconds to wait before retrying fallback |
| Task token limit | `ai.max_tokens.tasks` | `8192` | Max output tokens for the tasks thread |
| Plan text cap | `pipeline.plan_text_max_chars` | `6000` | Characters of PDF plan sent to Gemini |
| Inter-row cooldown | `pipeline.cooldown_seconds` | `10` | Seconds between processing jobs |
| Report font | `report.font_family` | `Cairo` | Arabic font used in generated Word docs |
| Institution color | `report.institutional_color` | `#1F4A37` | Primary green used in report styling |
| Drive system folder | `drive.system_folder_name` | `نظام_المتابعة_الدورية` | Root system folder name on Drive |

---

## 🌐 API Endpoints

### Public (No Authentication Required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/offices-list` | Returns all registered offices for the form dropdown |
| `POST` | `/api/upload-plan` | Uploads a monthly plan PDF to Supabase Storage (max 10MB) |
| `POST` | `/api/submit-report` | Submits a full monthly report and triggers background processing |

### Admin (JWT Cookie Required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/login` | Authenticates admin and sets `guss_session` cookie |
| `POST` | `/api/logout` | Clears the session cookie |
| `GET` | `/api/user/me` | Returns current authenticated user |
| `GET` | `/api/submissions` | Lists all submissions with optional filtering (office, month, year, status) |
| `GET` | `/api/submissions/{id}` | Returns full details + tasks for a single submission |
| `PATCH` | `/api/submissions/{id}` | Updates submission fields and/or replaces its task list |
| `DELETE` | `/api/submissions/{id}` | Deletes a submission (CASCADE deletes tasks + removes PDF from Storage) |
| `POST` | `/api/process` | Manually triggers background processing for a submission |
| `GET` | `/api/status` | Returns real-time pipeline status (progress, current stage, results) |
| `POST` | `/api/reset` | Resets pipeline state to idle |
| `GET` | `/api/settings` | Returns current system settings (API keys masked) |
| `POST` | `/api/settings` | Updates system settings live (persisted to `settings.yaml`) |
| `GET` | `/api/reports` | Lists locally generated `.docx` files in the `reports/` directory |
| `GET` | `/api/download/{filename}` | Securely downloads a generated report file |

---

## 🚀 Deployment

### Frontend → Netlify

The repository includes [`netlify.toml`](netlify.toml) — simply connect the repo to Netlify and it will auto-deploy from the `frontend/` directory.

```toml
[build]
  base    = "frontend"
  command = "npm run build"
  publish = "dist"
```

Set the `VITE_API_BASE_URL` environment variable in Netlify to point to your backend URL.

### Backend

The FastAPI backend can be deployed on any Linux server or container:

```bash
pip install -r requirements.txt
uvicorn web_server:app --host 0.0.0.0 --port 8000
```

Remember to set the following environment variables in production:
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `ALLOWED_ORIGIN` (your Netlify URL)
- `GUSS_COOKIE_SECURE=true` (enables `Secure` flag on the JWT cookie)

---

## 🧪 Running Tests

The test suite covers all system layers — API routes, data parsing, PDF handling, report generation, and the Supabase adapter.

```bash
# Activate the environment first
conda activate ai_env

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific module
pytest tests/test_submissions.py -v
```

**Current status:** ✅ 61 tests passing in ~2.8s

---

## 🔭 Planned Extensions

The following extension slots are documented in [`skill.md`](skill.md) and [`operational_map_v3.md`](operational_map_v3.md):

| Slot | Description |
|------|-------------|
| `ALTERNATIVE_PLAN_FORMATS` | Support image-based or Word document monthly plans |
| `REPORT_DISTRIBUTION` | Automated email / Slack delivery after report generation |
| `BATCH_RETRY` | Persistent queue for failed Drive uploads |
| `WEBHOOK_NOTIFY` | POST to an external endpoint when a report is finalized |
| `ADDITIONAL_GEMINI_MODEL` | Add more fallback model tiers for finer-grained failover |

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Before modifying core modules, read the **Surgeon Rule** in [`skill.md`](skill.md) — it defines the development contract and invariants that must be preserved.
4. Run the full test suite: `pytest`.
5. Open a Pull Request with a clear description of what changed and why.

---

## 📄 License

This project is released under the [MIT License](LICENSE).

---

<div align="center">

Built with ❤️ for the **General Union of Syrian Students**

</div>
