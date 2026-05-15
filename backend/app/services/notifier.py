from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import List, Optional

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sender: str,
        recipients: List[str],
        use_ssl: bool = True,
        mock: bool = False,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender
        self.recipients = recipients
        self.use_ssl = use_ssl
        self.mock = mock or not host or host.startswith("smtp.example")

    def send_upload_notice(
        self,
        subject: str,
        body: str,
        attachments: Optional[List[tuple]] = None,
    ) -> dict:
        if self.mock:
            logger.info(
                "[MOCK Email] to=%s subject=%s\n%s",
                self.recipients,
                subject,
                body,
            )
            return {"mock": True, "to": self.recipients, "subject": subject}

        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg["Subject"] = subject
        msg.set_content(body)
        for name, data, mime in attachments or []:
            maintype, _, subtype = mime.partition("/")
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)

        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=20) as s:
                s.login(self.user, self.password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=20) as s:
                s.starttls()
                s.login(self.user, self.password)
                s.send_message(msg)
        return {"ok": True, "to": self.recipients}
