"""
database.py — SQLAlchemy 异步 SQLite 数据库模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class RawFrame(Base):
    """原始帧记录表"""
    __tablename__ = "raw_frames"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)   # 入库时间
    node_addr = Column(Integer, index=True)                       # 节点地址
    frame_type = Column(Integer, index=True)                      # 0x01/0x02/0x03
    type_name = Column(String(16))                                # AD7606/RS485/CAN
    raw_hex = Column(Text)                                        # 完整帧十六进制
    crc_ok = Column(Boolean, default=True)
    topic = Column(String(128))                                   # 来源 MQTT topic


class AD7606Record(Base):
    """AD7606 解析后数据表"""
    __tablename__ = "ad7606_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    node_addr = Column(Integer, index=True)
    ch0_mv = Column(Float)
    ch1_mv = Column(Float)
    ch2_mv = Column(Float)
    ch3_mv = Column(Float)
    ch4_mv = Column(Float)
    ch5_mv = Column(Float)
    ch6_mv = Column(Float)
    ch7_mv = Column(Float)


async def init_db():
    """创建数据库表（首次启动时调用）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """FastAPI 依赖注入用的数据库会话"""
    async with AsyncSessionLocal() as session:
        yield session
