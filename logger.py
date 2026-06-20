"""
logger.py  —  نظام تسجيل الأحداث المركزي لـ GUSS
===================================================
يوفر تسجيل أحداث مُوحَّد بمستويين:
  - Console: مُنسَّق، مستوى INFO
  - ملف دوّار: مستوى DEBUG، يُحفظ في reports/

الاستخدام:
    from logger import get_logger
    log = get_logger("module_name")
    log.info("عملية ناجحة")
    log.warning("تحذير: %s", detail)
    log.error("فشل: %s", error)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False
_LOG_DIR: Path | None = None


def _setup_root(log_dir: Path | None = None) -> None:
    """يُهيّئ نظام التسجيل مرة واحدة عند أول استدعاء."""
    global _configured, _LOG_DIR
    if _configured:
        return

    root = logging.getLogger("guss")
    root.setLevel(logging.DEBUG)
    # لمنع التكرار إذا كان هناك handler افتراضي
    root.propagate = False

    # ── Console Handler (INFO+) ─────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter("%(message)s")
    console.setFormatter(console_fmt)
    root.addHandler(console)

    # ── File Handler (DEBUG+, دوّار 5 MB × 5 نسخ) ──────────────────────
    if log_dir is None:
        log_dir = Path(__file__).parent / "reports"
    log_dir.mkdir(exist_ok=True)
    _LOG_DIR = log_dir

    log_file = log_dir / f"guss_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    يُعيد logger مُهيَّأ تحت مساحة أسماء 'guss'.

    Args:
        name: اسم الوحدة (مثال: 'sheets', 'ai_engine', 'pipeline')

    Returns:
        logging.Logger مُهيَّأ بـ Console + File handlers.
    """
    _setup_root()
    return logging.getLogger(f"guss.{name}")


def get_log_dir() -> Path | None:
    """يُعيد مسار مجلد ملفات السجل."""
    return _LOG_DIR
