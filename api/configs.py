from fastapi import APIRouter
from pydantic import BaseModel

from config.config_manager import ConfigManager

# 创建路由器
router = APIRouter(prefix="/api", tags=["配置管理"])

# 定义请求数据模型
class ConfigUpdateRequest(BaseModel):
    key: str
    value: str
    description: str = ""
    config_type: str = "string"

@router.get("/configs")
async def get_configs():
    """获取所有配置"""
    try:
        configs = ConfigManager.get_all_configs()
        return {
            "success": True,
            "data": configs
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/configs")
async def update_config(request: ConfigUpdateRequest):
    """更新配置"""
    try:
        success = ConfigManager.set_config(
            request.key,
            request.value,
            request.description,
            request.config_type
        )
        if success:
            return {"success": True, "message": "配置更新成功"}
        else:
            return {"success": False, "error": "配置更新失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.delete("/configs/{config_key}")
async def delete_config(config_key: str):
    """删除配置"""
    try:
        success = ConfigManager.delete_config(config_key)
        if success:
            return {"success": True, "message": "配置删除成功"}
        else:
            return {"success": False, "error": "配置删除失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/refresh-configs")
async def refresh_configs():
    """刷新所有服务的配置缓存"""
    try:
        count = ConfigManager.refresh_all_services()
        return {
            "success": True,
            "message": "配置刷新成功",
            "count": count
        }
    except Exception as e:
        return {"success": False, "error": str(e)} 