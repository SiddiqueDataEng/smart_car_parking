"""
Centralized logging utility for SMART Parking Solutions pipeline.
All modules import from here for consistent log formatting.
"""
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

import yaml


def load_config():
    """Load project configuration from config.yaml."""
    config_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger writing to both console and the log file
    defined in config.yaml.
    """
    config = load_config()
    log_cfg = config.get("logging", {})

    log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_file = Path(__file__).resolve().parents[2] / log_cfg.get("file", "logs/pipeline.log")
    log_fmt = log_cfg.get(
        "format", "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Avoid duplicate handlers when imported multiple times
    if not logger.handlers:
        formatter = logging.Formatter(log_fmt)

        # File handler
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(log_level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger


# ── quick self-test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log = get_logger("logger_test")
    log.info("Logger initialised successfully — SMART Parking Solutions")
    log.info("Log file: %s", Path(__file__).resolve().parents[2] / "logs" / "pipeline.log")
    print("\n✅  Logger test passed — check logs/pipeline.log")
