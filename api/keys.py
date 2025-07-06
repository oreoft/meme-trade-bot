import base58
from fastapi import APIRouter, Form
from solders.keypair import Keypair

from services.birdeye_api import BirdEyeAPI
from services.monitor_service import MonitorService

# 创建路由器
router = APIRouter(prefix="/api/keys", tags=["私钥管理"])


@router.get("")
async def get_private_keys():
    """获取所有私钥列表"""
    try:
        keys = MonitorService.get_all_private_keys()
        return {
            "success": True,
            "data": keys
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("")
async def create_private_key(
        nickname: str = Form(...),
        private_key: str = Form(...)
):
    """创建私钥"""
    try:
        success, message, key_id = MonitorService.create_private_key(nickname, private_key)

        if success:
            return {
                "success": True,
                "message": message,
                "data": {"id": key_id}
            }
        else:
            return {"success": False, "error": message}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.put("/{key_id}")
async def update_private_key(
        key_id: int,
        nickname: str = Form(...),
        private_key: str = Form(...)
):
    """更新私钥"""
    try:
        success, message = MonitorService.update_private_key(key_id, nickname, private_key)

        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/generate")
async def generate_private_key():
    """生成新的Solana私钥"""
    try:
        # 生成新的Solana密钥对
        keypair = Keypair()

        # 获取私钥字节数组并转换为base58字符串
        private_key_bytes = bytes(keypair)
        private_key_base58 = base58.b58encode(private_key_bytes).decode('utf-8')

        # 获取公钥
        public_key = str(keypair.pubkey())

        return {
            "success": True,
            "data": {
                "private_key": private_key_base58,
                "public_key": public_key
            },
            "message": "私钥生成成功"
        }
    except Exception as e:
        return {"success": False, "error": f"生成私钥失败: {str(e)}"}


@router.post("/export")
async def export_private_keys(token: str = Form(...)):
    """导出私钥列表（需要token验证）"""
    try:
        # 验证token
        if token != "5Rx&FBclzfs^9HFF":
            return {"success": False, "error": "Token验证失败"}

        # 获取所有私钥的完整信息
        keys = MonitorService.get_all_private_keys_with_secrets()

        # 提取所有私钥并用逗号分割
        private_keys_list = [key["private_key"] for key in keys]
        private_keys_combined = ",".join(private_keys_list)

        # 构造导出数据
        export_data = {
            "export_time": MonitorService.get_current_time(),
            "total_count": len(keys),
            "private_keys": keys,
            "private_keys_combined": private_keys_combined
        }

        return {
            "success": True,
            "data": export_data,
            "message": "私钥导出成功"
        }
    except Exception as e:
        return {"success": False, "error": f"导出失败: {str(e)}"}


@router.delete("/{key_id}")
async def delete_private_key(key_id: int):
    """删除私钥"""
    try:
        success, message = MonitorService.delete_private_key(key_id)

        if success:
            return {"success": True, "message": message}
        else:
            return {"success": False, "error": message}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/{key_id}")
async def get_private_key_detail(key_id: int):
    """获取私钥详情（用于编辑）"""
    try:
        key_detail = MonitorService.get_private_key_by_id(key_id)
        if key_detail:
            return {
                "success": True,
                "data": key_detail
            }
        else:
            return {"success": False, "error": "私钥不存在"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/summary/tokens")
async def get_private_keys_token_summary():
    """获取所有私钥的token汇总信息"""
    try:
        # 获取所有私钥
        private_keys = MonitorService.get_all_private_keys_with_secrets()
        
        if not private_keys:
            return {
                "success": True,
                "data": {
                    "total_wallets": 0,
                    "total_sol": 0,
                    "total_usd": 0,
                    "tokens": []
                }
            }
        
        # 初始化BirdEye API
        api = BirdEyeAPI()
        
        # 汇总数据
        total_usd = 0
        total_sol = 0
        token_summary = {}  # {token_address: {name, symbol, total_amount, total_value, logo_uri}}
        
        # 遍历每个私钥获取token信息
        for pk in private_keys:
            public_key = pk.get('public_key')
            if not public_key:
                continue
                
            # 获取钱包token列表
            wallet_data = api.get_wallet_token_list(public_key)
            if not wallet_data:
                continue
                
            # 累计总USD价值
            wallet_usd = wallet_data.get('totalUsd', 0)
            total_usd += wallet_usd
            
            # 处理token项目
            items = wallet_data.get('items', [])
            for item in items:
                token_address = item.get('address', '')
                token_name = item.get('name', '未知')
                token_symbol = item.get('symbol', '未知')
                token_amount = item.get('uiAmount', 0)
                token_value = item.get('valueUsd', 0)
                token_logo = item.get('logoURI', '')
                
                # 统计SOL
                if token_symbol == 'SOL':
                    total_sol += token_amount
                
                # 汇总token数据
                if token_address in token_summary:
                    token_summary[token_address]['total_amount'] += token_amount
                    token_summary[token_address]['total_value'] += token_value
                else:
                    token_summary[token_address] = {
                        'name': token_name,
                        'symbol': token_symbol,
                        'total_amount': token_amount,
                        'total_value': token_value,
                        'logo_uri': token_logo
                    }
        
        # 转换为列表并按价值排序
        tokens_list = []
        for address, data in token_summary.items():
            tokens_list.append({
                'address': address,
                'name': data['name'],
                'symbol': data['symbol'],
                'total_amount': data['total_amount'],
                'total_value': data['total_value'],
                'logo_uri': data['logo_uri']
            })
        
        # 按总价值降序排序
        tokens_list.sort(key=lambda x: x['total_value'], reverse=True)
        
        return {
            "success": True,
            "data": {
                "total_wallets": len(private_keys),
                "total_sol": total_sol,
                "total_usd": total_usd,
                "tokens": tokens_list
            }
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/{key_id}/tokens")
async def get_private_key_tokens(key_id: int):
    """获取单个私钥的token明细"""
    try:
        # 获取私钥详情
        key_detail = MonitorService.get_private_key_by_id(key_id)
        if not key_detail:
            return {"success": False, "error": "私钥不存在"}
        
        public_key = key_detail.get('public_key')
        if not public_key:
            return {"success": False, "error": "公钥地址不存在"}
        
        # 初始化BirdEye API
        api = BirdEyeAPI()
        
        # 获取钱包token列表
        wallet_data = api.get_wallet_token_list(public_key)
        if not wallet_data:
            return {
                "success": True,
                "data": {
                    "wallet": public_key,
                    "total_usd": 0,
                    "tokens": []
                }
            }
        
        # 处理token数据
        items = wallet_data.get('items', [])
        tokens_list = []
        
        for item in items:
            tokens_list.append({
                'address': item.get('address', ''),
                'name': item.get('name', '未知'),
                'symbol': item.get('symbol', '未知'),
                'amount': item.get('uiAmount', 0),
                'price_usd': item.get('priceUsd', 0),
                'value_usd': item.get('valueUsd', 0),
                'logo_uri': item.get('logoURI', '')
            })
        
        # 按价值降序排序
        tokens_list.sort(key=lambda x: x['value_usd'], reverse=True)
        
        return {
            "success": True,
            "data": {
                "wallet": wallet_data.get('wallet', public_key),
                "total_usd": wallet_data.get('totalUsd', 0),
                "tokens": tokens_list
            }
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}
