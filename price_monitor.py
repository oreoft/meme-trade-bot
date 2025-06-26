import threading
import time
from datetime import datetime
from typing import Dict, List

from market_data import MarketDataFetcher
from models import MonitorRecord, MonitorLog, SessionLocal
from notifier import Notifier
from trader import SolanaTrader


class PriceMonitor:
    """价格监控器"""

    def __init__(self):
        self.running_monitors: Dict[int, threading.Thread] = {}
        self.monitor_states: Dict[int, bool] = {}
        self.market_fetcher = MarketDataFetcher()
        # 为每个监控记录维护通知时间戳
        self.last_notification_times: Dict[int, float] = {}
        self.notification_cooldown = 300  # 5分钟通知冷却时间（300秒）

        # 启动时自动恢复监控任务
        self._auto_recover_monitors()

    def _auto_recover_monitors(self):
        """启动时自动恢复所有状态为monitoring的监控任务"""
        print("正在自动恢复监控任务...")
        db = SessionLocal()
        try:
            # 查找所有状态为monitoring的记录
            monitoring_records = db.query(MonitorRecord).filter(
                MonitorRecord.status == "monitoring"
            ).all()

            recovered_count = 0
            for record in monitoring_records:
                try:
                    # 启动监控线程
                    self.monitor_states[record.id] = True
                    thread = threading.Thread(
                        target=self._monitor_loop,
                        args=(record.id,),
                        daemon=True
                    )
                    thread.start()
                    self.running_monitors[record.id] = thread
                    recovered_count += 1
                    print(f"已恢复监控任务: {record.name} (ID: {record.id})")
                except Exception as e:
                    print(f"恢复监控任务失败 {record.name} (ID: {record.id}): {e}")
                    # 将失败的任务状态设为stopped
                    record.status = "stopped"
                    db.commit()

            if recovered_count > 0:
                print(f"成功恢复 {recovered_count} 个监控任务")
            else:
                print("没有需要恢复的监控任务")

        except Exception as e:
            print(f"自动恢复监控任务时出错: {e}")
        finally:
            db.close()

    def start_monitor(self, record_id: int):
        """启动单个监控任务"""
        if record_id in self.running_monitors and self.monitor_states.get(record_id, False):
            return False, "监控已在运行中"

        db = SessionLocal()
        try:
            record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
            if not record:
                return False, "监控记录不存在"

            # 更新状态为监控中
            record.status = "monitoring"
            db.commit()

            # 启动监控线程
            self.monitor_states[record_id] = True
            thread = threading.Thread(target=self._monitor_loop, args=(record_id,), daemon=True)
            thread.start()
            self.running_monitors[record_id] = thread

            return True, "监控启动成功"
        except Exception as e:
            return False, f"启动失败: {str(e)}"
        finally:
            db.close()

    def stop_monitor(self, record_id: int):
        """停止单个监控任务"""
        if record_id in self.monitor_states:
            self.monitor_states[record_id] = False

        if record_id in self.running_monitors:
            del self.running_monitors[record_id]

        # 清理通知时间戳
        if record_id in self.last_notification_times:
            del self.last_notification_times[record_id]

        # 更新数据库状态
        db = SessionLocal()
        try:
            record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
            if record:
                record.status = "stopped"
                db.commit()
        finally:
            db.close()

        return True, "监控已停止"

    def _should_send_notification(self, record_id: int) -> bool:
        """检查是否应该发送通知（避免频繁通知）"""
        current_time = time.time()
        last_time = self.last_notification_times.get(record_id, 0)

        if current_time - last_time >= self.notification_cooldown:
            self.last_notification_times[record_id] = current_time
            return True
        return False

    def _monitor_loop(self, record_id: int):
        """监控循环"""
        db = SessionLocal()
        try:
            record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
            if not record:
                return

            # 创建专用的交易器和通知器
            trader = SolanaTrader(private_key=record.private_key)
            notifier = Notifier(webhook_url=record.webhook_url)

            while self.monitor_states.get(record_id, False):
                try:
                    # 获取价格信息
                    price_info = self.market_fetcher.get_price_info(record.token_address)
                    if not price_info:
                        time.sleep(record.check_interval)
                        continue

                    # 更新记录的最后检查时间和价格信息
                    record.last_check_at = datetime.utcnow()
                    record.last_price = price_info['price']
                    record.last_market_cap = price_info['market_cap']
                    db.commit()

                    # 记录监控日志
                    self._log_monitor_data(record_id, price_info, record.threshold)

                    # 检查是否达到阈值
                    if price_info['market_cap'] >= record.threshold:
                        print(
                            f"监控 {record.name} 市值达到阈值！当前: ${price_info['market_cap']:,.2f}, 阈值: ${record.threshold:,.2f}")

                        # 发送阈值达到通知
                        if self._should_send_notification(record_id):
                            notifier.send_price_alert(price_info, threshold_reached=True)

                        # 执行交易
                        try:
                            tx_hash = trader.sell_token_for_sol(record.token_address, record.sell_percentage)
                            if tx_hash:
                                print(f"交易成功: {tx_hash}")
                                # 记录交易日志 - 确保tx_hash是字符串类型
                                log = MonitorLog(
                                    monitor_record_id=record_id,
                                    price=price_info['price'],
                                    market_cap=price_info['market_cap'],
                                    threshold_reached=True,
                                    action_taken="自动出售",
                                    tx_hash=str(tx_hash)  # 确保转换为字符串
                                )
                                db.add(log)
                                db.commit()

                                # 发送交易成功通知
                                # 获取代币余额来计算实际出售数量
                                token_balance = trader.get_token_balance(record.token_address)
                                actual_sell_amount = token_balance * record.sell_percentage
                                estimated_usd_value = actual_sell_amount * price_info['price']
                                notifier.send_trade_notification(tx_hash, actual_sell_amount, estimated_usd_value)

                                print(f"交易完成，继续监控等待下一次达到阈值...")
                                # 交易成功后继续监控，不停止
                                # 可以选择等待一段时间再继续，避免频繁交易
                                time.sleep(60)  # 等待1分钟再继续监控

                        except Exception as e:
                            print(f"交易执行失败: {e}")
                            notifier.send_error_notification(f"交易执行失败: {e}")
                    else:
                        # 市值未达到阈值时，定期发送价格报告
                        print(
                            f"监控 {record.name} 市值未达到阈值。当前: ${price_info['market_cap']:,.2f}, 阈值: ${record.threshold:,.2f}")

                        # 定期发送价格报告（每5分钟一次）
                        if self._should_send_notification(record_id):
                            notifier.send_price_alert(price_info, threshold_reached=False)

                    time.sleep(record.check_interval)

                except Exception as e:
                    print(f"监控 {record.name} 过程中出错: {e}")
                    # 更新状态为错误
                    record.status = "error"
                    db.commit()
                    time.sleep(record.check_interval)

        except Exception as e:
            print(f"监控线程异常: {e}")
        finally:
            # 清理状态
            if record_id in self.monitor_states:
                self.monitor_states[record_id] = False
            if record_id in self.running_monitors:
                del self.running_monitors[record_id]
            if record_id in self.last_notification_times:
                del self.last_notification_times[record_id]

            # 更新数据库状态
            try:
                record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
                if record and record.status == "monitoring":
                    record.status = "stopped"
                    db.commit()
            except:
                pass
            finally:
                db.close()

    def _log_monitor_data(self, record_id: int, price_info: dict, threshold: float):
        """记录监控数据"""
        db = SessionLocal()
        try:
            log = MonitorLog(
                monitor_record_id=record_id,
                price=price_info['price'],
                market_cap=price_info['market_cap'],
                threshold_reached=price_info['market_cap'] >= threshold,
                action_taken="监控中" if price_info['market_cap'] < threshold else "阈值达到"
            )
            db.add(log)
            db.commit()
        finally:
            db.close()

    def get_all_monitor_status(self) -> List[Dict]:
        """获取所有监控状态"""
        db = SessionLocal()
        try:
            records = db.query(MonitorRecord).all()
            status_list = []
            for record in records:
                status_list.append({
                    'id': record.id,
                    'name': record.name,
                    'token_address': record.token_address,
                    'threshold': record.threshold,
                    'sell_percentage': record.sell_percentage,
                    'status': record.status,
                    'last_check_at': record.last_check_at.isoformat() if record.last_check_at else None,
                    'last_price': record.last_price,
                    'last_market_cap': record.last_market_cap,
                    'is_running': record.id in self.monitor_states and self.monitor_states[record.id]
                })
            return status_list
        finally:
            db.close()

    def stop_all_monitors(self):
        """停止所有监控任务"""
        for record_id in list(self.monitor_states.keys()):
            self.stop_monitor(record_id)

        # 清理所有通知时间戳
        self.last_notification_times.clear()

    def get_running_count(self) -> int:
        """获取正在运行的监控数量"""
        return len([state for state in self.monitor_states.values() if state])

    def is_monitor_running(self, record_id: int) -> bool:
        """检查指定监控是否在运行"""
        return record_id in self.monitor_states and self.monitor_states[record_id]

    def set_notification_cooldown(self, seconds: int):
        """设置通知冷却时间"""
        self.notification_cooldown = max(60, seconds)  # 最少1分钟

    def get_notification_cooldown(self) -> int:
        """获取通知冷却时间"""
        return self.notification_cooldown
