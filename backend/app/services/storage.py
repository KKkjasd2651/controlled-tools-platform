"""文件服务器抽象 —— 落在 Windows SMB 共享上 (UNC 路径)。

布局 (按 SBPC 现场约定)：
    <fs_root>/<工令号>/
        文件清单.xlsx                # DML，由 TDML 模板复制
        <code>.<ext>                # 受控文件 —— 平铺，文件名只保留 文档编码
                                     # 同编码上传新版本 → 覆盖旧文件 + DML.Log 追加新版本

历史完整文件名 (<code>_V<version> <title>.<ext>) 仅作为元信息保存在 DML.Log 与日志 zip 中。
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class FileServer:
    def __init__(self, root: Path, controlled_subdir: str = ""):
        self.root = Path(root)
        self.controlled_subdir = controlled_subdir or ""

    # ---------- 路径辅助 ----------
    def project_root(self, project_no: str) -> Path:
        return self.root / project_no

    def controlled_root(self, project_no: str) -> Path:
        p = self.project_root(project_no)
        if self.controlled_subdir:
            p = p / self.controlled_subdir
        return p

    def ensure_project_dirs(self, project_no: str) -> Path:
        p = self.project_root(project_no)
        p.mkdir(parents=True, exist_ok=True)
        cr = self.controlled_root(project_no)
        cr.mkdir(parents=True, exist_ok=True)
        return p

    def stored_filename(self, code: str, ext: str) -> str:
        """受控文件落盘名 —— SBPC 约定：仅用 <code>.<ext>，不含版本/标题。"""
        return f"{code}.{ext.lstrip('.').lower()}"

    def relpath(self, project_no: str, stored_name: str) -> str:
        parts = [project_no]
        if self.controlled_subdir:
            parts.append(self.controlled_subdir)
        parts.append(stored_name)
        return "/".join(parts)

    # ---------- 查询 ----------
    def find_by_code(self, project_no: str, code: str) -> List[Path]:
        """返回工令文件夹下所有以该编码开头的文件 (大小写不敏感)。

        因为历史上可能存在带版本/标题的旧命名 (<code>_V1.0 标题.pdf)，
        所以按前缀匹配，便于一次性替换为最新版的 <code>.<ext>。
        """
        cr = self.controlled_root(project_no)
        if not cr.exists():
            return []
        code_l = code.lower()
        return sorted(
            p for p in cr.iterdir()
            if p.is_file() and p.name.lower().startswith(code_l) and not p.name.lower().endswith(".xlsx")
        )

    def list_controlled(self, project_no: str) -> List[str]:
        cr = self.controlled_root(project_no)
        if not cr.exists():
            return []
        # DML 自己不算受控文件
        return sorted(
            p.name for p in cr.iterdir()
            if p.is_file() and not p.name.lower().endswith(".xlsx")
        )

    # ---------- 写入 ----------
    def write_with_name(
        self,
        project_no: str,
        filename: str,
        data: bytes,
    ) -> tuple[Path, List[str]]:
        """按指定文件名落盘到工令根；同名覆盖。

        返回 (新文件路径, 被覆盖的旧文件名列表 —— 当且仅当同名)。
        """
        self.ensure_project_dirs(project_no)
        cr = self.controlled_root(project_no)
        target = cr / filename

        replaced: List[str] = []
        if target.exists() and target.is_file():
            replaced.append(target.name)
            try:
                target.unlink()
            except Exception as e:
                logger.warning("无法删除已存在的同名文件 %s: %s", target, e)

        target.write_bytes(data)
        return target, replaced

    def write_controlled(
        self,
        project_no: str,
        code: str,
        ext: str,
        data: bytes,
    ) -> tuple[Path, List[str]]:
        """旧接口：落盘 <code>.<ext> 到工令根；编码前缀匹配删除旧文件。

        新流程默认改用 write_with_name；本方法保留作为按编码归并的可选模式。
        """
        self.ensure_project_dirs(project_no)
        cr = self.controlled_root(project_no)

        replaced: List[str] = []
        for old in self.find_by_code(project_no, code):
            try:
                replaced.append(old.name)
                old.unlink()
            except Exception as e:
                logger.warning("无法删除旧文件 %s: %s", old, e)

        target = cr / self.stored_filename(code, ext)
        target.write_bytes(data)
        return target, replaced

    # ---------- 自检 ----------
    def _do_writability_check(self) -> Optional[str]:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return f"无法创建/进入 {self.root}: {e}"
        probe = self.root / f".controlled_platform_probe_{os.getpid()}_{int(time.time()*1000)}"
        try:
            probe.write_bytes(b"")
            probe.unlink()
        except Exception as e:
            return f"无写权限 (探针 {probe.name}): {e}"
        return None

    def writability_check(self, timeout_seconds: float = 8.0) -> Optional[str]:
        """启动期可写性自检，带超时；UNC 路径下若 SMB 不响应不至于卡死服务启动。

        返回:
            None          —— 可读写
            错误字符串    —— 不可写 / 超时
        """
        import threading

        result: list[Optional[str]] = ["TIMEOUT"]
        done = threading.Event()

        def _run():
            try:
                result[0] = self._do_writability_check()
            except Exception as e:
                result[0] = f"自检异常: {e}"
            finally:
                done.set()

        t = threading.Thread(target=_run, daemon=True, name="fs-writability-check")
        t.start()
        if not done.wait(timeout=timeout_seconds):
            return (
                f"自检超时 ({timeout_seconds:.0f}s) —— SMB 路径 {self.root} 无响应。"
                f"在文件资源管理器里访问一次该路径输入凭据并勾选'记住凭据'后重试；"
                f"或在 .env 设 REQUIRE_WRITABLE_FS=false 跳过本检查。"
            )
        return result[0]

    # ---------- 下载链接 ----------
    def build_http_url(self, public_base_url: str, project_no: str, stored_name: str) -> str:
        return (
            f"{public_base_url.rstrip('/')}/files/"
            f"{self.relpath(project_no, stored_name).lstrip('/')}"
        )

    def build_unc_url(self, project_no: str, stored_name: str) -> str:
        """把磁盘路径转成给工程师点击的 UNC 链接（资源管理器可直接打开）。"""
        return str(self.controlled_root(project_no) / stored_name)
