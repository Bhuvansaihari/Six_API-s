# Auto-Apply System Code Documentation

## 1. Project Overview

The **Auto-Apply System** is a microservices-based Python application designed to automate job matching, application tracking, and candidate management. It bridges **Supabase** (PostgreSQL) for candidate data/webhooks and **SQL Server** for stored procedure execution.

### Tech Stack
- **Language**: Python 3.9+
- **Framework**: FastAPI (Async)
- **Database 1**: Supabase (PostgreSQL) - User/Candidate Data, Webhooks, Logs
- **Database 2**: Azure SQL Server - Core Business Logic (Stored Procedures)
- **Async Engine**: `asyncio` with `asyncio.gather` for parallel processing
- **Caching**: `aiocache` (for preferences)
- **HTTP Client**: `httpx` (via Supabase client)

---

## 2. System Architecture

The system follows a modular architecture where each functional area has its own API routes (`app/api/`) and service logic (`app/services/`).

### Key Layers
1.  **API Layer** (`app/api/`): Handles HTTP requests, validation, and routing.
2.  **Service Layer** (`app/services/`): Implements business logic (e.g., parsing, preferences, application limits).
3.  **Data Access Layer**:
    - `app/supabase/client.py`: Shared client for Supabase operations (CRUD, RPCS).
    - `app/db/sql_server.py`: Wrapper for `pyodbc` to execute SQL Server stored procedures.
4.  **Utilities** (`app/utils/`): Shared helpers for retries, data handling, etc.

---

## 3. Core Modules

### A. Resume Intake (`app/services/resume_intake`)
Handles candidate resume uploads.
- **Input**: PDF/Docx file + JSON metadata.
- **Process**:
    1.  Validates and parses resume data.
    2.  **Filename Generation**: Sanitizes candidate name to `FirstName_LastName.pdf` (Logic in `app/utils/filename_utils.py`).
    3.  Stores metadata in `auto_apply_cand` table.
- **Database**: `auto_apply_cand`, `parsed_cand_resume`.

### B. Apply Webhook (`app/api/apply_webhook`)
Triggered by Supabase when a candidate matches a job (`cand_job_matching`).
- **Trigger**: `INSERT` on `cand_job_matching` table.
- **Flow**:
    1.  **Similarity Check**: Skips if `similarity_score < 0.7` (Configurable in `app/constants.py`).
    2.  **Duplicate Check**: Prevents applying to the same job twice.
    3.  **Preference Check**:
        - Loads `auto_apply_agent_preferences`.
        - Checks `is_active` status.
        - **Daily Limit Enforcement**: Checks `daily_application_limit` (Default: 10).
    4.  **Parallel Filters** (Optimized):
        - Fetches `remote_flag` and `min_payrate` concurrently.
        - Skips if job doesn't match candidate preferences.
    5.  **Execution**: Calls SQL Server Stored Procedure to submit application.
    6.  **Tracking**: Logs application in `job_application_tracking`.

### C. Recommendations API (`app/services/recommendations`)
Provides job recommendations to candidates.
- **Key Feature**: Custom Connection Pool (`DatabasePool`) to handle SQL Server connections asynchronously.
- **Error Handling**: Gracefully handles `pyodbc.Error` (`HY000`) caused by `nextset()`.

### D. Preferences Service (`app/services/auto_apply_preferences`)
Manages candidate settings.
- **Caching**: Caches preferences for 5 minutes to reduce DB load.
- **Default Creation**: Auto-creates defaults (`limit=10, active=True`) if missing.
- **Safety**: **Do not cache** application counts (prevents race conditions).

---

## 4. Database Interactions

### Supabase Tables
1.  `auto_apply_cand`: Candidate profile data.
2.  `auto_apply_agent_preferences`: Settings for auto-apply (Limit, Status, Keywords).
3.  `job_application_tracking`: Log of all auto-applications.
4.  `cand_job_matching`: Source of truth for matches (Webhook trigger).

### SQL Server Stored Procedures
- Used for the final "Apply" action.
- Executed via `pyodbc` with retry mechanisms (`app/utils/retry_utils.py`).

---

## 5. Configuration & Constants

### Constants (`app/constants.py`)
Centralized configuration values:
```python
SIMILARITY_THRESHOLD = 0.7
DEFAULT_DAILY_LIMIT = 10
CACHE_TTL_PREFERENCES = 300
```

### Environment Variables (`config.py`)
- `SUPABASE_URL`, `SUPABASE_KEY`
- `SQL_SERVER_CONNECTION_STRING`
- `RETRY_*` settings for resiliency.

---

## 6. Optimization Features

### Performance
- **Parallel Execution**: Independent IO calls (e.g., checking remote status and pay rate) run in parallel using `asyncio.gather`.
- **Field Selection**: Supabase queries select only necessary fields to reduce payload size.
- **Connection Pooling**:
    - **SQL Server**: Custom async pool.
    - **Supabase**: Singleton pattern reusing `httpx` connection pool.

### Reliability
- **Retry Logic**: `retry_with_backoff` handles transient DB failures.
- **Sanitization**: Filenames and inputs are rigorously sanitized (`app/utils/filename_utils.py`).
- **Concurrency Safety**: Daily limits are enforced via real-time DB counts, not cached values.

---

## 7. Setup & Running

### Requirements
- Python 3.9+
- ODBC Driver 17/18 for SQL Server
- `.env` file with credentials

### Running
```bash
uvicorn app.main:app --reload
```

### Testing
- `test_daily_limit.py`: Verifies limit logic.
- `test_db_connection.py`: Verifies SQL Server connectivity.
