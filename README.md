# AutoApply Candidate Sync API

Unified FastAPI monorepo combining candidate synchronization, job application webhook processing, and resume intake.

## Overview

This project merges seven FastAPI services into a single unified application:

1. **Apply Webhook API** - Listens to Supabase webhooks for job-candidate matches and automatically applies candidates to jobs
2. **Candidate Sync API** - Synchronizes candidate data from SQL Server to Supabase
3. **Resume Intake API** - Processes resume files (PDF/DOCX/TXT), extracts structured data using GPT-4o, and stores embeddings in Qdrant
4. **Get Recommendations API** - Retrieves job recommendations for candidates using SQL Server stored procedures with caching and rate limiting
5. **Get Requirement Details API** - Fetches requirement/job details by ID from SQL Server with caching and rate limiting
6. **Outreach Agent V1 API** - Sends email (SendGrid) and SMS (Twilio) notifications to candidates when they're matched with jobs
7. **Manual Apply API** - Manually applies a candidate to a job requirement by accepting candidate_id and requirement_id directly

---

## 📁 Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                 # Unified FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   ├── apply_webhook/      # Apply Webhook API module
│   │   │   ├── router.py       # FastAPI routes
│   │   │   ├── logic.py        # Business logic
│   │   │   └── models.py       # Pydantic models
│   │   └── candidate_sync/     # Candidate Sync API module
│   │       ├── router.py       # FastAPI routes
│   │       ├── logic.py        # Business logic
│   │       └── schemas.py      # Pydantic schemas
│   │   ├── resume_intake/      # Resume Intake API module
│   │   │   ├── router.py       # FastAPI routes
│   │   │   └── logic.py        # Processing pipeline
│   │   ├── recommendations/    # Get Recommendations API module
│   │   │   └── router.py       # FastAPI routes for job recommendations
│   │   └── requirement_details/ # Get Requirement Details API module
│   │       ├── router.py       # FastAPI routes for requirement details
│   │       └── schemas.py      # Pydantic models
│   │   └── outreach_agent/     # Outreach Agent V1 API module
│   │       ├── router.py       # FastAPI routes for webhook notifications
│   │       └── schemas.py      # Pydantic models
│   │   └── manual_apply/      # Manual Apply API module
│   │       ├── router.py       # FastAPI routes for manual job applications
│   │       ├── logic.py        # Business logic
│   │       └── schemas.py      # Pydantic models
│   ├── db/
│   │   ├── __init__.py
│   │   └── sql_server.py       # SQL Server connections and repositories
│   ├── supabase/
│   │   ├── __init__.py
│   │   └── client.py           # Supabase clients and repositories
│   ├── services/
│   │   ├── __init__.py
│   │   ├── resume_intake/      # Resume Intake services
│   │   │   ├── resume_parser.py    # PDF/DOCX/TXT parsing
│   │   │   ├── database.py         # Supabase operations
│   │   │   ├── embeddings.py       # OpenAI embeddings
│   │   │   └── vector_store.py     # Qdrant operations
│   │   ├── recommendations/    # Get Recommendations services
│   │   │   ├── db_pool.py          # Database connection pool
│   │   │   ├── cache_manager.py    # Caching (memory/Redis)
│   │   │   └── database_service.py # Stored procedure execution
│   │   └── requirement_details/ # Get Requirement Details services
│   │       ├── db_pool.py          # Database connection pool
│   │       └── cache.py            # Caching with aiocache
│   │   └── outreach_agent/     # Outreach Agent V1 services
│   │       ├── database.py         # Supabase operations
│   │       ├── email_service.py    # SendGrid email sending
│   │       ├── sms_service.py      # Twilio SMS sending
│   │       ├── email_template.py   # Email template rendering
│   │       ├── utils.py            # Utility functions
│   │       └── templates/          # Email HTML templates
│   │           └── job_match_email.html
│   └── utils/
│       ├── __init__.py
│       ├── retry_utils.py       # Retry logic with exponential backoff
│       └── logger.py           # Logging configuration
├── config.py                    # Unified configuration
├── requirements.txt             # Merged Python dependencies
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore rules
├── Dockerfile                   # Docker configuration
└── README.md                    # This file
```

---

## 🔄 Migration Details

### Files Migrated from Apply_API-master

| Original Location | New Location | Description |
|------------------|--------------|-------------|
| `Apply_API-master/Apply_API-master/main.py` | `app/api/apply_webhook/router.py` | FastAPI routes for webhook endpoint |
| `Apply_API-master/Apply_API-master/services.py` | `app/api/apply_webhook/logic.py` | Webhook processing business logic |
| `Apply_API-master/Apply_API-master/models.py` | `app/api/apply_webhook/models.py` | Pydantic models for webhook payloads |
| `Apply_API-master/Apply_API-master/database.py` | `app/db/sql_server.py` | SQL Server connection pool and connection classes |
| `Apply_API-master/Apply_API-master/retry_utils.py` | `app/utils/retry_utils.py` | Retry logic with exponential backoff |
| `Apply_API-master/Apply_API-master/config.py` | `config.py` (merged) | Configuration merged with candidate sync config |

### Files Migrated from Candi_sync_api-main

| Original Location | New Location | Description |
|------------------|--------------|-------------|
| `Candi_sync_api-main/Candi_sync_api-main/main.py` | `app/api/candidate_sync/router.py` | FastAPI routes for candidate sync endpoint |
| `Candi_sync_api-main/Candi_sync_api-main/services/candidate_sync.py` | `app/api/candidate_sync/logic.py` | Candidate sync business logic |
| `Candi_sync_api-main/Candi_sync_api-main/schemas.py` | `app/api/candidate_sync/schemas.py` | Pydantic schemas for candidate sync |
| `Candi_sync_api-main/Candi_sync_api-main/db/sql_server.py` | `app/db/sql_server.py` (merged) | SQL Server repository merged with Apply API database code |
| `Candi_sync_api-main/Candi_sync_api-main/db/supabase.py` | `app/supabase/client.py` (merged) | Supabase repository merged with Apply API Supabase client |
| `Candi_sync_api-main/Candi_sync_api-main/logger.py` | `app/utils/logger.py` | Logging configuration |
| `Candi_sync_api-main/Candi_sync_api-main/config.py` | `config.py` (merged) | Configuration merged with Apply API config |

### Files Migrated from Resume_intake_API

| Original Location | New Location | Description |
|------------------|--------------|-------------|
| `Resume_intake_API/main.py` | `app/api/resume_intake/router.py` | FastAPI routes for resume processing endpoint |
| `Resume_intake_API/processor.py` | `app/api/resume_intake/logic.py` | Resume processing pipeline logic |
| `Resume_intake_API/services/resume_parser.py` | `app/services/resume_intake/resume_parser.py` | PDF/DOCX/TXT file parsing |
| `Resume_intake_API/services/database.py` | `app/services/resume_intake/database.py` | Supabase database operations |
| `Resume_intake_API/services/embeddings.py` | `app/services/resume_intake/embeddings.py` | OpenAI embeddings generation |
| `Resume_intake_API/services/vector_store.py` | `app/services/resume_intake/vector_store.py` | Qdrant vector storage |
| `Resume_intake_API/requirements.txt` | `requirements.txt` (merged) | Dependencies merged into unified requirements |
| `Resume_intake_API/.env.example` | `config.py` (merged) | Environment variables merged into unified config |

### Files Migrated from Get_Recommendations_API

| Original Location | New Location | Description |
|------------------|--------------|-------------|
| `Get_Recommendations_API/main.py` | `app/api/recommendations/router.py` | FastAPI routes for job recommendations endpoint |
| `Get_Recommendations_API/db_pool.py` | `app/services/recommendations/db_pool.py` | Database connection pool manager |
| `Get_Recommendations_API/cache_manager.py` | `app/services/recommendations/cache_manager.py` | Caching functionality (memory/Redis) |
| `Get_Recommendations_API/database_service.py` | `app/services/recommendations/database_service.py` | Database operations and stored procedure execution |
| `Get_Recommendations_API/requirements.txt` | `requirements.txt` (merged) | Dependencies merged into unified requirements |
| `Get_Recommendations_API/env.example.txt` | `config.py` (merged) | Environment variables merged into unified config |

### Files Migrated from Get_RequirementDetails_API

| Original Location | New Location | Description |
|------------------|--------------|-------------|
| `Get_RequirementDetails_API/main.py` | `app/api/requirement_details/router.py` | FastAPI routes for requirement details endpoint |
| `Get_RequirementDetails_API/database.py` | `app/services/requirement_details/db_pool.py` | Database connection pool manager |
| `Get_RequirementDetails_API/cache.py` | `app/services/requirement_details/cache.py` | Caching functionality with aiocache |
| `Get_RequirementDetails_API/models.py` | `app/api/requirement_details/schemas.py` | Pydantic models for API responses |
| `Get_RequirementDetails_API/requirements.txt` | `requirements.txt` (merged) | Dependencies merged into unified requirements |
| `Get_RequirementDetails_API/.env.example` | `config.py` (merged) | Environment variables merged into unified config |

### Files Migrated from Out_Reach_Agent-V1-

| Original Location | New Location | Description |
|------------------|--------------|-------------|
| `Out_Reach_Agent-V1-/webhook_receiver/main.py` | `app/api/outreach_agent/router.py` | FastAPI routes for webhook notifications |
| `Out_Reach_Agent-V1-/webhook_receiver/database.py` | `app/services/outreach_agent/database.py` | Supabase database operations |
| `Out_Reach_Agent-V1-/webhook_receiver/email_template.py` | `app/services/outreach_agent/email_template.py` | Email template rendering |
| `Out_Reach_Agent-V1-/webhook_receiver/utils.py` | `app/services/outreach_agent/utils.py` | Utility functions (formatting, validation) |
| `Out_Reach_Agent-V1-/webhook_receiver/job_match_email.html` | `app/services/outreach_agent/templates/job_match_email.html` | HTML email template |
| `Out_Reach_Agent-V1-/webhook_receiver/notifications.py` | `app/services/outreach_agent/email_service.py` + `sms_service.py` | Split into separate email and SMS services |
| `Out_Reach_Agent-V1-/requirements.txt` | `requirements.txt` (merged) | Dependencies merged into unified requirements |

### New Files Created

| File | Purpose |
|------|---------|
| `app/main.py` | Unified FastAPI application entry point |
| `app/__init__.py` | Python package marker |
| `app/api/__init__.py` | API package marker |
| `app/api/resume_intake/__init__.py` | Resume Intake API package marker |
| `app/db/__init__.py` | Database package marker |
| `app/supabase/__init__.py` | Supabase package marker |
| `app/services/__init__.py` | Services package marker |
| `app/services/resume_intake/__init__.py` | Resume Intake services package marker |
| `app/utils/__init__.py` | Utils package marker |
| `config.py` | Unified configuration combining all projects |
| `requirements.txt` | Merged dependencies from all projects |
| `.env.example` | Environment variables template |
| `.gitignore` | Git ignore rules |
| `Dockerfile` | Docker configuration |
| `README.md` | This comprehensive documentation |

### Files That Can Be Safely Deleted

All files from the original projects have been migrated. The following folders can be **safely deleted**:

#### ✅ Safe to Delete - Resume_intake_API/

#### ✅ Safe to Delete - Apply_API-master/

```
Apply_API-master/Apply_API-master/
├── config.py          ✅ Migrated to config.py (merged)
├── database.py        ✅ Migrated to app/db/sql_server.py
├── main.py            ✅ Migrated to app/api/apply_webhook/router.py
├── models.py          ✅ Migrated to app/api/apply_webhook/models.py
├── requirements.txt   ✅ Merged into requirements.txt
├── retry_utils.py     ✅ Migrated to app/utils/retry_utils.py
├── services.py        ✅ Migrated to app/api/apply_webhook/logic.py
├── README.md          ✅ Merged into README.md
├── test_quick.py      ⚠️  Optional: Test file (can be migrated if needed)
└── test_reliability.py ⚠️  Optional: Test file (can be migrated if needed)
```

#### ✅ Safe to Delete - Candi_sync_api-main/

```
Candi_sync_api-main/Candi_sync_api-main/
├── config.py          ✅ Migrated to config.py (merged)
├── main.py            ✅ Migrated to app/api/candidate_sync/router.py
├── schemas.py         ✅ Migrated to app/api/candidate_sync/schemas.py
├── logger.py          ✅ Migrated to app/utils/logger.py
├── requirements.txt   ✅ Merged into requirements.txt
├── README.md          ✅ Merged into README.md
├── run.bat            ⚠️  Optional: Helper script (can be recreated if needed)
├── run.ps1            ⚠️  Optional: Helper script (can be recreated if needed)
├── db/
│   ├── sql_server.py  ✅ Migrated to app/db/sql_server.py (merged)
│   └── supabase.py    ✅ Migrated to app/supabase/client.py (merged)
├── services/
│   └── candidate_sync.py ✅ Migrated to app/api/candidate_sync/logic.py
└── tests/
    └── test_candidate_sync.py ⚠️  Optional: Test file (can be migrated if needed)
