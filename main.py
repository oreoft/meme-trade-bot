import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 导入API路由模块
from api import (
    pages_router,
    configs_router,
    records_router,
    logs_router,
    keys_router,
    trade_router
)
from api.swing_monitor import router as swing_monitor_router
# 导入拆分后的模块
from config.config_manager import ConfigManager
# 导入日志配置模块
from config.log_config import setup_logging
from core.price_monitor import PriceMonitor
# 导入全局异常处理
from utils.exception_handler import GlobalExceptionHandler, setup_exception_handlers

# 初始化日志系统
setup_logging()

# 创建FastAPI应用
app = FastAPI(title="币价监控系统", description="实时监控代币价格，智能触发交易策略")

# 添加全局异常处理中间件
app.add_middleware(GlobalExceptionHandler)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法，包括DELETE
    allow_headers=["*"],
)

# 设置异常处理器
setup_exception_handlers(app)

# 全局监控器实例（单例模式，多次调用返回同一实例）
monitor = PriceMonitor()

# 初始化配置
ConfigManager.init_default_configs()

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册路由
app.include_router(pages_router)  # 页面路由
app.include_router(configs_router)  # 配置管理API
app.include_router(records_router)  # 监控记录管理API
app.include_router(logs_router)  # 日志API
app.include_router(keys_router)  # 私钥管理API
app.include_router(trade_router)  # 交易相关API
app.include_router(swing_monitor_router)  # 波段监控API

# 设置监控器实例到需要的路由模块中
from api import records as records_api

records_api.set_monitor(monitor)

if __name__ == "__main__":
    logging.info("🚀 币价监控系统启动中...")
    logging.info("📝 访问 http://localhost:8000 打开管理界面")
    logging.info("📚 访问 http://localhost:8000/docs 查看API文档")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        # reload=True,
        log_level="info"
    )
