"""文件名解析：<图号>_<文件版本> <图纸标题>.<后缀>

示例：
  D45H8-BF-03_A01 底横梁1-单页.pdf
  → code   = D45H8-BF-03
    fver   = A01           （图纸内部版本，仅记录，不直接用于 DML 版本号）
    title  = 底横梁1-单页
    ext    = pdf

DML 里的"版本"列由平台自动递增（1.0, 2.0, 3.0...），见 dml.next_log_version()。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FilenameMeta:
    code: str         # 图号 / 文档编码
    fver: str         # 图纸内部版本（A01 这种，来自文件名）
    title: str        # 图纸标题
    ext: str          # 扩展名（小写、不含点）
    raw: str          # 原始完整文件名


class FilenameError(ValueError):
    pass


def parse_filename(filename: str) -> FilenameMeta:
    """按 SBPC 约定解析图纸文件名。

    格式：<code>_<fver> <title>.<ext>
      - code 与 fver 之间是 _
      - fver 与 title 之间是空格（半角）
      - title 末尾 .<ext>

    code 自身不能含 `_`；title 可以含任何字符（含 `-`、空格、中文）。
    """
    name = (filename or "").strip()
    if not name:
        raise FilenameError("文件名为空")

    # 去掉扩展名
    if "." not in name:
        raise FilenameError(f"文件名缺少扩展名: {name!r}")
    stem, _, ext = name.rpartition(".")
    if not stem or not ext:
        raise FilenameError(f"文件名格式错误（扩展名）: {name!r}")

    # 第一个空格分隔 head + title
    if " " not in stem:
        raise FilenameError(
            f"文件名格式错误：缺少 ' ' 分隔的图纸标题段。"
            f"期望 <图号>_<版本> <标题>.<ext>，实得 {name!r}"
        )
    head, _, title = stem.partition(" ")
    title = title.strip()
    if not title:
        raise FilenameError(f"文件名缺少图纸标题: {name!r}")

    # head = code_fver；用 rpartition 以容忍 code 内含 `-` 等字符
    if "_" not in head:
        raise FilenameError(
            f"文件名格式错误：图号与版本之间应是 '_'。期望 <图号>_<版本> <标题>.<ext>，实得 {name!r}"
        )
    code, _, fver = head.rpartition("_")
    code = code.strip()
    fver = fver.strip()
    if not code:
        raise FilenameError(f"文件名缺少图号: {name!r}")
    if not fver:
        raise FilenameError(f"文件名缺少版本号: {name!r}")

    return FilenameMeta(
        code=code,
        fver=fver,
        title=title,
        ext=ext.lower(),
        raw=name,
    )


# 兼容旧接口
class FilenameParser:
    """旧接口包装，仅供历史代码沿用。新代码直接调用 parse_filename()。"""

    def __init__(self, pattern: str | None = None):
        # 忽略 pattern（旧的正则模式）
        self._pattern = pattern

    def parse(self, filename: str) -> FilenameMeta:
        return parse_filename(filename)
