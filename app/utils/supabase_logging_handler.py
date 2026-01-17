
"""
Custom Logging Handler for Supabase.

This module provides a thread-safe, non-blocking logging handler that pushes logs
to a Supabase table ('auto_apply_apis_logs'). It uses a background worker thread to process
log records from a queue, ensuring that the main application thread is never blocked
by network operations.
"""

import logging
import threading
import queue
import time
import json
import traceback
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from config import get_settings
from supabase import create_client, Client


class SafeSupabaseHandler(logging.Handler):
    """
    A non-blocking logging handler that writes to Supabase.
    
    Features:
    - Uses a Queue and Worker Thread to avoid blocking the main thread.
    - Filters: Logs standard ERRORs automatically. Logs INFO/WARNING only if 
      explicitly flagged with extra={'log_to_db': True}.
    - Robustness: Handles network failures gracefully (logs locally instead).
    - Table: auto_apply_apis_logs
    """
    
    def __init__(self, buffer_size: int = 1000, flush_interval: float = 1.0):
        super().__init__()
        self.log_queue = queue.Queue(maxsize=buffer_size)
        self.stop_event = threading.Event()
        self.flush_interval = flush_interval
        self._client: Optional[Client] = None
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="SupabaseLoggerWorker")
        self._worker_thread.start()
        
    def _get_client(self) -> Optional[Client]:
        """Lazy initialization of Supabase client."""
        if self._client:
            return self._client
            
        try:
            settings = get_settings()
            url = settings.supabase_url
            # Use service key if available for writing logs
            key = settings.supabase_service_key or settings.supabase_service_role_key
            
            if url and key:
                self._client = create_client(url, key.get_secret_value())
                return self._client
        except Exception:
            # If settings fail (e.g. during startup), return None
            pass
        return None

    def emit(self, record: logging.LogRecord):
        """
        Emit a log record.
        
        This method formats the record and puts it into the queue.
        It is non-blocking (unless queue is full, in which case it drops checks).
        """
        try:
            # Filter logic:
            # 1. Always log ERROR / CRITICAL
            # 2. Log INFO / WARNING only if extra={'log_to_db': True} is present
            
            should_log = False
            if record.levelno >= logging.ERROR:
                should_log = True
            else:
                # Check for 'log_to_db' in record.__dict__ or args
                if getattr(record, 'log_to_db', False):
                    should_log = True
            
            if not should_log:
                return

            # Prepare message
            msg = self.format(record)
            
            # Extract metadata
            metadata = {
                "filename": record.filename,
                "funcName": record.funcName,
                "lineno": record.lineno,
                "module": record.module,
                "timestamp_iso": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
            }
            
            # Extract additional extra fields
            standard_attrs = set(logging.LogRecord('', 0, '', 0, '', (), None).__dict__.keys())
            standard_attrs.add('message')
            standard_attrs.add('asctime')
            standard_attrs.add('created')
            standard_attrs.add('msecs')
            standard_attrs.add('relativeCreated')
            
            for key, value in record.__dict__.items():
                if key not in standard_attrs and key != 'log_to_db' and not key.startswith('_'):
                    try:
                        # Ensure value is serializable
                        json.dumps(value) 
                        metadata[key] = value
                    except (TypeError, OverflowError):
                        metadata[key] = str(value)

            # Add stack trace for errors
            if record.exc_info:
                metadata["stack_trace"] = traceback.format_exception(*record.exc_info)

            log_entry = {
                "service_name": getattr(record, "service_name", "api_service"), 
                "level": record.levelname,
                "message": msg,
                "metadata": metadata,
                # Use current UTC time for creation if DB default doesn't catch it roughly correct
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            try:
                self.log_queue.put_nowait(log_entry)
            except queue.Full:
                # Drop if full to non-block
                import sys
                print(f"Supabase Logging Queue Full! Dropped log: {msg}", file=sys.stderr)

        except Exception:
            self.handleError(record)

    def _worker_loop(self):
        """
        Background worker that consumes logs from the queue and batch inserts into Supabase.
        """
        batch = []
        last_flush = time.time()
        
        while not self.stop_event.is_set():
            try:
                # Wait for items
                try:
                    record = self.log_queue.get(timeout=0.5)
                    batch.append(record)
                except queue.Empty:
                    pass
                
                current_time = time.time()
                # Flush conditions
                if batch and (len(batch) >= 10 or (current_time - last_flush) >= self.flush_interval):
                    self._flush_batch(batch)
                    batch = []
                    last_flush = current_time
                    
            except Exception as e:
                import sys
                print(f"Error in Supabase Logger Worker: {e}", file=sys.stderr)
                time.sleep(1) 

        if batch:
            self._flush_batch(batch)

    def _flush_batch(self, batch):
        """Send batch of logs to Supabase table auto_apply_apis_logs."""
        client = self._get_client()
        if not client:
            return 
            
        try:
            # Using the specific table name provided by user
            client.table("auto_apply_apis_logs").insert(batch).execute()
        except Exception as e:
            import sys
            # Fallback log to stderr
            print(f"Failed to push logs to Supabase: {e}", file=sys.stderr)
            
    def close(self):
        """Cleanup handler."""
        self.stop_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        super().close()