```

#### ✅ Safe to Delete - Resume_intake_API/

```
Resume_intake_API/
├── main.py                    ✅ Migrated to app/api/resume_intake/router.py
├── processor.py               ✅ Migrated to app/api/resume_intake/logic.py
├── services/
│   ├── resume_parser.py       ✅ Migrated to app/services/resume_intake/resume_parser.py
│   ├── database.py            ✅ Migrated to app/services/resume_intake/database.py
│   ├── embeddings.py         ✅ Migrated to app/services/resume_intake/embeddings.py
│   └── vector_store.py       ✅ Migrated to app/services/resume_intake/vector_store.py
├── requirements.txt           ✅ Merged into requirements.txt
├── README.md                  ✅ Merged into README.md
├── SETUP_GUIDE.md             ⚠️  Optional: Documentation (can be kept for reference)
├── WORKFLOW_EXPLANATION.md    ⚠️  Optional: Documentation (can be kept for reference)
└── supabase_setup.sql         ⚠️  Optional: SQL setup script (can be kept for reference)
```

**Note:** Test files (`test_*.py`) are optional. You can:
- Delete them if you don't need tests
- Migrate them to `app/tests/` if you want to keep them (update import paths)

**Note:** Documentation files from Resume_intake_API are optional. You can:
- Delete them if you don't need the reference documentation
- Keep them for reference if needed

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- ODBC Driver 18 for SQL Server
- Supabase account with service role key
- SQL Server access

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# Linux/Mac:
source .venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values. **Required variables:**
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_KEY` - Your Supabase service role key
- `SQLSERVER_CONNECTION_STRING` - SQL Server connection string (or individual SQL_SERVER_* parameters)

