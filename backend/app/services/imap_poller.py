import asyncio
import imaplib
import email
from email.header import decode_header, make_header
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.auth.auth import decrypt_password
from app.db.database import SessionLocal
from app.models import EmailAccount, Platform, VerificationCode
from app.services.code_extractor import guess_platform, extract_code_from_body


class IMAPPoller:
    """Poller único exportado como `poller_instance`. Cualquier router que
    necesite hacer poll usa este mismo singleton para que las notificaciones
    WebSocket funcionen correctamente."""

    def __init__(self):
        self.running = False
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self.callbacks: list = []

    def on_new_code(self, callback_factory):
        self.callbacks.append(callback_factory)

    async def notify_new_code(self, code: VerificationCode, db: Session):
        for factory in self.callbacks:
            try:
                coro_or_value = factory(code, db)
                if asyncio.iscoroutine(coro_or_value):
                    await coro_or_value
            except Exception as e:
                print(f"Error en callback: {e}")

    def set_main_loop(self, loop: asyncio.AbstractEventLoop):
        self._main_loop = loop

    def _notify_new_code(self, code: VerificationCode, db: Session):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.notify_new_code(code, db))
            return
        except RuntimeError:
            pass

        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.notify_new_code(code, db), self._main_loop
            )
        else:
            print("⚠️ Event loop principal no disponible; omitiendo WS broadcast")

    # ---------------------------------------------------------------- IMAP (async via threads)
    async def connect_account(self, account: EmailAccount) -> Optional[imaplib.IMAP4_SSL]:
        def _connect():
            try:
                if account.email_type.value == "gmail":
                    host = account.imap_host or "imap.gmail.com"
                elif account.email_type.value == "outlook":
                    host = account.imap_host or "outlook.office365.com"
                elif account.email_type.value == "yahoo":
                    host = account.imap_host or "imap.mail.yahoo.com"
                else:
                    host = account.imap_host or "imap.gmail.com"

                port = account.imap_port or 993
                username = account.username or account.email
                password = decrypt_password(account.password_encrypted)

                mail = imaplib.IMAP4_SSL(host, port)
                mail.login(username, password)
                mail.select("INBOX")
                return mail
            except Exception as e:
                print(f"Error conectando a {account.email}: {e}")
                return None

        return await asyncio.to_thread(_connect)

    async def fetch_unread(self, mail: imaplib.IMAP4_SSL) -> list[dict]:
        def _fetch():
            messages = []
            try:
                status, ids = mail.search(None, "UNSEEN")
                if status != "OK":
                    return messages

                email_ids = ids[0].split()
                for eid in email_ids[-20:]:
                    status, data = mail.fetch(eid, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    subject = self._decode_header_str(msg["Subject"])
                    sender = msg["From"] or ""
                    body = self._get_email_body(msg)

                    messages.append({
                        "sender": sender,
                        "subject": subject,
                        "body": body,
                        "date": msg["Date"] or datetime.utcnow().isoformat(),
                        "uid": eid,
                    })

                    mail.store(eid, "+FLAGS", "\\Seen")

            except Exception as e:
                print(f"Error fetching emails: {e}")

            return messages

        return await asyncio.to_thread(_fetch)

    @staticmethod
    def _decode_header_str(header_value: Optional[str]) -> str:
        if not header_value:
            return ""
        try:
            return str(make_header(decode_header(header_value)))
        except Exception:
            return header_value

    def _get_email_body(self, msg) -> str:
        plain_parts: list[str] = []
        html_parts: list[str] = []
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                try:
                    payload = part.get_payload(decode=True) or b""
                    decoded = payload.decode("utf-8", errors="replace")
                except Exception:
                    continue
                if ctype == "text/plain":
                    plain_parts.append(decoded)
                elif ctype == "text/html":
                    html_parts.append(decoded)
        else:
            try:
                payload = msg.get_payload(decode=True) or b""
                content = payload.decode("utf-8", errors="replace")
                if msg.get_content_type() == "text/html":
                    html_parts.append(content)
                else:
                    plain_parts.append(content)
            except Exception:
                pass

        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            import re
            text = re.sub(r"<[^>]+>", " ", "\n".join(html_parts))
            return re.sub(r"\s+", " ", text)
        return ""

    # ---------------------------------------------------------------- Poll
    async def process_account(self, account_id: int, db: Session):
        def _load_account():
            return db.query(EmailAccount).filter(EmailAccount.id == account_id).first()

        account = await asyncio.to_thread(_load_account)
        if not account or not account.is_active:
            return

        mail = await self.connect_account(account)
        if not mail:
            return

        messages = await self.fetch_unread(mail)
        try:
            await asyncio.to_thread(mail.logout)
        except Exception:
            pass

        def _load_platforms():
            return db.query(Platform).all()

        platforms = await asyncio.to_thread(_load_platforms)

        for msg_data in messages:
            platform = account.platform
            if platform is None:
                platform = guess_platform(msg_data["sender"], msg_data["subject"], platforms)

            code_value = extract_code_from_body(msg_data["body"], platform)
            if not code_value:
                continue

            def _check_existing():
                return db.query(VerificationCode).filter(
                    VerificationCode.email_account_id == account_id,
                    VerificationCode.code == code_value,
                    VerificationCode.subject == msg_data["subject"],
                ).first()

            existing = await asyncio.to_thread(_check_existing)

            if not existing:
                new_code = VerificationCode(
                    email_account_id=account_id,
                    platform_id=platform.id if platform else None,
                    sender=msg_data["sender"][:255] if msg_data["sender"] else None,
                    subject=msg_data["subject"][:500] if msg_data["subject"] else None,
                    code=code_value,
                    raw_body=msg_data["body"][:5000],
                    received_at=msg_data.get("date") and _parse_date(msg_data["date"]) or datetime.utcnow(),
                )
                db.add(new_code)

                def _commit():
                    db.commit()
                    db.refresh(new_code)
                    _ = new_code.email_account
                    _ = new_code.platform

                await asyncio.to_thread(_commit)
                self._notify_new_code(new_code, db)

        def _update_checked():
            account.last_checked = datetime.utcnow()
            db.commit()

        await asyncio.to_thread(_update_checked)

    async def run_once(self):
        db = SessionLocal()
        try:
            def _load_active():
                return db.query(EmailAccount).filter(EmailAccount.is_active == True).all()

            accounts = await asyncio.to_thread(_load_active)
            for account in accounts:
                try:
                    await self.process_account(account.id, db)
                except Exception as e:
                    print(f"Error procesando {account.email}: {e}")
        finally:
            db.close()

    async def start(self, interval: int = 30):
        self.running = True
        self._main_loop = asyncio.get_running_loop()
        while self.running:
            await self.run_once()
            await asyncio.sleep(interval)

    def stop(self):
        self.running = False


def _parse_date(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(value)
    except Exception:
        return None


poller_instance = IMAPPoller()