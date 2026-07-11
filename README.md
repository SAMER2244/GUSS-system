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

**This system changes that entirely by offering two interfaces:**
1. **Public Form Wizard**: Office representatives fill in a guided multi-step web form (React 19). The moment they submit, the backend stores the structured data, downloads and parses the office's monthly plan PDF from secure cloud storage, runs a parallel AI audit, compiles a fully-formatted RTL Arabic `.docx` report, and uploads it to Google Drive.
2. **Admin Dashboard**: Evaluators log in using secure credentials to search/filter submissions, edit report details & task lists, manually re-run processing, update settings, and download locally archived report documents.

---

## 🏗️ System Architecture

The project supports both a **Decoupled Architecture** (for static CDN frontends like Netlify) and a **Monolithic Architecture** (where FastAPI serves all static and compiled frontend assets directly).

```
                                 OPTION A: Decoupled Deploy
                              ┌──────────────────────────────┐
                              │  Netlify Hosted React Client  │
                              │    (Multi-Step Form Wizard)  │
                              └──────────────┬───────────────┘
                                             │ POST /api/submit-report (CORS)
                                             │ POST /api/upload-plan
                                             ▼
                              ┌──────────────────────────────┐
                              │    FastAPI Web Backend       │
                              │       (web_server.py)        │
                              └──────┬───────────────┬───────┘
                                     │               │
                                     │               │ OPTION B: Monolithic Self-Hosted Deploy
                                     │               │ (FastAPI serves built-in frontends)
                                     │               ├─────────────────────────────────────────┐
                                     │               │ GET /         -> static/index.html      │
                                     │               │ GET /static/* -> static/*               │
                                     │               │ GET /form/*   -> static/form/index.html │
                                     │               └─────────────────────────────────────────┘
                                     │
                     ┌───────────────▼──┐    ┌──────────────────────────────────┐
                     │  Supabase         │    │  Background Execution Pipeline   │
                     │  PostgreSQL       │    │  (Runs asynchronously per submit)│
                     │  ┌─────────────┐ │    │                                  │
                     │  │  offices    │ │    │  1. Fetch submission from DB     │
                     │  │  submissions│ │    │  2. Download plan PDF           │
                     │  │  tasks      │ │    │  3. Extract text from PDF        │
                     │  └─────────────┘ │    │  4. Run AI Parallel Orchestrator ┼──► Gemini API
                     │  Storage Bucket  │    │  5. Build premium RTL .docx doc  │    (4 Threads)
                     │  (monthly-plans) │    │  6. Upload report to Google Drive│
                     └──────────────────┘    └──────────────────────────────────┘
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
| Component | Technology | Description |
|-----------|-----------|-------------|
| **Form Wizard (React)** | React 19 + Vite 8 | Guided wizard with step validation, dark/light themes, and file upload. Deployed via Netlify (`netlify.toml`) or built statically. |
| **Admin Dashboard** | Vanilla HTML5 / CSS3 / JS | Embedded dashboard for system management. Served directly by FastAPI on `/`. |
| **Compiled Client Wizard** | Static Assets | Compiled production React wizard served by FastAPI on `/static/form/` for all-in-one deploys. |

### Cloud Infrastructure
| Service | Purpose |
|---------|---------|
| Supabase (PostgreSQL) | Primary relational database |
| Supabase Storage | Private bucket (`monthly-plans`) for monthly plan PDFs |
| Google Drive | Final report archive (hierarchical folders) |
| Netlify | Frontend static hosting (Decoupled option) |

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
├── frontend/                   # React 19 + Vite Form Wizard (Decoupled Client)
│   ├── src/
│   │   ├── App.css             # Main styling overrides for the app wrapper
│   │   ├── App.jsx             # Main app with step wizard, API routing, and state
│   │   ├── main.jsx            # React mounting and entry point
│   │   ├── index.css           # Global custom CSS (glassmorphism, dark/light themes)
│   │   ├── assets/             # Assets used in the React frontend
│   │   └── components/         # Reusable step components:
│   │       ├── WelcomeStep.jsx       # Welcome landing screen
│   │       ├── BasicInfoStep.jsx     # Office selector, period, and PDF plan upload
│   │       ├── TasksStep.jsx         # Task creation wizard
│   │       ├── TaskCard.jsx          # Interactive card for individual task configuration
│   │       ├── ClosingStep.jsx       # Challenges and notes input
│   │       ├── SuccessScreen.jsx     # Submission success dashboard
│   │       ├── ProgressIndicator.jsx # Multi-step progress bar
│   │       └── ThemeToggle.jsx       # Dark/Light theme toggler component
│   │
│   ├── .env.example            # Template for frontend environment variables
│   ├── .gitignore              # Ignored folders (node_modules, dist)
│   ├── eslint.config.js        # ESLint linter configuration
│   ├── index.html              # HTML shell for Vite bundler
│   ├── package.json            # Node.js project manifest & script commands
│   ├── package-lock.json       # Strict package lock version file
│   └── vite.config.js          # Vite custom bundler settings
│
├── static/                     # Embedded Frontend Assets (Served directly by web_server.py)
│   ├── index.html              # HTML UI for the built-in Admin Dashboard (login, CRUD, actions)
│   ├── style.css               # Styling rules for the embedded dashboard
│   ├── app.js                  # Client logic for dashboard (handles JWT cookies, API CRUD, real-time pipeline status)
│   └── form/                   # Built React Form Wizard (compiled for static serving)
│       ├── assets/             # Compiled production JS/CSS assets
│       ├── index.html          # HTML entry point for the compiled wizard
│       ├── favicon.svg         # Tab icon
│       └── icons.svg           # Sprite sheet for dashboard/wizard icons
│
├── routes/                     # Backend API Router Modules
│   ├── __init__.py             # Python package initialization
│   ├── submissions.py          # Public API routes (submit report, upload PDF plan, list offices)
│   └── dashboard.py            # Protected Admin API routes (CRUD, manual processing trigger)
│
├── migrations/                 # PostgreSQL Database Migrations (Supabase)
│   ├── 001_create_tables.sql   # Creates offices, submissions, tasks, and answers tables + RLS policies
│   ├── 002_seed_offices.sql    # Seeds the initial 12 operational executive offices of GUSS
│   ├── 003_storage_bucket.sql  # Sets up the "monthly-plans" storage bucket with public/anon policies
│   └── 004_add_drive_link.sql  # Appends the drive_report_link column to submissions for tracking uploads
│
├── tests/                      # Automated Pytest Suite
│   ├── conftest.py             # Global test fixtures, environment setups, and security mocks
│   ├── test_adapter.py         # Unit tests for the legacy pipeline adapter functions
│   ├── test_dashboard.py       # Integration tests for protected admin routes & CRUD endpoints
│   ├── test_data_parser.py     # Unit tests for parsing database tasks into statistics
│   ├── test_pdf_handler.py     # Integration tests for PDF download (Supabase Storage) & text extraction
│   ├── test_report_generator.py# Unit tests for assembling Arabic A4 Word (.docx) reports
│   ├── test_submissions.py     # Integration tests for public submission routes & validation constraints
│   └── test_web_server.py      # Integration tests for server authentication & live pipeline endpoints
│
├── assets/                     # Shared static assets (Union logos, office banners)
│   ├── union_logo.png          # GUSS emblem logo
│   └── office_banner.jpg       # Assessment banner used in the Admin UI
│
├── ai_engine.py                # ParallelOrchestrator, failover wrapper & Gemini fallback thread management
├── report_generator.py         # Builds premium RTL Arabic docx report, matching AI comments to database tasks
├── pdf_handler.py              # Downloads files from Supabase Storage / Drive & extracts text with pdfplumber
├── drive_uploader.py           # Authenticates via OAuth2 Desktop client to upload reports to nested Drive folders
├── supabase_adapter.py         # Formats raw Supabase table rows into dict formats consumed by the generator
├── data_parser.py              # Calculates execution rates and classifies tasks (within/outside plan)
├── web_server.py               # Main FastAPI server initialization, JWT authentication, & background worker threads
├── database.py                 # Singleton manager for Supabase Client and storage configurations
├── models.py                   # PyRequest/Response schemas (Pydantic models)
├── config.py                   # Loads settings from environment variables & settings.yaml, converts custom colors
├── logger.py                   # Dual file/console logging configuration
├── exceptions.py               # Domain exception class hierarchy
├── retry.py                    # Decorator pattern for API retry resilience
├── settings.yaml               # Application config (colors, AI fallback models, retry counts, database aliases)
├── environment.yml             # Conda environment definition for setting up the package suite
├── requirements.txt            # Python pip dependencies
├── debug_test.py               # Dry-run diagnostic sandbox (dry-run Gemini calls & task matches)
├── logo.png                    # App branding asset
├── credentials.json            # [IGNORED] Google Service Account key for storage access
├── oauth_client.json           # [IGNORED] Google OAuth 2.0 client credentials for Drive uploads
├── token.json                  # [IGNORED] Google OAuth 2.0 user tokens persisted after first login
└── .env.example                # Sample environment configuration template for backend variables
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

Using Conda:
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

### Step 6 — Start the Backend (and Embedded Admin Dashboard)

```bash
python web_server.py
```

The API will be live at: `http://localhost:8000`

