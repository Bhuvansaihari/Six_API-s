from functools import lru_cache
from typing import Optional
from pathlib import Path
import os

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file explicitly from project root
# Try multiple possible locations
env_paths = [
    Path.cwd() / ".env",  # Current working directory (where uvicorn is run from)
    Path(__file__).parent / ".env",  # Same directory as config.py
    Path(__file__).parent.parent / ".env",  # Parent directory
]

env_loaded = False
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        env_loaded = True
        break

if not env_loaded:
    # If no .env file found, try loading from current directory anyway
    # (python-dotenv will look in current directory by default)
    load_dotenv(override=True)


class Settings(BaseSettings):
    """Unified application configuration loaded from environment variables."""

    # ========== Supabase Configuration ==========
    supabase_url: str = Field(
        ...,
        alias="SUPABASE_URL",
        description="Supabase project URL."
    )
    supabase_service_key: Optional[SecretStr] = Field(
        None,
        alias="SUPABASE_SERVICE_KEY",
        description="Supabase service role key with insert permissions."
    )
    supabase_service_role_key: Optional[SecretStr] = Field(
        None,
        alias="SUPABASE_SERVICE_ROLE_KEY",
        description="Supabase service role key (alias for SUPABASE_SERVICE_KEY for backward compatibility)."
    )
    supabase_table: str = Field(
        "auto_apply_cand",
        alias="SUPABASE_TABLE",
        description="Supabase table name to receive candidate records."
    )

    # ========== SQL Server Configuration (Apply API) ==========
    sql_server_host: Optional[str] = Field(
        None,
        alias="SQL_SERVER_HOST",
        description="SQL Server hostname."
    )
    sql_server_database: Optional[str] = Field(
        None,
        alias="SQL_SERVER_DATABASE",
        description="SQL Server database name."
    )
    sql_server_user: Optional[str] = Field(
        None,
        alias="SQL_SERVER_USER",
        description="SQL Server username."
    )
    sql_server_password: Optional[str] = Field(
        None,
        alias="SQL_SERVER_PASSWORD",
        description="SQL Server password."
    )
    sql_server_port: int = Field(
        1433,
        alias="SQL_SERVER_PORT",
        description="SQL Server port."
    )
    sql_server_driver: str = Field(
        "ODBC Driver 18 for SQL Server",
        alias="SQL_SERVER_DRIVER",
        description="ODBC driver name for SQL Server."
    )

    # ========== SQL Server Configuration (Candidate Sync API) ==========
    sqlserver_connection_string: Optional[SecretStr] = Field(
        None,
        alias="SQLSERVER_CONNECTION_STRING",
        description="ODBC connection string used by pyodbc to reach SQL Server."
    )
    sqlserver_connect_timeout: int = Field(
        5,
        alias="SQLSERVER_CONNECT_TIMEOUT",
        ge=1,
        description="Connection timeout for SQL Server in seconds."
    )
    sqlserver_query_timeout: int = Field(
        10,
        alias="SQLSERVER_QUERY_TIMEOUT",
        ge=1,
        description="Query timeout for SQL Server in seconds."
    )

    # ========== Connection Pool Configuration ==========
    sql_server_pool_min: int = Field(
        5,
        alias="SQL_SERVER_POOL_MIN",
        description="Minimum connections in pool."
    )
    sql_server_pool_max: int = Field(
        20,
        alias="SQL_SERVER_POOL_MAX",
        description="Maximum connections in pool."
    )

    # ========== Retry Configuration ==========
    retry_max_attempts: int = Field(
        3,
        alias="RETRY_MAX_ATTEMPTS",
        description="Maximum retry attempts."
    )
    retry_initial_delay: float = Field(
        1.0,
        alias="RETRY_INITIAL_DELAY",
        description="Initial delay in seconds."
    )
    retry_max_delay: float = Field(
        60.0,
        alias="RETRY_MAX_DELAY",
        description="Maximum delay in seconds."
    )
    retry_exponential_base: float = Field(
        2.0,
        alias="RETRY_EXPONENTIAL_BASE",
        description="Exponential backoff base."
    )

    # ========== Application Configuration ==========
    log_level: str = Field(
        "INFO",
        alias="LOG_LEVEL",
        description="Application log level."
    )
    log_json: bool = Field(
        False,
        alias="LOG_JSON",
        description="Emit logs in JSON format when True; otherwise plain text."
    )

    # ========== CORS Configuration ==========
    allowed_origins: Optional[str] = Field(
        None,
        alias="ALLOWED_ORIGINS",
        description="Comma-separated list of CORS origins."
    )

    # ========== Resume Intake API Configuration ==========
    openai_api_key: Optional[SecretStr] = Field(
        None,
        alias="OPENAI_API_KEY",
        description="OpenAI API key for GPT-4o and embeddings."
    )
    supabase_key: Optional[SecretStr] = Field(
        None,
        alias="SUPABASE_KEY",
        description="Supabase anon or service role key (for Resume Intake API)."
    )
    raw_resumes_table: str = Field(
        "auto_apply_cand",
        alias="RAW_RESUMES_TABLE",
        description="Supabase table name for raw resume data."
    )
    parsed_resumes_table: str = Field(
        "parsed_cand_resume",
        alias="PARSED_RESUMES_TABLE",
        description="Supabase table name for parsed resume data."
    )
    qdrant_url: Optional[str] = Field(
        None,
        alias="QDRANT_URL",
        description="Qdrant vector database URL."
    )
    qdrant_api_key: Optional[SecretStr] = Field(
        None,
        alias="QDRANT_API_KEY",
        description="Qdrant API key for authentication."
    )
    qdrant_collection_name: str = Field(
        "Auto-apply-Resume-Agent",
        alias="QDRANT_COLLECTION_NAME",
        description="Qdrant collection name for resume embeddings."
    )
    vector_size: int = Field(
        1536,
        alias="VECTOR_SIZE",
        description="Vector embedding size (dimensions)."
    )

    # ========== Get Recommendations API Configuration ==========
    # Database Configuration (for Recommendations API)
    recommendations_db_server: Optional[str] = Field(
        None,
        alias="DB_SERVER",
        description="SQL Server hostname for Recommendations API."
    )
    recommendations_db_database: Optional[str] = Field(
        None,
        alias="DB_DATABASE",
        description="SQL Server database name for Recommendations API."
    )
    recommendations_db_username: Optional[str] = Field(
        None,
        alias="DB_USERNAME",
        description="SQL Server username for Recommendations API (optional, uses Windows Auth if not provided)."
    )
    recommendations_db_password: Optional[SecretStr] = Field(
        None,
        alias="DB_PASSWORD",
        description="SQL Server password for Recommendations API (optional, uses Windows Auth if not provided)."
    )
    recommendations_db_driver: str = Field(
        "ODBC Driver 18 for SQL Server",
        alias="DB_DRIVER",
        description="ODBC driver name for SQL Server (Recommendations API)."
    )
    recommendations_db_trust_server_certificate: str = Field(
        "yes",
        alias="DB_TRUST_SERVER_CERTIFICATE",
        description="Trust server certificate for SQL Server (Recommendations API)."
    )
    recommendations_db_encrypt: str = Field(
        "yes",
        alias="DB_ENCRYPT",
        description="Encrypt connection for SQL Server (Recommendations API)."
    )

    # Connection Pool Configuration (Recommendations API)
    recommendations_db_pool_size: int = Field(
        10,
        alias="DB_POOL_SIZE",
        description="Maximum number of connections in pool (Recommendations API)."
    )
    recommendations_db_max_overflow: int = Field(
        20,
        alias="DB_MAX_OVERFLOW",
        description="Maximum additional connections beyond pool size (Recommendations API)."
    )
    recommendations_db_pool_timeout: int = Field(
        30,
        alias="DB_POOL_TIMEOUT",
        description="Timeout in seconds for acquiring a connection from pool (Recommendations API)."
    )

    # Cache Configuration (Recommendations API)
    recommendations_cache_ttl: int = Field(
        300,
        alias="CACHE_TTL",
        description="Cache TTL in seconds for Recommendations API (default: 300 = 5 minutes)."
    )
    recommendations_cache_type: str = Field(
        "memory",
        alias="CACHE_TYPE",
        description="Cache type for Recommendations API: 'memory' or 'redis'."
    )

    # Redis Configuration (if CACHE_TYPE=redis for Recommendations API)
    recommendations_redis_host: str = Field(
        "localhost",
        alias="REDIS_HOST",
        description="Redis server host for Recommendations API caching."
    )
    recommendations_redis_port: int = Field(
        6379,
        alias="REDIS_PORT",
        description="Redis server port for Recommendations API caching."
    )
    recommendations_redis_password: Optional[SecretStr] = Field(
        None,
        alias="REDIS_PASSWORD",
        description="Redis password for Recommendations API caching (optional)."
    )
    recommendations_redis_db: int = Field(
        0,
        alias="REDIS_DB",
        description="Redis database number for Recommendations API caching."
    )
    recommendations_redis_socket_timeout: int = Field(
        5,
        alias="REDIS_SOCKET_TIMEOUT",
        description="Redis socket timeout in seconds for Recommendations API."
    )

    # API Configuration (Recommendations API)
    recommendations_request_timeout: int = Field(
        30,
        alias="REQUEST_TIMEOUT",
        description="Request timeout in seconds for Recommendations API."
    )

    # Rate Limiting Configuration (Recommendations API)
    recommendations_rate_limit_enabled: bool = Field(
        True,
        alias="RATE_LIMIT_ENABLED",
        description="Enable rate limiting for Recommendations API."
    )
    recommendations_rate_limit_per_minute: int = Field(
        60,
        alias="RATE_LIMIT_PER_MINUTE",
        description="Rate limit per minute for Recommendations API."
    )

    # Retry Configuration (Recommendations API)
    recommendations_db_retry_attempts: int = Field(
        3,
        alias="DB_RETRY_ATTEMPTS",
        description="Number of retry attempts for database operations (Recommendations API)."
    )
    recommendations_db_retry_delay: float = Field(
        1.0,
        alias="DB_RETRY_DELAY",
        description="Initial retry delay in seconds for database operations (Recommendations API)."
    )

    # ========== Get Requirement Details API Configuration ==========
    # Database Configuration (for Requirement Details API)
    requirement_details_db_server: Optional[str] = Field(
        None,
        alias="REQUIREMENT_DETAILS_DB_SERVER",
        description="SQL Server hostname for Requirement Details API."
    )
    requirement_details_db_name: Optional[str] = Field(
        None,
        alias="REQUIREMENT_DETAILS_DB_NAME",
        description="SQL Server database name for Requirement Details API."
    )
    requirement_details_db_user: Optional[str] = Field(
        None,
        alias="REQUIREMENT_DETAILS_DB_USER",
        description="SQL Server username for Requirement Details API (optional, uses Windows Auth if not provided)."
    )
    requirement_details_db_password: Optional[SecretStr] = Field(
        None,
        alias="REQUIREMENT_DETAILS_DB_PASSWORD",
        description="SQL Server password for Requirement Details API (optional, uses Windows Auth if not provided)."
    )
    requirement_details_db_driver: str = Field(
        "ODBC Driver 17 for SQL Server",
        alias="REQUIREMENT_DETAILS_DB_DRIVER",
        description="ODBC driver name for SQL Server (Requirement Details API)."
    )
    requirement_details_db_pool_size: int = Field(
        20,
        alias="REQUIREMENT_DETAILS_DB_POOL_SIZE",
        description="Connection pool size for Requirement Details API (default: 20)."
    )

    # Rate Limiting Configuration (Requirement Details API)
    requirement_details_rate_limit: str = Field(
        "100/minute",
        alias="REQUIREMENT_DETAILS_RATE_LIMIT",
        description="Rate limit for Requirement Details API (format: 'number/period', e.g., '100/minute')."
    )



    # OpenAI Model Configuration (shared with Resume Intake API)
    openai_model: str = Field(
        "gpt-4o-mini",
        alias="MODEL",
        description="OpenAI model name (default: gpt-4o-mini)."
    )

    encryption_key: Optional[SecretStr] = Field(
        None,
        alias="ENCRYPTION_KEY",
        description="Master key for decrypting environment variables."
    )

    model_config = SettingsConfigDict(
        env_file=(".env", str(Path.cwd() / ".env")),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, value: str) -> str:
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("SUPABASE_URL must start with http:// or https://")
        return value.rstrip("/")

    def model_post_init(self, __context):
        """Sync SUPABASE_SERVICE_KEY and SUPABASE_SERVICE_ROLE_KEY after initialization."""
        
        # 1. DECRYPTION LOGIC
        # If we have an encryption key, try to decrypt all SecretStr fields
        if self.encryption_key:
            try:
                from cryptography.fernet import Fernet
                key = self.encryption_key.get_secret_value()
                f = Fernet(key)
                
                # Iterate over all fields in the model
                for field_name in self.model_fields:
                    value = getattr(self, field_name)
                    
                    # We only encrypt fields that are SecretStr (or potentially str if needed, but SecretStr is safest)
                    if isinstance(value, SecretStr):
                        secret_val = value.get_secret_value()
                        # Check magic header for Fernet
                        if secret_val.startswith("gAAAA"):
                            try:
                                decrypted = f.decrypt(secret_val.encode()).decode()
                                # Replace with decrypted value
                                setattr(self, field_name, SecretStr(decrypted))
                            except Exception:
                                # If decryption fails (e.g. invalid token), leave it as is 
                                # or log a warning (but we don't have logger here yet)
                                pass
                                
                    # If you have plain string fields that might be encrypted, handle them here too
                    elif isinstance(value, str):
                        if value.startswith("gAAAA"):
                            try:
                                decrypted = f.decrypt(value.encode()).decode()
                                setattr(self, field_name, decrypted)
                            except Exception:
                                pass
                                
            except ImportError:
                print("⚠️ Warning: 'cryptography' not installed. Secrets cannot be decrypted.")
            except Exception as e:
                print(f"⚠️ Warning: Secret decryption failed: {e}")

        # 2. VALIDATION LOGIC
        # Ensure at least one is set
        if not self.supabase_service_key and not self.supabase_service_role_key:
            raise ValueError("Either SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY must be set")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()

