import asyncio
import logging
from typing import Callable, Type, Tuple, Optional, Any
from functools import wraps

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Base exception for retryable errors"""
    pass


class NonRetryableError(Exception):
    """Base exception for non-retryable errors"""
    pass


def is_retryable_exception(exception: Exception) -> bool:
    """
    Determine if an exception should be retried
    
    Args:
        exception: The exception to check
        
    Returns:
        bool: True if exception should be retried, False otherwise
    """
    # Network/connection errors - retryable
    if isinstance(exception, (ConnectionError, TimeoutError, OSError)):
        return True
    
    # Database connection errors - retryable
    error_str = str(exception).lower()
    retryable_keywords = [
        'connection',
        'timeout',
        'network',
        'temporary',
        'retry',
        'deadlock',
        'lock',
        'busy',
        'unavailable',
        '503',  # Service unavailable
        '502',  # Bad gateway
        '504',  # Gateway timeout
    ]
    
    if any(keyword in error_str for keyword in retryable_keywords):
        return True
    
    # Specific non-retryable errors
    non_retryable_keywords = [
        'syntax error',
        'invalid',
        'not found',
        'permission denied',
        'authentication',
        'authorization',
        'foreign key',
        'unique constraint',
        '23503',  # Foreign key violation
        '23505',  # Unique violation
    ]
    
    if any(keyword in error_str for keyword in non_retryable_keywords):
        return False
    
    # Default: retry for unknown errors (could be transient)
    return True


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    **kwargs
) -> Any:
    """
    Retry a function with exponential backoff
    
    Args:
        func: The function to retry (can be sync or async)
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delay
        **kwargs: Keyword arguments for the function
        
    Returns:
        The result of the function call
        
    Raises:
        Exception: The last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            # Check if function is async
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            if attempt > 0:
                logger.info(f"Operation succeeded after {attempt} retry(ies)")
            
            return result
            
        except Exception as e:
            last_exception = e
            
            # Check if exception is retryable
            if not is_retryable_exception(e):
                logger.warning(f"Non-retryable exception: {str(e)}. Not retrying.")
                raise
            
            # Don't retry on last attempt
            if attempt >= max_retries:
                logger.error(f"Operation failed after {max_retries} retries. Last error: {str(e)}")
                raise
            
            # Calculate delay with exponential backoff
            delay = min(
                initial_delay * (exponential_base ** attempt),
                max_delay
            )
            
            # Add jitter to prevent thundering herd
            if jitter:
                import random
                jitter_amount = delay * 0.1  # 10% jitter
                delay = delay + random.uniform(-jitter_amount, jitter_amount)
                delay = max(0, delay)  # Ensure non-negative
            
            logger.warning(
                f"Operation failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. "
                f"Retrying in {delay:.2f} seconds..."
            )
            
            await asyncio.sleep(delay)
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception


def retry_async(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    Decorator for async functions with retry logic
    
    Usage:
        @retry_async(max_retries=3, initial_delay=1.0)
        async def my_async_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                func,
                *args,
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
                **kwargs
            )
        return wrapper
    return decorator

