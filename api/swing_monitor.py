from fastapi import APIRouter, Form

from core.price_monitor import PriceMonitor
from services.swing_monitor_service import SwingMonitorService
from utils.response import ApiResponse

router = APIRouter(prefix="/api/swing", tags=["波段监控"])


@router.get("/records")
async def get_swing_records():
    """获取所有波段监控记录"""
    try:
        records = SwingMonitorService.get_all_records()
        return ApiResponse.success(data=records)
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.post("/records")
async def create_swing_record(
    name: str = Form(...),
    private_key_id: int = Form(...),
    watch_token_address: str = Form(...),
    trade_token_address: str = Form(...),
    price_type: str = Form(...),
    sell_threshold: float = Form(...),
    buy_threshold: float = Form(...),
    sell_percentage: float = Form(...),
    buy_percentage: float = Form(...),
    webhook_url: str = Form(...),
    check_interval: int = Form(5),
    all_in_threshold: float = Form(50.0)
):
    """创建波段监控记录"""
    try:
        success, message, record_id = SwingMonitorService.create_record(
            name=name,
            private_key_id=private_key_id,
            watch_token_address=watch_token_address,
            trade_token_address=trade_token_address,
            price_type=price_type,
            sell_threshold=sell_threshold,
            buy_threshold=buy_threshold,
            sell_percentage=sell_percentage,
            buy_percentage=buy_percentage,
            webhook_url=webhook_url,
            check_interval=check_interval,
            all_in_threshold=all_in_threshold
        )

        if success:
            return ApiResponse.success(data={"id": record_id}, message=message)
        else:
            return ApiResponse.error(message=message)
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.put("/records/{record_id}")
async def update_swing_record(
    record_id: int,
    name: str = Form(...),
    private_key_id: int = Form(...),
    watch_token_address: str = Form(...),
    trade_token_address: str = Form(...),
    price_type: str = Form(...),
    sell_threshold: float = Form(...),
    buy_threshold: float = Form(...),
    sell_percentage: float = Form(...),
    buy_percentage: float = Form(...),
    webhook_url: str = Form(...),
    check_interval: int = Form(60),
    all_in_threshold: float = Form(50.0)
):
    """更新波段监控记录"""
    try:
        success, message = SwingMonitorService.update_record(
            record_id=record_id,
            name=name,
            private_key_id=private_key_id,
            watch_token_address=watch_token_address,
            trade_token_address=trade_token_address,
            price_type=price_type,
            sell_threshold=sell_threshold,
            buy_threshold=buy_threshold,
            sell_percentage=sell_percentage,
            buy_percentage=buy_percentage,
            webhook_url=webhook_url,
            check_interval=check_interval,
            all_in_threshold=all_in_threshold
        )

        if success:
            # 自动修复状态为stopped
            SwingMonitorService.update_record_status(record_id, "stopped")
            return ApiResponse.success(message=message)
        else:
            return ApiResponse.error(message=message)
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.delete("/records/{record_id}")
async def delete_swing_record(record_id: int):
    """删除波段监控记录"""
    try:
        success, message = SwingMonitorService.delete_record(record_id)

        if success:
            return ApiResponse.success(message=message)
        else:
            return ApiResponse.error(message=message)
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.get("/records/{record_id}")
async def get_swing_record(record_id: int):
    """获取单个波段监控记录"""
    try:
        record = SwingMonitorService.get_record_by_id(record_id)

        if record:
            return ApiResponse.success(data=record)
        else:
            return ApiResponse.error(message="波段监控记录不存在")
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.post("/start")
async def start_swing_monitor(record_id: int = Form(...)):
    """启动波段监控"""
    try:
        monitor = PriceMonitor()
        success, message = monitor.start_swing_monitor(record_id)

        if success:
            return ApiResponse.success(message=message)
        else:
            return ApiResponse.error(message=message)
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.post("/stop")
async def stop_swing_monitor(record_id: int = Form(...)):
    """停止波段监控"""
    try:
        monitor = PriceMonitor()
        success, message = monitor.stop_swing_monitor(record_id)

        if success:
            return ApiResponse.success(message=message)
        else:
            return ApiResponse.error(message=message)
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.get("/status")
async def get_swing_monitor_status():
    """获取波段监控状态"""
    try:
        monitor = PriceMonitor()
        running_count = monitor.get_swing_running_count()

        return ApiResponse.success(data={
            "running_count": running_count,
            "total_monitors": len(monitor.swing_monitor_states)
        })
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.get("/running/{record_id}")
async def is_swing_monitor_running(record_id: int):
    """检查波段监控是否在运行"""
    try:
        monitor = PriceMonitor()
        is_running = monitor.is_swing_monitor_running(record_id)

        return ApiResponse.success(data={"is_running": is_running})
    except Exception as e:
        return ApiResponse.error(message=str(e))
