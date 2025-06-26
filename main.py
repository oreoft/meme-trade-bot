import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# 导入拆分后的模块
from config_manager import ConfigManager
from monitor_service import MonitorService
from price_monitor import PriceMonitor


# 定义请求数据模型
class ConfigUpdateRequest(BaseModel):
    key: str
    value: str
    description: str = ""
    config_type: str = "string"

# 创建FastAPI应用
app = FastAPI(title="币价监控系统", description="实时监控代币价格，智能触发交易策略")

# 全局监控器实例
monitor = PriceMonitor()

# 初始化配置
ConfigManager.init_default_configs()

# 静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request})

@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page(request: Request):
    return templates.TemplateResponse("monitor.html", {"request": request})

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    return templates.TemplateResponse("logs.html", {"request": request})

@app.get("/api/configs")
async def get_configs():
    """获取所有配置"""
    try:
        configs = ConfigManager.get_all_configs()
        return {
            "success": True,
            "data": configs
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/configs")
async def update_config(request: ConfigUpdateRequest):
    """更新配置"""
    try:
        success = ConfigManager.set_config(
            request.key,
            request.value,
            request.description,
            request.config_type
        )
        if success:
            return {"success": True, "message": "配置更新成功"}
        else:
            return {"success": False, "error": "配置更新失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/monitor/start")
async def start_monitor(record_id: int):
    """启动监控"""
    result, message = monitor.start_monitor(record_id)
    return {"success": result, "message": message}

@app.post("/api/monitor/stop")
async def stop_monitor(record_id: int):
    """停止监控"""
    result, message = monitor.stop_monitor(record_id)
    return {"success": result, "message": message}

@app.get("/api/monitor/status")
async def get_monitor_status():
    """获取监控状态"""
    try:
        status_list = monitor.get_all_monitor_status()
        return {
            "success": True,
            "data": status_list
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/logs")
async def get_logs(page: int = 1, per_page: int = 20, monitor_record_id: int = None):
    """获取监控日志"""
    try:
        data = MonitorService.get_logs(page, per_page, monitor_record_id)
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# 监控记录管理API
@app.get("/api/monitor/records")
async def get_monitor_records():
    """获取所有监控记录"""
    try:
        records = MonitorService.get_all_records()
        # 添加运行状态信息
        for record in records:
            record["is_running"] = monitor.is_monitor_running(record["id"])

        return {
            "success": True,
            "data": records
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/monitor/records")
async def create_monitor_record(
    name: str = Form(...),
    private_key: str = Form(...),
    token_address: str = Form(...),
    threshold: float = Form(...),
    sell_percentage: float = Form(...),
    webhook_url: str = Form(...),
    check_interval: int = Form(5)
):
    """创建监控记录"""
    try:
        success, message, record_id = MonitorService.create_record(
            name, private_key, token_address, threshold,
            sell_percentage, webhook_url, check_interval
        )

        if success:
            return {
                "success": True,
                "message": message,
                "data": {"id": record_id}
            }
        else:
            return {"success": False, "error": message}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.put("/api/monitor/records/{record_id}")
async def update_monitor_record(
    record_id: int,
    name: str = Form(...),
    private_key: str = Form(...),
    token_address: str = Form(...),
    threshold: float = Form(...),
    sell_percentage: float = Form(...),
    webhook_url: str = Form(...),
    check_interval: int = Form(5)
):
    """更新监控记录"""
    try:
        # 如果监控正在运行，不允许修改
        if monitor.is_monitor_running(record_id):
            return {"success": False, "error": "请先停止监控再修改"}

        success, message = MonitorService.update_record(
            record_id, name, private_key, token_address,
            threshold, sell_percentage, webhook_url, check_interval
        )

        if success:
            # 自动修复状态为stopped
            MonitorService.update_record_status(record_id, "stopped")
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/monitor/records/{record_id}")
async def delete_monitor_record(record_id: int):
    """删除监控记录"""
    try:
        # 如果监控正在运行，先停止
        if monitor.is_monitor_running(record_id):
            monitor.stop_monitor(record_id)

        success, message = MonitorService.delete_record(record_id)

        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}
    except Exception as e:
        return {"success": False, "error": str(e)}



@app.post("/api/monitor/notification-cooldown")
async def set_notification_cooldown(cooldown_seconds: int = Form(...)):
    """设置通知冷却时间"""
    try:
        monitor.set_notification_cooldown(cooldown_seconds)
        return {
            "success": True,
            "message": f"通知冷却时间已设置为 {monitor.get_notification_cooldown()} 秒"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/monitor/notification-cooldown")
async def get_notification_cooldown():
    """获取通知冷却时间"""
    try:
        return {
            "success": True,
            "data": {"cooldown_seconds": monitor.get_notification_cooldown()}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

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
