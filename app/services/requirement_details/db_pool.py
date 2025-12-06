"""
Database connection and pooling module for Requirement Details API.

This module provides async database connection pooling using pyodbc
for the Requirement Details API.
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
    Get database connection string from unified settings.
    
    Returns:
        str: A formatted connection string for pyodbc.
    """
    settings = get_settings()
    
    # Strip curly braces from driver name if present (handle both formats)
    driver = settings.requirement_details_db_driver.strip()
    if driver.startswith("{") and driver.endswith("}"):
        driver = driver[1:-1]  # Remove existing braces
    
    if settings.requirement_details_db_user and settings.requirement_details_db_password:
        # SQL Server Authentication
        password = settings.requirement_details_db_password.get_secret_value()
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={settings.requirement_details_db_server};"
            f"DATABASE={settings.requirement_details_db_name};"
            f"UID={settings.requirement_details_db_user};"
            f"PWD={password};"
            f"TrustServerCertificate=yes;"
        )
    else:
        # Windows Authentication
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={settings.requirement_details_db_server};"
            f"DATABASE={settings.requirement_details_db_name};"
            f"Trusted_Connection=yes;"
            f"TrustServerCertificate=yes;"
        )


class DatabasePool:
    """
    Database connection pool for SQL Server using pyodbc.
    
    Manages a pool of pyodbc connections that can be reused across
    async operations. Connections are created on-demand and cached
    for reuse.
    
    Attributes:
        connection_string (str): SQL Server connection string
        pool_size (int): Maximum number of connections in the pool
        _pool (list): List of available connections
        _lock (asyncio.Lock): Lock for thread-safe operations
        _initialized (bool): Whether the pool has been initialized
    """
    
    def __init__(self, connection_string: str, pool_size: int = 20):
        """
        Initialize the database connection pool.
        
        Args:
            connection_string (str): SQL Server connection string
            pool_size (int): Maximum number of connections in the pool
        """
        self.connection_string = connection_string
        self.pool_size = pool_size
        self._pool: list[pyodbc.Connection] = []
        self._lock = asyncio.Lock()
        self._initialized = False
        logger.info(f"Database pool initialized with size {pool_size}")
    
    async def initialize(self):
        """Initialize the connection pool by creating initial connections."""
        if self._initialized:
            return
        
        async with self._lock:
            if self._initialized:
                return
            
            # Create initial connections
            for _ in range(self.pool_size):
                try:
                    conn = pyodbc.connect(self.connection_string, timeout=10)
                    self._pool.append(conn)
                except pyodbc.Error as e:
                    logger.error(f"Failed to create database connection: {e}")
                    raise
            
            self._initialized = True
            logger.info(f"Database pool initialized with {self.pool_size} connections")
    
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
                logger.debug("Reusing connection from pool")
                return conn
            else:
                # If pool is exhausted, create a new connection
                logger.debug("Pool exhausted, creating new connection")
                return pyodbc.connect(self.connection_string, timeout=10)
    
    async def return_connection(self, conn: pyodbc.Connection):
        """
        Return a connection to the pool.
        
        Checks if the connection is still alive before returning it.
        If the connection is dead, creates a new one.
        
        Args:
            conn (pyodbc.Connection): The connection to return to the pool
        """
        # Check if connection is still alive
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except Exception as e:
            # Connection is dead, create a new one
            logger.warning(f"Connection health check failed: {e}, creating new connection")
            try:
                conn.close()
            except:
                pass
            conn = pyodbc.connect(self.connection_string, timeout=10)
        
        async with self._lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(conn)
                logger.debug("Connection returned to pool")
            else:
                # Pool is full, close the connection
                try:
                    conn.close()
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
            for conn in self._pool:
                try:
                    conn.close()
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
        
    Raises:
        RuntimeError: If database pool initialization fails
    """
    global _db_pool
    
    if _db_pool is None:
        try:
            settings = get_settings()
            connection_string = get_connection_string()
            _db_pool = DatabasePool(
                connection_string,
                pool_size=settings.requirement_details_db_pool_size
            )
            await _db_pool.initialize()
            logger.info("Global database pool created for Requirement Details API")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise RuntimeError(f"Database pool initialization failed: {e}")
    
    return _db_pool


async def close_db_pool():
    """
    Close the global database pool and all its connections.
    
    This should be called during application shutdown.
    """
    global _db_pool
    
    if _db_pool is not None:
        await _db_pool.close_all()
        _db_pool = None
        logger.info("Global database pool closed for Requirement Details API")

