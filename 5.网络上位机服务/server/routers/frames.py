"""
routers/frames.py — 原始帧查询 API
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, RawFrame, AD7606Record

router = APIRouter(prefix="/api", tags=["frames"])


@router.get("/frames")
async def list_frames(
    node_addr: Optional[int] = Query(None, description="按节点地址过滤"),
    frame_type: Optional[int] = Query(None, description="按帧类型过滤 (1=AD7606,2=RS485,3=CAN)"),
    limit: int = Query(50, le=500),
    db: AsyncSession = Depends(get_db),
):
    """查询最近原始帧列表"""
    stmt = select(RawFrame).order_by(desc(RawFrame.ts)).limit(limit)
    if node_addr is not None:
        stmt = stmt.where(RawFrame.node_addr == node_addr)
    if frame_type is not None:
        stmt = stmt.where(RawFrame.frame_type == frame_type)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "ts": r.ts.isoformat() if r.ts else None,
            "node_addr": r.node_addr,
            "frame_type": r.frame_type,
            "type_name": r.type_name,
            "raw_hex": r.raw_hex,
            "crc_ok": r.crc_ok,
            "topic": r.topic,
        }
        for r in rows
    ]


@router.get("/ad7606")
async def list_ad7606(
    node_addr: Optional[int] = Query(None),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """查询 AD7606 历史数据（用于趋势图）"""
    stmt = select(AD7606Record).order_by(desc(AD7606Record.ts)).limit(limit)
    if node_addr is not None:
        stmt = stmt.where(AD7606Record.node_addr == node_addr)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "ts": r.ts.isoformat() if r.ts else None,
            "node_addr": r.node_addr,
            "channels_mv": [
                r.ch0_mv, r.ch1_mv, r.ch2_mv, r.ch3_mv,
                r.ch4_mv, r.ch5_mv, r.ch6_mv, r.ch7_mv,
            ],
        }
        for r in rows
    ]
