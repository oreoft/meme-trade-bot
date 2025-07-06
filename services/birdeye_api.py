import json
import logging
import time
from typing import Dict, Optional

import requests

from config.config_manager import ConfigManager
from database.models import TokenMetaData, SessionLocal


class BirdEyeAPI:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    """BirdEye API 工具类"""

    def __init__(self):
        if self._initialized:
            return
        self.base_url = 'https://public-api.birdeye.so'
        self._headers_cache = None
        self._last_config_update = 0
        # 初始化时加载配置
        self.refresh_config()
        # 注册到配置管理器，支持统一刷新
        from config.config_manager import ConfigManager
        ConfigManager.register_service(self)
        self._initialized = True

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
        """获取token元数据，带数据库缓存（永久有效）"""
        db = SessionLocal()
        try:
            # 1. 先查数据库缓存（只要有就直接返回）
            cache = db.query(TokenMetaData).filter_by(address=address).first()
            if cache:
                return cache.to_dict()

            # 2. 没有缓存，请求API
            url = f'{self.base_url}/defi/v3/token/meta-data/single'
            params = {'address': address}

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            json_response = response.json()
            if not json_response.get('success', False):
                logging.error(f"获取token元数据API返回失败: {json_response}")
                return None

            data = json_response.get('data', {})
            logging.info(f"成功获取token元数据: {address}")

            # 3. 写入数据库缓存
            data_str = json.dumps(data, ensure_ascii=False)
            cache = TokenMetaData(address=address, data=data_str, updated_at=time.time())
            db.add(cache)
            db.commit()
            return data

        except requests.exceptions.RequestException as e:
            logging.error(f"获取token元数据网络请求失败 [{address}]: {e}")
            return None
        except Exception as e:
            logging.error(f"解析token元数据失败 [{address}]: {e}")
            return None
        finally:
            db.close()

    def get_market_data(self, address: str) -> Optional[Dict]:
        """获取token市场数据

        Args:
            address: token地址

        Returns:
            市场数据字典，包含price, market_cap, liquidity等字段
        """
        try:
            url = f'{self.base_url}/defi/v3/token/market-data'
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

    def get_wallet_token_list(self, wallet_address: str) -> Optional[Dict]:
        """获取钱包的token列表

        Args:
            wallet_address: 钱包地址

        Returns:
            包含钱包token列表的字典，包含wallet, totalUsd, items等字段
        """
        try:
            # 使用v1版本的钱包API
            url = f'{self.base_url}/v1/wallet/token_list'
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
