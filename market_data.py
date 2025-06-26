import logging
import time
from typing import Dict, Optional

import requests

from config_manager import ConfigManager


class MarketDataFetcher:
    """市场数据获取器"""

    def __init__(self):
        self.base_url = 'https://public-api.birdeye.so/defi/v3'
        self._headers_cache = None
        self._last_config_update = 0
        # 初始化时加载配置
        self.refresh_config()
        # 注册到配置管理器，支持统一刷新
        ConfigManager.register_service(self)

    def refresh_config(self):
        """刷新配置缓存 - 可通过Web界面的刷新按钮调用"""
        self._headers_cache = {
            'X-API-KEY': ConfigManager.get_config('API_KEY', ''),
            'accept': 'application/json',
            'x-chain': ConfigManager.get_config('CHAIN_HEADER', 'solana')
        }
        self._last_config_update = time.time()
        logging.info("MarketDataFetcher配置已刷新")

    @property
    def headers(self):
        """获取请求头，使用缓存机制提高性能"""
        if not self._headers_cache:
            self.refresh_config()
        return self._headers_cache

    def get_market_data(self, address: str = None) -> Optional[Dict]:
        """获取市场数据"""
        try:
            url = f'{self.base_url}/token/market-data'
            params = {'address': address}

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            data = response.json().get('data', {})
            return data

        except requests.exceptions.RequestException as e:
            logging.error(f"获取市场数据失败: {e}")
            return None
        except Exception as e:
            logging.error(f"解析市场数据失败: {e}")
            return None

    def get_price_info(self, address: str = None) -> Optional[Dict]:
        """获取价格信息"""
        market_data = self.get_market_data(address)
        if not market_data:
            return None

        try:
            price_info = {
                'price': market_data.get('price', 0),
                'market_cap': market_data.get('market_cap', 0),
                'volume_24h': 0,  # 新API中不包含此字段
                'price_change_24h': 0,  # 新API中不包含此字段
                'liquidity': market_data.get('liquidity', 0),
                'total_supply': market_data.get('total_supply', 0),
                'circulating_supply': market_data.get('circulating_supply', 0),
                'fdv': market_data.get('fdv', 0),
                'timestamp': int(time.time())
            }
            return price_info
        except Exception as e:
            logging.error(f"处理价格信息失败: {e}")
            return None

    def format_price_info(self, price_info: Dict) -> str:
        """格式化价格信息为可读字符串"""
        if not price_info:
            return "无法获取价格信息"

        formatted_info = f"""
价格: ${price_info['price']:.8f}
市值: ${price_info['market_cap']:,.2f}
流动性: ${price_info['liquidity']:,.2f}
总供应量: {price_info['total_supply']:,.0f}
流通供应量: {price_info['circulating_supply']:,.0f}
完全稀释估值: ${price_info['fdv']:,.2f}
更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(price_info['timestamp']))}
        """.strip()

        # 如果有24小时数据，则添加
        if price_info.get('volume_24h', 0) > 0:
            formatted_info += f"\n24小时交易量: ${price_info['volume_24h']:,.2f}"
        if price_info.get('price_change_24h', 0) != 0:
            formatted_info += f"\n24小时涨跌幅: {price_info['price_change_24h']:.2f}%"

        return formatted_info