### 4. Run the Application

**Development mode:**
```bash
python -m app.main
```

**Using uvicorn directly:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Production mode:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at: `http://localhost:8000`

---

## 📡 API Endpoints

### Health Checks

- `GET /` - Basic health check
- `GET /health` - Detailed health check with version info

### Apply Webhook API

- `POST /webhook/cand-job-matching` - Receives Supabase webhook events

**Request Body:**
```json
{
  "type": "INSERT",
  "table": "cand_job_matching",
  "record": {
    "matching_id": 1,
    "cand_id": 2928,
    "requirement_id": "1001",
    "similarity_score": 0.85,
    "match_reason": "High skill match",
    "matched_skills": ["Python", "FastAPI", "SQL"],
    "matched_at": "2025-01-20T10:00:00Z",
    "is_active": true
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Stored procedure executed successfully",
  "matching_id": 1,
  "cand_id": 2928,
  "requirement_id": "1001",
  "similarity_score": 0.85,
  "selection_id": null,
  "application_id": 14
}
```

### Candidate Sync API

- `POST /candidate-sync` - Synchronizes a candidate from SQL Server to Supabase

**Request Body:**
```json
{
  "email": "candidate@example.com"
}
```

**Response (Success - 200):**
```json
{
  "success": true,
  "message": "Candidate synchronized successfully.",
  "data": {
    "candidate_id": 123,
    "first_name": "John",
    "last_name": "Doe",
    "email": "candidate@example.com",
    ...
  }
}
```

