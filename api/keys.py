from fastapi import APIRouter, Form

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