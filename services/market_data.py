import logging
import time
from typing import Dict, Optional

from config.config_manager import ConfigManager
from services.birdeye_api import BirdEyeAPI


class MarketDataFetcher:
    """市场数据获取器 - 基于BirdEyeAPI的封装"""

    def __init__(self):
        # 使用BirdEyeAPI作为底层实现
        self.api = BirdEyeAPI()
        # 注册到配置管理器，支持统一刷新
        ConfigManager.register_service(self)

    def refresh_config(self):
        """刷新配置缓存 - 可通过Web界面的刷新按钮调用"""
        # 委托给BirdEyeAPI进行配置刷新
        self.api.refresh_config()
        logging.info("MarketDataFetcher配置已刷新")

    def get_price_info(self, address: str = None) -> Optional[Dict]:
        """获取价格信息"""
        market_data = self.api.get_market_data(address)
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


# ====== 下面是模块级token信息查询函数 ======
def get_token_market_info(address: str):
    """
    查询token市场信息，返回dict: {name, symbol, logo_uri, decimals, price_usd}
    兼容birdeye_api.BirdEyeAPI.get_token_info_combined返回结构。
    """
    try:
        from birdeye_api import BirdEyeAPI
        api = BirdEyeAPI()
        info = api.get_token_info_combined(address)
        if not info:
            return None
        meta = info.get('meta_data', {})
        market = info.get('market_data', {})
        return {
            "name": meta.get("name", "未知"),
            "symbol": meta.get("symbol", "未知"),
            "logo_uri": meta.get("logo_uri") or meta.get("logoURI", ""),
            "decimals": meta.get("decimals", 9),
            "price_usd": market.get("price", 0)
        }
    except Exception:
        return None
