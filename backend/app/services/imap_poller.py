import asyncio
import email
import imaplib
import re
from datetime import datetime, timezone
from email.header import decode_header, make_header
from typing import Optional

import aioimaplib
from sqlalchemy.orm import Session

from app.auth.auth import decrypt_password
from app.config import settings
from app.db.database import SessionLocal
from app.models import EmailAccount, Platform, VerificationCode
from app.services.code_extractor import guess_platform, extract_code_from_body


class IMAPPoller:
    def __init__(self):
        self.running = False
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self.callbacks: list = []
        self._tasks: dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()

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

    @staticmethod
    def _default_host(email_type: str) -> str:
        hosts = {
            "gmail": "imap.gmail.com",
            "outlook": "outlook.office365.com",
            "yahoo": "imap.mail.yahoo.com",
        }
        return hosts.get(email_type, "imap.gmail.com")

    # ---------------------------------------------------------------
    # Sync IMAP (manual poll / test connection)
    # ---------------------------------------------------------------
    async def connect_account(self, account: EmailAccount) -> Optional[imaplib.IMAP4_SSL]:
        def _connect():
            try:
                host = account.imap_host or self._default_host(account.email_type.value)
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

    async def fetch_unread(self, mail) -> list[dict]:
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
                        "date": msg["Date"] or datetime.now(timezone.utc).isoformat(),
                        "uid": eid,
                    })

                    mail.store(eid, "+FLAGS", "\\Seen")

            except Exception as e:
                print(f"Error fetching emails: {e}")

            return messages

        return await asyncio.to_thread(_fetch)

    # ---------------------------------------------------------------
    # aioimaplib IDLE operations
    # ---------------------------------------------------------------
    async def _connect_idle(self, account: EmailAccount) -> Optional[aioimaplib.IMAP4_SSL]:
        try:
            host = account.imap_host or self._default_host(account.email_type.value)
            port = account.imap_port or 993
            username = account.username or account.email
            password = decrypt_password(account.password_encrypted)

            client = aioimaplib.IMAP4_SSL(host, port, timeout=30)
            await client.wait_hello_from_server()
            await client.login(username, password)
            return client
        except Exception as e:
            print(f"  ⚠️ Error conectando {account.email} (IDLE): {e}")
            return None

    async def _fetch_unread_idle(self, client: aioimaplib.IMAP4_SSL) -> list[dict]:
        messages = []
        try:
            response = await client.search("UNSEEN")
            if response.result != "OK":
                return messages

            ids_bytes = response.lines[0] if response.lines else b""
            email_ids = ids_bytes.decode().split()

            for eid in email_ids[-20:]:
                fetch_resp = await client.fetch(eid, "(RFC822)")
                if fetch_resp.result != "OK":
                    continue

                raw_email = fetch_resp.lines[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = self._decode_header_str(msg["Subject"])
                sender = msg["From"] or ""
                body = self._get_email_body(msg)

                messages.append({
                    "sender": sender,
                    "subject": subject,
                    "body": body,
                    "date": msg["Date"] or datetime.now(timezone.utc).isoformat(),
                    "uid": eid,
                })

                await client.store(eid, "+FLAGS", "\\Seen")

        except Exception as e:
            print(f"  ⚠️ Error fetching (IDLE): {e}")

        return messages

    # ---------------------------------------------------------------
    # Shared processing logic
    # ---------------------------------------------------------------
    def _process_messages(self, messages: list[dict], account_id: int,
                          platforms: list[Platform], account: EmailAccount,
                          db: Session) -> list[VerificationCode]:
        saved_codes = []
        for msg_data in messages:
            platform = account.platform
            if platform is None:
                platform = guess_platform(msg_data["sender"], msg_data["subject"], platforms)

            code_value = extract_code_from_body(msg_data["body"], platform)
            if not code_value:
                continue

            existing = db.query(VerificationCode).filter(
                VerificationCode.email_account_id == account_id,
                VerificationCode.code == code_value,
                VerificationCode.subject == msg_data["subject"],
            ).first()

            if not existing:
                new_code = VerificationCode(
                    email_account_id=account_id,
                    platform_id=platform.id if platform else None,
                    sender=msg_data["sender"][:255] if msg_data["sender"] else None,
                    subject=msg_data["subject"][:500] if msg_data["subject"] else None,
                    code=code_value,
                    raw_body=msg_data["body"][:5000],
                    received_at=_parse_date(msg_data.get("date")) or datetime.utcnow(),
                )
                db.add(new_code)
                saved_codes.append(new_code)

        if saved_codes:
            db.commit()
            for nc in saved_codes:
                db.refresh(nc)
                _ = nc.email_account
                _ = nc.platform
                self._notify_new_code(nc, db)

        return saved_codes

    # ---------------------------------------------------------------
    # One-shot poll (manual / fallback)
    # ---------------------------------------------------------------
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
        self._process_messages(messages, account_id, platforms, account, db)

        def _update_checked():
            account.last_checked = datetime.utcnow()
            db.commit()

        await asyncio.to_thread(_update_checked)

    # ---------------------------------------------------------------
    # IDLE watcher por cuenta
    # ---------------------------------------------------------------
    async def _watch_account(self, account_id: int):
        while self.running:
            db = SessionLocal()
            client = None
            try:
                account = db.query(EmailAccount).filter(
                    EmailAccount.id == account_id,
                    EmailAccount.is_active == True,
                ).first()
                if not account:
                    return

                platforms = db.query(Platform).all()

                client = await self._connect_idle(account)
                if not client:
                    await asyncio.sleep(30)
                    continue

                await client.select("INBOX")
                print(f"  ✅ IDLE activo: {account.email}")

                while self.running:
                    idle_task = await client.idle_start(
                        timeout=settings.imap_idle_timeout
                    )
                    try:
                        push = await asyncio.wait_for(
                            client.wait_server_push(),
                            timeout=settings.imap_idle_timeout,
                        )
                        if self.running:
                            client.idle_done()
                            await asyncio.wait_for(idle_task, timeout=5)
                            messages = await self._fetch_unread_idle(client)
                            if messages:
                                self._process_messages(
                                    messages, account_id, platforms, account, db
                                )
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        try:
                            client.idle_done()
                            await asyncio.wait_for(idle_task, timeout=5)
                        except Exception:
                            pass
                        if self.running:
                            messages = await self._fetch_unread_idle(client)
                            if messages:
                                self._process_messages(
                                    messages, account_id, platforms, account, db
                                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"  ⚠️ Error IDLE ({account_id}): {e}")
                await asyncio.sleep(10)
            finally:
                if client:
                    try:
                        await client.logout()
                    except Exception:
                        pass
                db.close()

    # ---------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------
    async def start(self):
        self.running = True
        self._main_loop = asyncio.get_running_loop()
        await self._reload_accounts()

    async def _reload_accounts(self):
        async with self._lock:
            for task in self._tasks.values():
                task.cancel()
            self._tasks.clear()

            db = SessionLocal()
            try:
                accounts = db.query(EmailAccount).filter(
                    EmailAccount.is_active == True
                ).all()
                for account in accounts:
                    task = asyncio.create_task(self._watch_account(account.id))
                    self._tasks[account.id] = task
                    await asyncio.sleep(0.1)
                n = len(accounts)
                print(f"  📡 IDLE vigilando {n} cuenta{'s' if n != 1 else ''}")
            finally:
                db.close()

    async def reload_accounts(self):
        if self.running:
            await self._reload_accounts()

    def stop(self):
        self.running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    # ---------------------------------------------------------------
    # Email parsing helpers
    # ---------------------------------------------------------------
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
            text = re.sub(r"<[^>]+>", " ", "\n".join(html_parts))
            return re.sub(r"\s+", " ", text)
        return ""


def _parse_date(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(value)
    except Exception:
        return None


poller_instance = IMAPPoller()