**Response (Not Found - 404):**
```json
{
  "detail": "We could not find an account with that email."
}
```

**Response (Multiple Accounts - 409):**
```json
{
  "detail": "Found multiple accounts with your email please contact the support team."
}
```

### Resume Intake API

- `POST /resume-intake/process-resume` - Process a resume file and extract structured data

**Query Parameters:**
- `candidate_id` (required, int): Candidate ID from logged-in user

**Request:**
```bash
curl -X POST "http://localhost:8000/resume-intake/process-resume?candidate_id=123" \
  -F "file=@resume.pdf"
```

**Supported File Types:**
- PDF (`.pdf`)
- Microsoft Word (`.docx`, `.doc`)
- Plain Text (`.txt`)

**Response (Success - 200):**
```json
{
  "success": true,
  "candidate_id": 123,
  "message": "Resume processed successfully. Candidate ID: 123",
  "cached": false
}
```

**Response (Cached - 200):**
```json
{
  "success": true,
  "candidate_id": 123,
  "message": "Resume processed successfully. Candidate ID: 123",
  "cached": true
}
```

**Processing Pipeline:**
1. Extract text from resume file (PDF/DOCX/TXT)
2. Structure data using GPT-4o (extracts personal info, experience, education, skills, etc.)
3. Update records in Supabase:
   - Updates `auto_apply_cand` table with candidate profile and resume metadata
   - Upserts `parsed_cand_resume` table with structured resume data
