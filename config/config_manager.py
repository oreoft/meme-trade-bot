import json
import logging
from datetime import datetime
from typing import Any

from database.models import Config, SessionLocal


class ConfigManager:
    """配置管理器"""

    DEFAULT_CONFIGS = {
        'API_KEY': {'value': 'xxx', 'description': 'Birdeye API密钥', 'config_type': 'string'},
        'CHAIN_HEADER': {'value': 'solana', 'description': '区块链类型', 'config_type': 'string'},
        'RPC_URL': {'value': 'https://api.mainnet-beta.solana.com', 'description': 'Solana RPC节点地址', 'config_type': 'string'},
        'JUPITER_API_URL': {'value': 'https://quote-api.jup.ag/v6', 'description': 'Jupiter API地址', 'config_type': 'string'},
        'SLIPPAGE_BPS': {'value': '100', 'description': '滑点设置（100 = 1%）', 'config_type': 'number'}
    }

    # 存储需要刷新配置的服务实例
    _service_instances = []

    @classmethod
    def register_service(cls, service_instance):
        """注册需要配置刷新的服务实例"""
        if service_instance not in cls._service_instances:
            cls._service_instances.append(service_instance)

    @classmethod
    def refresh_all_services(cls):
        """刷新所有已注册服务的配置"""
        refreshed_count = 0
        for service in cls._service_instances:
            if hasattr(service, 'refresh_config'):
                try:
                    service.refresh_config()
                    refreshed_count += 1
                except Exception as e:
                    logging.error(f"刷新服务配置失败: {e}")
        logging.info(f"已刷新 {refreshed_count} 个服务的配置")
        return refreshed_count

    @staticmethod
    def get_db():
        """获取数据库会话"""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def init_default_configs():
        """初始化默认配置"""
        db = SessionLocal()
        try:
            for key, config_data in ConfigManager.DEFAULT_CONFIGS.items():
                existing = db.query(Config).filter(Config.key == key).first()
                if not existing:
                    config = Config(
                        key=key,
                        value=config_data['value'],
                        description=config_data['description'],
                        config_type=config_data['config_type']
                    )
                    db.add(config)
            db.commit()
        finally:
            db.close()

    @staticmethod
    def get_config(key: str, default: Any = None) -> Any:
        """获取配置值"""
        db = SessionLocal()
        try:
            config = db.query(Config).filter(Config.key == key).first()
            if not config:
                return default

            value = config.value
            config_type = config.config_type

            if config_type == 'number':
                return float(value) if '.' in value else int(value)
            elif config_type == 'boolean':
                return value.lower() in ('true', '1', 'yes', 'on')
            elif config_type == 'json':
                return json.loads(value)
            else:
                return value
        except Exception:
            return default
        finally:
            db.close()

    @staticmethod
    def set_config(key: str, value: str, description: str = "", config_type: str = "string") -> bool:
        """设置配置值"""
        db = SessionLocal()
        try:
            config = db.query(Config).filter(Config.key == key).first()
            if config:
                config.value = value
                config.description = description
                config.config_type = config_type
                config.updated_at = datetime.utcnow()
            else:
                config = Config(key=key, value=value, description=description, config_type=config_type)
                db.add(config)

            db.commit()
            return True
        except Exception:
            return False
        finally:
            db.close()

    @staticmethod
    def get_all_configs() -> list:
        """获取所有配置"""
        db = SessionLocal()
        try:
            configs = db.query(Config).all()
            return [
                {
                    "id": config.id,
                    "key": config.key,
                    "value": config.value,
                    "description": config.description,
                    "config_type": config.config_type,
                    "updated_at": config.updated_at.isoformat() if config.updated_at else None
                }
                for config in configs
            ]
        finally:
            db.close()

    @staticmethod
    def delete_config(key: str) -> bool:
        """删除配置"""
        db = SessionLocal()
        try:
            config = db.query(Config).filter(Config.key == key).first()
            if config:
                db.delete(config)
                db.commit()
                return True
            return False
        except Exception:
            return False
        finally:
            db.close()
