import json
import logging
import sys
from typing import Any, Dict


def setup_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure application logging."""

    level_value = getattr(logging, level.upper(), logging.INFO)
    logging.captureWarnings(True)

    if json_output:
        logging.basicConfig(
            level=level_value,
            format="%(message)s",
            stream=sys.stdout,
        )
        logging.getLogger().handlers[0].addFilter(_JsonMessageAdapter())
    else:
        logging.basicConfig(
            level=level_value,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            stream=sys.stdout,
        )


class _JsonMessageAdapter(logging.Filter):
    """Transform log records into JSON payloads."""

    def filter(self, record: logging.LogRecord) -> bool:
        payload: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = logging.Formatter().formatException(record.exc_info)
        record.msg = json.dumps(payload, ensure_ascii=False)
        record.args = ()
        return True

