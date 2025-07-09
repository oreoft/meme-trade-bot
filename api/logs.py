from typing import List, Optional

from fastapi import APIRouter

from services.monitor_service import MonitorService
from utils.response import ApiResponse

# 创建路由器
router = APIRouter(prefix="/api", tags=["日志管理"])

@router.get("/logs")
async def get_logs(page: int = 1, per_page: int = 20, monitor_record_id: int = None, type: str = None, action_types: Optional[List[str]] = None):
    """
    获取监控日志，支持 type=normal/swing
    action_type: 动作类型列表，如果为空则不过滤
    """
    try:
        data = MonitorService.get_logs(page, per_page, monitor_record_id, type, action_types)
        return ApiResponse.success(data=data)
    except Exception as e:
        return ApiResponse.error(message=str(e))

@router.delete("/logs")
async def clear_logs(monitor_record_id: int = None):
    """清空日志"""
    try:
        success, message, count = MonitorService.clear_logs(monitor_record_id)
        if success:
            return ApiResponse.success(
                data={"count": count},
                message=message
            )
        else:
            return ApiResponse.error(message=message)
    except Exception as e:
        return ApiResponse.error(message=str(e))
