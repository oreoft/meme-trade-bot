# 工具模块包（预留扩展）

__all__ = []

def normalize_sol_address(address: str) -> str:
    """Jupiter只支持So11111111111111111111111111111111111111112，自动替换老SOL地址"""
    sol_alias = "So11111111111111111111111111111111111111111"
    sol_mint = "So11111111111111111111111111111111111111112"
    return sol_mint if address == sol_alias else address 