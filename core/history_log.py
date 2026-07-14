# core/history_log.py
from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_CSV = LOG_DIR / "history_log.csv"

FIELDNAMES: list[str] = [
    "timestamp",
    "status",
    "action",
    "message",
    "file_name",
    "tax_number",
    "environment",
    "details"
]

def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default

def _build_row(
    *,
    status: str,
    action: str,
    message: str,
    file_name: str = "",
    tax_number: str = "",
    environment: str = "",
    details: str = "",
) -> dict[str, str]:
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": _safe_text(status),
        "action": _safe_text(action),
        "message": _safe_text(message),
        "file_name": _safe_text(file_name),
        "tax_number": _safe_text(tax_number),
        "environment": _safe_text(environment),
        "details": _safe_text(details),
    }

def _ensure_file() -> None:
    if HISTORY_CSV.exists():
        return
    with HISTORY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

def log_history(
    *,
    status: str,
    action: str,
    message: str,
    file_name: str = "",
    tax_number: str = "",
    environment: str = "",
    details: str = "",
) -> dict[str, str]:
    """Központi tranzakció-író függvény, amely rögzíti a sorokat a history_log.csv fájlba."""
    _ensure_file()
    row = _build_row(
        status=status, action=action, message=message,
        file_name=file_name, tax_number=tax_number,
        environment=environment, details=details
    )
    try:
        with HISTORY_CSV.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writerow(row)
    except Exception as e:
        logger.error(f"Sikertelen írás a history_log.csv fájlba: {e}")
    return row

def log_upload_ok(file_name: str, environment: str = "", details: str = "") -> dict[str, str]:
    return log_history(
        status="SUCCESS",
        action="UPLOAD",
        message="A feltöltés sikeresen befejeződött.",
        file_name=file_name,
        environment=environment,
        details=details,
    )

def log_upload_error(message: str, file_name: str = "", environment: str = "", details: str = "") -> dict[str, str]:
    return log_history(
        status="ERROR",
        action="UPLOAD",
        message=message,
        file_name=file_name,
        environment=environment,
        details=details,
    )

def log_kapcsolat_teszt_ok(details: str = "") -> dict[str, str]:
    return log_history(
        status="SUCCESS",
        action="KAPCSOLAT_TESZT",
        message="A kapcsolatteszt sikeres volt.",
        details=details,
    )

def log_kapcsolat_teszt_error(message: str, details: str = "") -> dict[str, str]:
    return log_history(
        status="ERROR",
        action="KAPCSOLAT_TESZT",
        message=message,
        details=details,
    )

def read_history(limit: int = 100) -> list[dict[str, str]]:
    """Beolvassa és visszaadja a naplózott tranzakciókat."""
    _ensure_file()
    rows: list[dict[str, str]] = []
    try:
        with HISTORY_CSV.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
    except Exception as e:
        logger.error(f"Sikertelen olvasás a history_log.csv fájlból: {e}")
    return rows[-limit:]