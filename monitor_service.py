from datetime import datetime
from typing import List, Dict, Optional

from models import MonitorRecord, MonitorLog, SessionLocal


class MonitorService:
    """监控服务层"""

    @staticmethod
    def get_all_records() -> List[Dict]:
        """获取所有监控记录"""
        db = SessionLocal()
        try:
            records = db.query(MonitorRecord).all()
            return [
                {
                    "id": record.id,
                    "name": record.name,
                    "token_address": record.token_address,
                    "threshold": record.threshold,
                    "sell_percentage": record.sell_percentage,
                    "webhook_url": record.webhook_url,
                    "check_interval": record.check_interval,
                    "status": record.status,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "last_check_at": record.last_check_at.isoformat() if record.last_check_at else None,
                    "last_price": record.last_price,
                    "last_market_cap": record.last_market_cap
                }
                for record in records
            ]
        finally:
            db.close()

    @staticmethod
    def create_record(name: str, private_key: str, token_address: str,
                      threshold: float, sell_percentage: float, webhook_url: str,
                      check_interval: int = 5) -> tuple[bool, str, Optional[int]]:
        """创建监控记录"""
        # 验证输入
        if sell_percentage <= 0 or sell_percentage > 1:
            return False, "出售比例必须在0-1之间", None

        if threshold <= 0:
            return False, "阈值必须大于0", None

        if check_interval < 1:
            return False, "检查间隔必须大于等于1秒", None

        db = SessionLocal()
        try:
            record = MonitorRecord(
                name=name,
                private_key=private_key,
                token_address=token_address,
                threshold=threshold,
                sell_percentage=sell_percentage,
                webhook_url=webhook_url,
                check_interval=check_interval,
                status="stopped"
            )

            db.add(record)
            db.commit()
            db.refresh(record)

            return True, "监控记录创建成功", record.id
        except Exception as e:
            return False, str(e), None
        finally:
            db.close()

    @staticmethod
    def update_record(record_id: int, name: str, private_key: str,
                      token_address: str, threshold: float, sell_percentage: float,
                      webhook_url: str, check_interval: int = 5) -> tuple[bool, str]:
        """更新监控记录"""
        # 验证输入
        if sell_percentage <= 0 or sell_percentage > 1:
            return False, "出售比例必须在0-1之间"

        if threshold <= 0:
            return False, "阈值必须大于0"

        if check_interval < 1:
            return False, "检查间隔必须大于等于1秒"

        db = SessionLocal()
        try:
            record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
            if not record:
                return False, "监控记录不存在"

            record.name = name
            record.private_key = private_key
            record.token_address = token_address
            record.threshold = threshold
            record.sell_percentage = sell_percentage
            record.webhook_url = webhook_url
            record.check_interval = check_interval
            record.updated_at = datetime.utcnow()

            db.commit()
            return True, "监控记录更新成功"
        except Exception as e:
            return False, str(e)
        finally:
            db.close()

    @staticmethod
    def delete_record(record_id: int) -> tuple[bool, str]:
        """删除监控记录"""
        db = SessionLocal()
        try:
            record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
            if not record:
                return False, "监控记录不存在"

            # 删除相关日志
            db.query(MonitorLog).filter(MonitorLog.monitor_record_id == record_id).delete()

            # 删除记录
            db.delete(record)
            db.commit()

            return True, "监控记录删除成功"
        except Exception as e:
            return False, str(e)
        finally:
            db.close()

    @staticmethod
    def get_logs(page: int = 1, per_page: int = 20, monitor_record_id: Optional[int] = None):
        """获取监控日志"""
        db = SessionLocal()
        try:
            offset = (page - 1) * per_page
            query = db.query(MonitorLog)

            if monitor_record_id:
                query = query.filter(MonitorLog.monitor_record_id == monitor_record_id)

            logs = query.order_by(MonitorLog.timestamp.desc()).offset(offset).limit(per_page).all()
            total = query.count()

            return {
                "logs": [
                    {
                        "id": log.id,
                        "monitor_record_id": log.monitor_record_id,
                        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                        "price": log.price,
                        "market_cap": log.market_cap,
                        "threshold_reached": log.threshold_reached,
                        "action_taken": log.action_taken,
                        "tx_hash": log.tx_hash
                    }
                    for log in logs
                ],
                "total": total,
                "page": page,
                "per_page": per_page
            }
        finally:
            db.close()

    @staticmethod
    def get_record_by_id(record_id: int) -> Optional[Dict]:
        """根据ID获取监控记录"""
        db = SessionLocal()
        try:
            record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
            if not record:
                return None

            return {
                "id": record.id,
                "name": record.name,
                "private_key": record.private_key,
                "token_address": record.token_address,
                "threshold": record.threshold,
                "sell_percentage": record.sell_percentage,
                "webhook_url": record.webhook_url,
                "check_interval": record.check_interval,
                "status": record.status,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "last_check_at": record.last_check_at.isoformat() if record.last_check_at else None,
                "last_price": record.last_price,
                "last_market_cap": record.last_market_cap
            }
        finally:
            db.close()

    @staticmethod
    def update_record_status(record_id: int, status: str) -> bool:
        """更新监控记录状态"""
        db = SessionLocal()
        try:
            record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
            if record:
                record.status = status
                record.updated_at = datetime.utcnow()
                db.commit()
                return True
            return False
        except Exception:
            return False
        finally:
            db.close()
