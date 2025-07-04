from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# 数据库设置
DATABASE_URL = "sqlite:///./config.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Config(Base):
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text)
    description = Column(String)
    config_type = Column(String, default="string")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class PrivateKey(Base):
    __tablename__ = "private_keys"

    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String, nullable=False)  # 私钥昵称
    private_key = Column(Text, nullable=False)  # 私钥
    public_key = Column(String, nullable=False)  # 公钥
    deleted = Column(Boolean, default=False)  # 逻辑删除标记
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class MonitorRecord(Base):
    __tablename__ = "monitor_records"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # 监控名称
    private_key = Column(Text)  # 旧版本私钥字段（向后兼容）
    private_key_id = Column(Integer, ForeignKey("private_keys.id"))  # 私钥ID（新版本）
    token_address = Column(String, nullable=False)  # 代币地址
    # Token 元数据字段
    token_name = Column(String)  # Token名称
    token_symbol = Column(String)  # Token符号
    token_logo_uri = Column(String)  # Token Logo URI
    token_decimals = Column(Integer)  # Token小数位数
    threshold = Column(Float, nullable=False)  # 阈值
    sell_percentage = Column(Float, nullable=False)  # 出售比例
    webhook_url = Column(String, nullable=False)  # 通知webhook
    check_interval = Column(Integer, default=5)  # 检查间隔（秒）
    execution_mode = Column(String, default="single")  # 执行模式：single(单次), multiple(多次)
    minimum_hold_value = Column(Float, default=50.0)  # 最低持仓金额(USD)，用于多次执行模式
    status = Column(String, default="stopped")  # 状态：monitoring, stopped, error
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    last_check_at = Column(DateTime)
    last_price = Column(Float)
    last_market_cap = Column(Float)
    
    # 关系
    private_key_obj = relationship("PrivateKey", lazy="joined", foreign_keys=[private_key_id])

class MonitorLog(Base):
    __tablename__ = "monitor_logs"

    id = Column(Integer, primary_key=True, index=True)
    monitor_record_id = Column(Integer, nullable=False)  # 关联的监控记录ID
    timestamp = Column(DateTime, default=datetime.utcnow)
    price = Column(Float)
    market_cap = Column(Float)
    threshold_reached = Column(Boolean, default=False)
    action_taken = Column(String)
    tx_hash = Column(String)

# 创建表
Base.metadata.create_all(bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
