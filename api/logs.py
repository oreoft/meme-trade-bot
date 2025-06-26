from fastapi import APIRouter

from monitor_service import MonitorService

# 创建路由器
router = APIRouter(prefix="/api", tags=["日志管理"])

@router.get("/logs")
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