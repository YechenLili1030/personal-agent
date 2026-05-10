"""统一日志配置"""

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FORMAT = "%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    # 清除已有 handler 避免重复
    root.handlers.clear()
    root.addHandler(handler)

    # 静默第三方库的噪音
    for name in ("chromadb", "uvicorn.access", "sqlalchemy.engine", "httpx", "openai", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # 保留 uvicorn 自身的关键日志
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
