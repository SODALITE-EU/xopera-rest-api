import logging as base_logging
import os


def _get_level_from_envvar(default=base_logging.INFO) -> int:
    level_raw = os.getenv("LOG_LEVEL", None)
    if level_raw is None:
        return default

    level_raw = level_raw.strip().lower()
    string_levels = {
        "debug": base_logging.DEBUG,
        "info": base_logging.INFO,
        "warning": base_logging.WARNING,
        "warn": base_logging.WARNING,
        "error": base_logging.ERROR,
        "critical": base_logging.CRITICAL
    }
    return string_levels.get(level_raw, default)


def get_logger(module_name: str) -> base_logging.Logger:
    global_log_level = _get_level_from_envvar()

    result = base_logging.getLogger(module_name)
    result.setLevel(global_log_level)

    console_handler = base_logging.StreamHandler()
    console_handler.setLevel(global_log_level)

    formatter = base_logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    console_handler.setFormatter(formatter)
    result.addHandler(console_handler)

    return result