4. Generate vector embeddings using OpenAI (text-embedding-3-large)
5. Store embeddings in Qdrant vector database for semantic search

**Additional Endpoints:**
- `GET /resume-intake/cache/stats` - Get cache statistics

**Note:** 
- Rate limited to 10 requests per minute per IP address
- Results are cached for 1 hour based on file hash and candidate_id
- The candidate must already exist in the `auto_apply_cand` table

### Get Recommendations API

- `GET /api/recommendations?candidate_id={id}&use_cache={true|false}` - Get job recommendations for a candidate

**Query Parameters:**
- `candidate_id` (required, int): The candidate ID to get recommendations for (must be > 0)
- `use_cache` (optional, bool): Whether to use cache for this request (default: true)

**Response (Success - 200):**
```json
{
  "candidate_id": 1236,
  "recommendations": [
    {
      "Jobtitle": "Software Developer",
      "JobDescription": "We are looking for an experienced software developer...",
      "Duration": "Permanent",
      "Category": "IT",
      "JobType": "Full-time",
      "Remote/On-site": "Hybrid",
      "Client": "Tech Corp",
      "Location": "New York, NY"
    }
  ],
  "total_count": 50,
  "page_no": 1,
  "page_size": 10
}
```

**Additional Endpoints:**
- `GET /api/recommendations/cache/stats` - Get cache statistics
- `DELETE /api/recommendations/cache/clear` - Clear all cached entries

**Note:**
- Executes stored procedure `USP_SC_Get_JobSeekerRecommenededJobList`
- Rate limited (configurable, default: 60 requests per minute per IP)
- Results are cached with TTL (default: 5 minutes)
- Supports both in-memory and Redis caching
- Includes retry logic with exponential backoff for database operations

### Get Requirement Details API

- `GET /api/requirement/{requirement_id}?company_id=1` - Get requirement details by ID

**Path Parameters:**
- `requirement_id` (required, int): The requirement ID to fetch (must be > 0)

**Query Parameters:**
- `company_id` (optional, int): Company ID (default: 1, must be > 0)

**Response (Success - 200):**
```json
{
  "JobTitle": "Software Engineer",
  "City": "New York",
  "ZIPCode": "10001",
  "Duration": "12 months",
  "ShiftTimingFrom": "09:00",
  "ShiftTimingTo": "18:00",
  "HoursPerWeek": 37.5,
  "MinPayRate": 50000.0,
  "MaxPayRate": 80000.0,
  "JobDescription": "Job description here..."
}
```

**Response (Not Found - 404):**
```json
{
  "detail": "Requirement with ID 123 not found"
}
```

**Response Field Mapping:**

| Database Column | API Response Key |
|----------------|------------------|
| JobTitleText | JobTitle |
| CityName | City |
| ZIPCode | ZIPCode |
| RequirementDuration | Duration |
| RequirementShiftTimingFrom | ShiftTimingFrom |
| RequirementShiftTimingTo | ShiftTimingTo |
| RequirementHoursPerWeek | HoursPerWeek |
| MinPayRate | MinPayRate |
| MaxPayRate | MaxPayRate |
| RequirementJobDescription | JobDescription |

**Note:**
- Executes stored procedure `Beta_usp_Get_Requirement_Details`
- Rate limited (configurable, default: 100 requests per minute per IP)
- Results are cached with TTL (default: 5 minutes = 300 seconds)
- Uses async database connection pooling

### Outreach Agent V1 API

Sends email (SendGrid) and SMS (Twilio) notifications to candidates when they're matched with jobs via Supabase webhooks.

**Endpoint:** `POST /webhook/outreach/job-match`

**Description:**
- Receives webhook events from Supabase when a new job application is created
- Sends email and/or SMS notifications based on candidate preferences (`notify_email`, `notify_sms`)
- Marks notifications as sent in the `job_application_tracking` table
- Uses async concurrency control with configurable semaphore

**Request Headers:**
```
X-Webhook-Secret: <webhook_secret>  # Optional, if WEBHOOK_SECRET is configured
Content-Type: application/json
```

