import logging

from core.foundation.paths import core_paths

# ==========          CORE LOGGING          ==========

def setup_core_logging() -> logging.Logger:
    """
    Configure and return the main CORE logger.

    The logger writes to both the console and the CORE log file.
    For version 0.1 this setup is intentionally simple.
    """
    core_paths.ensure_required_dirs()

    logger = logging.getLogger("core")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        core_paths.logs / "core.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


core_logger = setup_core_logging()