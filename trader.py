import base64
import logging
import time
from typing import Dict, Optional

import base58
import requests
import solders
from solana.rpc.api import Client
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

try:
    from spl.token.instructions import get_associated_token_address
    from spl.token.client import Token
except ImportError:
    # 如果spl包导入失败，我们稍后会手动实现相关功能
    pass
from config_manager import ConfigManager


class SolanaTrader:
    """Solana交易器"""

    def __init__(self, private_key: str = None):
        self._private_key = private_key
        self.wallet = None
        # 配置缓存
        self._client_cache = None
        self._jupiter_url_cache = None
        self._slippage_bps_cache = None
        self._last_config_update = 0
        # 初始化配置和钱包
        self.refresh_config()
        self._init_wallet()
        # 注册到配置管理器，支持统一刷新
        ConfigManager.register_service(self)

    def refresh_config(self):
        """刷新配置缓存 - 可通过Web界面的刷新按钮调用"""
        rpc_url = ConfigManager.get_config('RPC_URL', 'https://api.mainnet-beta.solana.com')
        self._client_cache = Client(rpc_url)
        self._jupiter_url_cache = ConfigManager.get_config('JUPITER_API_URL', 'https://quote-api.jup.ag/v6')
        self._slippage_bps_cache = ConfigManager.get_config('SLIPPAGE_BPS', 100)
        self._last_config_update = time.time()
        logging.info("SolanaTrader配置已刷新")

    @property
    def client(self):
        """获取Solana客户端，使用缓存机制提高性能"""
        if not self._client_cache:
            self.refresh_config()
        return self._client_cache

    @property
    def jupiter_url(self):
        """获取Jupiter API URL，使用缓存机制提高性能"""
        if not self._jupiter_url_cache:
            self.refresh_config()
        return self._jupiter_url_cache

    @property
    def slippage_bps(self):
        """获取滑点设置，使用缓存机制提高性能"""
        if self._slippage_bps_cache is None:
            self.refresh_config()
        return self._slippage_bps_cache

    def _init_wallet(self):
        """初始化钱包"""
        if self._private_key:
            try:
                # 从私钥创建Keypair
                private_key_bytes = base58.b58decode(self._private_key)
                self.wallet = Keypair.from_bytes(private_key_bytes)
                logging.info(f"钱包地址: {self.wallet.pubkey()}")
            except Exception as e:
                logging.error(f"初始化钱包失败: {e}")
                self.wallet = None
        else:
            logging.warning("未设置私钥，无法进行交易")
            self.wallet = None

    def set_private_key(self, private_key: str):
        """设置私钥并重新初始化钱包"""
        self._private_key = private_key
        self._init_wallet()

    def get_token_balance(self, token_address: str) -> float:
        """获取代币余额"""
        if not self.wallet:
            return 0.0

        try:
            token_mint = Pubkey.from_string(token_address)
            # 简化处理：直接获取钱包地址的token账户
            # 在实际应用中可能需要更复杂的逻辑来获取关联token账户
            wallet_pubkey = self.wallet.pubkey()

            # 获取代币账户信息
            # 注意：这里需要实际的token账户地址，简化处理可能不准确
            # 实际使用时需要正确计算关联token账户地址
            try:
                from solana.rpc.types import TokenAccountOpts
                response = self.client.get_token_accounts_by_owner(
                    wallet_pubkey,
                    TokenAccountOpts(mint=token_mint)
                )
                if response.value:
                    for account in response.value:
                        balance_response = self.client.get_token_account_balance(account.pubkey)
                        if balance_response.value:
                            amount = float(balance_response.value.amount)
                            decimals = balance_response.value.decimals
                            return amount / (10 ** decimals)
            except:
                pass

            return 0.0
        except Exception as e:
            logging.error(f"获取代币余额失败: {e}")
            return 0.0

    def get_sol_balance(self) -> float:
        """获取SOL余额"""
        if not self.wallet:
            return 0.0

        try:
            response = self.client.get_balance(self.wallet.pubkey())
            return float(response.value) / 1e9  # 转换为SOL
        except Exception as e:
            logging.error(f"获取SOL余额失败: {e}")
            return 0.0

    def get_quote(self, input_mint: str, output_mint: str, amount: int) -> Optional[Dict]:
        """获取Jupiter交易报价"""
        try:
            url = f"{self.jupiter_url}/quote"
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': self.slippage_bps
            }

            response = requests.get(url, params=params)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            logging.error(f"获取交易报价失败: {e}")
            return None

    def execute_swap(self, quote_data: Dict) -> Optional[str]:
        """执行交换交易"""
        if not self.wallet:
            logging.error("钱包未初始化，无法执行交易")
            return None

        try:
            # 获取交易数据
            swap_url = f"{self.jupiter_url}/swap"
            swap_data = {
                'quoteResponse': quote_data,
                'userPublicKey': str(self.wallet.pubkey()),
                'wrapAndUnwrapSol': True
            }

            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.request("POST", swap_url, headers=headers, json=swap_data)
            print(response.json())
            response = response.json()

            if 'swapTransaction' not in response:
                print("No swap transaction found in the response.")
                logging.error("响应中未找到swapTransaction字段")
                return None

            swp = response['swapTransaction']
            swap_transaction_buf = base64.b64decode(swp)

            # 使用VersionedTransaction处理交易
            swap_transaction = VersionedTransaction.from_bytes(base64.b64decode(swp))

            # 获取最新的blockhash
            blockhash_response = self.client.get_latest_blockhash()
            recent_blockhash = blockhash_response.value.blockhash
            print(f"Recent blockhash: {recent_blockhash}")

            # 签名交易
            signature = self.wallet.sign_message(solders.message.to_bytes_versioned(swap_transaction.message))
            signed_tx = VersionedTransaction.populate(swap_transaction.message, [signature])
            encoded_tx = base64.b64encode(bytes(signed_tx)).decode('utf-8')

            # 使用重试机制发送交易
            for attempts in range(5):
                try:
                    txid = self.client.send_transaction(
                        signed_tx,
                        opts=TxOpts(skip_confirmation=False, preflight_commitment=Processed)
                    ).value
                    print("Your transaction Id is: ", txid)
                    logging.info(f"交易成功发送，ID: {txid}")
                    return str(txid)  # 转换为字符串
                except Exception as e:
                    print(f"Attempt {attempts + 1} failed due to timeout. Retrying in 5 seconds... [ reason: {e}]")
                    logging.warning(f"第{attempts + 1}次尝试失败: {e}")
                    if attempts < 4:  # 如果不是最后一次尝试
                        time.sleep(5)
                    else:
                        logging.error("所有重试尝试都失败了")
                        return None

        except Exception as e:
            logging.error(f"执行交易失败: {e}")
            return None

    def sell_token_for_sol(self, token_address: str, sell_percentage: float) -> Optional[str]:
        """将代币换成SOL"""
        try:
            # 获取代币余额
            token_balance = self.get_token_balance(token_address)
            if token_balance <= 0:
                logging.warning("代币余额为0，无法出售")
                return None

            # 计算出售数量
            sell_amount = token_balance * sell_percentage

            # 转换为最小单位（通常是6或9位小数）
            # 这里假设是9位小数，实际使用时需要根据代币的decimals调整
            sell_amount_lamports = int(sell_amount * 1e9)

            logging.info(f"准备出售 {sell_amount} 个代币")

            # SOL的mint地址
            sol_mint = "So11111111111111111111111111111111111111112"

            # 获取报价
            quote = self.get_quote(token_address, sol_mint, sell_amount_lamports)
            if not quote:
                logging.error("无法获取交易报价")
                return None

            # 执行交换
            tx_hash = self.execute_swap(quote)

            if tx_hash:
                logging.info(f"成功出售代币，获得 {float(quote['outAmount']) / 1e9:.4f} SOL")
                return tx_hash
            else:
                logging.error("交易执行失败")
                return None

        except Exception as e:
            logging.error(f"出售代币失败: {e}")
            return None