**Request Body (Supabase Webhook Payload):**
```json
{
  "type": "INSERT",
  "table": "job_application_tracking",
  "record": {
    "cand_id": 123,
    "requirement_id": "REQ-456",
    "application_id": 789,
    "similarity_score": 0.85,
    "application_status": "MATCHED"
  },
  "schema": "public"
}
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "message": "Notifications queued",
  "cand_id": 123,
  "requirement_id": "REQ-456",
  "timestamp": "2025-01-15T10:30:00.000Z",
  "concurrency": {
    "max_concurrent_tasks": 50
  }
}
```

**Health Check:** `GET /webhook/outreach/health`

**Response:**
```json
{
  "status": "healthy",
  "service": "outreach-agent-v1",
  "timestamp": "2025-01-15T10:30:00.000Z",
  "capabilities": ["email", "sms", "html_templates", "parallel_processing"]
}
```

**Features:**
- ✅ Respects candidate notification preferences (`notify_email`, `notify_sms`)
- ✅ Professional HTML email templates with job match details
- ✅ SMS notifications via Twilio (160 character limit)
- ✅ Async concurrency control (configurable `MAX_CONCURRENT_TASKS`)
- ✅ Webhook secret authentication (optional)
- ✅ Automatic tracking of sent notifications in database
- ✅ Uses Supabase RPC function `get_application_details` for data fetching

**Note:**
- Notifications are processed asynchronously in background tasks
- Email uses SendGrid with HTML templates
- SMS uses Twilio with phone number validation (E.164 format)
- Concurrency is controlled by semaphore (default: 20, configurable via `MAX_CONCURRENT_TASKS`)

### Manual Apply API

- `POST /apply-job` - Manually applies a candidate to a job requirement

**Request Body:**
```json
{
  "cand_id": 2928,
  "requirement_id": 130174
}
```

**Response (Success - 200):**
```json
{
  "success": true,
  "message": "Job application submitted successfully",
  "cand_id": 2928,
  "requirement_id": 130174,
  "selection_id": 12345,
  "application_id": 789
}
```

**Response (Error - 400):**
```json
{
  "detail": "Candidate with cand_id 2928 not found in auto_apply_cand table"
}
```

**Features:**
- ✅ Direct application without webhook or similarity score requirement
- ✅ Fetches candidate data from Supabase `auto_apply_cand` table
- ✅ Executes `Usp_SC_JobSeeker_IU_ApplyJob` stored procedure in SQL Server
- ✅ Creates tracking record in `job_application_tracking` table
- ✅ Tracking record has NULL `matching_id` and `similarity_score` (manual application)
- ✅ Uses same retry logic and error handling as webhook API

**Note:**
- This endpoint is for manual applications where you directly provide `cand_id` and `requirement_id`
- Unlike the webhook API, this does not require a similarity score or matching_id
- The tracking record will have `matching_id = NULL` and `similarity_score = NULL`
- The unique constraint on `(cand_id, requirement_id)` prevents duplicate applications

## 📚 API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🏗️ Architecture

### How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    app/main.py                          │
│  - Unified FastAPI Application                         │
│  - Lifespan Manager (startup/shutdown)                  │
│  - Includes all routers                                 │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┬───────────────┐
        │                               │               │
