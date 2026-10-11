"""Audit logging module for AAPA with zero-leakage sensitive data redaction."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from aapa.config import get_aapa_data_dir
from aapa.secret_filter import redact_secrets, sanitize_dict


class SensitiveDataFilter(logging.Filter):
    """Logging filter that ensures no secrets leak into standard log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = sanitize_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_secrets(a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def setup_application_logging(level: str = "INFO", log_file: Optional[Path] = None) -> logging.Logger:
    """Configures root logger with secret redaction filter."""
    logger = logging.getLogger("aapa")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SensitiveDataFilter())
        logger.addHandler(file_handler)

    return logger


class AuditLogger:
    """Thread-safe structured audit logger persisting events in JSONL format."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or (get_aapa_data_dir() / "audit.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event_type: str,
        request_id: str,
        action: str,
        cwd: str,
        risk_level: str,
        decision: str,
        recommendation: str,
        explanation: str,
        rule_name: str,
        user_confirmed: Optional[bool] = None,
        antigravity_response: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Appends a sanitized, timestamped event to the audit log."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "request_id": request_id,
            "action": redact_secrets(action),
            "cwd": redact_secrets(cwd),
            "risk_level": risk_level,
            "decision": decision,
            "recommendation": recommendation,
            "explanation": redact_secrets(explanation),
            "rule_name": rule_name,
            "user_confirmed": user_confirmed,
            "antigravity_response": antigravity_response,
            "metadata": sanitize_dict(metadata or {}),
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def get_recent_entries(
        self,
        limit: int = 100,
        project_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Reads recent audit log entries in reverse chronological order."""
        if not self.log_path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if project_path:
                            record_cwd = record.get("cwd", "")
                            if project_path.lower() not in record_cwd.lower():
                                continue
                        entries.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            logging.getLogger("aapa").error("Failed to read audit log: %s", exc)

        entries.reverse()
        return entries[:limit]
