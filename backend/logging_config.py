"""Three-file logging setup with rotation.

- application.log  general info, request lifecycle, errors
- security.log     auth failures, replay, missing headers, revoked connectors
- sync.log         structured summary of every successful sync

We never write secrets, signatures, or raw request bodies to any log. The
security + sync loggers do NOT propagate to root, so they are the sole
destination for their events (avoids leakage into application.log too).
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
_BACKUPS = 5

_APP_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_JSON_FORMAT = "%(asctime)s %(levelname)s %(message)s"


def _handler(path: Path, fmt: str) -> RotatingFileHandler:
    handler = RotatingFileHandler(path, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8")
    handler.setFormatter(logging.Formatter(fmt))
    return handler


def configure_logging() -> None:
    """Wire up application/security/sync loggers. Idempotent."""
    log_dir = Path(os.environ.get("LOG_DIR", "/app/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    # --- Root / application ---------------------------------------------------
    root = logging.getLogger()
    if not any(getattr(h, "_razio", False) for h in root.handlers):
        app_handler = _handler(log_dir / "application.log", _APP_FORMAT)
        app_handler._razio = True  # type: ignore[attr-defined]
        root.addHandler(app_handler)
        # Keep stderr too, so supervisor's log tail still shows things.
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter(_APP_FORMAT))
        stream._razio = True  # type: ignore[attr-defined]
        root.addHandler(stream)
        root.setLevel(logging.INFO)

    # --- Security -------------------------------------------------------------
    sec = logging.getLogger("razio.security")
    if not sec.handlers:
        sec.addHandler(_handler(log_dir / "security.log", _JSON_FORMAT))
        sec.setLevel(logging.INFO)
        sec.propagate = False

    # --- Sync -----------------------------------------------------------------
    syn = logging.getLogger("razio.sync")
    if not syn.handlers:
        syn.addHandler(_handler(log_dir / "sync.log", _JSON_FORMAT))
        syn.setLevel(logging.INFO)
        syn.propagate = False


def security_logger() -> logging.Logger:
    return logging.getLogger("razio.security")


def sync_logger() -> logging.Logger:
    return logging.getLogger("razio.sync")


def app_logger() -> logging.Logger:
    return logging.getLogger("razio.app")
