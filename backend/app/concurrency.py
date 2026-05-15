"""并发控制：每个工令一把 asyncio.Lock，避免同工令 DML 写入竞态。

模型：
  - 同工令上传 → 串行（保证 DML 写入原子）
  - 不同工令上传 → 完全并行
  - asyncio.Lock 在 await 处让出 event loop，搭配 asyncio.to_thread 不会卡住其他请求

跨进程：单 uvicorn worker 时本模块足够。若将来部署多 worker，
建议改用 filelock / portalocker 包对 DML 文件做文件级互斥。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

logger = logging.getLogger("controlled-platform.concurrency")

# 每个工令一把锁；进程内全局
_PROJECT_LOCKS: dict[str, asyncio.Lock] = {}
# 保护 _PROJECT_LOCKS 字典本身的元锁
_REGISTRY_LOCK: asyncio.Lock | None = None


def _get_registry_lock() -> asyncio.Lock:
    """asyncio.Lock 必须在 event loop 内创建；首次调用时惰性初始化。"""
    global _REGISTRY_LOCK
    if _REGISTRY_LOCK is None:
        _REGISTRY_LOCK = asyncio.Lock()
    return _REGISTRY_LOCK


async def _get_project_lock(project: str) -> asyncio.Lock:
    async with _get_registry_lock():
        lock = _PROJECT_LOCKS.get(project)
        if lock is None:
            lock = asyncio.Lock()
            _PROJECT_LOCKS[project] = lock
        return lock


@asynccontextmanager
async def project_lock(project: str, request_id: str | None = None):
    """串行化某工令的关键临界区。

    用法:
        async with project_lock("260455"):
            # DML 读改写在这里，保证同工令任意时刻只有一个请求在动
            ...

    通过 request_id 记录等待/获得锁的时间，便于在高并发时排查队列堆积。
    """
    lock = await _get_project_lock(project)
    rid = request_id or uuid.uuid4().hex[:8]
    waiters = "" if not lock.locked() else " (等待中)"
    logger.debug("[%s] 申请工令锁 %s%s", rid, project, waiters)
    async with lock:
        logger.debug("[%s] 获得工令锁 %s", rid, project)
        try:
            yield
        finally:
            logger.debug("[%s] 释放工令锁 %s", rid, project)


def lock_stats() -> dict:
    """用于 /api/health 等端点输出当前锁占用情况。"""
    return {
        "tracked_projects": len(_PROJECT_LOCKS),
        "locked_now": [p for p, l in _PROJECT_LOCKS.items() if l.locked()],
    }
