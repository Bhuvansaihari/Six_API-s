from __future__ import annotations

import pyodbc
import logging
from typing import Optional
from contextlib import contextmanager
from queue import Queue
from threading import Lock
from dataclasses import dataclass
from datetime import date
from typing import List

from config import get_settings

logger = logging.getLogger(__name__)

pyodbc.pooling = True


@dataclass
class CandidateRecord:
    """Candidate record from SQL Server"""
    candidate_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    password: Optional[str]
    birth_date: Optional[date]
    ssn: Optional[str]
    over_18_age: Optional[bool]
    mobile: Optional[str]
    home: Optional[str]
    work: Optional[str]
    work_ext: Optional[str]
    relocation: Optional[bool]


class SQLServerConnectionPool:
    """Connection pool for SQL Server using pyodbc (for Apply API)"""
    
    def __init__(self, min_connections: int = 5, max_connections: int = 20):
        settings = get_settings()
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_string = self._build_connection_string(settings)
        self.pool: Queue = Queue(maxsize=max_connections)
        self.lock = Lock()
        self.current_connections = 0
        
        # Initialize minimum connections
        self._initialize_pool()
    
    def _build_connection_string(self, settings) -> str:
        """Build SQL Server connection string with driver 18"""
        return (
            f"DRIVER={{{settings.sql_server_driver}}};"
            f"SERVER={settings.sql_server_host},{settings.sql_server_port};"
            f"DATABASE={settings.sql_server_database};"
            f"UID={settings.sql_server_user};"
            f"PWD={settings.sql_server_password};"
            f"TrustServerCertificate=yes;"
            f"Encrypt=yes;"
        )
    
    def _create_connection(self):
        """Create a new database connection"""
        try:
            conn = pyodbc.connect(self.connection_string, timeout=10)
            # Test the connection
            conn.execute("SELECT 1")
            return conn
        except Exception as e:
            logger.error(f"Failed to create SQL Server connection: {str(e)}")
            raise
    
    def _initialize_pool(self):
        """Initialize the connection pool with minimum connections"""
        for _ in range(self.min_connections):
            try:
                conn = self._create_connection()
                self.pool.put(conn)
                self.current_connections += 1
            except Exception as e:
                logger.warning(f"Failed to initialize connection in pool: {str(e)}")
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = None
        try:
            # Try to get connection from pool (non-blocking)
            try:
                conn = self.pool.get_nowait()
            except:
                # Pool is empty, create new connection if under max
                with self.lock:
                    if self.current_connections < self.max_connections:
                        conn = self._create_connection()
                        self.current_connections += 1
                        logger.debug(f"Created new connection. Pool size: {self.current_connections}")
                    else:
                        # Wait for a connection to become available
                        logger.warning("Connection pool exhausted, waiting for available connection...")
                        conn = self.pool.get(timeout=30)  # Wait up to 30 seconds
            
            yield conn
            
        except Exception as e:
            logger.error(f"Error with connection: {str(e)}")
            # If connection is bad, don't return it to pool
            if conn:
                try:
                    conn.close()
                except:
                    pass
                with self.lock:
                    self.current_connections -= 1
            raise
        finally:
            # Return connection to pool if it's still valid
            if conn:
                try:
                    # Test if connection is still alive
                    conn.execute("SELECT 1")
                    self.pool.put(conn)
                except:
                    # Connection is dead, don't return to pool
                    try:
                        conn.close()
                    except:
                        pass
                    with self.lock:
                        self.current_connections -= 1
                        # Try to create a replacement
                        if self.current_connections < self.min_connections:
                            try:
                                new_conn = self._create_connection()
                                self.pool.put(new_conn)
                                self.current_connections += 1
                            except:
                                pass
    
    def close_all(self):
        """Close all connections in the pool"""
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except:
                pass
        self.current_connections = 0


# Global connection pool instance (for Apply API)
_connection_pool: Optional[SQLServerConnectionPool] = None


def get_connection_pool() -> SQLServerConnectionPool:
    """Get or create the global connection pool (for Apply API)"""
    global _connection_pool
    if _connection_pool is None:
        settings = get_settings()
        _connection_pool = SQLServerConnectionPool(
            min_connections=settings.sql_server_pool_min,
            max_connections=settings.sql_server_pool_max
        )
    return _connection_pool


