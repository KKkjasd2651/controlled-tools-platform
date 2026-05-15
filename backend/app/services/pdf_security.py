"""PDF 印章 + 加密。

印章样式（参考 Nitro PDF Pro 自带的 "Controlled" Stamp）：
  ┌────────────────────────────┐
  │     CONTROLLED             │  ← 蓝色大字
  │  By <作者> at <时:分:秒, 年-月-日>  │  ← 蓝色小字
  └────────────────────────────┘
  - 圆角矩形双线边框、蓝紫色、整体 50% 透明度
  - 默认放在每页**右下角**
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.constants import UserAccessPermissions as _UAP
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


_FONT_REGISTERED = False
_FONT_NAME = "Helvetica"  # fallback


def _register_cjk_font() -> str:
    """注册一个能渲染中文的 TTF；失败回退 Helvetica（中文丢失但英文 OK）。

    支持 Windows / Linux (Debian/Ubuntu) / macOS：
      - Windows: msyhbd / msyh / simhei / simsun
      - Linux:   Noto Sans CJK (apt install fonts-noto-cjk) / 文泉驿
      - macOS:   PingFang / STHeiti
    """
    global _FONT_REGISTERED, _FONT_NAME
    if _FONT_REGISTERED:
        return _FONT_NAME
    candidates = [
        # ---- Windows ----
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        # ---- Linux: Noto Sans CJK (Debian/Ubuntu: apt install fonts-noto-cjk) ----
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        # ---- Linux: 文泉驿 (apt install fonts-wqy-microhei / fonts-wqy-zenhei) ----
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        # ---- macOS ----
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("StampCJK", path))
                _FONT_NAME = "StampCJK"
                _FONT_REGISTERED = True
                return _FONT_NAME
            except Exception:
                continue
    _FONT_REGISTERED = True
    return _FONT_NAME


def _build_stamp_pdf(top_text: str, bottom_text: str) -> bytes:
    """生成只含右下角印章的 A4 透明 PDF。"""
    font = _register_cjk_font()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    # 印章尺寸 & 位置
    stamp_w = 65 * mm
    stamp_h = 22 * mm
    margin = 15 * mm
    x = page_w - stamp_w - margin
    y = margin

    # 蓝紫色 (参考截图)
    R, G, B = 0.40, 0.30, 0.85

    # ---- 50% 透明 ----
    c.saveState()
    c.setFillAlpha(0.5)
    c.setStrokeAlpha(0.6)

    c.setStrokeColorRGB(R, G, B)
    c.setFillColorRGB(R, G, B)

    # 双线圆角矩形边框
    c.setLineWidth(1.6)
    c.roundRect(x, y, stamp_w, stamp_h, 4 * mm, stroke=1, fill=0)
    c.setLineWidth(0.6)
    c.roundRect(x + 1.5, y + 1.5, stamp_w - 3, stamp_h - 3, 3.5 * mm, stroke=1, fill=0)

    # 大字 CONTROLLED
    try:
        c.setFont(font, 22)
    except Exception:
        c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(x + stamp_w / 2, y + stamp_h * 0.50, top_text)

    # 小字 By <作者> at <时间>
    try:
        c.setFont(font, 8)
    except Exception:
        c.setFont("Helvetica", 8)
    c.drawCentredString(x + stamp_w / 2, y + stamp_h * 0.18, bottom_text)

    c.restoreState()
    c.save()
    return buf.getvalue()


def stamp_and_encrypt_pdf(
    pdf_bytes: bytes,
    author: str,
    stamp_top: str,
    owner_password: str,
    user_password: str = "",
) -> bytes:
    """给 PDF 每页打印章，再加密。"""
    bottom = f"By {author} at {datetime.now().strftime('%H:%M:%S, %Y-%m-%d')}"
    stamp_pdf = _build_stamp_pdf(stamp_top, bottom)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    stamp_reader = PdfReader(io.BytesIO(stamp_pdf))
    stamp_page = stamp_reader.pages[0]

    writer = PdfWriter()
    for page in reader.pages:
        page.merge_page(stamp_page)
        writer.add_page(page)

    # 权限位：**只允许打印**，禁止编辑/复制/注释/拼装/填表
    # 阅读器（Acrobat/Nitro/WPS/Foxit）会在标题栏显示"已加密"+
    # 把编辑/复制按钮置灰；需要 owner_password 才能解除。
    permissions = _UAP.PRINT | _UAP.PRINT_TO_REPRESENTATION
    writer.encrypt(
        user_password=user_password or "",     # 空 = 任何人都能打开查看
        owner_password=owner_password,         # 强口令 = 解除限制需要它
        use_128bit=True,
        permissions_flag=permissions,
    )
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def protect_file(
    file_bytes: bytes,
    ext: str,
    author: str,
    stamp_top: str,
    owner_password: str,
    user_password: str = "",
) -> bytes:
    """PDF → 打印章 + 加密；其他格式原样返回（暂不支持）。"""
    if ext.lower() == "pdf":
        return stamp_and_encrypt_pdf(
            file_bytes,
            author=author,
            stamp_top=stamp_top,
            owner_password=owner_password,
            user_password=user_password,
        )
    return file_bytes
