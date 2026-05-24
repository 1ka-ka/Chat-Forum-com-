from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, user, post, comment, like, chat, notification
from utils.auth import decode_token
import os
import logging
from logging.handlers import RotatingFileHandler

# ========== 日志配置 ==========
# 同时输出到终端和文件，文件存放在与 Drogon 共享的 logs/ 目录
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("chatforum")
logger.setLevel(logging.INFO)

# 日志格式：时间 | 级别 | 消息
log_format = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

# 终端输出（StreamHandler）
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

# 文件输出（RotatingFileHandler：按大小轮转，与 Drogon 日志放在同一目录）
file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "chatforum-py.log"),
    maxBytes=10 * 1024 * 1024,  # 10MB 轮转
    backupCount=5,               # 保留 5 个旧文件
    encoding="utf-8",
)
file_handler.setFormatter(log_format)
logger.addHandler(file_handler)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "frontend", "dist")
HAS_FRONTEND = os.path.isfile(os.path.join(STATIC_DIR, "index.html"))

os.makedirs("./uploads/images", exist_ok=True)
os.makedirs("./uploads/avatars", exist_ok=True)

app = FastAPI(title="畅谈 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    skip_auth = (
        path in ["/", "/api/health"]
        or path.startswith("/uploads")
        or path.startswith("/docs")
        or path.startswith("/openapi")
        or path == "/api/auth/login"
        or path == "/api/auth/register"
        or path.startswith("/ws")
        or path.startswith("/assets")
    )
    if skip_auth:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    user_id = 0
    if auth_header.startswith("Bearer "):
        try:
            user_id = decode_token(auth_header[7:])
        except Exception:
            pass

    request.state.user_id = user_id

    response = await call_next(request)

    # 请求日志：方法 + 路径 + 状态码 + 用户ID
    logger.info(f"{request.method} {path} {response.status_code} user={user_id}")

    return response


app.include_router(auth.router)
app.include_router(user.router)
app.include_router(post.router)
app.include_router(comment.router)
app.include_router(like.router)
app.include_router(chat.router)
app.include_router(notification.router)

app.websocket("/ws/chat")(chat.websocket_chat)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

if HAS_FRONTEND:
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if HAS_FRONTEND:
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.on_event("startup")
async def startup():
    # 保存事件循环引用，供同步代码（like/comment）推送 WebSocket 通知
    import asyncio
    from utils.notification import set_event_loop
    set_event_loop(asyncio.get_running_loop())

    logger.info("=" * 50)
    logger.info("  ChatForum Server Starting...")
    logger.info(f"  API:       http://localhost:8080/api")
    logger.info(f"  WebSocket: ws://localhost:8080/ws/chat")
    if HAS_FRONTEND:
        logger.info(f"  Frontend:  http://localhost:8080")
    else:
        logger.info(f"  Frontend:  http://localhost:5173 (dev server needed)")
        logger.info(f"  Run 'build.bat' to enable single-server mode")
    logger.info(f"  Log file:  {os.path.join(LOG_DIR, 'chatforum-py.log')}")
    logger.info("=" * 50)
