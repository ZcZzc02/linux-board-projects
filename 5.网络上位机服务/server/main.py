"""
main.py — FastAPI 主入口 + MQTT 启动
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 确保 server/ 目录在 sys.path 中（从任意目录启动都能正常导入）
sys.path.insert(0, str(Path(__file__).parent))

from config import MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE, WEB_HOST, WEB_PORT
from database import init_db, AsyncSessionLocal, RawFrame, AD7606Record
from mqtt_client import create_mqtt_client, set_broadcast, set_save_frame
from routers import frames, realtime, commands


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("main")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)

# ──────────────────────────────────────────────
# 数据库写入（在 asyncio 线程中执行）
# ──────────────────────────────────────────────
_loop_ref: asyncio.AbstractEventLoop | None = None


def save_frame_callback(record: dict):
    if _loop_ref:
        asyncio.run_coroutine_threadsafe(_save_to_db(record), _loop_ref)


async def _save_to_db(record: dict):
    parsed = record.get("parsed") or {}
    async with AsyncSessionLocal() as db:
        # 保存原始帧
        frame = RawFrame(
            ts=datetime.utcnow(),
            node_addr=parsed.get("node_addr"),
            frame_type=parsed.get("frame_type"),
            type_name=parsed.get("type_name"),
            raw_hex=record.get("raw_hex"),
            crc_ok=parsed.get("crc_ok", True),
            topic=record.get("topic"),
        )
        db.add(frame)

        # 如果是 AD7606，额外存解析表
        if parsed.get("frame_type") == 0x01 and parsed.get("crc_ok"):
            chs = parsed.get("channels_mv", [None] * 8)
            while len(chs) < 8:
                chs.append(None)
            rec = AD7606Record(
                ts=datetime.utcnow(),
                node_addr=parsed.get("node_addr"),
                ch0_mv=chs[0], ch1_mv=chs[1], ch2_mv=chs[2], ch3_mv=chs[3],
                ch4_mv=chs[4], ch5_mv=chs[5], ch6_mv=chs[6], ch7_mv=chs[7],
            )
            db.add(rec)

        await db.commit()


# ──────────────────────────────────────────────
# 应用生命周期
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop_ref
    _loop_ref = asyncio.get_running_loop()

    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 注入 WebSocket 事件循环
    realtime.set_loop(_loop_ref)

    # 创建 MQTT 客户端
    mqtt_client = create_mqtt_client()
    set_broadcast(realtime.broadcast)
    set_save_frame(save_frame_callback)
    commands.set_mqtt_client(mqtt_client)

    # 连接并在后台线程中运行（paho 自带线程）
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
    mqtt_client.loop_start()
    logger.info(f"MQTT 客户端启动，正在连接 {MQTT_BROKER}:{MQTT_PORT}")

    # 网关超时检测（90秒无消息则标记离线，LWT 正常时这里是兜底）
    async def _gw_watchdog():
        from mqtt_client import _gw_last_seen, _gw_online
        from datetime import timezone
        while True:
            await asyncio.sleep(30)
            import mqtt_client as _mc
            if _mc._gw_online and _mc._gw_last_seen is not None:
                elapsed = (datetime.now(timezone.utc) - _mc._gw_last_seen).total_seconds()
                if elapsed > 90:
                    logger.warning(f"网关超时 {elapsed:.0f}s，标记离线")
                    _mc._gw_online = False
                    _mc._gw_transport = None
                    from routers.realtime import update_status, broadcast
                    update_status("gw_online", False)
                    update_status("gw_transport", None)
                    broadcast({"type": "gw_status", "online": False,
                               "transport": None,
                               "ts": datetime.utcnow().isoformat()})

    watchdog_task = asyncio.create_task(_gw_watchdog())

    yield  # 应用运行中

    watchdog_task.cancel()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    logger.info("MQTT 客户端已关闭")


# ──────────────────────────────────────────────
# FastAPI 应用
# ──────────────────────────────────────────────
app = FastAPI(title="网络上位机服务", version="0.1.0", lifespan=lifespan)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# 注册路由
app.include_router(frames.router)
app.include_router(realtime.router)
app.include_router(commands.router)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(str(_static_dir / "favicon.ico"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


if __name__ == "__main__":
    import socket
    import threading
    import time
    import urllib.request
    import uvicorn
    import webview

    # 启动前检测端口是否空闲
    _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        _sock.bind(("127.0.0.1", WEB_PORT))
        _sock.close()
    except OSError:
        _sock.close()
        import tkinter.messagebox as _mb
        _mb.showerror(
            "端口冲突",
            f"端口 {WEB_PORT} 已被占用，请先关闭旧的上位机窗口再重新启动。"
        )
        sys.exit(1)

    url = f"http://127.0.0.1:{WEB_PORT}"

    def _start_server():
        """后台线程运行 uvicorn"""
        uvicorn.run(app, host="127.0.0.1", port=WEB_PORT, log_level="info")

    # 先启动服务线程
    threading.Thread(target=_start_server, daemon=True).start()

    # 主线程等待服务就绪（最多 18 秒），再创建窗口
    for _ in range(60):
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except Exception:
            time.sleep(0.3)

    # 服务已就绪，直接用真实 URL 创建窗口
    window = webview.create_window(
        title="数据采集监控",
        url=url,
        width=1400,
        height=900,
        min_size=(900, 600),
        text_select=True,
    )
    webview.start()
