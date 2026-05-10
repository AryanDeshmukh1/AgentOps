"""Centralized logger for all agents."""
import logging
import os

def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.
    Use as: logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    return logger