class SQLServerConnection:
    """SQL Server connection handler using connection pool (for Apply API)"""
    
    def __init__(self):
        self.pool = get_connection_pool()
    
    def execute_stored_procedure(self, params: dict) -> Optional[int]:
        """Execute Usp_SC_JobSeeker_IU_ApplyJob stored procedure"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Prepare the stored procedure call
                sql = """
                EXEC Usp_SC_JobSeeker_IU_ApplyJob
                    @CandidateID = ?,
                    @RequirementID = ?,
                    @DisabilityID = ?,
                    @VeteranDisclosureID = ?,
                    @EthnicityID = ?,
                    @HumanRaceID = ?,
                    @GenderID = ?,
                    @FileName = ?,
                    @FileExtension = ?,
                    @FileType = ?,
                    @FileContent = ?,
                    @ResumeID = ?,
                    @ServedAsTxnsJson = ?,
                    @ReqTalentChannelID = ?
                """
                
                # Execute with parameters
                cursor.execute(sql, (
                    params.get('CandidateID', 0),
                    params.get('RequirementID', 0),
                    params.get('DisabilityID', 0),
                    params.get('VeteranDisclosureID', 0),
                    params.get('EthnicityID', 0),
                    params.get('HumanRaceID', 0),
                    params.get('GenderID', 0),
                    params.get('FileName'),
                    params.get('FileExtension'),
                    params.get('FileType'),
                    params.get('FileContent'),
                    params.get('ResumeID', 0),
                    params.get('ServedAsTxnsJson'),
                    params.get('ReqTalentChannelID', 0)
                ))
                
                # Commit the transaction
                conn.commit()
                
                # Try to fetch result if stored procedure returns SelectionID
                try:
                    result = cursor.fetchone()
                    if result:
                        return result[0] if result[0] else None
                except:
                    # Some stored procedures don't return results via fetch
                    pass
                
                return None
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error executing stored procedure: {str(e)}")
                raise
            finally:
                cursor.close()


    def fetch_requirement_details(self, requirement_id: int) -> Optional[dict]:
        """
        Fetch minimal requirement details for Lazy Sync.
        Uses USP_AI_Get_JobSeekerRecommenededJobDetails (SourceID=1 for defaults).
        """
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Execute stored procedure
                cursor.execute(
                    "EXEC [dbo].[USP_AI_Get_JobSeekerRecommenededJobDetails] @RequirementID=?, @SourceID=?",
                    requirement_id,
                    1 # SourceID 1 (Talent Acquisition) as default source
                )
                
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Lazy Sync: USP_AI_Get_JobSeekerRecommenededJobDetails returned no rows for ReqID={requirement_id}")
                    return None
                
                columns = [column[0] for column in cursor.description]
                result = dict(zip(columns, row))
                
                # Debug logging if needed
                # logger.debug(f"SP Result Keys: {result.keys()}")

                def get_val(keys):
                    for k in keys:
                        if k in result: return result[k]
                    return None

                remote_val = get_val(["remote_option", "RemoteOption", "RemoteOptionType"])
                is_remote = False
                if remote_val and isinstance(remote_val, str):
                    if remote_val.lower() in ["remote", "hybrid"]:
                        is_remote = True
                
                return {
                    "requirement_id": str(requirement_id),
                    "client_job_title": get_val(["job_title", "JobTitle", "JobTitleText"]),
                    "requirement_job_description": get_val(["job_description", "JobDescription", "RequirementJobDescription"]),
                    "min_payrate": get_val(["pay_rate_to_candidate", "PayRateToCandidate", "MinPayRate"]),
                    "client_name": get_val(["client_name", "ClientName"]),
                    "address": get_val(["location", "Location"]),
                    "is_remote_location": is_remote,
                    "created_at": get_val(["created_date", "CreatedDate"])
                }
                
            except Exception as e:
                logger.error(f"Error fetching requirement details: {str(e)}")
                return None
            finally:
                cursor.close()

class SQLServerRepository:
    """Repository for fetching candidates from SQL Server (for Candidate Sync API)"""

    def __init__(
        self,
        connection_string: str,
        connect_timeout: int = 5,
        query_timeout: int = 10,
    ) -> None:
        self._connection_string = connection_string
        self._connect_timeout = connect_timeout
        self._query_timeout = query_timeout

    def _get_connection(self) -> pyodbc.Connection:
        """Create and return a pyodbc connection to SQL Server.
        
        Note: Connection timeout is set via the timeout parameter.
        Query timeout is not directly settable in pyodbc, but connection
        timeout provides reasonable protection against hanging connections.
        """
        return pyodbc.connect(
            self._connection_string,
            timeout=self._connect_timeout,
            autocommit=False,
        )

    def fetch_candidates_by_email(self, email: str) -> List[CandidateRecord]:
        query = """
            SELECT
                CandidateID,
                FirstName,
                LastName,
                Email,
                Password,
                Birthdate,
                SSN,
                Over18Age,
                Mobile,
                Home,
                Work,
                WorkExt,
                Relocation
            FROM HealthWorks.dbo.CandidateMaster WITH (NOLOCK)
            WHERE UPPER(Email) = UPPER(?)
        """
        with self._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(query, email)
            rows = cursor.fetchall()

        return [
            CandidateRecord(
                candidate_id=row.CandidateID,
                first_name=row.FirstName,
                last_name=row.LastName,
                email=row.Email,
                password=row.Password,
                birth_date=row.Birthdate if row.Birthdate else None,
                ssn=row.SSN,
                over_18_age=bool(row.Over18Age) if row.Over18Age is not None else None,
                mobile=row.Mobile,
                home=row.Home,
                work=row.Work,
                work_ext=row.WorkExt,
                relocation=bool(row.Relocation) if row.Relocation is not None else None,
            )
            for row in rows
        ]

