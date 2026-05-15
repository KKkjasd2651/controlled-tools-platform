from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    file_server_root: str = "./fileserver"
    dml_template: str = "./templates/DML_template.xlsx"
    dml_filename: str = "文件清单.xlsx"
    # 空串 = 文件平铺在 <工令号>/ 根下（按 SBPC 现场约定）；非空则放到子目录
    controlled_dir: str = ""
    # 启动期对文件服务器做可写性自检；失败拒绝起服务
    require_writable_fs: bool = True

    # 严格 TDML 模式: <code>_V<version> <title>.<ext>
    #   <code> = <project>-<专业代码>-<图档类型>-<序号>
    filename_regex: str = (
        r"^(?P<code>(?P<project>[A-Za-z0-9]+)-[A-Za-z]{2}-[A-Za-z]{2}-[A-Za-z0-9]+)"
        r"_V(?P<version>\d+(?:\.\d+)*)\s+(?P<title>.+)"
        r"\.(?P<ext>pdf|PDF|docx|DOCX|xlsx|XLSX|dwg|DWG)$"
    )

    pdf_owner_password: str = "changeit-owner"
    pdf_user_password: str = ""
    # 印章大字 —— 显示在 CONTROLLED 那一行
    watermark_text: str = "CONTROLLED"

    # === Seatable / SMTP - 暂未启用，保留字段以便日后接入 ===
    seatable_server_url: str = "https://cloud.seatable.io"
    seatable_api_token: str = ""
    seatable_table_name: str = "钣金件清单"

    smtp_host: str = "smtp.example.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = True
    mail_from: str = "noreply@example.com"
    mail_to: str = "team@example.com"

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    public_base_url: str = "http://localhost:8000"

    @property
    def backend_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def fs_root(self) -> Path:
        p = Path(self.file_server_root)
        if not p.is_absolute():
            p = (self.backend_root / p)
        # 不对 UNC 路径调用 .resolve() ——
        # Windows 上 resolve() 会触发 GetFinalPathNameByHandleW，
        # 进而打开 SMB 句柄；如果当前进程没有该共享的会话，
        # 会立即抛 WinError 64 / 67，让整个服务起不来。
        # 普通本地路径才走 resolve() 做规范化。
        if str(p).startswith("\\\\"):
            return p
        try:
            return p.resolve()
        except OSError:
            return p

    @property
    def template_path(self) -> Path:
        p = Path(self.dml_template)
        if not p.is_absolute():
            p = self.backend_root / p
        try:
            return p.resolve()
        except OSError:
            return p

    def project_dir(self, project_no: str) -> Path:
        return self.fs_root / project_no

    def dml_path(self, project_no: str) -> Path:
        return self.project_dir(project_no) / self.dml_filename

    def controlled_dir_for(self, project_no: str) -> Path:
        if self.controlled_dir:
            return self.project_dir(project_no) / self.controlled_dir
        return self.project_dir(project_no)


settings = Settings()
