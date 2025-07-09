import json
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
    pre_sniper_mode = Column(Boolean, default=False)  # 是否开启预抢购模式
    type = Column(String, default="sell")  # 监控类型：sell(出售监听), buy(购买监听)
    max_buy_amount = Column(Float, default=0.0)  # 累计购买上限(USD)，仅买入监听用，0表示不限制
    accumulated_buy_usd = Column(Float, default=0.0)  # 累计已购买金额(USD)，持久化

    # 关系
    private_key_obj = relationship("PrivateKey", lazy="joined", foreign_keys=[private_key_id])


class SwingMonitorRecord(Base):
    """波段监控记录表"""
    __tablename__ = "swing_monitor_records"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # 监控名称
    private_key_id = Column(Integer, ForeignKey("private_keys.id"), nullable=False)  # 私钥ID
    
    # 监听代币配置
    watch_token_address = Column(String, nullable=False)  # 监听的代币地址
    watch_token_name = Column(String)  # 监听代币名称
    watch_token_symbol = Column(String)  # 监听代币符号
    watch_token_logo_uri = Column(String)  # 监听代币Logo URI
    watch_token_decimals = Column(Integer)  # 监听代币小数位数
    
    # 交易代币配置
    trade_token_address = Column(String, nullable=False)  # 交易的代币地址
    trade_token_name = Column(String)  # 交易代币名称
    trade_token_symbol = Column(String)  # 交易代币符号
    trade_token_logo_uri = Column(String)  # 交易代币Logo URI
    trade_token_decimals = Column(Integer)  # 交易代币小数位数
    
    # 价格监控配置
    price_type = Column(String, default="market_cap")  # 价格类型：market_cap(市值), price(单价)
    sell_threshold = Column(Float, nullable=False)  # 卖出阈值
    buy_threshold = Column(Float, nullable=False)  # 买入阈值
    sell_percentage = Column(Float, nullable=False)  # 卖出比例 (0-1)
    buy_percentage = Column(Float, nullable=False)  # 买入比例 (0-1)
    
    # 其他配置
    webhook_url = Column(String, nullable=False)  # 通知webhook
    check_interval = Column(Integer, default=5)  # 检查间隔（秒）
    all_in_threshold = Column(Float, default=50.0)  # 触发全仓操作的最小金额(USD)
    
    # 状态字段
    status = Column(String, default="stopped")  # 状态：monitoring, stopped, error, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    last_check_at = Column(DateTime)
    last_watch_price = Column(Float)  # 最后监听价格
    last_watch_market_cap = Column(Float)  # 最后监听市值
    
    # 关系
    private_key_obj = relationship("PrivateKey", lazy="joined", foreign_keys=[private_key_id])


class MonitorLog(Base):
    __tablename__ = "monitor_logs"

    id = Column(Integer, primary_key=True, index=True)
    monitor_record_id = Column(Integer, nullable=True)  # 关联的监控记录ID，波段监控可为null
    timestamp = Column(DateTime, default=datetime.utcnow)
    price = Column(Float)
    market_cap = Column(Float)
    threshold_reached = Column(Boolean, default=False)
    action_taken = Column(String)
    tx_hash = Column(String)
    # 新增字段
    monitor_type = Column(String, default='normal')  # normal/swing
    price_type = Column(String)
    current_value = Column(Float)
    sell_threshold = Column(Float)
    buy_threshold = Column(Float)
    action_type = Column(String)
    watch_token_address = Column(String)
    trade_token_address = Column(String)


class TokenMetaData(Base):
    __tablename__ = "token_meta_data"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String(100), unique=True, nullable=False, index=True)
    data = Column(Text, nullable=False)  # 存json字符串
    updated_at = Column(Float, nullable=False)  # 时间戳

    def to_dict(self):
        return json.loads(self.data)

# 创建表
Base.metadata.create_all(bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
