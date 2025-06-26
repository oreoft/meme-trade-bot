import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# 导入API路由模块
from api import (
    pages_router,
    configs_router,
    monitor_router,
    records_router,
    logs_router
)
# 导入拆分后的模块
from config_manager import ConfigManager
from price_monitor import PriceMonitor

# 创建FastAPI应用
app = FastAPI(title="币价监控系统", description="实时监控代币价格，智能触发交易策略")

# 全局监控器实例
monitor = PriceMonitor()

# 初始化配置
ConfigManager.init_default_configs()

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册路由
app.include_router(pages_router)  # 页面路由
app.include_router(configs_router)  # 配置管理API
app.include_router(monitor_router)  # 监控管理API
app.include_router(records_router)  # 监控记录管理API
app.include_router(logs_router)  # 日志API

# 设置监控器实例到需要的路由模块中
from api import monitor as monitor_api
from api import records as records_api

monitor_api.set_monitor(monitor)
records_api.set_monitor(monitor)

if __name__ == "__main__":
    print("🚀 币价监控系统启动中...")
    print("📝 访问 http://localhost:8000 打开管理界面")
    print("📚 访问 http://localhost:8000/docs 查看API文档")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
