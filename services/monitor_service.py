from datetime import datetime
from typing import List, Dict, Optional

from solders.keypair import Keypair

from database.models import MonitorRecord, MonitorLog, PrivateKey, SessionLocal
from services.birdeye_api import BirdEyeAPI
from utils import normalize_sol_address


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
                    "execution_mode": record.execution_mode,
                    "minimum_hold_value": record.minimum_hold_value,
                    "status": record.status,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "last_check_at": record.last_check_at.isoformat() if record.last_check_at else None,
                    "last_price": record.last_price,
                    "last_market_cap": record.last_market_cap,
                    "type": record.type,
                    "max_buy_amount": record.max_buy_amount,
                    "accumulated_buy_usd": record.accumulated_buy_usd or 0.0
                }
                for record in records
            ]
        finally:
            db.close()

    @staticmethod
    def create_record(name: str, private_key_id: int, token_address: str,
                      threshold: float, sell_percentage: float, webhook_url: str,
                      check_interval: int = 5, execution_mode: str = "single",
                      minimum_hold_value: float = 50.0, pre_sniper_mode: bool = False,
                      type: str = "sell", max_buy_amount: float = 0.0) -> tuple[bool, str, Optional[int]]:
        """创建监控记录，支持买入/卖出类型"""
        # 校验type
        if type not in ["sell", "buy"]:
            return False, "监控类型必须是 'sell' 或 'buy'", None
        # 校验比例
        if type == "sell":
            if sell_percentage <= 0 or sell_percentage > 1:
                return False, "出售比例必须在0-1之间", None
        else:
            if sell_percentage <= 0 or sell_percentage > 1:
                return False, "购买比例必须在0-1之间", None
            if max_buy_amount < 0:
                return False, "累计购买上限必须大于等于0", None
        if threshold <= 0:
            return False, "阈值必须大于0", None
        if check_interval < 1:
            return False, "检查间隔必须大于等于1秒", None
        if execution_mode not in ["single", "multiple"]:
            return False, "执行模式必须是 'single' 或 'multiple'", None
        if minimum_hold_value < 0:
            return False, "最低持仓金额必须大于等于0", None
        db = SessionLocal()
        try:
            private_key_obj = db.query(PrivateKey).filter(PrivateKey.id == private_key_id,
                                                          PrivateKey.deleted == False).first()
            if not private_key_obj:
                return False, "私钥不存在或已删除", None
            api = BirdEyeAPI()
            token_meta_data = api.get_token_meta_data(normalize_sol_address(token_address))
            if not token_meta_data:
                return False, "无法获取Token信息，请检查Token地址是否正确", None
            token_name = token_meta_data.get('name')
            token_symbol = token_meta_data.get('symbol')
            token_logo_uri = token_meta_data.get('logo_uri')
            token_decimals = token_meta_data.get('decimals')
            record = MonitorRecord(
                name=name,
                private_key=private_key_obj.private_key,
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
                execution_mode=execution_mode,
                minimum_hold_value=minimum_hold_value,
                pre_sniper_mode=pre_sniper_mode if type == "sell" else False,
                status="stopped",
                type=type,
                max_buy_amount=max_buy_amount if type == "buy" else 0.0
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            success_message = f"监控记录创建成功，类型: {type}，已获取Token信息: {token_name or 'Unknown'} ({token_symbol or 'N/A'})"
            return True, success_message, record.id
        except Exception as e:
            return False, str(e), None
        finally:
            db.close()

    @staticmethod
    def update_record(record_id: int, name: str, private_key_id: int,
                      token_address: str, threshold: float, sell_percentage: float,
                      webhook_url: str, check_interval: int = 5, execution_mode: str = "single",
                      minimum_hold_value: float = 50.0, pre_sniper_mode: bool = False,
                      type: str = "sell", max_buy_amount: float = 0.0) -> tuple[bool, str]:
        """更新监控记录，支持买入/卖出类型"""
        if type not in ["sell", "buy"]:
            return False, "监控类型必须是 'sell' 或 'buy'"
        if type == "sell":
            if sell_percentage <= 0 or sell_percentage > 1:
                return False, "出售比例必须在0-1之间"
        else:
            if sell_percentage <= 0 or sell_percentage > 1:
                return False, "购买比例必须在0-1之间"
            if max_buy_amount < 0:
                return False, "累计购买上限必须大于等于0"
        if threshold <= 0:
            return False, "阈值必须大于0"
        if check_interval < 1:
            return False, "检查间隔必须大于等于1秒"
        if execution_mode not in ["single", "multiple"]:
            return False, "执行模式必须是 'single' 或 'multiple'"
        if minimum_hold_value < 0:
            return False, "最低持仓金额必须大于等于0"
        db = SessionLocal()
        try:
            record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
            if not record:
                return False, "监控记录不存在"
            private_key_obj = db.query(PrivateKey).filter(PrivateKey.id == private_key_id,
                                                          PrivateKey.deleted == False).first()
            if not private_key_obj:
                return False, "私钥不存在或已删除"
            token_address_changed = record.token_address != token_address
            if token_address_changed:
                api = BirdEyeAPI()
                token_meta_data = api.get_token_meta_data(normalize_sol_address(token_address))
                if not token_meta_data:
                    return False, "无法获取新Token信息，请检查Token地址是否正确"
                record.token_name = token_meta_data.get('name')
                record.token_symbol = token_meta_data.get('symbol')
                record.token_logo_uri = token_meta_data.get('logo_uri')
                record.token_decimals = token_meta_data.get('decimals')
            record.name = name
            record.private_key = private_key_obj.private_key
            record.private_key_id = private_key_id
            record.token_address = token_address
            record.threshold = threshold
            record.sell_percentage = sell_percentage
            record.webhook_url = webhook_url
            record.check_interval = check_interval
            record.execution_mode = execution_mode
            record.minimum_hold_value = minimum_hold_value
            record.pre_sniper_mode = pre_sniper_mode if type == "sell" else False
            record.type = type
            record.max_buy_amount = max_buy_amount if type == "buy" else 0.0
            record.updated_at = datetime.utcnow()
            db.commit()
            success_message = "监控记录更新成功"
            if token_address_changed:
                success_message += f"，已更新Token信息: {record.token_name or 'Unknown'} ({record.token_symbol or 'N/A'})"
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
            # 获取普通监控日志
            normal_query = db.query(MonitorLog)
            if monitor_record_id:
                normal_query = normal_query.filter(MonitorLog.monitor_record_id == monitor_record_id)
            
            # 按时间排序
            normal_logs = normal_query.order_by(MonitorLog.timestamp.desc()).all()
            
            # 转换为统一格式
            log_list = []
            
            # 添加普通监控日志
            for log in normal_logs:
                log_list.append({
                    "id": f"normal_{log.id}",
                    "monitor_record_id": log.monitor_record_id,
                    "monitor_type": "normal",
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "price": log.price,
                    "market_cap": log.market_cap,
                    "threshold_reached": log.threshold_reached,
                    "action_taken": log.action_taken,
                    "tx_hash": log.tx_hash
                })
            
            # 按时间排序
            log_list.sort(key=lambda x: x['timestamp'] if x['timestamp'] else '', reverse=True)
            
            # 分页
            total = len(log_list)
            offset = (page - 1) * per_page
            log_list = log_list[offset:offset + per_page]

            return {
                "logs": log_list,
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
                "execution_mode": record.execution_mode,
                "minimum_hold_value": record.minimum_hold_value,
                "status": record.status,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "last_check_at": record.last_check_at.isoformat() if record.last_check_at else None,
                "last_price": record.last_price,
                "last_market_cap": record.last_market_cap,
                "type": record.type,
                "max_buy_amount": record.max_buy_amount,
                "accumulated_buy_usd": record.accumulated_buy_usd or 0.0
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
            monitor_record_id: 普通监控记录ID，如果为None则清空所有普通监控日志

        Returns:
            tuple[bool, str, int]: (是否成功, 消息, 清空的日志数量)
        """
        db = SessionLocal()
        try:
            total_count = 0
            
            # 清空普通监控日志
            normal_query = db.query(MonitorLog)
            if monitor_record_id:
                normal_query = normal_query.filter(MonitorLog.monitor_record_id == monitor_record_id)
            normal_count = normal_query.count()
            normal_query.delete()
            
            total_count = normal_count
            
            if monitor_record_id:
                message = f"成功清空监控记录 {monitor_record_id} 的 {normal_count} 条日志"
            else:
                message = f"成功清空所有日志：{normal_count} 条普通监控日志"
            
            db.commit()
            return True, message, total_count
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
            private_keys = db.query(PrivateKey).filter(PrivateKey.deleted == False).all()
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
    def get_all_private_keys_with_secrets() -> List[Dict]:
        """获取所有私钥（包含完整私钥信息，仅用于导出）"""
        db = SessionLocal()
        try:
            private_keys = db.query(PrivateKey).filter(PrivateKey.deleted == False).all()
            return [
                {
                    "id": pk.id,
                    "nickname": pk.nickname,
                    "public_key": pk.public_key,
                    "private_key": pk.private_key,
                    "private_key_preview": pk.private_key[:4] + "..." if pk.private_key else "...",
                    "created_at": pk.created_at.isoformat() if pk.created_at else None,
                    "updated_at": pk.updated_at.isoformat() if pk.updated_at else None
                }
                for pk in private_keys
            ]
        finally:
            db.close()

    @staticmethod
    def get_current_time() -> str:
        """获取当前时间字符串"""
        return datetime.utcnow().isoformat()

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

            # 检查昵称是否已存在（只检查未删除的）
            existing = db.query(PrivateKey).filter(PrivateKey.nickname == nickname, PrivateKey.deleted == False).first()
            if existing:
                return False, "私钥昵称已存在", None

            # 检查私钥是否已存在（只检查未删除的）
            existing = db.query(PrivateKey).filter(PrivateKey.private_key == private_key,
                                                   PrivateKey.deleted == False).first()
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
            pk_record = db.query(PrivateKey).filter(PrivateKey.id == pk_id, PrivateKey.deleted == False).first()
            if not pk_record:
                return False, "私钥记录不存在或已删除"

            # 验证私钥格式并生成公钥
            try:
                keypair = Keypair.from_base58_string(private_key)
                public_key = str(keypair.pubkey())
            except Exception as e:
                return False, f"私钥格式错误: {str(e)}"

            # 检查昵称是否已被其他记录使用（只检查未删除的）
            existing = db.query(PrivateKey).filter(
                PrivateKey.nickname == nickname,
                PrivateKey.id != pk_id,
                PrivateKey.deleted == False
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
        """删除私钥记录（逻辑删除）"""
        db = SessionLocal()
        try:
            pk_record = db.query(PrivateKey).filter(PrivateKey.id == pk_id, PrivateKey.deleted == False).first()
            if not pk_record:
                return False, "私钥记录不存在或已删除"

            # 检查是否有监控记录在使用该私钥
            using_records = db.query(MonitorRecord).filter(MonitorRecord.private_key_id == pk_id).count()
            if using_records > 0:
                return False, f"该私钥正被 {using_records} 个监控记录使用，无法删除"

            # 逻辑删除：设置 deleted 标记为 True
            pk_record.deleted = True
            pk_record.updated_at = datetime.utcnow()
            db.commit()

            return True, "私钥已删除（逻辑删除）"
        except Exception as e:
            return False, str(e)
        finally:
            db.close()

    @staticmethod
    def get_private_key_by_id(pk_id: int) -> Optional[Dict]:
        """根据ID获取私钥详情"""
        db = SessionLocal()
        try:
            pk = db.query(PrivateKey).filter(PrivateKey.id == pk_id, PrivateKey.deleted == False).first()
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
