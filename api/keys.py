import base58
from fastapi import APIRouter, Form
from solders.keypair import Keypair

from monitor_service import MonitorService

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
