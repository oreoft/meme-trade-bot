import logging
import threading
import time
from datetime import datetime
from typing import Dict

from core.trader import SolanaTrader
from database.models import MonitorRecord, MonitorLog, SwingMonitorRecord, SessionLocal
from services import TokenAPI
from services.notifier import Notifier
from utils import normalize_sol_address


class PriceMonitor:
    """价格监控器 - 单例模式"""

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 防止重复初始化
        if self._initialized:
            logging.debug("PriceMonitor 已经初始化，跳过重复初始化")
            return

        with self._lock:
            if self._initialized:
                logging.debug("PriceMonitor 已经初始化，跳过重复初始化")
                return

            # 普通监控状态
            self.running_monitors: Dict[int, threading.Thread] = {}
            self.monitor_states: Dict[int, bool] = {}

            # 波段监控状态
            self.running_swing_monitors: Dict[int, threading.Thread] = {}
            self.swing_monitor_states: Dict[int, bool] = {}

            # 为每个token地址维护上一次的市值（而不是按record_id）
            self.last_market_caps: Dict[str, float] = {}
            # 市值变化阈值（百分比）
            self.market_cap_change_threshold = 0.05  # 5%变化时推送

            # 防重复执行标志
            self._auto_recovery_done = False

            # 启动时自动恢复监控任务
            self._auto_recover_monitors()

            self._initialized = True

    def _auto_recover_monitors(self):
        """启动时自动恢复所有状态为monitoring的监控任务"""
        # 防重复执行
        if self._auto_recovery_done:
            logging.debug("自动恢复已完成，跳过重复执行")
            return

        logging.info("正在自动恢复监控任务...")
        db = SessionLocal()
        try:
            # 恢复普通监控任务
            monitoring_records = db.query(MonitorRecord).filter(
                MonitorRecord.status == "monitoring"
            ).all()

            recovered_count = 0
            for record in monitoring_records:
                try:
                    # 创建通知器并发送启动通知
                    notifier = Notifier(webhook_url=record.webhook_url)
                    notifier.send_startup_notification(record.name)

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
                    logging.info(f"已恢复普通监控任务: {record.name} (ID: {record.id})")
                except Exception as e:
                    logging.error(f"恢复普通监控任务失败 {record.name} (ID: {record.id}): {e}")
                    # 将失败的任务状态设为stopped
                    record.status = "stopped"
                    db.commit()

            # 恢复波段监控任务
            swing_monitoring_records = db.query(SwingMonitorRecord).filter(
                SwingMonitorRecord.status == "monitoring"
            ).all()

            swing_recovered_count = 0
            for record in swing_monitoring_records:
                try:
                    # 创建通知器并发送启动通知
                    notifier = Notifier(webhook_url=record.webhook_url)
                    notifier.send_startup_notification(record.name)

                    # 启动波段监控线程
                    self.swing_monitor_states[record.id] = True
                    thread = threading.Thread(
                        target=self._swing_monitor_loop,
                        args=(record.id,),
                        daemon=True
                    )
                    thread.start()
                    self.running_swing_monitors[record.id] = thread
                    swing_recovered_count += 1
                    logging.info(f"已恢复波段监控任务: {record.name} (ID: {record.id})")
                except Exception as e:
                    logging.error(f"恢复波段监控任务失败 {record.name} (ID: {record.id}): {e}")
                    # 将失败的任务状态设为stopped
                    record.status = "stopped"
                    db.commit()

            total_recovered = recovered_count + swing_recovered_count
            if total_recovered > 0:
                logging.info(
                    f"成功恢复 {recovered_count} 个普通监控任务，{swing_recovered_count} 个波段监控任务，共 {total_recovered} 个")
            else:
                logging.info("没有需要恢复的监控任务")

            # 标记为已完成
            self._auto_recovery_done = True

        except Exception as e:
            logging.error(f"自动恢复监控任务时出错: {e}")
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

            # 创建通知器并发送启动通知
            notifier = Notifier(webhook_url=record.webhook_url)
            notifier.send_startup_notification(record.name)

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

        # 注意：不在这里清理last_market_caps，因为其他监控可能还在使用相同的token

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

    def start_swing_monitor(self, record_id: int):
        """启动单个波段监控任务"""
        if record_id in self.running_swing_monitors and self.swing_monitor_states.get(record_id, False):
            return False, "波段监控已在运行中"

        db = SessionLocal()
        try:
            record = db.query(SwingMonitorRecord).filter(SwingMonitorRecord.id == record_id).first()
            if not record:
                return False, "波段监控记录不存在"

            # 更新状态为监控中
            record.status = "monitoring"
            db.commit()

            # 创建通知器并发送启动通知
            notifier = Notifier(webhook_url=record.webhook_url)
            notifier.send_startup_notification(record.name)

            # 启动波段监控线程
            self.swing_monitor_states[record_id] = True
            thread = threading.Thread(target=self._swing_monitor_loop, args=(record_id,), daemon=True)
            thread.start()
            self.running_swing_monitors[record_id] = thread

            return True, "波段监控启动成功"
        except Exception as e:
            return False, f"启动失败: {str(e)}"
        finally:
            db.close()

    def stop_swing_monitor(self, record_id: int):
        """停止单个波段监控任务"""
        if record_id in self.swing_monitor_states:
            self.swing_monitor_states[record_id] = False

        if record_id in self.running_swing_monitors:
            del self.running_swing_monitors[record_id]

        # 更新数据库状态
        db = SessionLocal()
        try:
            record = db.query(SwingMonitorRecord).filter(SwingMonitorRecord.id == record_id).first()
            if record:
                record.status = "stopped"
                db.commit()
        finally:
            db.close()

        return True, "波段监控已停止"

    def _should_send_price_update(self, token_address: str, current_mc: float) -> tuple:
        """检查是否应该发送价格更新通知（基于token地址的市值变化），返回(是否通知, 百分比变化)"""
        if token_address not in self.last_market_caps:
            # 第一次检查，记录市值但不发送通知
            self.last_market_caps[token_address] = current_mc
            return False, None

        last_mc = self.last_market_caps[token_address]
        percent_change = None
        if last_mc > 0:
            try:
                percent_change = (current_mc - last_mc) / last_mc * 100
            except Exception:
                percent_change = None
            change_percent = abs((current_mc - last_mc) / last_mc)
            if change_percent >= self.market_cap_change_threshold:
                self.last_market_caps[token_address] = current_mc
                return True, percent_change
        return False, percent_change

    def _complete_monitor_task(self, record_id: int, record, notifier, db, reason: str, message_title: str,
                               message_content: str):
        """完成监控任务的通用方法"""
        logging.info(f"{reason}: {record.name}")
        # 更新状态为已完成
        record.status = "completed"
        db.commit()

        # 发送完成通知
        notifier.send_message(message_title, message_content)

        # 停止监控循环
        self.monitor_states[record_id] = False

    def _handle_buy_monitor(self, record, trader, notifier, price_info, db, record_id, sol_balance):
        """处理买入监听逻辑"""
        # 获取SOL的美元价格
        sol_mint = "So11111111111111111111111111111111111111112"
        sol_info = TokenAPI().get_market_data(normalize_sol_address(sol_mint))
        sol_usd_price = sol_info['price'] if sol_info and sol_info['price'] else 0.0
        actual_buy_percentage = record.sell_percentage
        if record.execution_mode != "single":
            min_hold_usd = getattr(record, 'minimum_hold_value', 0.0)
            min_hold_sol = min_hold_usd / sol_usd_price if sol_usd_price > 0 else 0.0
            if sol_balance - (sol_balance * actual_buy_percentage) < min_hold_sol:
                actual_buy_percentage = 1.0  # 全部买入
        buy_amount = sol_balance * actual_buy_percentage
        estimated_usd_value = buy_amount * sol_usd_price
        max_buy = getattr(record, 'max_buy_amount', 0.0)
        if max_buy > 0 and (getattr(record, '_accumulated_buy_usd', 0.0) + estimated_usd_value) > max_buy:
            self._complete_monitor_task(
                record_id, record, notifier, db,
                reason="累计买入金额已达上限，停止监控任务",
                message_title=f"🎯 【{record.name}】累计买入上限已达",
                message_content=f"【{record.name}】累计买入金额已达上限（{max_buy} USD），监控任务自动停止。"
            )
            return False
        result = trader.buy_token_for_sol(record.token_address, actual_buy_percentage)
        if result["success"]:
            tx_hash = result["tx_hash"]
            logging.info(f"买入交易成功: {tx_hash}")
            log = MonitorLog(
                monitor_record_id=record_id,
                price=price_info['price'],
                market_cap=price_info['market_cap'],
                threshold_reached=True,
                transaction_usd=estimated_usd_value,
                action_taken="自动买入",
                action_type="buy",
                tx_hash=str(tx_hash)
            )
            db.add(log)
            db.commit()
            # 买入专用通知
            notifier.send_trade_notification(
                tx_hash, buy_amount, estimated_usd_value, record.name, record.token_symbol, action_type='buy'
            )
            # 累计金额持久化
            record.accumulated_buy_usd = (record.accumulated_buy_usd or 0.0) + estimated_usd_value
            db.commit()
            if record.execution_mode == "single" or actual_buy_percentage >= 1.0:
                self._complete_monitor_task(
                    record_id, record, notifier, db,
                    reason="买入任务完成，停止监控任务",
                    message_title=f"🎯 【{record.name}】买入任务完成",
                    message_content=f"【{record.name}】买入任务已完成，监控任务自动停止。"
                )
                return False
            else:
                logging.info(f"买入完成，继续监控等待下一次低于阈值...")
                time.sleep(60)
                return True
        else:
            error_msg = result["error"]
            logging.error(f"买入交易失败: {error_msg}")
            notifier.send_error_notification(f"买入交易失败: {error_msg}", record.name)
            return True

    def _handle_sell_monitor(self, record, trader, notifier, price_info, db, record_id, token_balance_before):
        """处理卖出监听逻辑"""
        actual_sell_percentage = record.sell_percentage
        if record.execution_mode != "single" and price_info['price'] is not None:
            total_asset_value = token_balance_before * price_info['price']
            minimum_hold_value = getattr(record, 'minimum_hold_value', 50.0)
            if total_asset_value < minimum_hold_value:
                actual_sell_percentage = 1.0
        actual_sell_amount = token_balance_before * actual_sell_percentage
        estimated_usd_value = actual_sell_amount * price_info['price']
        result = trader.sell_token_for_sol(record.token_address, actual_sell_percentage)
        if result["success"]:
            tx_hash = result["tx_hash"]
            logging.info(f"交易成功: {tx_hash}")
            log = MonitorLog(
                monitor_record_id=record_id,
                price=price_info['price'],
                market_cap=price_info['market_cap'],
                threshold_reached=True,
                action_taken="自动出售",
                action_type="sell",
                transaction_usd=estimated_usd_value,
                tx_hash=str(tx_hash)
            )
            db.add(log)
            db.commit()
            # 卖出专用通知
            notifier.send_trade_notification(
                tx_hash, actual_sell_amount, estimated_usd_value, record.name, record.token_symbol, action_type='sell'
            )
            if record.execution_mode == "single":
                sell_percentage_text = f"{(actual_sell_percentage * 100):.1f}%"
                self._complete_monitor_task(
                    record_id, record, notifier, db,
                    reason="单次执行模式完成，停止监控任务",
                    message_title=f"🎯 【{record.name}】单次执行完成",
                    message_content=f"【{record.name}】单次执行模式已完成交易（出售{sell_percentage_text}），监控任务自动停止。"
                )
                return False
            elif actual_sell_percentage >= 1.0:
                self._complete_monitor_task(
                    record_id, record, notifier, db,
                    reason="已100%出售完毕，停止监控任务",
                    message_title=f"🎯 【{record.name}】监控任务完成",
                    message_content=f"【{record.name}】已100%出售完毕，监控任务自动停止。"
                )
                return False
            else:
                logging.info(f"交易完成，继续监控等待下一次达到阈值...")
                time.sleep(60)
                return True
        else:
            error_msg = result["error"]
            logging.error(f"交易执行失败: {error_msg}")
            notifier.send_error_notification(f"交易执行失败: {error_msg}", record.name)
            return True

    def _monitor_loop(self, record_id: int):
        """监控循环"""
        db = SessionLocal()
        try:
            record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
            if not record:
                return

            private_key = record.private_key_obj.private_key
            trader = SolanaTrader(private_key=private_key)
            notifier = Notifier(webhook_url=record.webhook_url)

            while self.monitor_states.get(record_id, False):
                try:
                    price_info = TokenAPI().get_market_data(normalize_sol_address(record.token_address))
                    if not price_info:
                        time.sleep(record.check_interval)
                        continue

                    record.last_check_at = datetime.utcnow()
                    record.last_price = price_info['price']
                    record.last_market_cap = price_info['market_cap']
                    db.commit()

                    self._log_monitor_data(record_id=record_id, price_info=price_info, threshold=record.threshold,
                                           action_type='monitoring')

                    is_buy = getattr(record, 'type', 'sell') == 'buy'

                    if is_buy:
                        if price_info['market_cap'] < record.threshold:
                            logging.info(
                                f"监控 {record.name} 市值低于阈值，尝试买入。当前: ${price_info['market_cap']:,.2f}, 阈值: ${record.threshold:,.2f}")
                            notifier.send_price_alert(
                                {**price_info, 'threshold': record.threshold, 'token_symbol': record.token_symbol},
                                record.name, True, 'buy')
                            if not hasattr(record, '_accumulated_buy_usd'):
                                record._accumulated_buy_usd = 0.0
                            sol_balance = trader.get_sol_balance()
                            # 计算买入数量, 账号里面需要留一点sol作为token的账户的租费,如果token全部卖了,sol理论上可以全提走
                            buy_amount = (sol_balance * record.sell_percentage) - (
                                0.0021 if record.sell_percentage == 1 else 0)
                            if sol_balance <= 0 or buy_amount <= 0:
                                self._complete_monitor_task(
                                    record_id, record, notifier, db,
                                    reason="SOL余额不足，停止买入监控任务",
                                    message_title=f"⚠️ 【{record.name}】SOL余额不足",
                                    message_content=f"【{record.name}】SOL余额为0，监控任务自动停止。"
                                )
                                break
                            try:
                                should_continue = self._handle_buy_monitor(record, trader, notifier, price_info, db,
                                                                           record_id, sol_balance)
                                if not should_continue:
                                    break
                            except Exception as e:
                                logging.error(f"买入执行失败: {e}")
                                notifier.send_error_notification(f"买入执行失败: {e}", record.name)
                        else:
                            logging.debug(
                                f"监控 {record.name} 市值未低于阈值。当前: ${price_info['market_cap']:,.2f}, 阈值: ${record.threshold:,.2f}")
                            notify, percent_change = self._should_send_price_update(record.token_address,
                                                                                    price_info['market_cap'])
                            if notify:
                                notifier.send_price_alert(
                                    {**price_info, 'threshold': record.threshold, 'token_symbol': record.token_symbol},
                                    record.name, False, 'buy', percent_change)
                        time.sleep(record.check_interval)
                        continue
                    # 卖出监听
                    if price_info['market_cap'] >= record.threshold:
                        logging.info(
                            f"监控 {record.name} 市值达到阈值！当前: ${price_info['market_cap']:,.2f}, 阈值: ${record.threshold:,.2f}")
                        notifier.send_price_alert(
                            {**price_info, 'threshold': record.threshold, 'token_symbol': record.token_symbol},
                            record.name, True, 'sell')
                        try:
                            token_balance_before = trader.get_token_balance(record.token_address)
                            if token_balance_before <= 0:
                                if getattr(record, 'pre_sniper_mode', False):
                                    logging.info(f"余额不足，预抢购模式开启，跳过本次监控: {record.name}")
                                    time.sleep(record.check_interval)
                                    continue
                                else:
                                    self._complete_monitor_task(
                                        record_id, record, notifier, db,
                                        reason="代币余额为0，停止监控任务",
                                        message_title=f"⚠️ 【{record.name}】余额不足",
                                        message_content=f"【{record.name}】代币余额为0，监控任务自动停止。"
                                    )
                                    break
                            should_continue = self._handle_sell_monitor(record, trader, notifier, price_info, db,
                                                                        record_id, token_balance_before)
                            if not should_continue:
                                break
                        except Exception as e:
                            logging.error(f"交易执行失败: {e}")
                            notifier.send_error_notification(f"交易执行失败: {e}", record.name)
                    else:
                        logging.debug(
                            f"监控 {record.name} 市值未达到阈值。当前: ${price_info['market_cap']:,.2f}, 阈值: ${record.threshold:,.2f}")
                        notify, percent_change = self._should_send_price_update(record.token_address,
                                                                                price_info['market_cap'])
                        if notify:
                            notifier.send_price_alert(
                                {**price_info, 'threshold': record.threshold, 'token_symbol': record.token_symbol},
                                record.name, False, 'sell', percent_change)
                    time.sleep(record.check_interval)

                except Exception as e:
                    logging.error(f"监控 {record.name} 过程中出错: {e}")
                    record.status = "error"
                    db.commit()
                    time.sleep(record.check_interval)

        except Exception as e:
            logging.error(f"监控线程异常: {e}")
        finally:
            # 清理状态
            if record_id in self.monitor_states:
                self.monitor_states[record_id] = False
            if record_id in self.running_monitors:
                del self.running_monitors[record_id]
            # 注意：不在这里清理last_market_caps，因为其他监控可能还在使用相同的token

            # 更新数据库状态
            try:
                record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
                if record and record.status == "monitoring":
                    record.status = "stopped"
                    db.commit()
            except:
                logging.error(f"更新监控记录状态失败: {record_id}")
            finally:
                db.close()

    def _log_monitor_data(self, record_id: int, price_info: dict, threshold: float, *,
                          monitor_type: str = 'normal', price_type: str = None, current_value: float = None,
                          sell_threshold: float = None,
                          transaction_usd: float = None,
                          buy_threshold: float = None, action_type: str = None,
                          action_taken: str = None, tx_hash: str = None, watch_token_address: str = None,
                          trade_token_address: str = None):
        """记录监控数据，兼容普通和波段监控"""
        db = SessionLocal()
        try:
            log = MonitorLog(
                monitor_record_id=record_id,
                timestamp=datetime.utcnow(),
                price=price_info.get('price'),
                market_cap=price_info.get('market_cap'),
                threshold_reached=(
                        price_info.get('market_cap') >= threshold) if threshold is not None and price_info.get(
                    'market_cap') is not None else False,
                action_taken=action_taken or (
                    "监控中" if threshold is not None and price_info.get('market_cap') is not None and price_info.get(
                        'market_cap') < threshold else "阈值达到"),
                tx_hash=tx_hash,
                monitor_type=monitor_type,
                price_type=price_type,
                current_value=current_value,
                sell_threshold=sell_threshold,
                buy_threshold=buy_threshold,
                action_type=action_type,
                watch_token_address=watch_token_address,
                trade_token_address=trade_token_address,
                transaction_usd=transaction_usd,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()

    def stop_all_monitors(self):
        """停止所有监控任务"""
        # 停止普通监控
        for record_id in list(self.monitor_states.keys()):
            self.stop_monitor(record_id)

        # 停止波段监控
        for record_id in list(self.swing_monitor_states.keys()):
            self.stop_swing_monitor(record_id)

        # 清理所有市值记录
        self.last_market_caps.clear()

    def get_running_count(self) -> int:
        """获取正在运行的监控数量"""
        normal_count = len([state for state in self.monitor_states.values() if state])
        swing_count = len([state for state in self.swing_monitor_states.values() if state])
        return normal_count + swing_count

    def get_swing_running_count(self) -> int:
        """获取正在运行的波段监控数量"""
        return len([state for state in self.swing_monitor_states.values() if state])

    def is_monitor_running(self, record_id: int) -> bool:
        """检查指定监控是否在运行"""
        return record_id in self.monitor_states and self.monitor_states[record_id]

    def is_swing_monitor_running(self, record_id: int) -> bool:
        """检查指定波段监控是否在运行"""
        return record_id in self.swing_monitor_states and self.swing_monitor_states[record_id]

    def set_market_cap_change_threshold(self, threshold: float):
        """设置市值变化阈值（百分比）"""
        self.market_cap_change_threshold = max(0.01, min(1.0, threshold))  # 限制在1%-100%之间

    def get_market_cap_change_threshold(self) -> float:
        """获取市值变化阈值"""
        return self.market_cap_change_threshold

    def cleanup_unused_market_caps(self):
        """清理不再使用的token市值缓存"""
        db = SessionLocal()
        try:
            # 获取所有正在运行的监控的token地址
            active_tokens = set()
            for record_id in self.monitor_states.keys():
                if self.monitor_states[record_id]:  # 正在运行
                    record = db.query(MonitorRecord).filter(MonitorRecord.id == record_id).first()
                    if record:
                        active_tokens.add(record.token_address)

            # 清理不在活跃列表中的token缓存
            tokens_to_remove = []
            for token_address in self.last_market_caps.keys():
                if token_address not in active_tokens:
                    tokens_to_remove.append(token_address)

            for token_address in tokens_to_remove:
                del self.last_market_caps[token_address]

        finally:
            db.close()

    def _swing_monitor_loop(self, record_id: int):
        """波段监控循环"""
        db = SessionLocal()
        try:
            record = db.query(SwingMonitorRecord).filter(SwingMonitorRecord.id == record_id).first()
            if not record:
                return

            private_key = record.private_key_obj.private_key
            trader = SolanaTrader(private_key=private_key)
            notifier = Notifier(webhook_url=record.webhook_url)

            last_trade_time = 0

            while self.swing_monitor_states.get(record_id, False):
                try:
                    logging.info(
                        f"波段监控 {record.name} 开始新的循环迭代，时间: {datetime.utcnow().strftime('%H:%M:%S')}")

                    current_time = time.time()
                    if current_time - last_trade_time < 60:
                        remaining_cooldown = 60 - (current_time - last_trade_time)
                        logging.info(f"波段监控 {record.name} 交易冷却中，剩余 {remaining_cooldown:.1f} 秒")
                        time.sleep(min(remaining_cooldown, record.check_interval))
                        continue

                    watch_price_info = TokenAPI().get_market_data(normalize_sol_address(record.watch_token_address))
                    if not watch_price_info:
                        time.sleep(record.check_interval)
                        continue

                    record.last_check_at = datetime.utcnow()
                    record.last_watch_price = watch_price_info['price']
                    record.last_watch_market_cap = watch_price_info['market_cap']
                    db.commit()

                    if record.price_type == "price":
                        current_value = watch_price_info['price']
                        sell_threshold = record.sell_threshold
                        buy_threshold = record.buy_threshold
                        value_name = "价格"
                        value_unit = "USD"
                    else:
                        current_value = watch_price_info['market_cap']
                        sell_threshold = record.sell_threshold
                        buy_threshold = record.buy_threshold
                        value_name = "市值"
                        value_unit = "USD"

                    logging.debug(
                        f"波段监控 {record.name} 当前{value_name}: ${current_value:,.2f}, 卖出阈值: ${sell_threshold:,.2f}, 买入阈值: ${buy_threshold:,.2f}")

                    # 记录监控日志
                    self._log_monitor_data(
                        record_id=record.id,
                        price_info=watch_price_info,
                        threshold=None,
                        monitor_type='swing',
                        price_type=record.price_type,
                        current_value=current_value,
                        sell_threshold=sell_threshold,
                        buy_threshold=buy_threshold,
                        action_type='monitoring',
                        action_taken=None,
                        watch_token_address=record.watch_token_address,
                        trade_token_address=record.trade_token_address
                    )

                    # 判断是否达到卖出条件
                    if current_value >= sell_threshold:
                        logging.info(
                            f"波段监控 {record.name} 达到卖出条件！当前{value_name}: ${current_value:,.2f}, 卖出阈值: ${sell_threshold:,.2f}")

                        try:
                            # 检查监听代币余额（卖出监听代币）
                            watch_token_balance = trader.get_token_balance(record.watch_token_address)
                            if watch_token_balance <= 0:
                                logging.info(f"波段监控 {record.name} 监听代币余额为0，跳过卖出")
                                time.sleep(record.check_interval)
                                continue

                            # 余额足够，发送卖出预警
                            notifier.send_price_alert(
                                {**watch_price_info, 'threshold': sell_threshold,
                                 'token_symbol': record.watch_token_symbol},
                                record.name, True, 'sell')

                            # 计算卖出比例
                            actual_sell_percentage = record.sell_percentage

                            # 检查是否需要全仓卖出
                            if record.all_in_threshold > 0:
                                if watch_price_info and watch_price_info['price']:
                                    total_value = watch_token_balance * watch_price_info['price']
                                    if total_value <= record.all_in_threshold:
                                        actual_sell_percentage = 1.0
                                        logging.info(f"波段监控 {record.name} 资产价值低于全仓阈值，全仓卖出")

                            # 执行卖出交易：卖出监听代币换取交易代币
                            result = self._execute_swing_trade(
                                trader, record.watch_token_address, record.trade_token_address,
                                actual_sell_percentage, 'sell', record, notifier, db
                            )

                            if result:
                                logging.info(f"波段监控 {record.name} 卖出交易完成，设置60秒冷却期")
                                # 设置交易冷却时间
                                last_trade_time = time.time()
                                # 在等待前更新数据库状态
                                record.last_check_at = datetime.utcnow()
                                db.commit()
                                # 立即等待60秒
                                logging.info(f"波段监控 {record.name} 开始60秒冷却等待...")
                                time.sleep(60)
                                logging.info(f"波段监控 {record.name} 冷却期结束，继续监控")
                                continue  # 跳过本次循环的常规检查间隔

                        except Exception as e:
                            logging.error(f"波段监控 {record.name} 卖出执行失败: {e}")
                            notifier.send_error_notification(f"波段卖出执行失败: {e}", record.name)
                            # 卖出失败时也要等待一下，避免频繁重试
                            time.sleep(record.check_interval)

                    # 判断是否达到买入条件
                    elif current_value <= buy_threshold:
                        logging.info(
                            f"波段监控 {record.name} 达到买入条件！当前{value_name}: ${current_value:,.2f}, 买入阈值: ${buy_threshold:,.2f}")

                        try:
                            # 检查交易代币余额（用交易代币买入监听代币）
                            trade_token_balance = trader.get_token_balance(record.trade_token_address)
                            if trade_token_balance <= 0:
                                logging.info(f"波段监控 {record.name} 交易代币余额为0，跳过买入")
                                time.sleep(record.check_interval)
                                continue

                            # 余额足够，发送买入预警
                            notifier.send_price_alert(
                                {**watch_price_info, 'threshold': buy_threshold,
                                 'token_symbol': record.watch_token_symbol},
                                record.name, True, 'buy')

                            # 计算买入比例
                            actual_buy_percentage = record.buy_percentage

                            # 检查是否需要全仓买入
                            if record.all_in_threshold > 0:
                                trade_token_price_info = TokenAPI().get_market_data(
                                    normalize_sol_address(record.trade_token_address))
                                if trade_token_price_info and trade_token_price_info['price']:
                                    total_value = trade_token_balance * trade_token_price_info['price']
                                    if total_value <= record.all_in_threshold:
                                        actual_buy_percentage = 1.0
                                        logging.info(f"波段监控 {record.name} 资产价值低于全仓阈值，全仓买入")

                            # 执行买入交易：用交易代币买入监听代币
                            result = self._execute_swing_trade(
                                trader, record.trade_token_address, record.watch_token_address,
                                actual_buy_percentage, 'buy', record, notifier, db
                            )

                            if result:
                                logging.info(f"波段监控 {record.name} 买入交易完成，设置60秒冷却期")
                                # 设置交易冷却时间
                                last_trade_time = time.time()
                                # 在等待前更新数据库状态
                                record.last_check_at = datetime.utcnow()
                                db.commit()
                                # 立即等待60秒
                                logging.info(f"波段监控 {record.name} 开始60秒冷却等待...")
                                time.sleep(60)
                                logging.info(f"波段监控 {record.name} 冷却期结束，继续监控")
                                continue  # 跳过本次循环的常规检查间隔

                        except Exception as e:
                            logging.error(f"波段监控 {record.name} 买入执行失败: {e}")
                            notifier.send_error_notification(f"波段买入执行失败: {e}", record.name)
                            # 买入失败时也要等待一下，避免频繁重试
                            time.sleep(record.check_interval)

                    else:
                        # 价格在买入和卖出阈值之间，继续监控
                        logging.debug(f"波段监控 {record.name} {value_name}在正常范围内，继续监控")

                        # 检查是否需要发送价格变化通知
                        notify, percent_change = self._should_send_price_update(record.watch_token_address,
                                                                                current_value)
                        if notify:
                            notifier.send_price_alert(
                                {**watch_price_info, 'threshold': sell_threshold,
                                 'token_symbol': record.watch_token_symbol},
                                record.name, False, 'swing', percent_change)

                    time.sleep(record.check_interval)

                except Exception as e:
                    logging.error(f"波段监控 {record.name} 过程中出错: {e}")
                    record.status = "error"
                    db.commit()
                    time.sleep(record.check_interval)

        except Exception as e:
            logging.error(f"波段监控线程异常: {e}")
        finally:
            # 清理状态
            if record_id in self.swing_monitor_states:
                self.swing_monitor_states[record_id] = False
            if record_id in self.running_swing_monitors:
                del self.running_swing_monitors[record_id]

            # 更新数据库状态
            try:
                record = db.query(SwingMonitorRecord).filter(SwingMonitorRecord.id == record_id).first()
                if record and record.status == "monitoring":
                    record.status = "stopped"
                    db.commit()
            except:
                logging.error(f"更新波段监控记录状态失败: {record_id}")
            finally:
                db.close()

    def _execute_swing_trade(self, trader: SolanaTrader, from_token: str, to_token: str,
                             percentage: float, action_type: str, record: SwingMonitorRecord,
                             notifier: Notifier, db) -> bool:
        """执行波段交易"""
        try:
            from_balance = trader.get_token_balance(from_token)
            if from_balance <= 0:
                logging.warning(f"波段监控 {record.name} {action_type} 源代币余额为0")
                return False

            trade_amount = from_balance * percentage
            from_price_info = TokenAPI().get_market_data(normalize_sol_address(from_token))
            estimated_usd_value = trade_amount * from_price_info['price'] if from_price_info and from_price_info[
                'price'] else 0
            from_decimals = trader.get_token_decimals(from_token)
            lamports = int(trade_amount * (10 ** from_decimals))
            quote = trader.get_quote(from_token, to_token, lamports)
            if not quote or "error" in quote:
                error_msg = quote.get("error", "获取交易报价失败") if quote else "获取交易报价失败"
                logging.error(f"波段监控 {record.name} {action_type} 报价失败: {error_msg}")
                notifier.send_error_notification(f"波段{action_type}报价失败: {error_msg}", record.name)
                return False

            tx_hash = trader.execute_swap(quote)
            if isinstance(tx_hash, str) and tx_hash:
                logging.info(f"波段监控 {record.name} {action_type} 交易成功: {tx_hash}")
                action_name = "买入" if action_type == 'buy' else "卖出"
                from_symbol = record.watch_token_symbol if from_token == record.watch_token_address else record.trade_token_symbol
                to_symbol = record.trade_token_symbol if to_token == record.trade_token_address else record.watch_token_symbol
                notifier.send_trade_notification(
                    tx_hash, trade_amount, estimated_usd_value,
                    record.name, f"{from_symbol}→{to_symbol}", action_type=action_type
                )
                # 记录交易日志
                watch_price_info = TokenAPI().get_market_data(normalize_sol_address(record.watch_token_address))
                if watch_price_info:
                    current_value = watch_price_info['price'] if record.price_type == 'price' else watch_price_info[
                        'market_cap']
                    self._log_monitor_data(
                        record_id=record.id,
                        price_info=watch_price_info,
                        threshold=None,
                        monitor_type='swing',
                        price_type=record.price_type,
                        current_value=current_value,
                        sell_threshold=record.sell_threshold,
                        buy_threshold=record.buy_threshold,
                        action_type=action_type,
                        action_taken=f"波段{action_name}",
                        tx_hash=tx_hash,
                        transaction_usd=estimated_usd_value,
                        watch_token_address=record.watch_token_address,
                        trade_token_address=record.trade_token_address
                    )
                logging.info(f"波段监控 {record.name} {action_type} _execute_swing_trade 返回 True")
                return True
            else:
                if isinstance(tx_hash, dict) and "error" in tx_hash:
                    error_msg = tx_hash["error"]
                else:
                    error_msg = "交易执行失败"
                logging.error(f"波段监控 {record.name} {action_type} 交易失败: {error_msg}")
                notifier.send_error_notification(f"波段{action_type}交易失败: {error_msg}", record.name)
                return False
        except Exception as e:
            logging.error(f"波段监控 {record.name} {action_type} 交易异常: {e}")
            notifier.send_error_notification(f"波段{action_type}交易异常: {e}", record.name)
            return False