- **Admin Dashboard UI**: Go to `http://localhost:8000/` in your browser.
- **Compiled Form Wizard**: Go to `http://localhost:8000/static/form/index.html`.
- **Interactive Swagger Docs**: Go to `http://localhost:8000/docs`.

---

### Step 7 — Start the Development Frontend (Optional — Decoupled Setup)

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

**Current status:** ✅ 61 tests passing in ~4.0s

---

## 🛠️ Local Sandbox & AI Dry-Run

For diagnostic dry-runs without database or Drive connections, developers can use the sandbox utility script:

```bash
python debug_test.py
```

This script:
1. Builds a mock office dataset.
2. Formats and prints the prompt payload sent to Gemini.
3. Performs a live test call to the Gemini API using your `GEMINI_API_KEY`.
4. Demonstrates task matching performance (exact, diacritics removal, contains, etc.) and lists LLM compliance.

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

### Backend & Monolithic Deploy

The FastAPI backend can be deployed on any Linux server or container:

```bash
pip install -r requirements.txt
uvicorn web_server:app --host 0.0.0.0 --port 8000
```

Remember to set the following environment variables in production:
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `ALLOWED_ORIGIN` (your Netlify URL or static host URL)
- `GUSS_COOKIE_SECURE=true` (enables `Secure` flag on the JWT cookie)

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Run the full test suite: `pytest`.
4. Open a Pull Request with a clear description of what changed and why.

---

## 📄 License

This project is released under the [MIT License](LICENSE).

---

<div align="center">

Built with ❤️ for the **General Union of Syrian Students**

</div>
