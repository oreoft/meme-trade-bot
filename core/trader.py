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
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer as system_transfer
from solders.transaction import Transaction
from solders.transaction import VersionedTransaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.constants import WRAPPED_SOL_MINT
from spl.token.instructions import create_idempotent_associated_token_account, \
    transfer, TransferParams as TokenTransferParams

from services.birdeye_api import BirdEyeAPI

try:
    from spl.token.instructions import get_associated_token_address
    from spl.token.client import Token
except ImportError:
    logging.error("无法导入spl包，部分功能可能无法使用")
    pass
from config.config_manager import ConfigManager
from database.models import MonitorRecord, SessionLocal


service_fee= 0.000896  # 默认服务费，单位为SOL
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
            # 检查是否是SOL地址，如果是则直接调用get_sol_balance()
            from utils import normalize_sol_address
            normalized_address = normalize_sol_address(token_address)
            sol_mint = "So11111111111111111111111111111111111111112"
            
            if normalized_address == sol_mint:
                logging.debug(f"检测到SOL地址，直接调用get_sol_balance()")
                return self.get_sol_balance()

            token_mint = Pubkey.from_string(token_address)
            wallet_pubkey = self.wallet.pubkey()

            # 使用关联token账户地址获取余额
            try:
                from spl.token.instructions import get_associated_token_address
                from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
                mint_program_id = self.client.get_account_info(token_mint).value.owner
                # 计算关联token账户地址
                ata = get_associated_token_address(wallet_pubkey, token_mint, mint_program_id)
                # 直接获取关联token账户余额
                balance_response = self.client.get_token_account_balance(ata)
                if balance_response.value:
                    amount = float(balance_response.value.amount)
                    decimals = balance_response.value.decimals
                    return amount / (10 ** decimals)
            except Exception as e:
                # 如果关联token账户不存在或获取失败，尝试其他方法
                logging.debug(f"无法从关联token账户获取余额，尝试其他方法: {e}")

                # 备用方法：获取所有token账户
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
                except Exception as e2:
                    logging.debug(f"备用方法也失败: {e2}")

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
            logging.debug(f"Jupiter API响应: {response.json()}")
            response = response.json()

            if 'swapTransaction' not in response:
                logging.error("响应中未找到swapTransaction字段")
                return None

            # 使用VersionedTransaction处理交易
            swap_transaction = VersionedTransaction.from_bytes(base64.b64decode(response['swapTransaction']))

            # 获取最新的blockhash
            blockhash_response = self.client.get_latest_blockhash()
            recent_blockhash = blockhash_response.value.blockhash
            logging.debug(f"Recent blockhash: {recent_blockhash}")

            # 签名交易
            signature = self.wallet.sign_message(solders.message.to_bytes_versioned(swap_transaction.message))
            signed_tx = VersionedTransaction.populate(swap_transaction.message, [signature])

            # 使用重试机制发送交易
            for attempts in range(5):
                try:
                    txid = self.client.send_transaction(
                        signed_tx,
                        opts=TxOpts(skip_confirmation=False, preflight_commitment=Processed)
                    ).value
                    logging.info(f"交易成功发送，ID: {txid}")
                    return str(txid)  # 转换为字符串
                except Exception as e:
                    err_str = str(e)
                    # 如果包含insufficient lamports错误，直接返回失败
                    if "insufficient lamports" in err_str:
                        program_logs = self.extract_program_logs(err_str)
                        logging.error(f"交易失败: {err_str}")
                        return {"error": f"交易失败: {err_str}", "program_logs": program_logs}
                    logging.warning(f"第{attempts + 1}次尝试失败，5秒后重试... [原因: {e}]")
                    if attempts < 4:  # 如果不是最后一次尝试
                        time.sleep(5)
                    else:
                        program_logs = self.extract_program_logs(err_str)
                        if program_logs:
                            error_detail = "\n".join(program_logs)
                            logging.error(f"所有重试尝试都失败了，链上日志：{error_detail}")
                            return {"error": f"交易失败，链上日志：\n{error_detail}", "program_logs": program_logs}
                        logging.error("所有重试尝试都失败了")
                        return {"error": f"交易失败: {err_str}", "program_logs": program_logs}

        except Exception as e:
            err_str = str(e)
            program_logs = self.extract_program_logs(err_str)
            if program_logs:
                error_detail = "\n".join(program_logs)
                logging.error(f"执行交易失败，链上日志：{error_detail}")
                return {"error": f"交易失败，链上日志：\n{error_detail}", "program_logs": program_logs}
            logging.error(f"执行交易失败: {e}")
            return {"error": f"交易失败: {err_str}", "program_logs": program_logs}

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
                from utils import normalize_sol_address
                token_meta_data = api.get_token_meta_data(normalize_sol_address(token_address))
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

    def sell_token_for_sol(self, token_address: str, sell_percentage: float) -> Dict:
        """将代币换成SOL

        Returns:
            Dict: 包含以下字段的字典
                - success (bool): 是否成功
                - tx_hash (str): 成功时的交易哈希，失败时为None
                - error (str): 失败时的错误信息，成功时为None
        """
        try:
            # 获取代币余额
            token_balance = self.get_token_balance(token_address)
            if token_balance <= 0:
                error_msg = "代币余额为0，无法出售"
                logging.warning(error_msg)
                return {"success": False, "tx_hash": None, "error": error_msg}

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
            if not quote or "error" in quote:
                if quote and "error" in quote:
                    error_msg = f"获取交易报价失败: {quote['error']}"
                    logging.error(error_msg)
                    return {"success": False, "tx_hash": None, "error": error_msg}
                else:
                    error_msg = "无法获取交易报价"
                    logging.error(error_msg)
                    return {"success": False, "tx_hash": None, "error": error_msg}

            # 执行交换
            tx_hash = self.execute_swap(quote)

            # 只有当返回值是字符串类型的交易哈希时才算成功
            if isinstance(tx_hash, str) and tx_hash:
                logging.info(f"成功出售代币，获得 {float(quote['outAmount']) / 1e9:.4f} SOL，交易哈希: {tx_hash}")
                return {"success": True, "tx_hash": tx_hash, "error": None}
            else:
                # 失败情况：记录错误并返回错误信息
                if isinstance(tx_hash, dict) and "error" in tx_hash:
                    error_msg = f"交易执行失败: {tx_hash['error']}"
                    logging.error(error_msg)
                    return {"success": False, "tx_hash": None, "error": error_msg}
                else:
                    error_msg = "交易执行失败"
                    logging.error(error_msg)
                    return {"success": False, "tx_hash": None, "error": error_msg}

        except Exception as e:
            error_msg = f"出售代币失败: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "tx_hash": None, "error": error_msg}

    def buy_token_for_sol(self, token_address: str, buy_percentage: float) -> Dict:
        """用SOL买入指定代币

        Returns:
            Dict: 包含以下字段的字典
                - success (bool): 是否成功
                - tx_hash (str): 成功时的交易哈希，失败时为None
                - error (str): 失败时的错误信息，成功时为None
        """
        try:
            # 获取SOL余额
            sol_balance = self.get_sol_balance()
            # 计算买入数量, 账号里面需要留一点sol作为token的账户的租费,如果token全部卖了,sol理论上可以全提走
            buy_amount = (sol_balance * buy_percentage) - (0.0021 if buy_percentage == 1 else 0)
            if sol_balance <= 0 or buy_amount <= 0:
                error_msg = "SOL余额不足，无法买入"
                logging.warning(error_msg)
                return {"success": False, "tx_hash": None, "error": error_msg}

            # SOL的mint地址
            sol_mint = "So11111111111111111111111111111111111111112"

            # 转换为最小单位（SOL是9位小数）
            buy_amount_lamports = int(buy_amount * 1e9)

            logging.info(f"准备用 {buy_amount} SOL 买入代币 {token_address}")

            # 获取报价
            quote = self.get_quote(sol_mint, token_address, buy_amount_lamports)
            if not quote or "error" in quote:
                if quote and "error" in quote:
                    error_msg = f"获取买入交易报价失败: {quote['error']}"
                    logging.error(error_msg)
                    return {"success": False, "tx_hash": None, "error": error_msg}
                else:
                    error_msg = "无法获取买入交易报价"
                    logging.error(error_msg)
                    return {"success": False, "tx_hash": None, "error": error_msg}

            # 执行交换
            tx_hash = self.execute_swap(quote)

            # 只有当返回值是字符串类型的交易哈希时才算成功
            if isinstance(tx_hash, str) and tx_hash:
                logging.info(f"成功买入代币，花费 {buy_amount} SOL，交易哈希: {tx_hash}")
                return {"success": True, "tx_hash": tx_hash, "error": None}
            else:
                # 失败情况：记录错误并返回错误信息
                if isinstance(tx_hash, dict) and "error" in tx_hash:
                    error_msg = f"买入交易执行失败: {tx_hash['error']}"
                    logging.error(error_msg)
                    return {"success": False, "tx_hash": None, "error": error_msg}
                else:
                    error_msg = "买入交易执行失败"
                    logging.error(error_msg)
                    return {"success": False, "tx_hash": None, "error": error_msg}

        except Exception as e:
            error_msg = f"买入代币失败: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "tx_hash": None, "error": error_msg}

    def extract_program_logs(self, err_str: str) -> list:
        """从错误字符串中提取所有Program log信息"""
        program_logs = []
        for line in err_str.splitlines():
            if "Program log:" in line:
                log_msg = line.split("Program log:", 1)[-1].strip()
                program_logs.append(log_msg)
        return program_logs

    def _validate_balance(self, token_address: str, amount: float) -> None:
        """验证余额是否足够"""
        if token_address == str(WRAPPED_SOL_MINT):
            current_balance = self.get_sol_balance()
            token_name = "SOL"
        else:
            current_balance = self.get_token_balance(token_address)
            token_name = "Token"

        if amount > current_balance:
            raise Exception(f"{token_name}余额不足，当前余额: {current_balance}")

    def _build_sol_transfer_transaction(self, to_address: str, amount: float, recent_blockhash):
        """构建SOL转账交易"""
        receiver_pubkey = Pubkey.from_string(to_address)
        transfer_params = TransferParams(
            from_pubkey=self.wallet.pubkey(),
            to_pubkey=receiver_pubkey,
            lamports=int(amount * 10 ** 9)
        )

        message = Message.new_with_blockhash(
            [system_transfer(transfer_params)],
            self.wallet.pubkey(),
            recent_blockhash
        )

        return Transaction(
            from_keypairs=[self.wallet],
            recent_blockhash=recent_blockhash,
            message=message
        )

    def _build_token_transfer_transaction(self, token_address: str, to_address: str, amount: float, recent_blockhash):
        """构建Token转账交易"""
        token_decimals = self.get_token_decimals(token_address)
        owner = self.wallet.pubkey()
        mint = Pubkey.from_string(token_address)
        dest_owner = Pubkey.from_string(to_address)

        # 获取关联token账户地址
        mint_program_id = self.client.get_account_info(mint).value.owner
        source_ata = get_associated_token_address(owner, mint, mint_program_id)
        dest_ata = get_associated_token_address(dest_owner, mint, mint_program_id)

        instructions = []
        # 检查目标ATA是否存在，如果不存在则创建
        dest_ata_info = self.client.get_account_info(dest_ata)
        if dest_ata_info.value is None:
            # 创建目标ATA指令
            create_ata_ix = create_idempotent_associated_token_account(
                payer=owner,
                owner=dest_owner,
                mint=mint,
                token_program_id=mint_program_id,
            )
            instructions.append(create_ata_ix)

        # 添加转账指令
        instructions.append(transfer(
            TokenTransferParams(
                program_id=mint_program_id,
                source=source_ata,
                dest=dest_ata,
                owner=owner,
                amount=int(amount * (10 ** token_decimals)),
                signers=[]
            )
        ))

        # 构建消息
        message = Message.new_with_blockhash(
            instructions,
            self.wallet.pubkey(),
            recent_blockhash
        )

        return Transaction(
            from_keypairs=[self.wallet],
            recent_blockhash=recent_blockhash,
            message=message
        )

    def _calculate_transfer_result(self, token_address: str, amount: float, fee: float, tx_hash: str = None) -> dict:
        """计算转账结果"""
        from utils import normalize_sol_address
        price = BirdEyeAPI().get_market_data(normalize_sol_address(token_address)).get('price', 0)
        amount_usd = amount * price

        if token_address == str(WRAPPED_SOL_MINT):
            current_balance = self.get_sol_balance()
            after_balance = current_balance - amount - fee
        else:
            current_balance = self.get_sol_balance()
            after_balance = current_balance - fee

        result = {
            "amount": amount,
            "amount_usd": amount_usd,
            "fee": fee,
            "after_balance": after_balance,
        }

        if tx_hash:
            result["actual_amount"] = amount
            result["tx_hash"] = tx_hash

        return result

    def _simulate_transaction(self, transaction) -> dict:
        """模拟交易并返回结果"""
        sim_result = self.client.simulate_transaction(transaction)

        # 处理模拟结果
        value = getattr(sim_result, 'value', sim_result)
        fee = getattr(value, 'fee', 5000) / 1e9 if hasattr(value, 'fee') else service_fee
        err = getattr(value, 'err', None)
        logs = getattr(value, 'logs', None)

        if err is not None and not isinstance(err, str):
            err = str(err)
        if logs is not None:
            logs = [str(l) for l in logs]

        return {
            "fee": fee,
            "err": err,
            "logs": logs
        }

    def _ensure_ata_ix(self, owner_pubkey, mint_pubkey, payer_pubkey):
        """如果目标ATA不存在，返回创建ATA的指令，否则返回None"""
        ata = get_associated_token_address(owner_pubkey, mint_pubkey, TOKEN_PROGRAM_ID)
        # 检查ATA是否存在
        resp = self.client.get_account_info(ata)
        if resp.value is None:
            # 需要创建ATA
            return create_idempotent_associated_token_account(
                payer=payer_pubkey,
                owner=owner_pubkey,
                mint=mint_pubkey,
                token_program_id=TOKEN_PROGRAM_ID
            )
        return None

    def transfer_preview(self, token_address: str, to_address: str, amount: float) -> dict:
        """转账预览"""
        try:
            # 验证余额
            self._validate_balance(token_address, amount)

            # 获取最新区块哈希
            recent_blockhash = self.client.get_latest_blockhash().value.blockhash

            # 构建交易
            if token_address == str(WRAPPED_SOL_MINT):
                transaction = self._build_sol_transfer_transaction(to_address, amount, recent_blockhash)
            else:
                transaction = self._build_token_transfer_transaction(token_address, to_address, amount,
                                                                     recent_blockhash)
            # 模拟交易
            sim_result = self._simulate_transaction(transaction)

            # 如果模拟失败，返回错误
            if sim_result["err"]:
                return {
                    "err": sim_result["err"],
                    "logs": sim_result["logs"]
                }

            # 计算结果
            result = self._calculate_transfer_result(token_address, amount, sim_result["fee"] or service_fee)
            result.update({
                "to": to_address,
                "err": sim_result["err"],
                "logs": sim_result["logs"]
            })

            return result

        except Exception as e:
            err_str = str(e)
            logging.error(f"转账预览失败: {err_str}")
            if hasattr(e, 'args') and e.args and not isinstance(e.args[0], str):
                err_str = str(e.args[0])
            program_logs = self.extract_program_logs(err_str)
            return {"err": err_str, "program_logs": program_logs}

    def transfer(self, token_address: str, to_address: str, amount: float) -> dict:
        """执行转账"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 验证余额
                self._validate_balance(token_address, amount)

                # 获取最新区块哈希
                recent_blockhash = self.client.get_latest_blockhash().value.blockhash

                # 构建交易
                if token_address == str(WRAPPED_SOL_MINT):
                    transaction = self._build_sol_transfer_transaction(to_address, amount, recent_blockhash)
                else:
                    transaction = self._build_token_transfer_transaction(token_address, to_address, amount,
                                                                         recent_blockhash)

                # 发送交易
                result = self.client.send_transaction(
                    transaction,
                    opts=TxOpts(skip_preflight=True)
                )

                tx_hash = str(result.value)
                token_name = "SOL" if token_address == str(WRAPPED_SOL_MINT) else "Token"
                logging.info(f"{token_name}转账成功，交易哈希: {tx_hash}")

                # 计算并返回结果
                return self._calculate_transfer_result(token_address, amount, service_fee, tx_hash)

            except Exception as e:
                err_str = str(e)
                logging.error(f"转账失败: {err_str}")
                if hasattr(e, 'args') and e.args and not isinstance(e.args[0], str):
                    err_str = str(e.args[0])

                # 检查是否是可重试的错误
                retryable_errors = [
                    "blockhash not found",
                    "timeout",
                    "connection error",
                    "network error",
                    "rpc error",
                    "insufficient compute budget"
                ]

                is_retryable = any(error in err_str.lower() for error in retryable_errors)

                if attempt < max_retries - 1 and is_retryable:
                    logging.warning(f"转账第{attempt + 1}次尝试失败，将重试: {err_str}")
                    time.sleep(2 ** attempt)  # 指数退避
                    continue
                else:
                    # 最后一次尝试失败或不可重试的错误
                    program_logs = self.extract_program_logs(err_str)
                    logging.error(f"转账失败: {err_str}")
                    return {"err": err_str, "program_logs": program_logs}

        # 如果所有重试都失败了
        return {"err": "所有重试尝试都失败了", "program_logs": []}
