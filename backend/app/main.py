from __future__ import annotations

import asyncio
import gc
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .concurrency import lock_stats, project_lock
from .config import settings
from .schemas import UploadResponse, ValidateResponse
from .services.dml import (
    append_log_entry,
    ensure_project_dml,
    find_existing_version,
    list_codes,
    log_rows,
    next_log_version,
    upsert_list_row,
)
from .services.filename import FilenameError, FilenameParser, parse_filename
from .services.pdf_security import protect_file
from .services.storage import FileServer

# === 外部集成模块（暂未启用，后续要接入时取消下面 4 行注释 + 解开 upload() 里两段调用） ===
# from .services.notifier import Notifier
# from .services.seatable_client import SeatableClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    force=True,  # 强制覆盖 uvicorn 预设，否则我们的 logger.info 被静默丢弃
)
logger = logging.getLogger("controlled-platform")


def _say(msg: str) -> None:
    """启动期关键消息双通道输出：print() 立即可见 + 日志归档。"""
    print(f"[startup] {msg}", flush=True)
    logger.info(msg)

app = FastAPI(title="受控文件工具平台", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """给每个请求生成一个短 ID，写到日志，便于在并发环境追踪。"""
    rid = uuid.uuid4().hex[:8]
    request.state.request_id = rid
    logger.info("[%s] %s %s", rid, request.method, request.url.path)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    except Exception:
        logger.exception("[%s] 请求处理异常", rid)
        raise

parser = FilenameParser(settings.filename_regex)
fs = FileServer(settings.fs_root, settings.controlled_dir)
TEMPLATE = settings.template_path

if not TEMPLATE.exists():
    raise RuntimeError(
        f"DML 模板缺失: {TEMPLATE} —— 请将 TDML.xlsx 放到 backend/templates/DML_template.xlsx"
    )

# 启动期 SMB / 本地目录可写性自检（带超时；可关闭）
_say(f"FILE_SERVER_ROOT = {settings.fs_root}")
_say(f"REQUIRE_WRITABLE_FS = {settings.require_writable_fs}")

if settings.require_writable_fs:
    _say("开始自检文件服务器可写性 (最长 8 秒) ...")
    _writability_err = fs.writability_check(timeout_seconds=8.0)
    if _writability_err:
        msg = (
            f"\n[启动失败] 文件服务器根目录不可写: {settings.fs_root}\n"
            f"原因: {_writability_err}\n"
            f"应对:\n"
            f"  1) 在文件资源管理器里访问 {settings.fs_root}，若需要凭据则输入并勾选'记住凭据'，再重试启动\n"
            f"  2) 临时绕过: 在 backend/.env 设 REQUIRE_WRITABLE_FS=false（仍会尝试写，写失败按上传请求级处理）\n"
            f"  3) 本地演示: 把 FILE_SERVER_ROOT=./fileserver 改成本地目录\n"
        )
        print(msg, flush=True)
        raise RuntimeError(msg)
    _say(f"[OK] 文件服务器可读写: {settings.fs_root}")
else:
    _say(
        f"REQUIRE_WRITABLE_FS=false —— 跳过启动期自检。"
        f"上传时若文件服务器不可写，请求会返回 502。fs_root={settings.fs_root}"
    )

# === Seatable / 邮件通知 - 暂未启用，启用时取消下面整段注释 ===
# seatable = SeatableClient(
#     server_url=settings.seatable_server_url,
#     api_token=settings.seatable_api_token,
#     table_name=settings.seatable_table_name,
#     mock=False,
# )
# notifier = Notifier(
#     host=settings.smtp_host,
#     port=settings.smtp_port,
#     user=settings.smtp_user,
#     password=settings.smtp_password,
#     sender=settings.mail_from,
#     recipients=[r.strip() for r in settings.mail_to.split(",") if r.strip()],
#     use_ssl=settings.smtp_use_ssl,
#     mock=False,
# )

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="ui")

