#!/usr/bin/env python3
"""
Logging Configuration for Mathematricks Trader
Centralized logging with file and console handlers
"""

import logging
import os
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


def setup_logger(
    name: str,
    log_file: str = None,
    level: str = None,
    console_output: bool = True
) -> logging.Logger:
    """
    Set up a logger with file and console handlers

    Args:
        name: Logger name
        log_file: Log file name (defaults to {name}.log)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Whether to output to console

    Returns:
        Configured logger instance
    """
    # Get logger
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Set level
    log_level = getattr(logging, (level or os.getenv('LOG_LEVEL', 'INFO')).upper())
    logger.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler with rotation
    if log_file is None:
        log_file = f"{name}.log"

    file_path = LOGS_DIR / log_file
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler (optional)
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)

    # If logger doesn't have handlers, set it up
    if not logger.handlers:
        return setup_logger(name)

    return logger


# Create main application logger
main_logger = setup_logger('mathematricks_trader', 'main.log')
