"""Console + rotating file logging so every decision and trade is auditable."""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str = "logs") -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("crypto_agent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "crypto_agent.log"), maxBytes=2_000_000, backupCount=5
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
