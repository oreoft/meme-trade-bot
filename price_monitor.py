import threading
import time
from datetime import datetime
from typing import Dict, List

from market_data import MarketDataFetcher
from models import MonitorRecord, MonitorLog, SessionLocal
from notifier import Notifier
from trader import SolanaTrader


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
            print("PriceMonitor 已经初始化，跳过重复初始化")
            return

        with self._lock:
            if self._initialized:
                print("PriceMonitor 已经初始化，跳过重复初始化")
                return

            self.running_monitors: Dict[int, threading.Thread] = {}
            self.monitor_states: Dict[int, bool] = {}
            self.market_fetcher = MarketDataFetcher()
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
            print("自动恢复已完成，跳过重复执行")
            return

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

            # 标记为已完成
            self._auto_recovery_done = True

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
        print(f"{reason}: {record.name}")
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
        sol_info = self.market_fetcher.get_price_info(sol_mint)
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
        tx_hash = trader.buy_token_for_sol(record.token_address, actual_buy_percentage)
        if tx_hash:
            print(f"买入交易成功: {tx_hash}")
            log = MonitorLog(
                monitor_record_id=record_id,
                price=price_info['price'],
                market_cap=price_info['market_cap'],
                threshold_reached=True,
                action_taken="自动买入",
                tx_hash=str(tx_hash)
            )
            db.add(log)
            db.commit()
            # 买入专用通知
            notifier.send_trade_notification(
                tx_hash, buy_amount, estimated_usd_value, record.name, record.token_symbol, action_type='buy'
            )
            record._accumulated_buy_usd = getattr(record, '_accumulated_buy_usd', 0.0) + estimated_usd_value
            if record.execution_mode == "single" or actual_buy_percentage >= 1.0:
                self._complete_monitor_task(
                    record_id, record, notifier, db,
                    reason="买入任务完成，停止监控任务",
                    message_title=f"🎯 【{record.name}】买入任务完成",
                    message_content=f"【{record.name}】买入任务已完成，监控任务自动停止。"
                )
                return False
            else:
                print(f"买入完成，继续监控等待下一次低于阈值...")
                time.sleep(60)
                return True
        else:
            print(f"买入交易失败")
            notifier.send_error_notification(f"买入交易失败", record.name)
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
        tx_hash = trader.sell_token_for_sol(record.token_address, actual_sell_percentage)
        if tx_hash:
            print(f"交易成功: {tx_hash}")
            log = MonitorLog(
                monitor_record_id=record_id,
                price=price_info['price'],
                market_cap=price_info['market_cap'],
                threshold_reached=True,
                action_taken="自动出售",
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
                print(f"交易完成，继续监控等待下一次达到阈值...")
                time.sleep(60)
                return True
        else:
            print(f"交易执行失败")
            notifier.send_error_notification(f"交易执行失败", record.name)
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
                    price_info = self.market_fetcher.get_price_info(record.token_address)
                    if not price_info:
                        time.sleep(record.check_interval)
                        continue

                    record.last_check_at = datetime.utcnow()
                    record.last_price = price_info['price']
                    record.last_market_cap = price_info['market_cap']
                    db.commit()

                    self._log_monitor_data(record_id, price_info, record.threshold)

                    is_buy = getattr(record, 'type', 'sell') == 'buy'
                    action_type = 'buy' if is_buy else 'sell'

                    if is_buy:
                        if price_info['market_cap'] < record.threshold:
                            print(
                                f"监控 {record.name} 市值低于阈值，尝试买入。当前: ${price_info['market_cap']:,.2f}, 阈值: ${record.threshold:,.2f}")
                            notifier.send_price_alert(
                                {**price_info, 'threshold': record.threshold, 'token_symbol': record.token_symbol},
                                record.name, True, 'buy')
                            if not hasattr(record, '_accumulated_buy_usd'):
                                record._accumulated_buy_usd = 0.0
                            sol_balance = trader.get_sol_balance()
                            if sol_balance <= 0:
                                self._complete_monitor_task(
                                    record_id, record, notifier, db,
                                    reason="SOL余额为0，停止买入监控任务",
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
                                print(f"买入执行失败: {e}")
                                notifier.send_error_notification(f"买入执行失败: {e}", record.name)
                        else:
                            print(
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
                        print(
                            f"监控 {record.name} 市值达到阈值！当前: ${price_info['market_cap']:,.2f}, 阈值: ${record.threshold:,.2f}")
                        notifier.send_price_alert(
                            {**price_info, 'threshold': record.threshold, 'token_symbol': record.token_symbol},
                            record.name, True, 'sell')
                        try:
                            token_balance_before = trader.get_token_balance(record.token_address)
                            if token_balance_before <= 0:
                                if getattr(record, 'pre_sniper_mode', False):
                                    print(f"余额不足，预抢购模式开启，跳过本次监控: {record.name}")
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
                            print(f"交易执行失败: {e}")
                            notifier.send_error_notification(f"交易执行失败: {e}", record.name)
                    else:
                        print(
                            f"监控 {record.name} 市值未达到阈值。当前: ${price_info['market_cap']:,.2f}, 阈值: ${record.threshold:,.2f}")
                        notify, percent_change = self._should_send_price_update(record.token_address,
                                                                                price_info['market_cap'])
                        if notify:
                            notifier.send_price_alert(
                                {**price_info, 'threshold': record.threshold, 'token_symbol': record.token_symbol},
                                record.name, False, 'sell', percent_change)
                    time.sleep(record.check_interval)

                except Exception as e:
                    print(f"监控 {record.name} 过程中出错: {e}")
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
            # 注意：不在这里清理last_market_caps，因为其他监控可能还在使用相同的token

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

        # 清理所有市值记录
        self.last_market_caps.clear()

    def get_running_count(self) -> int:
        """获取正在运行的监控数量"""
        return len([state for state in self.monitor_states.values() if state])

    def is_monitor_running(self, record_id: int) -> bool:
        """检查指定监控是否在运行"""
        return record_id in self.monitor_states and self.monitor_states[record_id]

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
