from datetime import datetime
from typing import List, Dict, Optional

from solders.keypair import Keypair

from birdeye_api import BirdEyeAPI
from models import MonitorRecord, MonitorLog, PrivateKey, SessionLocal


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
                    "private_key_id": record.private_key_id,
                    "private_key_nickname": record.private_key_obj.nickname if record.private_key_obj else "未知",
                    "token_address": record.token_address,
                    "token_name": record.token_name,
                    "token_symbol": record.token_symbol,
                    "token_logo_uri": record.token_logo_uri,
                    "token_decimals": record.token_decimals,
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
    def create_record(name: str, private_key_id: int, token_address: str,
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
            # 检查私钥是否存在
            private_key_obj = db.query(PrivateKey).filter(PrivateKey.id == private_key_id).first()
            if not private_key_obj:
                return False, "私钥不存在", None

            # 获取token元数据
            api = BirdEyeAPI()
            token_meta_data = api.get_token_meta_data(token_address)
            
            # 提取token信息，如果获取失败则使用默认值
            token_name = None
            token_symbol = None
            token_logo_uri = None
            token_decimals = None
            
            if token_meta_data:
                token_name = token_meta_data.get('name')
                token_symbol = token_meta_data.get('symbol')
                token_logo_uri = token_meta_data.get('logo_uri')
                token_decimals = token_meta_data.get('decimals')

            record = MonitorRecord(
                name=name,
                private_key=private_key_obj.private_key,  # 向后兼容
                private_key_id=private_key_id,
                token_address=token_address,
                token_name=token_name,
                token_symbol=token_symbol,
                token_logo_uri=token_logo_uri,
                token_decimals=token_decimals,
                threshold=threshold,
                sell_percentage=sell_percentage,
                webhook_url=webhook_url,
                check_interval=check_interval,
                status="stopped"
            )

            db.add(record)
            db.commit()
            db.refresh(record)

            success_message = "监控记录创建成功"
            if token_meta_data:
                success_message += f"，已获取Token信息: {token_name or 'Unknown'} ({token_symbol or 'N/A'})"
            else:
                success_message += "，但无法获取Token元数据"

            return True, success_message, record.id
        except Exception as e:
            return False, str(e), None
        finally:
            db.close()

    @staticmethod
    def update_record(record_id: int, name: str, private_key_id: int,
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

            # 检查私钥是否存在
            private_key_obj = db.query(PrivateKey).filter(PrivateKey.id == private_key_id).first()
            if not private_key_obj:
                return False, "私钥不存在"

            # 检查token地址是否改变，如果改变则重新获取元数据
            token_address_changed = record.token_address != token_address
            if token_address_changed:
                api = BirdEyeAPI()
                token_meta_data = api.get_token_meta_data(token_address)
                
                if token_meta_data:
                    record.token_name = token_meta_data.get('name')
                    record.token_symbol = token_meta_data.get('symbol')
                    record.token_logo_uri = token_meta_data.get('logo_uri')
                    record.token_decimals = token_meta_data.get('decimals')
                else:
                    # 如果获取失败，清空原有的token信息
                    record.token_name = None
                    record.token_symbol = None
                    record.token_logo_uri = None
                    record.token_decimals = None

            record.name = name
            record.private_key = private_key_obj.private_key  # 向后兼容
            record.private_key_id = private_key_id
            record.token_address = token_address
            record.threshold = threshold
            record.sell_percentage = sell_percentage
            record.webhook_url = webhook_url
            record.check_interval = check_interval
            record.updated_at = datetime.utcnow()

            db.commit()
            
            success_message = "监控记录更新成功"
            if token_address_changed:
                if record.token_name:
                    success_message += f"，已更新Token信息: {record.token_name} ({record.token_symbol or 'N/A'})"
                else:
                    success_message += "，但无法获取新Token的元数据"
            
            return True, success_message
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
                "private_key_id": record.private_key_id,
                "private_key": record.private_key_obj.private_key if record.private_key_obj else record.private_key,
                "token_address": record.token_address,
                "token_name": record.token_name,
                "token_symbol": record.token_symbol,
                "token_logo_uri": record.token_logo_uri,
                "token_decimals": record.token_decimals,
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

    @staticmethod
    def clear_logs(monitor_record_id: Optional[int] = None) -> tuple[bool, str, int]:
        """清空日志

        Args:
            monitor_record_id: 监控记录ID，如果为None则清空所有日志

        Returns:
            tuple[bool, str, int]: (是否成功, 消息, 清空的日志数量)
        """
        db = SessionLocal()
        try:
            query = db.query(MonitorLog)

            if monitor_record_id:
                query = query.filter(MonitorLog.monitor_record_id == monitor_record_id)

            # 获取要删除的日志数量
            count = query.count()

            # 删除日志
            query.delete()
            db.commit()

            if monitor_record_id:
                return True, f"成功清空监控记录 {monitor_record_id} 的 {count} 条日志", count
            else:
                return True, f"成功清空所有 {count} 条日志", count
        except Exception as e:
            return False, f"清空日志失败: {str(e)}", 0
        finally:
            db.close()

    # 私钥管理方法
    @staticmethod
    def get_all_private_keys() -> List[Dict]:
        """获取所有私钥（安全显示）"""
        db = SessionLocal()
        try:
            private_keys = db.query(PrivateKey).all()
            return [
                {
                    "id": pk.id,
                    "nickname": pk.nickname,
                    "public_key": pk.public_key,
                    "private_key_preview": pk.private_key[:4] + "..." if pk.private_key else "...",
                    "created_at": pk.created_at.isoformat() if pk.created_at else None
                }
                for pk in private_keys
            ]
        finally:
            db.close()

    @staticmethod
    def create_private_key(nickname: str, private_key: str) -> tuple[bool, str, Optional[int]]:
        """创建私钥记录"""
        db = SessionLocal()
        try:
            # 验证私钥格式并生成公钥
            try:
                # 尝试从base58解码私钥
                keypair = Keypair.from_base58_string(private_key)
                public_key = str(keypair.pubkey())
            except Exception as e:
                return False, f"私钥格式错误: {str(e)}", None

            # 检查昵称是否已存在
            existing = db.query(PrivateKey).filter(PrivateKey.nickname == nickname).first()
            if existing:
                return False, "私钥昵称已存在", None

            # 检查私钥是否已存在
            existing = db.query(PrivateKey).filter(PrivateKey.private_key == private_key).first()
            if existing:
                return False, "该私钥已存在", None

            pk = PrivateKey(
                nickname=nickname,
                private_key=private_key,
                public_key=public_key
            )

            db.add(pk)
            db.commit()
            db.refresh(pk)

            return True, "私钥添加成功", pk.id
        except Exception as e:
            return False, str(e), None
        finally:
            db.close()

    @staticmethod
    def update_private_key(pk_id: int, nickname: str, private_key: str) -> tuple[bool, str]:
        """更新私钥记录"""
        db = SessionLocal()
        try:
            pk_record = db.query(PrivateKey).filter(PrivateKey.id == pk_id).first()
            if not pk_record:
                return False, "私钥记录不存在"

            # 验证私钥格式并生成公钥
            try:
                keypair = Keypair.from_base58_string(private_key)
                public_key = str(keypair.pubkey())
            except Exception as e:
                return False, f"私钥格式错误: {str(e)}"

            # 检查昵称是否已被其他记录使用
            existing = db.query(PrivateKey).filter(
                PrivateKey.nickname == nickname,
                PrivateKey.id != pk_id
            ).first()
            if existing:
                return False, "私钥昵称已存在"

            pk_record.nickname = nickname
            pk_record.private_key = private_key
            pk_record.public_key = public_key
            pk_record.updated_at = datetime.utcnow()

            db.commit()
            return True, "私钥更新成功"
        except Exception as e:
            return False, str(e)
        finally:
            db.close()

    @staticmethod
    def delete_private_key(pk_id: int) -> tuple[bool, str]:
        """删除私钥记录"""
        db = SessionLocal()
        try:
            # 检查是否有监控记录在使用该私钥
            using_records = db.query(MonitorRecord).filter(MonitorRecord.private_key_id == pk_id).count()
            if using_records > 0:
                return False, f"该私钥正被 {using_records} 个监控记录使用，无法删除"

            pk_record = db.query(PrivateKey).filter(PrivateKey.id == pk_id).first()
            if not pk_record:
                return False, "私钥记录不存在"

            db.delete(pk_record)
            db.commit()

            return True, "私钥删除成功"
        except Exception as e:
            return False, str(e)
        finally:
            db.close()

    @staticmethod
    def get_private_key_by_id(pk_id: int) -> Optional[Dict]:
        """根据ID获取私钥详情"""
        db = SessionLocal()
        try:
            pk = db.query(PrivateKey).filter(PrivateKey.id == pk_id).first()
            if not pk:
                return None

            return {
                "id": pk.id,
                "nickname": pk.nickname,
                "private_key": pk.private_key,
                "public_key": pk.public_key,
                "created_at": pk.created_at.isoformat() if pk.created_at else None
            }
        finally:
            db.close()
