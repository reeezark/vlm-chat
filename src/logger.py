"""
日志模块
提供统一的日志配置和获取方法
"""
import logging
import os
import sys
from typing import Optional

# 彻底抑制 openai/httpx 库的所有输出
for _name in ["httpx", "httpcore", "openai", "urllib3"]:
    _logger = logging.getLogger(_name)
    _logger.setLevel(logging.CRITICAL)
    _logger.disabled = True
    _logger.propagate = False
    _logger.handlers = []

# 设置环境变量抑制 openai 调试输出
os.environ["OPENAI_LOG"] = "error"


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_format: Optional[str] = None
) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    if log_format is None:
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def get_api_logger() -> logging.Logger:
    return setup_logger("src.api_client")

def get_chat_logger() -> logging.Logger:
    return setup_logger("src.chat_manager")

def get_image_logger() -> logging.Logger:
    return setup_logger("src.image_processor")

def get_app_logger() -> logging.Logger:
    return setup_logger("app")
