from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from aiocache import Cache
from aiocache.serializers import JsonSerializer

from config import get_settings
from app.db.sql_server import SQLServerRepository
from app.supabase.client import SupabaseRepository
from app.utils.logger import setup_logging
from app.api.apply_webhook.router import router as apply_webhook_router
from app.api.candidate_sync.router import router as candidate_sync_router
from app.api.resume_intake.router import router as resume_intake_router
from app.api.recommendations.router import router as recommendations_router
from app.api.requirement_details.router import router as requirement_details_router
from app.api.manual_apply.router import router as manual_apply_router
from app.api.job_list.router import router as job_list_router
# TEMPORARY TEST ENDPOINT - Can be safely deleted later
from app.api.resume_test.router import router as resume_test_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown"""
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_json)

    app.state.settings = settings
    
    # Initialize SQL Server repository for candidate sync (if connection string is provided)
    if settings.sqlserver_connection_string:
        conn_str = settings.get_decrypted_sqlserver_connection_string()
        app.state.sql_repo = SQLServerRepository(
            conn_str,
            connect_timeout=settings.sqlserver_connect_timeout,
            query_timeout=settings.sqlserver_query_timeout,
        )
    else:
        app.state.sql_repo = None
        logging.warning("SQLSERVER_CONNECTION_STRING not set. Candidate sync API will not work.")
    
    # Initialize Supabase repository for candidate sync
    service_key = settings.supabase_service_key
    if not service_key and settings.supabase_service_role_key:
        service_key = settings.supabase_service_role_key
    if service_key:
        app.state.supabase_repo = SupabaseRepository(
            settings.supabase_url,
            service_key.get_secret_value(),
            settings.supabase_table,
        )
    else:
        app.state.supabase_repo = None
        logging.warning("SUPABASE_SERVICE_KEY not set. Candidate sync API will not work.")
    
    # Configure CORS after settings are loaded
    configure_cors(app, settings)
    
    # Initialize rate limiter and cache for Resume Intake API
    app.state.resume_limiter = Limiter(key_func=get_remote_address)
    app.state.resume_cache = Cache(
        Cache.MEMORY,
        serializer=JsonSerializer(),
        namespace="resume_api",
        timeout=3600  # 1 hour default TTL
    )
    logging.info("Resume Intake API: Cache and rate limiter initialized")
    
    # Initialize database pool and rate limiter for Recommendations API
    try:
        from app.services.recommendations.db_pool import get_db_pool
        await get_db_pool()  # Initialize the pool with await
        logging.info("Recommendations API: Database pool initialized")
    except Exception as e:
        logging.warning(f"Recommendations API: Database pool initialization failed: {e}")
        logging.warning("Recommendations API will not be available without database configuration")
    
    app.state.recommendations_limiter = Limiter(key_func=get_remote_address)
    logging.info("Recommendations API: Rate limiter initialized")

    # Initialize rate limiter and cache for Requirement Details API
    app.state.requirement_details_limiter = Limiter(key_func=get_remote_address)
    from app.services.requirement_details.cache import initialize_cache
    app.state.requirement_details_cache = initialize_cache()
    logging.info("Requirement Details API: Cache and rate limiter initialized")

    # Initialize database pool for Requirement Details API
    try:
        from app.services.requirement_details.db_pool import get_db_pool
        await get_db_pool()  # Initialize the pool
        logging.info("Requirement Details API: Database pool initialized")
    except Exception as e:
        logging.warning(f"Requirement Details API: Database pool initialization failed: {e}")
        logging.warning("Requirement Details API will not be available without database configuration")

    # Initialize rate limiter for Job List API
    app.state.job_list_limiter = Limiter(key_func=get_remote_address)
    logging.info("Job List API: Rate limiter initialized")

    yield
    
    # Shutdown: Close cache and database pool
    await app.state.resume_cache.close()
    logging.info("Resume Intake API: Cache closed")
    
    # Close Recommendations API database pool
    try:
        from app.services.recommendations.db_pool import close_db_pool
        await close_db_pool()
        logging.info("Recommendations API: Database pool closed")
    except Exception as e:
        logging.warning(f"Error closing Recommendations API database pool: {e}")

    # Close Requirement Details API cache and database pool
    try:
        await app.state.requirement_details_cache.close()
        logging.info("Requirement Details API: Cache closed")
    except Exception as e:
        logging.warning(f"Error closing Requirement Details API cache: {e}")

    try:
        from app.services.requirement_details.db_pool import close_db_pool
        await close_db_pool()
        logging.info("Requirement Details API: Database pool closed")
    except Exception as e:
        logging.warning(f"Error closing Requirement Details API database pool: {e}")


def configure_cors(app: FastAPI, settings) -> None:
    """Configure CORS middleware"""
    if settings.allowed_origins:
        origins = [origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()]
        if origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )


app = FastAPI(
    title="AutoApply Candidate Sync API",
    description="Unified FastAPI application for candidate synchronization, job application webhooks, resume processing, job recommendations, requirement details, outreach notifications, and manual job applications",
    version="6.1.0",
    lifespan=lifespan
)

# Add rate limiter exception handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(apply_webhook_router)
app.include_router(candidate_sync_router)
app.include_router(resume_intake_router)
app.include_router(recommendations_router)
app.include_router(requirement_details_router)
app.include_router(manual_apply_router)
app.include_router(job_list_router, prefix="/api")
# TEMPORARY TEST ENDPOINT - Can be safely deleted later
app.include_router(resume_test_router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AutoApply Candidate Sync API",
        "version": "6.1.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "service": "AutoApply Candidate Sync API",
        "version": "6.1.0",
        "endpoints": {
            "webhook": "/webhook/cand-job-matching",
            "candidate_sync": "/candidate-sync",
            "resume_intake": "/resume-intake/process-resume",
            "recommendations": "/api/recommendations",
            "requirement_details": "/api/requirement/{requirement_id}",
            "manual_apply": "/apply-job"
        }
    }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )

