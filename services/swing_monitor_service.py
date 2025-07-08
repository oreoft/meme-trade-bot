from datetime import datetime
from typing import List, Dict, Optional

from database.models import SwingMonitorRecord, PrivateKey, SessionLocal
from services.birdeye_api import BirdEyeAPI
from utils import normalize_sol_address


class SwingMonitorService:
    """波段监控服务层"""

    @staticmethod
    def get_all_records() -> List[Dict]:
        """获取所有波段监控记录"""
        db = SessionLocal()
        try:
            records = db.query(SwingMonitorRecord).all()
            return [
                {
                    "id": record.id,
                    "name": record.name,
                    "private_key_id": record.private_key_id,
                    "private_key_nickname": record.private_key_obj.nickname if record.private_key_obj else "未知",

                    # 监听代币信息
                    "watch_token_address": record.watch_token_address,
                    "watch_token_name": record.watch_token_name,
                    "watch_token_symbol": record.watch_token_symbol,
                    "watch_token_logo_uri": record.watch_token_logo_uri,
                    "watch_token_decimals": record.watch_token_decimals,

                    # 交易代币信息
                    "trade_token_address": record.trade_token_address,
                    "trade_token_name": record.trade_token_name,
                    "trade_token_symbol": record.trade_token_symbol,
                    "trade_token_logo_uri": record.trade_token_logo_uri,
                    "trade_token_decimals": record.trade_token_decimals,

                    # 配置信息
                    "price_type": record.price_type,
                    "sell_threshold": record.sell_threshold,
                    "buy_threshold": record.buy_threshold,
                    "sell_percentage": record.sell_percentage,
                    "buy_percentage": record.buy_percentage,
                    "webhook_url": record.webhook_url,
                    "check_interval": record.check_interval,
                    "all_in_threshold": record.all_in_threshold,

                    # 状态信息
                    "status": record.status,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "last_check_at": record.last_check_at.isoformat() if record.last_check_at else None,
                    "last_watch_price": record.last_watch_price,
                    "last_watch_market_cap": record.last_watch_market_cap,
                }
                for record in records
            ]
        finally:
            db.close()

    @staticmethod
    def create_record(name: str, private_key_id: int, watch_token_address: str, trade_token_address: str,
                      price_type: str, sell_threshold: float, buy_threshold: float,
                      sell_percentage: float, buy_percentage: float, webhook_url: str,
                      check_interval: int = 5, all_in_threshold: float = 50.0) -> tuple[bool, str, Optional[int]]:
        """创建波段监控记录"""
        # 参数校验
        if price_type not in ["market_cap", "price"]:
            return False, "价格类型必须是 'market_cap' 或 'price'", None
        if sell_threshold <= buy_threshold:
            return False, "卖出阈值必须大于买入阈值", None
        if sell_percentage <= 0 or sell_percentage > 1:
            return False, "卖出比例必须在0-1之间", None
        if buy_percentage <= 0 or buy_percentage > 1:
            return False, "买入比例必须在0-1之间", None
        if check_interval < 1:
            return False, "检查间隔必须大于等于1秒", None
        if all_in_threshold < 0:
            return False, "全仓阈值必须大于等于0", None

        db = SessionLocal()
        try:
            # 检查私钥是否存在
            private_key_obj = db.query(PrivateKey).filter(
                PrivateKey.id == private_key_id,
                PrivateKey.deleted == False
            ).first()
            if not private_key_obj:
                return False, "私钥不存在或已删除", None

            # 获取监听代币信息
            api = BirdEyeAPI()
            watch_token_meta = api.get_token_meta_data(normalize_sol_address(watch_token_address))
            if not watch_token_meta:
                return False, "无法获取监听代币信息，请检查代币地址是否正确", None

            # 获取交易代币信息
            trade_token_meta = api.get_token_meta_data(normalize_sol_address(trade_token_address))
            if not trade_token_meta:
                return False, "无法获取交易代币信息，请检查代币地址是否正确", None

            # 创建记录
            record = SwingMonitorRecord(
                name=name,
                private_key_id=private_key_id,

                # 监听代币信息
                watch_token_address=watch_token_address,
                watch_token_name=watch_token_meta.get('name'),
                watch_token_symbol=watch_token_meta.get('symbol'),
                watch_token_logo_uri=watch_token_meta.get('logo_uri'),
                watch_token_decimals=watch_token_meta.get('decimals'),

                # 交易代币信息
                trade_token_address=trade_token_address,
                trade_token_name=trade_token_meta.get('name'),
                trade_token_symbol=trade_token_meta.get('symbol'),
                trade_token_logo_uri=trade_token_meta.get('logo_uri'),
                trade_token_decimals=trade_token_meta.get('decimals'),

                # 配置信息
                price_type=price_type,
                sell_threshold=sell_threshold,
                buy_threshold=buy_threshold,
                sell_percentage=sell_percentage,
                buy_percentage=buy_percentage,
                webhook_url=webhook_url,
                check_interval=check_interval,
                all_in_threshold=all_in_threshold,

                status="stopped"
            )

            db.add(record)
            db.commit()
            db.refresh(record)

            success_message = f"波段监控记录创建成功，监听: {watch_token_meta.get('name', 'Unknown')} ({watch_token_meta.get('symbol', 'N/A')})，交易: {trade_token_meta.get('name', 'Unknown')} ({trade_token_meta.get('symbol', 'N/A')})"
            return True, success_message, record.id

        except Exception as e:
            return False, str(e), None
        finally:
            db.close()

    @staticmethod
    def update_record(record_id: int, name: str, private_key_id: int, watch_token_address: str,
                      trade_token_address: str, price_type: str, sell_threshold: float,
                      buy_threshold: float, sell_percentage: float, buy_percentage: float,
                      webhook_url: str, check_interval: int = 5,
                      all_in_threshold: float = 50.0) -> tuple[bool, str]:
        """更新波段监控记录"""
        # 参数校验
        if price_type not in ["market_cap", "price"]:
            return False, "价格类型必须是 'market_cap' 或 'price'"
        if sell_threshold <= buy_threshold:
            return False, "卖出阈值必须大于买入阈值"
        if sell_percentage <= 0 or sell_percentage > 1:
            return False, "卖出比例必须在0-1之间"
        if buy_percentage <= 0 or buy_percentage > 1:
            return False, "买入比例必须在0-1之间"
        if check_interval < 1:
            return False, "检查间隔必须大于等于1秒"
        if all_in_threshold < 0:
            return False, "全仓阈值必须大于等于0"

        db = SessionLocal()
        try:
            # 检查记录是否存在
            record = db.query(SwingMonitorRecord).filter(SwingMonitorRecord.id == record_id).first()
            if not record:
                return False, "波段监控记录不存在"

            # 检查私钥是否存在
            private_key_obj = db.query(PrivateKey).filter(
                PrivateKey.id == private_key_id,
                PrivateKey.deleted == False
            ).first()
            if not private_key_obj:
                return False, "私钥不存在或已删除"

            # 检查代币地址是否变化
            watch_token_changed = record.watch_token_address != watch_token_address
            trade_token_changed = record.trade_token_address != trade_token_address

            api = BirdEyeAPI()

            # 更新监听代币信息
            if watch_token_changed:
                watch_token_meta = api.get_token_meta_data(normalize_sol_address(watch_token_address))
                if not watch_token_meta:
                    return False, "无法获取新的监听代币信息，请检查代币地址是否正确"
                record.watch_token_name = watch_token_meta.get('name')
                record.watch_token_symbol = watch_token_meta.get('symbol')
                record.watch_token_logo_uri = watch_token_meta.get('logo_uri')
                record.watch_token_decimals = watch_token_meta.get('decimals')

            # 更新交易代币信息
            if trade_token_changed:
                trade_token_meta = api.get_token_meta_data(normalize_sol_address(trade_token_address))
                if not trade_token_meta:
                    return False, "无法获取新的交易代币信息，请检查代币地址是否正确"
                record.trade_token_name = trade_token_meta.get('name')
                record.trade_token_symbol = trade_token_meta.get('symbol')
                record.trade_token_logo_uri = trade_token_meta.get('logo_uri')
                record.trade_token_decimals = trade_token_meta.get('decimals')

            # 更新其他字段
            record.name = name
            record.private_key_id = private_key_id
            record.watch_token_address = watch_token_address
            record.trade_token_address = trade_token_address
            record.price_type = price_type
            record.sell_threshold = sell_threshold
            record.buy_threshold = buy_threshold
            record.sell_percentage = sell_percentage
            record.buy_percentage = buy_percentage
            record.webhook_url = webhook_url
            record.check_interval = check_interval
            record.all_in_threshold = all_in_threshold
            record.updated_at = datetime.utcnow()

            db.commit()

            success_message = "波段监控记录更新成功"
            if watch_token_changed or trade_token_changed:
                success_message += f"，已更新代币信息"
            return True, success_message

        except Exception as e:
            return False, str(e)
        finally:
            db.close()

    @staticmethod
    def delete_record(record_id: int) -> tuple[bool, str]:
        """删除波段监控记录"""
        db = SessionLocal()
        try:
            record = db.query(SwingMonitorRecord).filter(SwingMonitorRecord.id == record_id).first()
            if not record:
                return False, "波段监控记录不存在"

            # 删除记录
            db.delete(record)
            db.commit()

            return True, "波段监控记录删除成功"
        except Exception as e:
            return False, str(e)
        finally:
            db.close()

    @staticmethod
    def get_record_by_id(record_id: int) -> Optional[Dict]:
        """根据ID获取波段监控记录"""
        db = SessionLocal()
        try:
            record = db.query(SwingMonitorRecord).filter(SwingMonitorRecord.id == record_id).first()
            if not record:
                return None

            return {
                "id": record.id,
                "name": record.name,
                "private_key_id": record.private_key_id,
                "private_key": record.private_key_obj.private_key if record.private_key_obj else None,

                # 监听代币信息
                "watch_token_address": record.watch_token_address,
                "watch_token_name": record.watch_token_name,
                "watch_token_symbol": record.watch_token_symbol,
                "watch_token_logo_uri": record.watch_token_logo_uri,
                "watch_token_decimals": record.watch_token_decimals,

                # 交易代币信息
                "trade_token_address": record.trade_token_address,
                "trade_token_name": record.trade_token_name,
                "trade_token_symbol": record.trade_token_symbol,
                "trade_token_logo_uri": record.trade_token_logo_uri,
                "trade_token_decimals": record.trade_token_decimals,

                # 配置信息
                "price_type": record.price_type,
                "sell_threshold": record.sell_threshold,
                "buy_threshold": record.buy_threshold,
                "sell_percentage": record.sell_percentage,
                "buy_percentage": record.buy_percentage,
                "webhook_url": record.webhook_url,
                "check_interval": record.check_interval,
                "all_in_threshold": record.all_in_threshold,

                # 状态信息
                "status": record.status,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "last_check_at": record.last_check_at.isoformat() if record.last_check_at else None,
                "last_watch_price": record.last_watch_price,
                "last_watch_market_cap": record.last_watch_market_cap,
            }
        finally:
            db.close()

    @staticmethod
    def update_record_status(record_id: int, status: str) -> bool:
        """更新波段监控记录状态"""
        db = SessionLocal()
        try:
            record = db.query(SwingMonitorRecord).filter(SwingMonitorRecord.id == record_id).first()
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
