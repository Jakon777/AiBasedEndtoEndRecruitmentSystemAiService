import logging
import os
import sys

# ANSI Colors matching Spring Boot's default logback console output
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BOLD = "\033[1m"

COLOR_MAP = {
    "DEBUG": "\033[34m",   # Blue
    "INFO": GREEN,
    "WARNING": YELLOW,
    "WARN": YELLOW,
    "ERROR": RED,
    "CRITICAL": "\033[41m\033[37m",  # White on Red
}


class SpringBootLogFormatter(logging.Formatter):
    """
    Formats logs to exactly match Spring Boot 3 standard console logs:
    2026-10-06 00:30:21.456  INFO 12345 --- [     MainThread] c.a.A.service.ShortlistService      : Log message
    """

    def __init__(self, use_color: bool = True):
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        # Timestamp with milliseconds
        asctime = self.formatTime(record, self.datefmt)
        msecs = f"{int(record.msecs):03d}"
        timestamp = f"{asctime}.{msecs}"

        # Level name padded to 5 chars (matching Spring Boot)
        levelname = record.levelname
        if levelname == "WARNING":
            levelname = "WARN"
        padded_level = f"{levelname:>5}"

        # Process and thread
        process = record.process
        thread_name = record.threadName
        if len(thread_name) > 15:
            thread_name = thread_name[:12] + "..."
        thread_field = f"[{thread_name:>15}]"

        # Logger name padded / truncated to 35 chars
        logger_name = record.name
        if len(logger_name) > 35:
            # Shorten like Java package: a.b.c.d
            parts = logger_name.split(".")
            if len(parts) > 1:
                logger_name = ".".join(p[0] for p in parts[:-1]) + "." + parts[-1]
            if len(logger_name) > 35:
                logger_name = logger_name[-35:]
        logger_field = f"{logger_name:<35}"

        message = record.getMessage()

        if self.use_color:
            level_color = COLOR_MAP.get(levelname, "")
            formatted = (
                f"{CYAN}{timestamp}{RESET} "
                f"{level_color}{padded_level}{RESET} "
                f"{MAGENTA}{process}{RESET} --- "
                f"{thread_field} "
                f"{CYAN}{logger_field}{RESET} : "
                f"{message}"
            )
        else:
            formatted = (
                f"{timestamp} {padded_level} {process} --- "
                f"{thread_field} {logger_field} : {message}"
            )

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                formatted = f"{formatted}\n{record.exc_text}"

        return formatted


def setup_spring_boot_logging(level: int = logging.INFO) -> None:
    """
    Configures root and app-level loggers to emit Spring-Boot-style log outputs.
    """
    # Check if color is explicitly disabled or enabled via env
    no_color = os.getenv("NO_COLOR", "").lower() in ("1", "true")
    formatter = SpringBootLogFormatter(use_color=not no_color)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if reloaded
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Align uvicorn and starlette logs to the same standard
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        u_logger = logging.getLogger(name)
        u_logger.handlers.clear()
        u_logger.addHandler(handler)
        u_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Helper to get a named logger with Spring Boot naming semantics.
    """
    return logging.getLogger(name)
