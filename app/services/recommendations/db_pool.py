"""
Database connection pool manager module for Recommendations API.

This module provides async database connection pooling using pyodbc
with thread-safe connection management.
"""

import pyodbc
import asyncio
from typing import Optional
from contextlib import asynccontextmanager
from queue import Queue, Empty
import threading
import logging
from config import get_settings

# Configure logging
logger = logging.getLogger(__name__)


def get_connection_string() -> str:
    """
    Constructs the SQL Server connection string for Recommendations API.
    
    Returns:
        str: A formatted connection string for pyodbc.
    """
    settings = get_settings()
    
    if settings.recommendations_db_username and settings.recommendations_db_password:
        # SQL Server Authentication
        password = settings.recommendations_db_password.get_secret_value()
        conn_str = (
            f"DRIVER={{{settings.recommendations_db_driver}}};"
            f"SERVER={settings.recommendations_db_server};"
            f"DATABASE={settings.recommendations_db_database};"
            f"UID={settings.recommendations_db_username};"
            f"PWD={password};"
            f"TrustServerCertificate={settings.recommendations_db_trust_server_certificate};"
            f"Encrypt={settings.recommendations_db_encrypt};"
        )
    else:
        # Windows Authentication
        conn_str = (
            f"DRIVER={{{settings.recommendations_db_driver}}};"
            f"SERVER={settings.recommendations_db_server};"
            f"DATABASE={settings.recommendations_db_database};"
            f"Trusted_Connection=yes;"
            f"TrustServerCertificate={settings.recommendations_db_trust_server_certificate};"
            f"Encrypt={settings.recommendations_db_encrypt};"
        )
    
    return conn_str


class DatabasePool:
    """
    Thread-safe database connection pool for SQL Server.
    
    Manages a pool of pyodbc connections that can be reused across
    async operations. Connections are created on-demand and cached
    for reuse.
    """
    
    def __init__(
        self,
        connection_string: str,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30
    ):
        """
        Initialize the database connection pool.
        
        Args:
            connection_string (str): SQL Server connection string
            pool_size (int): Maximum number of connections in the pool
            max_overflow (int): Maximum additional connections beyond pool_size
            pool_timeout (int): Timeout in seconds for acquiring a connection
        """
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self._pool: Queue = Queue(maxsize=pool_size + max_overflow)
        self._created_connections = 0
        self._lock = threading.Lock()
        logger.info(f"Database pool initialized with size {pool_size}, max overflow {max_overflow}")
    
    def _create_connection(self) -> pyodbc.Connection:
        """Create a new database connection."""
        try:
            conn = pyodbc.connect(self.connection_string, timeout=10)
            logger.debug("New database connection created")
            return conn
        except pyodbc.Error as e:
            logger.error(f"Failed to create database connection: {e}")
            raise
    
    def _is_connection_alive(self, conn: pyodbc.Connection) -> bool:
        """Check if a database connection is still alive and usable."""
        try:
            if conn.closed:
                return False
            
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        except (pyodbc.Error, AttributeError, Exception) as e:
            logger.debug(f"Connection health check failed: {e}")
            return False
    
    def _get_connection(self) -> Optional[pyodbc.Connection]:
        """Get a connection from the pool or create a new one."""
        try:
            conn = self._pool.get_nowait()
            
            if self._is_connection_alive(conn):
                logger.debug("Reusing existing connection from pool")
                return conn
            else:
                try:
                    conn.close()
                except Exception:
                    pass
                logger.warning("Dead connection removed from pool, creating new one")
                with self._lock:
                    self._created_connections -= 1
        except Empty:
            pass
        
        with self._lock:
            if self._created_connections < self.pool_size + self.max_overflow:
                conn = self._create_connection()
                self._created_connections += 1
                logger.debug(f"Created new connection. Total: {self._created_connections}")
                return conn
        
        return None
    
    def _return_connection(self, conn: pyodbc.Connection) -> None:
        """Return a connection to the pool."""
        try:
            self._pool.put_nowait(conn)
            logger.debug("Connection returned to pool")
        except:
            try:
                conn.close()
                with self._lock:
                    self._created_connections -= 1
                logger.debug("Pool full, connection closed")
            except:
                pass
    
    @asynccontextmanager
    async def get_connection(self):
        """
        Async context manager for getting a database connection from the pool.
        
        Yields:
            pyodbc.Connection: A database connection from the pool
        """
        loop = asyncio.get_event_loop()
        start_time = asyncio.get_event_loop().time()
        conn = None
        
        while conn is None:
            conn = await loop.run_in_executor(None, self._get_connection)
            
            if conn is None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= self.pool_timeout:
                    raise TimeoutError(
                        f"Failed to acquire connection from pool within {self.pool_timeout} seconds"
                    )
                await asyncio.sleep(0.1)
        
        try:
            yield conn
        finally:
            await loop.run_in_executor(None, self._return_connection, conn)
    
    def close_all(self) -> None:
        """Close all connections in the pool."""
        logger.info("Closing all connections in pool")
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass
        
        with self._lock:
            self._created_connections = 0
        logger.info("All connections closed")


# Global database pool instance
_db_pool: Optional[DatabasePool] = None


def get_db_pool() -> DatabasePool:
    """
    Get or create the global database pool instance.
    
    Returns:
        DatabasePool: The global database connection pool
    """
    global _db_pool
    
    if _db_pool is None:
        try:
            settings = get_settings()
            connection_string = get_connection_string()
            _db_pool = DatabasePool(
                connection_string=connection_string,
                pool_size=settings.recommendations_db_pool_size,
                max_overflow=settings.recommendations_db_max_overflow,
                pool_timeout=settings.recommendations_db_pool_timeout
            )
            logger.info("Global database pool created")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise RuntimeError(f"Database pool initialization failed: {e}")
    
    return _db_pool


def close_db_pool() -> None:
    """Close the global database pool and all its connections."""
    global _db_pool
    
    if _db_pool is not None:
        _db_pool.close_all()
        _db_pool = None
        logger.info("Global database pool closed")

