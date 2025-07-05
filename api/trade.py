from fastapi import APIRouter, Query, Body

from market_data import get_token_market_info
from monitor_service import MonitorService
from trader import SolanaTrader

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
async def quote(from_: str = Query(..., alias="from"), to: str = Query(...), amount: float = Query(...), key_id: int = Query(...)):
    """获取兑换报价"""
    try:
        from_ = normalize_sol_address(from_)
        to = normalize_sol_address(to)
        # 获取私钥
        key = MonitorService.get_private_key_by_id(key_id)
        if not key:
            return {"success": False, "error": "私钥不存在"}
        trader = SolanaTrader(key["private_key"])
        # 获取from token decimals
        from_decimals = trader.get_token_decimals(from_)
        lamports = int(float(amount) * (10 ** from_decimals))
        quote = trader.get_quote(from_, to, lamports)
        if not quote or "outAmount" not in quote:
            return {"success": False, "error": "获取报价失败"}
        # 查询to token市场信息
        to_info = get_token_market_info(to)
        out_amount = float(quote["outAmount"]) / (10 ** (to_info["decimals"] if to_info and "decimals" in to_info else 9))
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
        if txid:
            return {"success": True, "data": {"txid": txid}}
        else:
            return {"success": False, "error": "交易失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}
