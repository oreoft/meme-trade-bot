# API 模块包
from .configs import router as configs_router
from .logs import router as logs_router
from .monitor import router as monitor_router
from .pages import router as pages_router
from .records import router as records_router

__all__ = [
    "pages_router",
    "configs_router",
    "monitor_router",
    "records_router",
    "logs_router"
]