# StaticFiles 在 UNC 路径下也可行；若失败前端就直接给 UNC 链接
try:
    app.mount("/files", StaticFiles(directory=str(settings.fs_root)), name="files")
    _files_http = True
except Exception:
    logger.exception("无法挂载 /files 到 %s，前端将给 UNC 链接", settings.fs_root)
    _files_http = False


@app.get("/", response_class=HTMLResponse)
def root():
    return (
        '<meta http-equiv="refresh" content="0; url=/ui/">'
        '<a href="/ui/">前往受控文件上传页</a>'
    )


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "fs_root": str(settings.fs_root),
        "files_http": _files_http,
        "concurrency": lock_stats(),
    }


def _to_js_regex(py_regex: str) -> str:
    import re as _re
    return _re.sub(r"\(\?P<", "(?<", py_regex)


@app.get("/api/config")
def api_config():
    return {
        "filename_regex": _to_js_regex(settings.filename_regex),
        "filename_regex_py": settings.filename_regex,
        "watermark_text": settings.watermark_text,
        "dml_filename": settings.dml_filename,
    }


@app.post("/api/validate", response_model=ValidateResponse)
def validate_filename(filename: str = Form(...)):
    try:
        meta = parser.parse(filename)
        return ValidateResponse(ok=True, message="文件名合规", meta=meta.__dict__)
    except FilenameError as e:
        return ValidateResponse(ok=False, message=str(e))


def _ensure_dml(project: str) -> Path:
    fs.ensure_project_dirs(project)
    target = settings.dml_path(project)
    # H1 链接给到该工令文件夹的 UNC 路径，工程师在 Excel 里可直接点开
    fs_url = str(fs.project_root(project)) + ("\\" if not str(fs.project_root(project)).endswith("\\") else "")
    ensure_project_dml(TEMPLATE, target, project, fs_root_url=fs_url)
    return target


