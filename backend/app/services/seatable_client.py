from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SeatableClient:
    """Seatable 钣金件清单更新；mock 模式下仅记录日志。"""

    def __init__(
        self,
        server_url: str,
        api_token: str,
        table_name: str,
        mock: bool = False,
    ):
        self.server_url = server_url
        self.api_token = api_token
        self.table_name = table_name
        self.mock = mock or not api_token or api_token.startswith("replace")
        self._base: Optional[object] = None

    def _get_base(self):
        if self._base is not None:
            return self._base
        from seatable_api import Base  # 延迟导入，避免离线时启动失败
        base = Base(self.api_token, self.server_url)
        base.auth()
        self._base = base
        return base

    def upsert_sheet_metal_row(self, record: dict) -> dict:
        """按文件编码 + 版本 upsert 一条钣金件记录。"""
        if self.mock:
            logger.info("[MOCK Seatable] upsert %s -> %s", self.table_name, record)
            return {"mock": True, "record": record}

        base = self._get_base()
        code = record.get("文件编码")
        version = record.get("版本")
        # 查询是否已有相同 文件编码 + 版本
        query = (
            f"select * from `{self.table_name}` where `文件编码`='{code}' "
            f"and `版本`='{version}' limit 1"
        )
        existing = base.query(query) or []
        if existing:
            row_id = existing[0]["_id"]
            base.update_row(self.table_name, row_id, record)
            return {"action": "update", "row_id": row_id}
        new_row = base.append_row(self.table_name, record)
        return {"action": "insert", "row": new_row}
