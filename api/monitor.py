from fastapi import APIRouter, Form

from utils.response import ApiResponse

# 创建路由器
router = APIRouter(prefix="/api/monitor", tags=["监控管理"])

# 监控器实例 - 这里我们需要在main.py中注入
_monitor = None

def set_monitor(monitor):
    """设置监控器实例"""
    global _monitor
    _monitor = monitor

@router.post("/start")
async def start_monitor(record_id: int):
    """启动监控"""
    if _monitor is None:
        return ApiResponse.error(message="监控器未初始化")

    result, message = _monitor.start_monitor(record_id)
    if result:
        return ApiResponse.success(message=message)
    else:
        return ApiResponse.error(message=message)

@router.post("/stop")
async def stop_monitor(record_id: int):
    """停止监控"""
    if _monitor is None:
        return ApiResponse.error(message="监控器未初始化")

    result, message = _monitor.stop_monitor(record_id)
    if result:
        return ApiResponse.success(message=message)
    else:
        return ApiResponse.error(message=message)

@router.get("/status")
async def get_monitor_status():
    """获取监控状态"""
    if _monitor is None:
        return ApiResponse.error(message="监控器未初始化")

    try:
        status_list = _monitor.get_all_monitor_status()
        return ApiResponse.success(data=status_list)
    except Exception as e:
        return ApiResponse.error(message=str(e))

@router.post("/notification-cooldown")
async def set_notification_cooldown(cooldown_seconds: int = Form(...)):
    """设置通知冷却时间"""
    if _monitor is None:
        return ApiResponse.error(message="监控器未初始化")

    try:
        _monitor.set_notification_cooldown(cooldown_seconds)
        return ApiResponse.success(
            message=f"通知冷却时间已设置为 {_monitor.get_notification_cooldown()} 秒"
        )
    except Exception as e:
        return ApiResponse.error(message=str(e))

@router.get("/notification-cooldown")
async def get_notification_cooldown():
    """获取通知冷却时间"""
    if _monitor is None:
        return ApiResponse.error(message="监控器未初始化")

    try:
        return ApiResponse.success(
            data={"cooldown_seconds": _monitor.get_notification_cooldown()}
        )
    except Exception as e:
        return ApiResponse.error(message=str(e))
