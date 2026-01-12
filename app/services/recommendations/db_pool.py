"""
Database connection pool manager module for Recommendations API.

This module provides async database connection pooling using pyodbc
with thread-safe connection management.
"""

import pyodbc
import asyncio
from typing import Optional
from contextlib import asynccontextmanager
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
    Async database connection pool for SQL Server.
    
    Manages a pool of pyodbc connections that can be reused across
    async operations. Connections are pre-initialized at startup
    for better reliability and performance.
    
    Attributes:
        connection_string (str): SQL Server connection string
        pool_size (int): Maximum number of connections in the pool
        _pool (list): List of available connections
        _lock (asyncio.Lock): Lock for thread-safe operations
        _initialized (bool): Whether the pool has been initialized
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
            max_overflow (int): Maximum additional connections beyond pool_size (for compatibility)
            pool_timeout (int): Timeout in seconds for acquiring a connection (for compatibility)
        """
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.max_overflow = max_overflow  # Kept for compatibility
        self.pool_timeout = pool_timeout  # Kept for compatibility
        self._pool: list[pyodbc.Connection] = []
        self._lock = asyncio.Lock()
        self._initialized = False
        logger.info(f"Database pool initialized with size {pool_size}, max overflow {max_overflow}")
    
    def _sanitize_connection_string(self, conn_str: str) -> str:
        """Sanitize connection string for logging (remove password)."""
        import re
        return re.sub(r'PWD=([^;]+)', 'PWD=***', conn_str, flags=re.IGNORECASE)
    
    async def initialize(self):
        """Initialize the connection pool by creating initial connections."""
        if self._initialized:
            return
        
        async with self._lock:
            if self._initialized:
                return
            
            logger.info(f"Initializing database pool with {self.pool_size} connections...")
            logger.debug(f"Connection string: {self._sanitize_connection_string(self.connection_string)}")
            
            # Create initial connections
            loop = asyncio.get_event_loop()
            for i in range(self.pool_size):
                try:
                    conn = await loop.run_in_executor(
                        None, 
                        lambda: pyodbc.connect(self.connection_string, timeout=30)
                    )
                    self._pool.append(conn)
                    logger.debug(f"Created connection {i+1}/{self.pool_size}")
                except pyodbc.Error as e:
                    error_code = e.args[0] if e.args else 'UNKNOWN'
                    error_msg = e.args[1] if len(e.args) > 1 else str(e)
                    logger.error(f"Failed to create database connection {i+1}/{self.pool_size}")
                    logger.error(f"PyODBC Error Code: {error_code}")
                    logger.error(f"PyODBC Error Message: {error_msg}")
                    logger.error(f"Connection string: {self._sanitize_connection_string(self.connection_string)}")
                    raise
            
            self._initialized = True
            logger.info(f"Database pool initialized with {len(self._pool)} connections")
    
    async def _is_connection_alive(self, conn: pyodbc.Connection) -> bool:
        """Check if a database connection is still alive and usable."""
        try:
            if conn.closed:
                logger.debug("Connection is closed")
                return False
            
            loop = asyncio.get_event_loop()
            
            def _check():
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return True
            
            result = await loop.run_in_executor(None, _check)
            return result
        except (pyodbc.Error, AttributeError, Exception) as e:
            logger.debug(f"Connection health check failed: {e}")
            return False
    
    async def get_connection(self) -> pyodbc.Connection:
        """
        Get a connection from the pool.
        
        Returns:
            pyodbc.Connection: A database connection from the pool
        """
        if not self._initialized:
            await self.initialize()
        
        async with self._lock:
            if self._pool:
                conn = self._pool.pop()
                logger.debug(f"Reusing connection from pool ({len(self._pool)} remaining)")
                
                # Verify connection is alive
                if await self._is_connection_alive(conn):
                    return conn
                else:
                    # Connection is dead, create a new one
                    logger.warning("Dead connection detected, creating new connection")
                    try:
                        await asyncio.get_event_loop().run_in_executor(None, conn.close)
                    except:
                        pass
            
            # If pool is exhausted or connection was dead, create a new connection
            logger.debug("Pool exhausted or connection dead, creating new connection")
            loop = asyncio.get_event_loop()
            try:
                conn = await loop.run_in_executor(
                    None,
                    lambda: pyodbc.connect(self.connection_string, timeout=30)
                )
                return conn
            except pyodbc.Error as e:
                error_code = e.args[0] if e.args else 'UNKNOWN'
                error_msg = e.args[1] if len(e.args) > 1 else str(e)
                logger.error(f"Failed to create new database connection")
                logger.error(f"PyODBC Error Code: {error_code}")
                logger.error(f"PyODBC Error Message: {error_msg}")
                raise
    
    async def return_connection(self, conn: pyodbc.Connection):
        """
        Return a connection to the pool.
        
        Checks if the connection is still alive before returning it.
        If the connection is dead, creates a new one.
        
        Args:
            conn (pyodbc.Connection): The connection to return to the pool
        """
        # Check if connection is still alive
        is_alive = await self._is_connection_alive(conn)
        
        if not is_alive:
            # Connection is dead, create a new one
            logger.warning("Connection health check failed during return, creating new connection")
            try:
                await asyncio.get_event_loop().run_in_executor(None, conn.close)
            except:
                pass
            
            try:
                loop = asyncio.get_event_loop()
                conn = await loop.run_in_executor(
                    None,
                    lambda: pyodbc.connect(self.connection_string, timeout=30)
                )
            except pyodbc.Error as e:
                error_code = e.args[0] if e.args else 'UNKNOWN'
                error_msg = e.args[1] if len(e.args) > 1 else str(e)
                logger.error(f"Failed to recreate connection during return")
                logger.error(f"PyODBC Error Code: {error_code}")
                logger.error(f"PyODBC Error Message: {error_msg}")
                # Don't raise, just don't return the connection to pool
                return
        
        async with self._lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(conn)
                logger.debug(f"Connection returned to pool ({len(self._pool)} available)")
            else:
                # Pool is full, close the connection
                try:
                    await asyncio.get_event_loop().run_in_executor(None, conn.close)
                    logger.debug("Pool full, connection closed")
                except:
                    pass
    
    @asynccontextmanager
    async def get_connection_context(self):
        """
        Context manager for getting a connection from the pool.
        
        Yields:
            pyodbc.Connection: A database connection from the pool
            
        Example:
            >>> async with pool.get_connection_context() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("SELECT * FROM table")
        """
        conn = await self.get_connection()
        try:
            yield conn
        finally:
            await self.return_connection(conn)
    
    async def close_all(self):
        """Close all connections in the pool."""
        async with self._lock:
            logger.info(f"Closing all {len(self._pool)} connections in pool")
            for conn in self._pool:
                try:
                    await asyncio.get_event_loop().run_in_executor(None, conn.close)
                except:
                    pass
            self._pool.clear()
            self._initialized = False
            logger.info("All database connections closed")


# Global database pool instance
_db_pool: Optional[DatabasePool] = None


async def get_db_pool() -> DatabasePool:
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
            await _db_pool.initialize()
            logger.info("Global database pool created")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise RuntimeError(f"Database pool initialization failed: {e}")
    
    return _db_pool


async def close_db_pool() -> None:
    """Close the global database pool and all its connections."""
    global _db_pool
    
    if _db_pool is not None:
        await _db_pool.close_all()
        _db_pool = None
        logger.info("Global database pool closed")