┌───────▼────────┐            ┌─────────▼──────────┐   │
│ Apply Webhook  │            │ Candidate Sync     │   │
│ API Router     │            │ API Router         │   │
│ /webhook/*     │            │ /candidate-sync/*  │   │
└───────┬────────┘            └─────────┬──────────┘   │
        │                               │               │
        │                               │      ┌────────▼──────────┐
┌───────▼────────┐            ┌─────────▼──────│ Resume Intake     │
│ Webhook        │            │ sync_candidate │ API Router        │
│ Processing     │            │ _by_email      │ /resume-intake/*  │
│ Service        │            │                └─────────┬─────────┘
└───────┬────────┘            └─────────┬──────────┘       │
        │                               │                  │
        │                               │      ┌───────────▼──────────┐
        │                               │      │ Resume Processing    │
        │                               │      │ Pipeline             │
        │                               │      │ - Parse              │
        │                               │      │ - Structure (GPT-4o) │
        │                               │      │ - Store (Supabase)   │
        │                               │      │ - Embed (OpenAI)     │
        │                               │      │ - Vector (Qdrant)    │
        │                               │      └───────────┬──────────┘
        │                               │                  │
┌───────▼──────────┬───────────────────▼──────────┬───────▼──────────┐
│  Shared Layers                                  │                  │
│  - app/db/sql_server.py                         │                  │
│  - app/supabase/client.py                       │                  │
│  - app/services/resume_intake/                  │                  │
│  - app/utils/retry_utils.py                     │                  │
│  - app/utils/logger.py                          │                  │
└─────────────────────────────────────────────────┴──────────────────┘
        │                               │                  │
        │                               │                  │
┌───────▼──────────┐          ┌─────────▼──────────┐      │
│ SQL Server       │          │ Supabase           │      │
│ Database         │          │ Database           │      │
└──────────────────┘          └────────────────────┘      │
                                                           │
                                                  ┌────────▼──────────┐
                                                  │ Qdrant            │
                                                  │ Vector Database   │
                                                  └───────────────────┘
```

### Data Flow

**1. Candidate Sync Flow:**
```
SQL Server → SQLServerRepository → SupabaseRepository → Supabase
```

**2. Apply Webhook Flow:**
```
Supabase Webhook → WebhookProcessingService → SQL Server (Stored Procedure) → Supabase (Tracking)
```

**3. Resume Intake Flow:**
```
Resume File → ResumeParser → GPT-4o (Structure) → DatabaseService → Supabase
                                                      ↓
                                              EmbeddingService → OpenAI → Qdrant
```

---

## ⚙️ Configuration

### Environment Variables

See `.env.example` for all available configuration options.

**Required:**
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_KEY` or `SUPABASE_SERVICE_ROLE_KEY` - Service role key (for Apply Webhook and Candidate Sync)
- `SQLSERVER_CONNECTION_STRING` OR individual `SQL_SERVER_*` parameters (for Apply Webhook and Candidate Sync)

**Required for Resume Intake API:**
- `OPENAI_API_KEY` - OpenAI API key for GPT-4o and embeddings
- `QDRANT_URL` - Qdrant vector database URL
- `QDRANT_API_KEY` - Qdrant API key for authentication

**Required for Get Recommendations API:**
- `DB_SERVER` - SQL Server hostname (aliased as `recommendations_db_server`)
- `DB_DATABASE` - SQL Server database name (aliased as `recommendations_db_database`)
- `DB_USERNAME` / `DB_PASSWORD` - SQL Server credentials (optional, uses Windows Auth if not provided)
- `DB_DRIVER` - ODBC driver name (default: `ODBC Driver 18 for SQL Server`)

**Required for Get Requirement Details API:**
- `REQUIREMENT_DETAILS_DB_SERVER` - SQL Server hostname
- `REQUIREMENT_DETAILS_DB_NAME` - SQL Server database name
- `REQUIREMENT_DETAILS_DB_USER` / `REQUIREMENT_DETAILS_DB_PASSWORD` - SQL Server credentials (optional, uses Windows Auth if not provided)
- `REQUIREMENT_DETAILS_DB_DRIVER` - ODBC driver name (default: `ODBC Driver 17 for SQL Server`)

**Required for Outreach Agent V1 API:**
- `SENDGRID_API_KEY` - SendGrid API key for sending emails
- `SENDGRID_FROM_EMAIL` - Sender email address for SendGrid
- `TWILIO_ACCOUNT_SID` - Twilio account SID
- `TWILIO_AUTH_TOKEN` - Twilio authentication token
- `TWILIO_PHONE_NUMBER` - Twilio phone number (E.164 format, e.g., +1234567890)

**Optional for Outreach Agent V1 API:**
- `SENDGRID_REPLY_TO_EMAIL` - Reply-to email address (defaults to `SENDGRID_FROM_EMAIL`)
- `WEBHOOK_SECRET` - Secret key for webhook authentication (optional, but recommended)
- `MAX_CONCURRENT_TASKS` - Maximum concurrent notification tasks (default: 20)
- `MODEL` - OpenAI model name (default: `gpt-4o-mini`, shared with Resume Intake API)

**Optional:**
- `LOG_LEVEL` - Logging level (default: INFO)
- `LOG_JSON` - JSON logging format (default: false)
- `ALLOWED_ORIGINS` - CORS origins (comma-separated)
- `RAW_RESUMES_TABLE` - Supabase table for raw resume data (default: `auto_apply_cand`)
- `PARSED_RESUMES_TABLE` - Supabase table for parsed resume data (default: `parsed_cand_resume`)
- `QDRANT_COLLECTION_NAME` - Qdrant collection name (default: `Auto-apply-Resume-Agent`)
- `VECTOR_SIZE` - Vector embedding dimensions (default: `1536`)
- Connection pool settings
- Retry configuration

### Connection Pool

- `SQL_SERVER_POOL_MIN`: Minimum connections (default: 5)
- `SQL_SERVER_POOL_MAX`: Maximum connections (default: 20)

### Retry Configuration

- `RETRY_MAX_ATTEMPTS`: Maximum retry attempts (default: 3)
- `RETRY_INITIAL_DELAY`: Initial delay in seconds (default: 1.0)
- `RETRY_MAX_DELAY`: Maximum delay in seconds (default: 60.0)
- `RETRY_EXPONENTIAL_BASE`: Exponential backoff base (default: 2.0)

---

## 🐳 Docker

### Build the image

```bash
docker build -t autoapply-api .
```

### Run the container

```bash
docker run -p 8000:8000 --env-file .env autoapply-api
```

---

## 🧪 Testing

### Manual Testing

**Test Apply Webhook:**
```bash
curl -X POST http://localhost:8000/webhook/cand-job-matching \
  -H "Content-Type: application/json" \
  -d '{
    "type": "INSERT",
    "table": "cand_job_matching",
    "record": {
      "matching_id": 1,
      "cand_id": 2928,
      "requirement_id": "1001",
      "similarity_score": 0.85
    }
  }'
```

**Test Candidate Sync:**
```bash
curl -X POST http://localhost:8000/candidate-sync \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

### Automated Tests

Test files from the original projects can be migrated to `app/tests/` if needed. Update import paths to use the new structure.

---

## 🔧 Troubleshooting

### ODBC Driver Error
1. Install the Microsoft ODBC Driver for SQL Server
2. Check available drivers: `Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}`
3. Update the driver name in your `.env` file

### SSL Certificate Error
- For **ODBC Driver 18**: Use `TrustServerCertificate=yes` in connection string for development
- **Note**: Use proper SSL certificates in production

### Connection Timeout
- Check your SQL Server credentials and network connectivity
- Increase `SQLSERVER_CONNECT_TIMEOUT` and `SQLSERVER_QUERY_TIMEOUT` in `.env`

### Supabase Insert Errors
- Ensure you're using the **service_role** key (not anon key) for write operations
- Verify the `auto_apply_cand` table exists and has the correct schema
- Check Supabase logs for detailed error messages

### Table Not Found Errors
- Verify the database name in your connection string matches your SQL Server database
- Check that the table `HealthWorks.dbo.CandidateMaster` exists (or update the query in `app/db/sql_server.py`)

---

## 🚢 Production Deployment

### Recommended Setup

1. **Use Gunicorn** with multiple workers:
   ```bash
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

2. **Set up reverse proxy** (Nginx/Traefik) for SSL termination

3. **Use process manager** (systemd, supervisor, PM2) for auto-restart

4. **Monitor logs** and set up alerts for errors

5. **Configure connection pool** based on your SQL Server capacity

6. **Set appropriate retry settings** based on your network conditions

### Environment Variables

Ensure all production environment variables are set securely (use secrets management).

---

## 📝 Cleanup Instructions

After verifying the unified application works correctly, you can safely delete the original project folders:

```bash
# Windows PowerShell
Remove-Item -Recurse -Force Apply_API-master
Remove-Item -Recurse -Force Candi_sync_api-main
Remove-Item -Recurse -Force Resume_intake_API
Remove-Item -Recurse -Force Get_Recommendations_API
Remove-Item -Recurse -Force Get_RequirementDetails_API

# Linux/Mac
rm -rf Apply_API-master/
rm -rf Candi_sync_api-main/
rm -rf Resume_intake_API/
rm -rf Get_Recommendations_API/
rm -rf Get_RequirementDetails_API/
```

**Before deleting, ensure:**
- ✅ The unified app runs: `python -m app.main` or `uvicorn app.main:app --reload`
- ✅ All endpoints work correctly
- ✅ All environment variables are configured
- ✅ Test files are migrated (if needed)

---

## 📄 License

[Add your license here]

## 🤝 Support

For issues and questions, please create an issue or contact the development team.

---

## 📊 Migration Summary

- **Total Files Migrated**: 30+ files
- **New Files Created**: 40+ files
- **Original Projects**: Fully preserved (can be deleted after verification)
- **Code Reuse**: Shared database, Supabase, and utility modules
- **Unified Configuration**: Single `.env` file for all APIs
- **Single Deployment**: One FastAPI app, one port, unified infrastructure
- **APIs Merged**: 5 APIs (Apply Webhook, Candidate Sync, Resume Intake, Get Recommendations, Get Requirement Details)
