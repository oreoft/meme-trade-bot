from fastapi import APIRouter, Form

from monitor_service import MonitorService

# 创建路由器
router = APIRouter(prefix="/api/monitor/records", tags=["监控记录管理"])

# 监控器实例 - 这里我们需要在main.py中注入
_monitor = None

def set_monitor(monitor):
    """设置监控器实例"""
    global _monitor
    _monitor = monitor

@router.get("")
async def get_monitor_records():
    """获取所有监控记录"""
    try:
        records = MonitorService.get_all_records()
        # 添加运行状态信息
        if _monitor:
            for record in records:
                record["is_running"] = _monitor.is_monitor_running(record["id"])
        else:
            for record in records:
                record["is_running"] = False

        return {
            "success": True,
            "data": records
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("")
async def create_monitor_record(
    name: str = Form(...),
    private_key_id: int = Form(...),
    token_address: str = Form(...),
    threshold: float = Form(...),
    sell_percentage: float = Form(...),
    webhook_url: str = Form(...),
    check_interval: int = Form(5),
    execution_mode: str = Form("single"),
    minimum_hold_value: float = Form(50.0),
    pre_sniper_mode: bool = Form(False)
):
    """创建监控记录"""
    try:
        success, message, record_id = MonitorService.create_record(
            name, private_key_id, token_address, threshold,
            sell_percentage, webhook_url, check_interval,
            execution_mode, minimum_hold_value, pre_sniper_mode
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

@router.put("/{record_id}")
async def update_monitor_record(
    record_id: int,
    name: str = Form(...),
    private_key_id: int = Form(...),
    token_address: str = Form(...),
    threshold: float = Form(...),
    sell_percentage: float = Form(...),
    webhook_url: str = Form(...),
    check_interval: int = Form(5),
    execution_mode: str = Form("single"),
    minimum_hold_value: float = Form(50.0),
    pre_sniper_mode: bool = Form(False)
):
    """更新监控记录"""
    try:
        # 如果监控正在运行，不允许修改
        if _monitor and _monitor.is_monitor_running(record_id):
            return {"success": False, "error": "请先停止监控再修改"}

        success, message = MonitorService.update_record(
            record_id, name, private_key_id, token_address,
            threshold, sell_percentage, webhook_url, check_interval,
            execution_mode, minimum_hold_value, pre_sniper_mode
        )

        if success:
            # 自动修复状态为stopped
            MonitorService.update_record_status(record_id, "stopped")
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.delete("/{record_id}")
async def delete_monitor_record(record_id: int):
    """删除监控记录"""
    try:
        # 如果监控正在运行，先停止
        if _monitor and _monitor.is_monitor_running(record_id):
            _monitor.stop_monitor(record_id)

        success, message = MonitorService.delete_record(record_id)

        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}
    except Exception as e:
        return {"success": False, "error": str(e)} 