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

from birdeye_api import BirdEyeAPI

try:
    from spl.token.instructions import get_associated_token_address
    from spl.token.client import Token
except ImportError:
    # 如果spl包导入失败，我们稍后会手动实现相关功能
    pass
from config_manager import ConfigManager
from models import MonitorRecord, SessionLocal


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
            # 尝试提取Jupiter返回的JSON错误信息
            try:
                import json
                err_str = str(e)
                if err_str.startswith('{') and '"error"' in err_str:
                    err_json = json.loads(err_str)
                    if 'error' in err_json:
                        return {"error": err_json['error']}
            except Exception:
                pass
            return {"error": str(e)}

    def execute_swap(self, quote_data: Dict) -> Optional[str]:
        """执行交换交易"""
        if not self.wallet:
            logging.error("钱包未初始化，无法执行交易")
            return None

        try:
            # 获取交易数据
            swap_url = f"{self.jupiter_url}/swap"
            # 只传quote['quote']部分，确保字段正确
            quote_response = quote_data.get('quote') if 'quote' in quote_data else quote_data
            swap_data = {
                'quoteResponse': quote_response,
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
                        # 提取Program log详细信息
                        err_str = str(e)
                        program_logs = []
                        for line in err_str.splitlines():
                            if "Program log:" in line:
                                log_msg = line.split("Program log:", 1)[-1].strip()
                                program_logs.append(log_msg)
                        if program_logs:
                            error_detail = "\n".join(program_logs)
                            logging.error(f"所有重试尝试都失败了，链上日志：{error_detail}")
                            return {"error": f"交易失败，链上日志：\n{error_detail}"}
                        logging.error("所有重试尝试都失败了")
                        return {"error": f"交易失败: {err_str}"}

        except Exception as e:
            # 提取Program log详细信息
            err_str = str(e)
            program_logs = []
            for line in err_str.splitlines():
                if "Program log:" in line:
                    log_msg = line.split("Program log:", 1)[-1].strip()
                    program_logs.append(log_msg)
            if program_logs:
                error_detail = "\n".join(program_logs)
                logging.error(f"执行交易失败，链上日志：{error_detail}")
                return {"error": f"交易失败，链上日志：\n{error_detail}"}
            logging.error(f"执行交易失败: {e}")
            return {"error": f"交易失败: {err_str}"}

    def get_token_decimals(self, token_address: str) -> int:
        """从数据库获取token的小数位数"""
        db = SessionLocal()
        try:
            # 查询监控记录中是否有这个token的信息
            record = db.query(MonitorRecord).filter(
                MonitorRecord.token_address == token_address
            ).first()

            if record and record.token_decimals is not None:
                logging.info(f"从数据库获取token decimals: {record.token_decimals}")
                return record.token_decimals
            else:
                # 如果数据库中没有，默认使用9位小数（大多数Solana代币的标准）
                api = BirdEyeAPI()
                token_meta_data = api.get_token_meta_data(token_address)
                token_decimals = token_meta_data.get('decimals')
                if token_decimals is not None:
                    logging.info(f"从API获取token decimals: {token_decimals}")
                    return token_decimals
                logging.warning("从api也未找到token decimals，使用默认值9")
                return 9
        except Exception as e:
            logging.error(f"查询token decimals失败: {e}")
            return 9  # 默认返回9
        finally:
            db.close()

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

            # 从数据库获取正确的小数位数
            token_decimals = self.get_token_decimals(token_address)

            # 转换为最小单位（使用实际的decimals）
            sell_amount_lamports = int(sell_amount * (10 ** token_decimals))

            logging.info(f"准备出售 {sell_amount} 个代币 (decimals: {token_decimals})")

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

    def buy_token_for_sol(self, token_address: str, buy_percentage: float) -> Optional[str]:
        """用SOL买入指定代币"""
        try:
            # 获取SOL余额
            sol_balance = self.get_sol_balance()
            if sol_balance <= 0:
                logging.warning("SOL余额为0，无法买入")
                return None

            # 计算买入数量
            buy_amount = sol_balance * buy_percentage

            # SOL的mint地址
            sol_mint = "So11111111111111111111111111111111111111112"

            # 转换为最小单位（SOL是9位小数）
            buy_amount_lamports = int(buy_amount * 1e9)

            logging.info(f"准备用 {buy_amount} SOL 买入代币 {token_address}")

            # 获取报价
            quote = self.get_quote(sol_mint, token_address, buy_amount_lamports)
            if not quote:
                logging.error("无法获取买入交易报价")
                return None

            # 执行交换
            tx_hash = self.execute_swap(quote)

            if tx_hash:
                logging.info(f"成功买入代币，花费 {buy_amount} SOL")
                return tx_hash
            else:
                logging.error("买入交易执行失败")
                return None

        except Exception as e:
            logging.error(f"买入代币失败: {e}")
            return None
