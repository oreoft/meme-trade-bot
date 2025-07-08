from fastapi import APIRouter, Query, Body, Form

from core.trader import SolanaTrader
from services import BirdEyeAPI
from services.monitor_service import MonitorService
from utils import normalize_sol_address
from utils.response import ApiResponse

router = APIRouter(prefix="/api", tags=["交易相关"])


@router.get("/token_info")
async def token_info(address: str = Query(...)):
    """根据token地址查询token基本信息（名称、symbol、logo等）"""
    try:
        address = normalize_sol_address(address)
        info = BirdEyeAPI().get_token_info_combined(address)
        if info:
            res = info.get('meta_data', {})
            res["price_usd"] = info.get('market_data', {}).get("price", 0)
            return ApiResponse.success(data=res)
        else:
            return ApiResponse.error(message="未找到Token信息")
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.get("/quote")
async def quote(
        from_: str = Query(..., alias="from"),
        to: str = Query(...),
        amount: float = Query(None),
        key_id: int = Query(...),
        amount_in_usd: float = Query(None)
):
    """获取兑换报价"""
    try:
        from_ = normalize_sol_address(from_)
        to = normalize_sol_address(to)
        key = MonitorService.get_private_key_by_id(key_id)
        if not key:
            return ApiResponse.error(message="私钥不存在")
        trader = SolanaTrader(key["private_key"])
        from_decimals = trader.get_token_decimals(from_)

        # 新增：支持按USD金额输入
        if amount_in_usd is not None:
            # 获取Token价格
            from_info = BirdEyeAPI().get_market_data(from_)
            if not from_info or "price_usd" not in from_info or not from_info["price_usd"]:
                return ApiResponse.error(message="无法获取Token价格")
            amount = float(amount_in_usd) / float(from_info["price_usd"])
        if amount is None:
            return ApiResponse.error(message="兑换数量不能为空")

        lamports = int(float(amount) * (10 ** from_decimals))
        quote = trader.get_quote(from_, to, lamports)
        if not quote or "outAmount" not in quote:
            # 如果quote里有error字段，直接返回详细错误
            if isinstance(quote, dict) and "error" in quote:
                return ApiResponse.error(message=quote["error"])
            return ApiResponse.error(message="获取报价失败")
        to_info = BirdEyeAPI().get_token_info_combined(to)
        meta_data = to_info.get("meta_data", {})
        market_data = to_info.get("market_data", {})
        out_amount = float(quote["outAmount"]) / (
                10 ** (meta_data["decimals"] if to_info and "decimals" in meta_data else 9))
        usd = out_amount * (market_data["price"] if to_info and "price" in market_data else 0)
        return ApiResponse.success(data={
            "outAmount": quote["outAmount"],
            "outAmountDisplay": f"{out_amount:.6f}",
            "estimatedUsd": f"{usd:.2f}",
            "quote": quote
        })
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.post("/swap")
async def swap(data: dict = Body(...)):
    """执行兑换交易"""
    try:
        key_id = data.get("key_id")
        from_ = normalize_sol_address(data.get("from"))
        to = normalize_sol_address(data.get("to"))
        amount = float(data.get("amount"))
        quote = data.get("quote")
        key = MonitorService.get_private_key_by_id(key_id)
        if not key:
            return ApiResponse.error(message="私钥不存在")
        trader = SolanaTrader(key["private_key"])
        # 直接用quote数据执行
        txid = trader.execute_swap(quote)
        if isinstance(txid, str) and txid:
            return ApiResponse.success(data={"txid": txid})
        elif isinstance(txid, dict) and "error" in txid:
            # 透传后端详细错误
            return ApiResponse.error(message=txid["error"])
        else:
            return ApiResponse.error(message="交易失败")
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.post("/transfer_preview")
async def transfer_preview(
        key_id: int = Form(...),
        token_address: str = Form(...),
        to_address: str = Form(...),
        amount: float = Form(...)
):
    """转账预览，返回真实手续费、转账后余额、USD金额等"""
    try:
        key = MonitorService.get_private_key_by_id(key_id)
        if not key:
            return ApiResponse.error(message="私钥不存在")
        trader = SolanaTrader(key["private_key"])
        preview = trader.transfer_preview(normalize_sol_address(token_address), normalize_sol_address(to_address),
                                          amount)
        if isinstance(preview, dict) and preview.get("err"):
            # 业务错误，返回-1，错误信息在message
            return ApiResponse.error(message=preview.get("err"), data=preview.get("program_logs"))
        return ApiResponse.success(data=preview)
    except Exception as e:
        return ApiResponse.error(message=str(e))


@router.post("/transfer")
async def transfer(
        key_id: int = Form(...),
        token_address: str = Form(...),
        to_address: str = Form(...),
        amount: float = Form(...)
):
    """执行转账，返回交易哈希等信息"""
    try:
        key = MonitorService.get_private_key_by_id(key_id)
        if not key:
            return ApiResponse.error(message="私钥不存在")
        trader = SolanaTrader(key["private_key"])
        result = trader.transfer(normalize_sol_address(token_address), normalize_sol_address(to_address), amount)
        if isinstance(result, dict) and result.get("err"):
            return ApiResponse.error(message=result.get("err"), data=result.get("program_logs"))
        return ApiResponse.success(data=result)
    except Exception as e:
        return ApiResponse.error(message=str(e))
