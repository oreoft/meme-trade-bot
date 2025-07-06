from fastapi import APIRouter, Query, Body

from core.trader import SolanaTrader
from services.market_data import get_token_market_info
from services.monitor_service import MonitorService

router = APIRouter(prefix="/api", tags=["交易相关"])


def normalize_sol_address(address: str) -> str:
    """Jupiter只支持So11111111111111111111111111111111111111112，自动替换老SOL地址"""
    sol_alias = "So11111111111111111111111111111111111111111"
    sol_mint = "So11111111111111111111111111111111111111112"
    return sol_mint if address == sol_alias else address


@router.get("/token_info")
async def token_info(address: str = Query(...)):
    """根据token地址查询token基本信息（名称、symbol、logo等）"""
    try:
        address = normalize_sol_address(address)
        info = get_token_market_info(address)
        if info:
            return {"success": True, "data": info}
        else:
            return {"success": False, "error": "未找到Token信息"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
            return {"success": False, "error": "私钥不存在"}
        trader = SolanaTrader(key["private_key"])
        from_decimals = trader.get_token_decimals(from_)

        # 新增：支持按USD金额输入
        if amount_in_usd is not None:
            # 获取Token价格
            from_info = get_token_market_info(from_)
            if not from_info or "price_usd" not in from_info or not from_info["price_usd"]:
                return {"success": False, "error": "无法获取Token价格"}
            amount = float(amount_in_usd) / float(from_info["price_usd"])
        if amount is None:
            return {"success": False, "error": "兑换数量不能为空"}

        lamports = int(float(amount) * (10 ** from_decimals))
        quote = trader.get_quote(from_, to, lamports)
        if not quote or "outAmount" not in quote:
            # 如果quote里有error字段，直接返回详细错误
            if isinstance(quote, dict) and "error" in quote:
                return {"success": False, "error": quote["error"]}
            return {"success": False, "error": "获取报价失败"}
        to_info = get_token_market_info(to)
        out_amount = float(quote["outAmount"]) / (
                10 ** (to_info["decimals"] if to_info and "decimals" in to_info else 9))
        usd = out_amount * (to_info["price_usd"] if to_info and "price_usd" in to_info else 0)
        return {"success": True, "data": {
            "outAmount": quote["outAmount"],
            "outAmountDisplay": f"{out_amount:.6f}",
            "estimatedUsd": f"{usd:.2f}",
            "quote": quote
        }}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
            return {"success": False, "error": "私钥不存在"}
        trader = SolanaTrader(key["private_key"])
        # 直接用quote数据执行
        txid = trader.execute_swap(quote)
        if isinstance(txid, str) and txid:
            return {"success": True, "data": {"txid": txid}}
        elif isinstance(txid, dict) and "error" in txid:
            # 透传后端详细错误
            return {"success": False, "error": txid["error"], "program_logs": txid.get("program_logs")}
        else:
            return {"success": False, "error": "交易失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}
