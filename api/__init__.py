# API 模块包
from .configs import router as configs_router
from .keys import router as keys_router
from .logs import router as logs_router
from .pages import router as pages_router
from .records import router as records_router
from .trade import router as trade_router

__all__ = [
    "pages_router",
    "configs_router",
    "records_router",
    "logs_router",
    "keys_router",
    "trade_router"
]
