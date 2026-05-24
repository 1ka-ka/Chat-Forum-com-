from database import get_db_cursor

# 全局引用：uvicorn 启动后保存事件循环，供同步代码推送 WebSocket 通知
_event_loop = None


def set_event_loop(loop):
    """在应用启动时调用，保存事件循环引用"""
    global _event_loop
    _event_loop = loop


def create_notification(user_id: int, actor_id: int, ntype: str, post_id: int = None,
                        comment_id: int = None, message: str = ""):
    if user_id == actor_id:
        return
    cursor, conn = get_db_cursor()
    try:
        cursor.execute(
            "INSERT INTO notifications (user_id, actor_id, type, post_id, comment_id, message) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, actor_id, ntype, post_id, comment_id, message)
        )
        conn.commit()
        notification_id = cursor.lastrowid

        # Push notification via WebSocket
        _push_notification(user_id, notification_id, ntype, post_id, comment_id, message, actor_id)
    finally:
        conn.close()


def _push_notification(user_id: int, notification_id: int, ntype: str,
                       post_id: int, comment_id: int, message: str, actor_id: int):
    """Push notification to user via WebSocket (best effort)

    核心问题：like/comment 路由是同步函数，不在异步上下文中，
    无法直接 await 或 asyncio.ensure_future。
    解决方案：用 run_coroutine_threadsafe 从同步线程安全地提交协程到事件循环。
    """
    try:
        import asyncio
        from routers.chat import manager

        data = {
            "type": "notification",
            "notification": {
                "id": notification_id,
                "type": ntype,
                "post_id": post_id,
                "comment_id": comment_id,
                "message": message,
                "is_read": 0,
                "actor_id": actor_id,
            }
        }

        loop = _event_loop
        if loop and loop.is_running():
            # 从同步代码安全地提交协程到正在运行的事件循环
            asyncio.run_coroutine_threadsafe(manager.send_to_user(user_id, data), loop)
    except Exception:
        pass