@app.post("/api/upload", response_model=UploadResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    project: str = Form(..., description="工令号"),
    username: str = Form(..., description="用户名 (作者)"),
):
    """上传一份受控文件。

    新策略（SBPC 现场约定）：
      * 文件名**强制**符合 `<图号>_<文件版本> <图纸标题>.<ext>`
        例：`D45H8-BF-03_A01 底横梁1-单页.pdf`
      * 落盘文件名 = 上传原文件名，同名直接覆盖
      * DML.Log 自动递增版本（1.0 → 2.0 → 3.0 ...）
      * DML.List upsert：B 列写图纸标题，F 列写作者（前端用户名）
    """
    rid = getattr(request.state, "request_id", uuid.uuid4().hex[:8])
    raw_name = (file.filename or "").strip()
    if not raw_name:
        raise HTTPException(status_code=400, detail="未提供文件名")

    # 强制按 SBPC 规范解析文件名
    try:
        meta = parse_filename(raw_name)
    except FilenameError as e:
        raise HTTPException(status_code=400, detail=f"文件名不合规: {e}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")

    project = project.strip()
    username = username.strip()
    code = meta.code
    title = meta.title
    fver = meta.fver  # 图纸内部版本（A01 这种），仅记录到 record
    ext = meta.ext

    logger.info(
        "[%s] upload start project=%s code=%s title=%s fver=%s file=%s by=%s",
        rid, project, code, title, fver, raw_name, username,
    )

    # ---------- PDF 印章 + 加密 (CPU 重活；放进线程池) ----------
    try:
        protected = await asyncio.to_thread(
            protect_file,
            data,
            ext,
            username,                       # 作者 (印章小字里的 "By <author>")
            settings.watermark_text,        # 印章大字 (默认 "CONTROLLED")
            settings.pdf_owner_password,
            settings.pdf_user_password,
        )
    except Exception as e:
        logger.exception("[%s] PDF 处理失败", rid)
        raise HTTPException(status_code=500, detail=f"印章/加密失败: {e}") from e

    # ---------- 临界区：同工令串行（DML 读改写 + 落盘）----------
    async with project_lock(project, request_id=rid):
        # 1) 初始化 / 备份 DML
        try:
            dml_path = await asyncio.to_thread(_ensure_dml, project)
        except Exception as e:
            logger.exception("[%s] _ensure_dml 失败 project=%s", rid, project)
            raise HTTPException(status_code=409, detail=str(e)) from e

        declared = await asyncio.to_thread(list_codes, dml_path)
        in_list = code in declared

        # 2) 版本号直接用文件名里解析出的 fver（A01、A02 这种），
        #    不再做自动递增；如果 fver 为空（理论上前端已拦截）兜底 "1.0"
        version = fver or "1.0"
        logger.info("[%s] version (from filename) = %s for %s", rid, version, code)

        # 3) 落盘 PDF（按原文件名，同名覆盖）
        try:
            saved_path, replaced = await asyncio.to_thread(
                fs.write_with_name, project, raw_name, protected
            )
        except Exception as e:
            logger.exception("[%s] 写入文件服务器失败", rid)
            raise HTTPException(
                status_code=502,
                detail=f"写入文件服务器失败 ({settings.fs_root}): {e}",
            ) from e

        # 4) DML.Log 追加 (日期, 文档编码, 版本, 文档标题, 完整文件名)
        try:
            appended_row = await asyncio.to_thread(
                append_log_entry, dml_path, code, version, title, raw_name, datetime.now()
            )
        except Exception as e:
            logger.exception("[%s] DML.Log 追加失败", rid)
            raise HTTPException(
                status_code=409,
                detail=f"DML 写入失败 (可能 Excel 占用): {e}",
            ) from e

        # 5) DML.List upsert：B 列写图纸标题，F 列写作者
        try:
            list_row, list_action = await asyncio.to_thread(
                upsert_list_row, dml_path, code, title, username,
            )
            logger.info("[%s] List upsert: row=%s action=%s", rid, list_row, list_action)
        except Exception as e:
            # List 写入失败不阻断主流程；Log 已写入即视为受控
            logger.exception("[%s] DML.List upsert 失败 (不中断)", rid)
            list_row, list_action = None, f"failed: {e}"

    stored_name = saved_path.name
    file_url = fs.build_http_url(settings.public_base_url, project, stored_name)
    unc_url = fs.build_unc_url(project, stored_name)

    # 给 Seatable / 邮件用的元数据；目前两者都暂未启用，但保留构造以便日后接入
    record = {
        "文档编码": code,
        "版本": version,           # 平台自动递增的 DML 版本（1.0/2.0/3.0…）
        "文件版本": fver,           # 文件名里的 A01 等图纸内部版本
        "文档标题": title,
        "工令号": project,
        "上传人": username,
        "上传时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "下载链接": file_url,
        "UNC路径": unc_url,
        "落盘文件名": stored_name,
        "Log行号": appended_row,
        "List行号": list_row,
        "List动作": list_action,
        "在清单中": in_list,
        "覆盖旧文件": bool(replaced),
        "被覆盖文件": replaced,
    }
    logger.info("[%s] upload ok: %s", rid, record)

    # 强制 GC：openpyxl 在 read_only 模式遗留的对象、PDF 加密时持有的 bytes、
    # uvicorn 异步任务暂存的 file body 等都立即释放。对 SMB 共享文件能否被外部
    # 删除/重命名 影响很大 —— 不做 GC 时 Python 句柄会等到下次循环才释放。
    del data, protected
    gc.collect()

    # === Seatable 钣金件清单同步 - 暂未启用，启用时取消下面整段注释 ===
    # try:
    #     await asyncio.to_thread(seatable.upsert_sheet_metal_row, record)
    # except Exception:
    #     logger.exception("[%s] Seatable 更新失败（不中断主流程）", rid)

    # === 邮件通知 - 暂未启用，启用时取消下面整段注释 ===
    # body = (
    #     f"文件 {stored_name} 已受控入库。\n"
    #     f"工令号: {project}\n"
    #     f"文档编码: {code}\n"
    #     f"版本: V{version}\n"
    #     f"标题: {title or '(未填)'}\n"
    #     f"上传人: {username}\n"
    #     f"落盘路径: {unc_url}\n"
    #     f"HTTP下载: {file_url}\n"
    #     f"在清单中: {in_list}\n"
    #     f"覆盖旧文件: {bool(replaced)} {replaced or ''}"
    # )
    # try:
    #     await asyncio.to_thread(
    #         notifier.send_upload_notice,
    #         f"[受控文件] {code} V{version} {title}".strip(),
    #         body,
    #     )
    # except Exception:
    #     logger.exception("[%s] 邮件发送失败（不中断主流程）", rid)

    msg_parts = ["上传成功"]
    if replaced:
        msg_parts.append(f"已覆盖旧文件: {', '.join(replaced)}")
    if not in_list:
        msg_parts.append("[!] 该文档编码不在 List 清单中，请确认")
    return UploadResponse(
        ok=True,
        message=" | ".join(msg_parts),
        filename=stored_name,
        url=file_url,
        duplicate=bool(replaced),
        meta={
            "code": code,
            "version": version,
            "fver": fver,
            "title": title,
            "ext": ext,
            "project": project,
            "raw": raw_name,
            "in_list": in_list,
            "log_row": appended_row,
            "list_row": list_row,
            "list_action": list_action,
            "replaced": replaced,
            "unc": unc_url,
        },
    )


