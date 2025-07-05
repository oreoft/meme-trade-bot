import logging
from typing import Dict

import requests


class Notifier:
    """通知器"""

    def __init__(self, webhook_url: str = None):
        self._webhook_url = webhook_url
        self.webhook_url = webhook_url

    def set_webhook_url(self, webhook_url: str):
        """设置webhook地址"""
        self._webhook_url = webhook_url
        self.webhook_url = webhook_url

    def send_message(self, title: str, content: str, msg_type: str = "text") -> bool:
        """发送消息到飞书"""
        if not self.webhook_url:
            logging.warning("未设置Webhook URL，无法发送通知")
            return False

        try:
            payload = {
                "msg_type": msg_type,
                "content": {
                    msg_type: content
                }
            }

            if title:
                payload["content"]["title"] = title

            response = requests.post(
                self.webhook_url,
                headers={'Content-Type': 'application/json'},
                json=payload
            )

            response.raise_for_status()

            result = response.json()
            if result.get('code') == 0:
                logging.info("通知发送成功")
                return True
            else:
                logging.error(f"通知发送失败: {result}")
                return False

        except Exception as e:
            logging.error(f"发送通知时出错: {e}")
            return False

    def send_price_alert(self, price_info: Dict, meme_name: str, threshold_reached: bool = False,
                         action_type: str = 'sell', percent_change: float = None) -> bool:
        """发送价格预警，action_type: 'buy' or 'sell'，支持百分比变化，格式为多行详细说明"""
        try:
            if threshold_reached:
                if action_type == 'buy':
                    title = f"【{meme_name}】市值阈值已达到！"
                    content = f"""【{meme_name}】市值阈值已达到！\n当前价格: ${price_info['price']:.8f}\n当前市值: ${price_info['market_cap']:,.2f}\n\n系统准备执行自动买入操作..."""
                else:
                    title = f"【{meme_name}】市值阈值已达到！"
                    content = f"""【{meme_name}】市值阈值已达到！\n当前价格: ${price_info['price']:.8f}\n当前市值: ${price_info['market_cap']:,.2f}\n\n系统准备执行自动出售操作..."""
            else:
                if percent_change is not None:
                    direction = "激增" if percent_change > 0 else "骤降"
                    title = f"【{meme_name}】市值{direction}{abs(percent_change):.2f}%"
                    content = f"{title}\n\n当前价格: ${price_info['price']:.8f}\n当前市值: ${price_info['market_cap']:,.2f}\n与上次相比{direction}{abs(percent_change):.2f}%"
                else:
                    title = f"【{meme_name}】市值变化通知"
                    content = f"当前价格: ${price_info['price']:.8f}\n当前市值: ${price_info['market_cap']:,.2f}"
            return self.send_message(title, content)
        except Exception as e:
            logging.error(f"发送价格预警失败: {e}")
            return False

    def send_trade_notification(self, tx_hash: str, amount: float, estimated_usd_value: float,
                                meme_name: str, token_symbol: str = None, action_type: str = 'sell') -> bool:
        """发送交易通知，action_type: 'buy' or 'sell'，格式为多行详细说明"""
        try:
            if action_type == 'buy':
                title = f"【{meme_name}】自动买入交易已完成！"
                content = f"""【{meme_name}】自动买入交易已完成！\n买入数量: {amount:.6f} {token_symbol or '代币'}\n估算价值: ${estimated_usd_value:.2f} USD\n交易哈希: {tx_hash}\n查看交易: https://solscan.io/tx/{tx_hash}"""
            else:
                title = f"【{meme_name}】自动出售交易已完成！"
                content = f"""【{meme_name}】自动出售交易已完成！\n出售数量: {amount:.6f} {token_symbol or '代币'}\n估算价值: ${estimated_usd_value:.2f} USD\n交易哈希: {tx_hash}\n查看交易: https://solscan.io/tx/{tx_hash}"""
            return self.send_message(title, content)
        except Exception as e:
            logging.error(f"发送交易通知失败: {e}")
            return False

    def send_error_notification(self, error_msg: str, meme_name: str = None) -> bool:
        """发送错误通知"""
        try:
            if meme_name:
                title = f"❌ 【{meme_name}】系统错误"
                content = f"【{meme_name}】监控系统遇到错误: {error_msg}"
            else:
                title = "❌ 系统错误"
                content = f"监控系统遇到错误: {error_msg}"

            return self.send_message(title, content)

        except Exception as e:
            logging.error(f"发送错误通知失败: {e}")
            return False

    def send_startup_notification(self, meme_name: str = None) -> bool:
        """发送启动通知"""
        try:
            if meme_name:
                title = f"🚀 【{meme_name}】监控系统启动"
                content = f"【{meme_name}】币价监控系统已启动，开始监控市值变化..."
            else:
                title = "🚀 监控系统启动"
                content = "币价监控系统已启动，开始监控市值变化..."

            return self.send_message(title, content)

        except Exception as e:
            logging.error(f"发送启动通知失败: {e}")
            return False
