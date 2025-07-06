import logging
import time
from typing import Dict, Optional

import requests

from config.config_manager import ConfigManager


class BirdEyeAPI:
    """BirdEye API 工具类"""

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
        logging.info("BirdEyeAPI配置已刷新")

    @property
    def headers(self):
        """获取请求头，使用缓存机制提高性能"""
        if not self._headers_cache:
            self.refresh_config()
        return self._headers_cache

    def get_token_meta_data(self, address: str) -> Optional[Dict]:
        """获取token元数据

        Args:
            address: token地址

        Returns:
            token元数据字典，包含address, name, symbol, decimals, extensions, logo_uri等字段
        """
        try:
            url = f'{self.base_url}/token/meta-data/single'
            params = {'address': address}

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            json_response = response.json()
            if not json_response.get('success', False):
                logging.error(f"获取token元数据API返回失败: {json_response}")
                return None

            data = json_response.get('data', {})
            logging.info(f"成功获取token元数据: {address}")
            return data

        except requests.exceptions.RequestException as e:
            logging.error(f"获取token元数据网络请求失败 [{address}]: {e}")
            return None
        except Exception as e:
            logging.error(f"解析token元数据失败 [{address}]: {e}")
            return None

    def get_market_data(self, address: str) -> Optional[Dict]:
        """获取token市场数据

        Args:
            address: token地址

        Returns:
            市场数据字典，包含price, market_cap, liquidity等字段
        """
        try:
            url = f'{self.base_url}/token/market-data'
            params = {'address': address}

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            json_response = response.json()
            if not json_response.get('success', False):
                logging.error(f"获取市场数据API返回失败: {json_response}")
                return None

            data = json_response.get('data', {})
            logging.info(f"成功获取市场数据: {address}")
            return data

        except requests.exceptions.RequestException as e:
            logging.error(f"获取市场数据网络请求失败 [{address}]: {e}")
            return None
        except Exception as e:
            logging.error(f"解析市场数据失败 [{address}]: {e}")
            return None

    def format_token_meta_data(self, meta_data: Dict) -> str:
        """格式化token元数据为可读字符串"""
        if not meta_data:
            return "无法获取token元数据"

        formatted_info = f"""
Token地址: {meta_data.get('address', '未知')}
Token名称: {meta_data.get('name', '未知')}
Token符号: {meta_data.get('symbol', '未知')}
小数位数: {meta_data.get('decimals', 0)}
        """.strip()

        # 添加描述信息（如果存在）
        extensions = meta_data.get('extensions', {})
        if extensions.get('description'):
            formatted_info += f"\n描述: {extensions['description']}"

        # 添加Logo URI（如果存在）
        if meta_data.get('logo_uri'):
            formatted_info += f"\nLogo: {meta_data['logo_uri']}"

        return formatted_info

    def format_market_data(self, market_data: Dict) -> str:
        """格式化市场数据为可读字符串"""
        if not market_data:
            return "无法获取市场数据"

        formatted_info = f"""
价格: ${market_data.get('price', 0):.8f}
市值: ${market_data.get('market_cap', 0):,.2f}
流动性: ${market_data.get('liquidity', 0):,.2f}
总供应量: {market_data.get('total_supply', 0):,.0f}
流通供应量: {market_data.get('circulating_supply', 0):,.0f}
完全稀释估值: ${market_data.get('fdv', 0):,.2f}
更新时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}
        """.strip()

        return formatted_info

    def get_token_info_combined(self, address: str) -> Optional[Dict]:
        """获取token的完整信息（元数据 + 市场数据）

        Args:
            address: token地址

        Returns:
            包含元数据和市场数据的组合字典
        """
        meta_data = self.get_token_meta_data(address)
        market_data = self.get_market_data(address)

        if not meta_data and not market_data:
            return None

        combined_info = {
            'meta_data': meta_data or {},
            'market_data': market_data or {},
            'timestamp': int(time.time())
        }

        return combined_info

    def format_token_info_combined(self, combined_info: Dict) -> str:
        """格式化组合token信息为可读字符串"""
        if not combined_info:
            return "无法获取token信息"

        meta_data = combined_info.get('meta_data', {})
        market_data = combined_info.get('market_data', {})

        formatted_info = "=== Token信息 ===\n"

        if meta_data:
            formatted_info += self.format_token_meta_data(meta_data) + "\n\n"

        if market_data:
            formatted_info += "=== 市场数据 ===\n"
            formatted_info += self.format_market_data(market_data)

        return formatted_info

    def get_wallet_token_list(self, wallet_address: str) -> Optional[Dict]:
        """获取钱包的token列表

        Args:
            wallet_address: 钱包地址

        Returns:
            包含钱包token列表的字典，包含wallet, totalUsd, items等字段
        """
        try:
            # 使用v1版本的钱包API
            url = 'https://public-api.birdeye.so/v1/wallet/token_list'
            params = {'wallet': wallet_address}

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            json_response = response.json()
            if not json_response.get('success', False):
                logging.error(f"获取钱包token列表API返回失败: {json_response}")
                return None

            data = json_response.get('data', {})
            logging.info(f"成功获取钱包token列表: {wallet_address}")
            return data

        except requests.exceptions.RequestException as e:
            logging.error(f"获取钱包token列表网络请求失败 [{wallet_address}]: {e}")
            return None
        except Exception as e:
            logging.error(f"解析钱包token列表失败 [{wallet_address}]: {e}")
            return None

    def format_wallet_token_list(self, wallet_data: Dict) -> str:
        """格式化钱包token列表为可读字符串"""
        if not wallet_data:
            return "无法获取钱包token列表"

        wallet_address = wallet_data.get('wallet', '未知')
        total_usd = wallet_data.get('totalUsd', 0)
        items = wallet_data.get('items', [])

        formatted_info = f"""
钱包地址: {wallet_address}
总价值: ${total_usd:.2f}
Token数量: {len(items)}

=== Token列表 ===
        """.strip()

        if items:
            formatted_info += "\n"
            for item in items:
                name = item.get('name', '未知')
                symbol = item.get('symbol', '未知')
                ui_amount = item.get('uiAmount', 0)
                price_usd = item.get('priceUsd', 0)
                value_usd = item.get('valueUsd', 0)

                formatted_info += f"""
{name} ({symbol})
  数量: {ui_amount:.6f}
  价格: ${price_usd:.6f}
  价值: ${value_usd:.2f}
                """.strip() + "\n"

        return formatted_info