def _list_projects_sync() -> tuple[list[str], str | None]:
    out: list[str] = []
    err: str | None = None
    try:
        root = settings.fs_root
        if root.exists():
            for p in root.iterdir():
                try:
                    if p.is_dir() and (p / settings.dml_filename).exists():
                        out.append(p.name)
                except Exception as inner:
                    logger.warning("枚举工令子目录失败 %s: %s", p, inner)
    except Exception as e:
        logger.exception("/api/projects 列举失败")
        err = f"{type(e).__name__}: {e}"
    return sorted(out), err


@app.get("/api/projects")
async def list_projects():
    """列工令号。SMB IO 放进线程池，不阻塞 event loop。"""
    projects, err = await asyncio.to_thread(_list_projects_sync)
    return {"projects": projects, "error": err}


@app.get("/api/dml")
async def dump_dml(project: str = Query(..., description="工令号")):
    """读取该工令的 DML 内容 —— 纯只读，绝不会创建/重命名文件。
    所有 SMB IO 放进线程池，避免阻塞 event loop。
    """
    dml = settings.dml_path(project)
    codes: list[str] = []
    log: list[dict] = []
    files: list[str] = []
    errors: list[str] = []

    dml_exists = await asyncio.to_thread(dml.exists)
    if not dml_exists:
        try:
            files = await asyncio.to_thread(fs.list_controlled, project)
        except Exception as e:
            errors.append(f"list_controlled: {e}")
        return {
            "project": project,
            "codes": [],
            "log": [],
            "files": files,
            "dml_exists": False,
            "dml_download": None,
            "dml_unc": str(dml),
            "error": "; ".join(errors) if errors else None,
        }

    try:
        codes = await asyncio.to_thread(list_codes, dml)
    except Exception as e:
        logger.exception("list_codes 失败")
        errors.append(f"list_codes: {e}")
    try:
        log = await asyncio.to_thread(log_rows, dml)
    except Exception as e:
        logger.exception("log_rows 失败")
        errors.append(f"log_rows: {e}")
    try:
        files = await asyncio.to_thread(fs.list_controlled, project)
    except Exception as e:
        logger.exception("list_controlled 失败")
        errors.append(f"list_controlled: {e}")

    return {
        "project": project,
        "codes": codes,
        "log": log,
        "files": files,
        "dml_exists": True,
        "dml_download": f"{settings.public_base_url.rstrip('/')}/files/{project}/{settings.dml_filename}"
        if _files_http else None,
        "dml_unc": str(dml),
        "error": "; ".join(errors) if errors else None,
    }
