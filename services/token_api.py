import json
import logging
import time
from typing import Dict, Optional

import requests
from cachetools import TTLCache, cached

from database.models import TokenMetaData, SessionLocal
from config.config_manager import ConfigManager

class TokenAPI:
    """代币数据 API 工具类 (免费去中心化方案)
    - 价格/市值: DexScreener
    - 钱包余额: Solana RPC
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        # DexScreener 免费 API
        self.dex_url = 'https://api.dexscreener.com/latest/dex/tokens'
        self._last_config_update = 0
        self.refresh_config()
        
        # 注册到配置管理器
        ConfigManager.register_service(self)
        self._initialized = True

    def refresh_config(self):
        """刷新配置"""
        # 获取 Solana RPC 节点，默认使用官方节点
        self.rpc_url = ConfigManager.get_config('RPC_URL', 'https://api.mainnet-beta.solana.com')
        self._last_config_update = time.time()
        logging.info("TokenAPI配置已刷新 (切换为免费 DexScreener + RPC 方案)")

    def get_token_meta_data(self, address: str) -> Optional[Dict]:
        """获取token元数据，带数据库缓存（永久有效）"""
        db = SessionLocal()
        try:
            # 1. 查缓存
            cache = db.query(TokenMetaData).filter_by(address=address).first()
            if cache:
                return cache.to_dict()

            # 2. 从 DexScreener 获取基础信息
            response = requests.get(f"{self.dex_url}/{address}", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            pairs = data.get('pairs')
            
            # 构造统一返回格式 (兼容旧逻辑)
            meta_data = {
                "address": address,
                "symbol": "UNKNOWN",
                "name": "Unknown Token",
                "decimals": 6 # 默认值
            }
            
            if pairs and len(pairs) > 0:
                base_token = pairs[0].get('baseToken', {})
                meta_data["symbol"] = base_token.get('symbol', 'UNKNOWN')
                meta_data["name"] = base_token.get('name', 'Unknown Token')
            else:
                logging.warning(f"DexScreener未找到元数据 [{address}], 采用默认值")

            logging.info(f"成功获取token元数据: {address}")

            # 3. 写入数据库缓存
            data_str = json.dumps(meta_data, ensure_ascii=False)
            cache_obj = TokenMetaData(address=address, data=data_str, updated_at=time.time())
            db.add(cache_obj)
            db.commit()
            return meta_data

        except Exception as e:
            logging.error(f"获取token元数据失败 [{address}]: {e}")
            return {
                "address": address,
                "symbol": "ERROR",
                "name": "Error Fetching",
                "decimals": 6
            }
        finally:
            db.close()

    @cached(cache=TTLCache(maxsize=1000, ttl=60))
    def get_market_data(self, address: str) -> Optional[Dict]:
        """获取token市场数据 (价格、市值)，带内存缓存（TTL 60秒）"""
        try:
            response = requests.get(f"{self.dex_url}/{address}", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            pairs = data.get('pairs')
            
            # 如果撤池子/无流动性，赋予0值并返回
            if not pairs or len(pairs) == 0:
                logging.warning(f"代币 {address} 无活跃流动性，价格与市值置为0")
                return {
                    "price": 0.0,
                    "market_cap": 0.0,
                    "liquidity": 0.0
                }
            
            # 取流动性最大的池子(DexScreener默认按流动性/交易量排序)
            pair = pairs[0]
            price_usd = float(pair.get('priceUsd', 0.0))
            fdv = float(pair.get('fdv', 0.0))
            liquidity = float(pair.get('liquidity', {}).get('usd', 0.0))
            
            # 如果有 fdv (全流通市值) 优先用，否则用 marketCap
            market_cap = fdv if fdv > 0 else float(pair.get('marketCap', 0.0))

            return {
                "price": price_usd,
                "market_cap": market_cap,
                "liquidity": liquidity
            }

        except Exception as e:
            logging.error(f"解析市场数据失败 [{address}]: {e}")
            return None

    def get_token_info_combined(self, address: str) -> Optional[Dict]:
        """获取token的完整信息"""
        meta_data = self.get_token_meta_data(address)
        market_data = self.get_market_data(address)

        if not meta_data and not market_data:
            return None

        return {
            'meta_data': meta_data or {},
            'market_data': market_data or {},
            'timestamp': int(time.time())
        }

    def get_wallet_token_list(self, wallet_address: str) -> Optional[Dict]:
        """使用 Solana 原生 RPC 获取钱包所有代币余额"""
        try:
            headers = {"Content-Type": "application/json"}
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet_address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"}
                ]
            }

            response = requests.post(self.rpc_url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()

            json_resp = response.json()
            if "error" in json_resp:
                logging.error(f"RPC请求钱包错误: {json_resp['error']}")
                return None

            accounts = json_resp.get("result", {}).get("value", [])
            
            items = []
            for acc in accounts:
                info = acc.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                mint = info.get("mint")
                ui_amount = info.get("tokenAmount", {}).get("uiAmount", 0.0)
                decimals = info.get("tokenAmount", {}).get("decimals", 6)
                
                # 过滤掉余额为 0 的无效账本
                if ui_amount > 0:
                    items.append({
                        "address": mint,
                        "uiAmount": ui_amount,
                        "decimals": decimals
                    })

            logging.info(f"成功通过RPC获取钱包代币列表: {wallet_address}, 共 {len(items)} 种有效资产")
            
            # 返回兼容旧版Birdeye的结构
            return {
                "wallet": wallet_address,
                "items": items
            }

        except Exception as e:
            logging.error(f"获取钱包余额RPC请求失败 [{wallet_address}]: {e}")
            return None
