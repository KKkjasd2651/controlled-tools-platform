from typing import Optional
from pydantic import BaseModel


class UploadResponse(BaseModel):
    ok: bool
    message: str
    filename: Optional[str] = None
    url: Optional[str] = None
    duplicate: bool = False
    meta: Optional[dict] = None


class ValidateResponse(BaseModel):
    ok: bool
    message: str
    meta: Optional[dict] = None
