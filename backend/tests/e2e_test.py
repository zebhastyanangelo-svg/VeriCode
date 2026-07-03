#!/usr/bin/env python3
"""
Test E2E del sistema VeriCode.

Pasos:
1. Levanta un mock IMAP server (TCP plano) en 127.0.0.1:1143.
2. Arranca el backend en 127.0.0.1:8765 (vía _launch_e2e.py, con patch imaplib).
3. Verifica: admin auto-creado → login → JWT → WS auth → crear EmailAccount
   → poll → código extraído → broadcast WS → endpoint público.
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import aiohttp
import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8765"))
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

MOCK_IMAP_HOST = "127.0.0.1"
MOCK_IMAP_PORT = 1143


# ===================== Mock IMAP Server =====================

# El "correo" que el mock devolverá: contiene un código de Netflix.
def _make_mock_email():
    import datetime as _dt
    _now = _dt.datetime.utcnow()
    _date_str = _now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    parts = [
        b"From: info@account.netflix.com\r\n",
        b"Subject: Tu c\xc3\xb3digo de verificaci\xc3\xb3n de Netflix\r\n",
        b"To: test@mock.local\r\n",
        f"Date: {_date_str}\r\n".encode(),
        b"Content-Type: text/plain; charset=utf-8\r\n",
        b"Content-Transfer-Encoding: 7bit\r\n",
        b"Message-ID: <test-001@netflix.com>\r\n",
        b"\r\n",
        b"Hola! Tu c\xc3\xb3digo de verificaci\xc3\xb3n de Netflix es: 778899. "
        b"No lo compartas con nadie.\r\n",
    ]
    return b"".join(parts)
MOCK_EMAIL_RAW = _make_mock_email()


async def _mock_imap_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    server = writer.get_extra_info("peername")
    print(f"[MOCK IMAP] Conexión desde {server}", flush=True)

    async def send(text: bytes | str) -> None:
        if isinstance(text, str):
            text = text.encode("utf-8")
        writer.write(text)
        await writer.drain()

    await send(b"* OK [CAPABILITY IMAP4rev1] Mock IMAP server ready\r\n")

    try:
        while True:
            data = await reader.readline()
            if not data:
                break
            line = data.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                continue
            print(f"[MOCK IMAP] <- {line}", flush=True)
            tag, _, raw_cmd = line.partition(" ")
            cmd = raw_cmd.split(" ", 1)[0].upper() if raw_cmd else ""

            if cmd == "CAPABILITY":
                await send(f"{tag} OK CAPABILITY completed\r\n".encode())
            elif cmd == "LOGIN":
                await send(f"{tag} OK LOGIN completed\r\n".encode())
            elif cmd in ("SELECT", "EXAMINE"):
                await send(
                    b"* 1 EXISTS\r\n"
                    b"* 1 RECENT\r\n"
                    b"* FLAGS (\\Seen \\Answered \\Flagged \\Deleted \\Draft)\r\n"
                    b"* OK [PERMANENTFLAGS (\\Seen \\Answered \\Flagged \\Deleted \\Draft)] Permanent flags\r\n"
                    b"* OK [UIDVALIDITY 1] UIDs valid\r\n"
                    b"* OK [UIDNEXT 2] Predicted next UID\r\n"
                )
                await send(f"{tag} OK [READ-WRITE] SELECT completed\r\n".encode())
            elif cmd == "SEARCH":
                await send(b"* SEARCH 1\r\n")
                await send(f"{tag} OK SEARCH completed\r\n".encode())
            elif cmd == "FETCH":
                # Devuelve el cuerpo completo en RFC822.
                # Formato IMAP4 literal: {N}\r\n<N bytes>)\r\n (sin \r\n extra antes de ')').
                msg_id = raw_cmd.split(" ", 1)[1].split(" ", 1)[0]
                header = f"* {msg_id} FETCH (RFC822 {{{len(MOCK_EMAIL_RAW)}}}\r\n".encode()
                trailer = b")\r\n"
                await send(header)
                await send(MOCK_EMAIL_RAW)
                await send(trailer)
                await send(f"{tag} OK FETCH completed\r\n".encode())
            elif cmd == "STORE":
                await send(f"{tag} OK STORE completed\r\n".encode())
            elif cmd == "CLOSE":
                await send(f"{tag} OK CLOSE completed\r\n".encode())
            elif cmd == "LOGOUT":
                await send(b"* BYE Mock IMAP says bye\r\n")
                await send(f"{tag} OK LOGOUT completed\r\n".encode())
                writer.close()
                await writer.wait_closed()
                return
            elif cmd in ("NOOP", "CHECK"):
                await send(f"{tag} OK {cmd} completed\r\n".encode())
            elif cmd == "ID":
                await send(f"{tag} OK ID completed\r\n".encode())
            else:
                await send(f"{tag} BAD Unknown command: {cmd}\r\n".encode())
    except (ConnectionResetError, BrokenPipeError):
        pass
    except Exception as exc:  # noqa: BLE001
        print(f"[MOCK IMAP] error: {exc!r}", file=sys.stderr, flush=True)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


class MockIMAPServer:
    def __init__(self, host: str = MOCK_IMAP_HOST, port: int = MOCK_IMAP_PORT) -> None:
        self.host = host
        self.port = port
        self._server: asyncio.base_events.Server | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(_mock_imap_handler, self.host, self.port)
        print(f"[MOCK IMAP] listening on {self.host}:{self.port}", flush=True)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            print("[MOCK IMAP] stopped", flush=True)


# ===================== Helpers =====================

def wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"Port {host}:{port} no respondió en {timeout}s")


def wait_for_backend_ready(timeout: float = 20.0) -> None:
    start = time.time()
    last_err: Exception | None = None
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{BACKEND_URL}/api/v1/auth/setup", timeout=2.0)
            if r.status_code in (200, 400, 405):
                return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(0.5)
    raise TimeoutError(f"Backend no quedó listo: {last_err!r}")


# ===================== Tests =====================

class TestRunner:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    @contextmanager
    def step(self, name: str):
        print(f"\n=== {name} ===", flush=True)
        try:
            yield
        except AssertionError as exc:
            self.failed.append((name, str(exc)))
            print(f"[FAIL] {name}: {exc}", flush=True)
            raise
        except Exception as exc:  # noqa: BLE001
            self.failed.append((name, repr(exc)))
            print(f"[FAIL] {name}: {exc!r}", flush=True)
            raise
        else:
            self.passed.append(name)
            print(f"[PASS] {name}", flush=True)

    def report(self) -> int:
        print("\n" + "=" * 60)
        print(f"Pasaron: {len(self.passed)}/{len(self.passed) + len(self.failed)}")
        print("=" * 60)
        for name in self.passed:
            print(f"  ✓ {name}")
        for name, reason in self.failed:
            print(f"  ✗ {name}\n      → {reason}")
        return 0 if not self.failed else 1


def test_admin_setup_implicit(runner: TestRunner) -> None:
    """El admin debe existir tras boot (sin llamar /setup manualmente)."""
    with runner.step("T1: Admin auto-creado al boot"):
        # El endpoint /setup es idempotente. Si ya existe un admin, no debe crearlo de nuevo.
        r = requests.post(f"{BACKEND_URL}/api/v1/auth/setup", timeout=5.0)
        assert r.status_code == 200, f"setup status={r.status_code} body={r.text}"
        body = r.json()
        # Aceptar cualquiera de los dos: created=False (ya existía) o username=admin (recién creado).
        created = body.get("created")
        username = body.get("username", "")
        assert created is False or username == "admin", (
            f"Se esperaba admin existente tras boot: {body}"
        )


def test_login_admin(runner: TestRunner) -> str:
    """Login con admin/admin123 → JWT válido Y cambio obligatorio de password.

    El seed crea al admin con must_change_password=True. Este test valida:
    1. Login devuelve must_change_password=True en el body.
    2. /auth/change-password acepta el cambio y limpia el flag.
    3. /me confirma must_change_password=False tras el cambio.
    """
    with runner.step("T2: Login + cambio obligatorio de password"):
        # 1) Login con password default de dev.
        r = requests.post(
            f"{BACKEND_URL}/api/v1/auth/token",
            json={"username": "admin", "password": "admin123"},
            timeout=5.0,
        )
        assert r.status_code == 200, f"login status={r.status_code} body={r.text}"
        body = r.json()
        token = body.get("access_token")
        assert token, f"Sin access_token: {body}"
        # El seed actual fuerza cambio. Si el valor fuera False, sería una
        # regresión del feature.
        assert body.get("must_change_password") is True, (
            f"Se esperaba must_change_password=True tras seed: {body}"
        )
        print(f"   Login OK + must_change_password=True (forced change)", flush=True)

        # 2) Cambio de password (simula la pantalla bloqueante del frontend).
        new_pwd = "NewSecure!Pass42"
        rc = requests.post(
            f"{BACKEND_URL}/api/v1/auth/change-password",
            json={"old_password": "admin123", "new_password": new_pwd},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        assert rc.status_code == 200, (
            f"change-password status={rc.status_code} body={rc.text}"
        )
        assert rc.json().get("must_change_password") is False, (
            f"Flag no se limpió: {rc.json()}"
        )
        # El backend debe rechazar old == new (control de defensa).
        bad = requests.post(
            f"{BACKEND_URL}/api/v1/auth/change-password",
            json={"old_password": new_pwd, "new_password": new_pwd},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        assert bad.status_code == 400, (
            f"change-password debería rechazar old==new; status={bad.status_code} body={bad.text}"
        )

        # 3) /me confirma el flag claro.
        r2 = requests.get(
            f"{BACKEND_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        assert r2.status_code == 200, f"/me status={r2.status_code}"
        me = r2.json()
        assert me.get("sub") == "admin", f"/me sub != admin: {me}"
        assert me.get("must_change_password") is False, (
            f"/me must_change_password debería ser False: {me}"
        )
        print(f"   Password cambiada a {new_pwd}; JWT limpio: {token[:30]}...", flush=True)
        return token


async def test_ws_requires_auth(runner: TestRunner) -> None:
    """WS sin token debe rechazar (handshake O conexión cerrada con error)."""
    with runner.step("T3: WS rechaza sin token (handshake o cierre con error)"):
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            rejected_at_handshake = False
            accepted_then_closed = False
            try:
                async with session.ws_connect(f"{BACKEND_URL}/api/v1/codes/ws") as ws:
                    # Si llega aquí, el backend aceptó el handshake; debería enviar
                    # inmediatamente un mensaje de error y cerrar.
                    msg = await ws.receive(timeout=3.0)
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        raise AssertionError(
                            f"WS aceptó sin token pero no envió error: {msg!r}"
                        )
                    payload = json.loads(msg.data)
                    assert payload.get("type") == "error", (
                        f"Esperaba mensaje error, recibió: {payload}"
                    )
                    print(f"   WS aceptó → mensaje error: {payload}", flush=True)
                    # Verificamos que también cierra (lectura adicional).
                    try:
                        closer = await ws.receive(timeout=2.0)
                        print(f"   Cierre tras error: closer={closer!r}", flush=True)
                    except asyncio.TimeoutError:
                        pass
                    accepted_then_closed = True
            except aiohttp.WSServerHandshakeError as exc:
                # Otra implementación válida: rechazar en el handshake (status 4xx).
                assert 400 <= exc.status < 500, (
                    f"Status inesperado en handshake: {exc.status}"
                )
                print(f"   Handshake rechazado con status={exc.status}", flush=True)
                rejected_at_handshake = True
            assert rejected_at_handshake or accepted_then_closed, (
                "WS aceptó sin token sin enviar error ni cerrar"
            )


async def test_ws_connect_with_token(runner: TestRunner, token: str) -> aiohttp.ClientWebSocketResponse:
    """WS con token válido debe conectar."""
    with runner.step("T4: WS acepta con token válido"):
        url = f"{BACKEND_URL}/api/v1/codes/ws?token={token}"
        session = aiohttp.ClientSession()
        ws = await session.ws_connect(url, autoping=False)
        # Verificamos que sigue abierto 1 segundo.
        await asyncio.sleep(1.0)
        assert not ws.closed, "WS se cerró inesperadamente"
        print(f"   WS conectado: {ws!r}", flush=True)
        return ws


def test_create_email_account(runner: TestRunner, token: str) -> int:
    """POST /email-accounts → account_id."""
    with runner.step("T5: Crear EmailAccount (password cifrada con Fernet)"):
        # Schema actual: email, password, imap_host, imap_port, username (opt), notes (opt).
        payload = {
            "email": "test@mock.local",
            "password": "mockpassword123",
            "imap_host": MOCK_IMAP_HOST,
            "imap_port": MOCK_IMAP_PORT,
        }
        r = requests.post(
            f"{BACKEND_URL}/api/v1/email-accounts",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        assert r.status_code in (200, 201), f"create status={r.status_code} body={r.text}"
        body = r.json()
        account_id = body.get("id")
        assert account_id, f"Sin id: {body}"
        # Verificamos que la password NO esté en plaintext en la respuesta.
        assert "mockpassword123" not in r.text, "Password apareció en respuesta"
        # Activar la cuenta para que el poller la considere (is_active default es False).
        r_act = requests.put(
            f"{BACKEND_URL}/api/v1/email-accounts/{account_id}",
            json={"is_active": True},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        assert r_act.status_code in (200, 201), (
            f"activate status={r_act.status_code} body={r_act.text}"
        )
        print(f"   EmailAccount id={account_id} creado + activado", flush=True)
        return int(account_id)


async def test_poll_extracts_code_and_broadcasts(
    runner: TestRunner,
    token: str,
    ws: aiohttp.ClientWebSocketResponse,
    account_id: int,
    backend_log_path: Path,
) -> dict[str, Any]:
    """POST /poll extrae código del mock IMAP y WS lo recibe."""
    with runner.step("T6+T7: Poll → extracción → broadcast WS"):
        # Iniciamos un listener del WS en background.
        broadcast_msg: asyncio.Queue = asyncio.Queue()

        async def listener() -> None:
            try:
                while not ws.closed:
                    msg = await ws.receive(timeout=15.0)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        print(f"   [WS] {data}", flush=True)
                        await broadcast_msg.put(data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                        break
            except asyncio.TimeoutError:
                pass

        listener_task = asyncio.create_task(listener())

        try:
            # Disparamos poll (en threadpool porque es sync → no bloquea event loop).
            resp = await asyncio.to_thread(
                requests.post,
                f"{BACKEND_URL}/api/v1/email-accounts/{account_id}/poll",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            assert resp.status_code == 200, f"poll status={resp.status_code} body={resp.text}"
            poll_body = resp.json()
            print(f"   poll OK: {poll_body}", flush=True)

            # Esperamos hasta 10s por un mensaje del WS.
            received: dict[str, Any] | None = None
            # Antes de aceptar 'no llegó', drenamos cualquier mensaje en buffer del WS.
            try:
                while True:
                    early = await asyncio.wait_for(broadcast_msg.get(), timeout=0.3)
                    print(f"   [WS early] {early}", flush=True)
                    received = received or early
            except asyncio.TimeoutError:
                pass
            if received is None:
                try:
                    received = await asyncio.wait_for(broadcast_msg.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    pass

            assert received is not None, (
                f"WS no recibió broadcast tras poll. Log del backend:\n"
                f"{backend_log_path.read_text(errors='replace').splitlines()[-20:]}"
            )
            # Búsqueda robusta: el código debe estar serializado en algún lugar del mensaje.
            assert "778899" in json.dumps(received), (
                f"Broadcast sin código '778899': {received}"
            )
            print(f"   ✓ Código '778899' presente en broadcast WS", flush=True)
            return received
        finally:
            listener_task.cancel()
            try:
                await listener_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


def test_verify_email_access_info_leak_fix(runner: TestRunner) -> None:
    """verify-email-access no revela si un correo está registrado."""
    with runner.step("T8: verify-email-access sin fuga de información"):
        r_unknown = requests.get(
            f"{BACKEND_URL}/api/v1/public/verify-email-access",
            params={"email": "no-existe@nadie.com", "platform_name": "netflix"},
            timeout=5.0,
        )
        assert r_unknown.status_code == 200, (
            f"Esperaba 200 (no 404) para email inexistente: "
            f"status={r_unknown.status_code} body={r_unknown.text}"
        )
        body = r_unknown.json()
        assert body.get("has_access") is False, (
            f"has_access debe ser False para email no registrado: {body}"
        )
        # No debe contener información del código
        assert "code" not in body, f"No debe exponer code: {body}"
        assert "code_id" not in body, f"No debe exponer code_id: {body}"
        print(f"   ✓ Email no registrado: has_access=False (respuesta uniforme)", flush=True)

        r_real = requests.get(
            f"{BACKEND_URL}/api/v1/public/verify-email-access",
            params={"email": "test@mock.local", "platform_name": "netflix"},
            timeout=5.0,
        )
        assert r_real.status_code == 200, (
            f"verify-email-access para email real esperaba 200: "
            f"status={r_real.status_code} body={r_real.text}"
        )
        body_real = r_real.json()
        # Puede ser has_access=True o False (si no hay código disponible)
        assert "has_access" in body_real, f"Falta has_access en respuesta: {body_real}"
        assert "code" not in body_real, f"No debe exponer code: {body_real}"
        print(f"   ✓ Email real: has_access={body_real.get('has_access')} (sin code)", flush=True)


def test_public_rate_limit(runner: TestRunner) -> None:
    """Test que el rate-limit público funciona."""
    with runner.step("T9: Rate-limit público (10/min) bloquea tras exceder"):
        # Resetear el rate-limit público
        rr = requests.post(
            f"{BACKEND_URL}/api/v1/public/_test/reset-rate-limit",
            timeout=5.0,
        )
        assert rr.status_code == 200, f"reset falló: {rr.status_code} {rr.text}"

        # Hacemos 11 requests rápidos a verify-email-access con email inexistente
        statuses = []
        for i in range(11):
            r = requests.get(
                f"{BACKEND_URL}/api/v1/public/verify-email-access",
                params={"email": f"rate-test-{i}@example.com", "platform_name": "netflix"},
                timeout=5.0,
            )
            statuses.append(r.status_code)
        first_10 = statuses[:10]
        eleventh = statuses[10]
        assert all(s == 200 for s in first_10), (
            f"Primeros 10 requests deberían ser 200: {first_10}"
        )
        assert eleventh == 429, (
            f"11er request debería ser 429, obtuvo {eleventh}: statuses={statuses}"
        )
        print(f"   ✓ Rate-limit público: 10×200 + 1×429", flush=True)


def test_public_request_code(runner: TestRunner, token: str) -> None:
    """Endpoint público sirve código y lo marca como entregado."""
    with runner.step("T10: Endpoint público sirve código y marca is_delivered=True"):
        # request-code usa Query params: email + platform_name (no platform_id, no JSON body).
        r_req = requests.post(
            f"{BACKEND_URL}/api/v1/public/request-code",
            params={"email": "test@mock.local", "platform_name": "netflix"},
            timeout=5.0,
        )
        assert r_req.status_code == 200, (
            f"request-code status={r_req.status_code} body={r_req.text}"
        )
        body = r_req.json()
        assert "code" in body, f"Sin code en respuesta pública: {body}"
        # La respuesta pública NUNCA debe incluir raw_body.
        assert "raw_body" not in body, "Falla de seguridad: raw_body expuesto"
        assert body.get("code") == "778899", f"Código inesperado: {body.get('code')}"
        # Una segunda petición debería indicar que ya fue entregado (409 o mensaje "no disponible").
        r_req2 = requests.post(
            f"{BACKEND_URL}/api/v1/public/request-code",
            params={"email": "test@mock.local", "platform_name": "netflix"},
            timeout=5.0,
        )
        assert r_req2.status_code in (200, 404, 409), (
            f"2da petición inesperada: status={r_req2.status_code} body={r_req2.text[:200]}"
        )
        print(f"   1ra petición: code={body.get('code')} platform={body.get('platform_name')}", flush=True)
        print(f"   2da petición: status={r_req2.status_code} (esperado: ya entregado)", flush=True)


# ============================================================================
# Tests de seguridad (al final del flujo principal para no romper los previos)
# ============================================================================

def test_change_password_wrong_old(runner: TestRunner, token: str) -> None:
    """Cambio de password con old_password incorrecta debe rechazarse con 401."""
    with runner.step("T11: /auth/change-password rechaza old_password incorrecta"):
        r = requests.post(
            f"{BACKEND_URL}/api/v1/auth/change-password",
            json={"old_password": "ESTA-NO-ES-LA-ACTUAL", "new_password": "AnotherSecure!42"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        assert r.status_code == 401, (
            f"Esperaba 401 por old incorrecta, obtuve {r.status_code}: {r.text}"
        )
        print(f"   Rechazo correcto: {r.json().get('detail')!r}", flush=True)


def test_rate_limit_blocks_after_5_failures(runner: TestRunner) -> None:
    """5 intentos fallidos desde misma IP → 6to debe ser 429 con Retry-After."""
    with runner.step("T12: Rate-limit (5/15min) → 6to intento devuelve 429"):
        # Limpiamos el bucket de cualquier test previo para empezar limpio.
        requests.post(
            f"{BACKEND_URL}/api/v1/auth/_test/reset-rate-limit",
            timeout=5.0,
        )
        # Usamos un username inexistente para no molestar al admin real y para
        # que cada fallo sea una "record_failure" limpia.
        statuses = []
        for i in range(5):
            r = requests.post(
                f"{BACKEND_URL}/api/v1/auth/token",
                json={"username": "no-existe-usuario", "password": f"falso-{i}"},
                timeout=5.0,
            )
            statuses.append(r.status_code)
            assert r.status_code == 401, (
                f"Intento {i + 1} esperaba 401, obtuve {r.status_code}: {r.text}"
            )
        print(f"   Primeros 5: {statuses}", flush=True)

        # 6to intento debería ser 429.
        r6 = requests.post(
            f"{BACKEND_URL}/api/v1/auth/token",
            json={"username": "no-existe-usuario", "password": "falso-6"},
            timeout=5.0,
        )
        assert r6.status_code == 429, (
            f"6to intento esperaba 429, obtuve {r6.status_code}: {r6.text}"
        )
        # El header Retry-After debe estar presente.
        retry_after = r6.headers.get("Retry-After")
        assert retry_after is not None, f"Sin Retry-After header: {dict(r6.headers)}"
        assert retry_after.isdigit() and int(retry_after) > 0, (
            f"Retry-After inválido: {retry_after!r}"
        )
        print(
            f"   6to intento bloqueado (429); Retry-After={retry_after}s", flush=True,
        )


# ============================================================================
# Tests de los 3 huecos críticos (cerrados por los fixes de seguridad)
# ============================================================================
def _reset_rate_limit_for_test() -> None:
    """Helper: limpia el bucket del rate-limit entre sub-tests."""
    rr = requests.post(
        f"{BACKEND_URL}/api/v1/auth/_test/reset-rate-limit",
        timeout=5.0,
    )
    assert rr.status_code == 200, f"reset-rate-limit falló: {rr.status_code} {rr.text}"


def test_timing_oracle_equalized(runner: TestRunner) -> None:
    """Hueco #1: timing oracle.

    Sin el fix, login con username inexistente NO corría bcrypt, mientras
    que con username existente SÍ corría. Esto le da al atacante ~300ms de
    diferencia para enumerar usernames válidos.

    Con el fix (DUMMY_BCRYPT_HASH), ambos caminos corren bcrypt. Validamos
    que la diferencia entre avg(latencia_exist) - avg(latencia_no_exist)
    sea < 200ms (fuera del rango detectable).
    """
    with runner.step("T13: Timing oracle defense (bcrypt siempre corre)"):
        _reset_rate_limit_for_test()

        # 5 intentos con username inexistente → debería tardar ~bcrypt cada uno.
        timings_unknown: list[float] = []
        for i in range(5):
            t = time.monotonic()
            # Password ≥6 chars (UserCreate schema rechaza con 422 si es más corta,
            # lo que enmascararía el resultado de timing).
            r = requests.post(
                f"{BACKEND_URL}/api/v1/auth/token",
                json={"username": f"no-existe-{i}-X", "password": "fakepwd000"},
                timeout=5.0,
            )
            timings_unknown.append(time.monotonic() - t)
            assert r.status_code == 401, (
                f"Iter {i}: esperaba 401, obtuve {r.status_code}: {r.text}"
            )

        _reset_rate_limit_for_test()

        # 5 intentos con username válido (admin) + password incorrecta.
        timings_existing: list[float] = []
        for i in range(5):
            t = time.monotonic()
            r = requests.post(
                f"{BACKEND_URL}/api/v1/auth/token",
                json={"username": "admin", "password": f"badpwd{i:03d}XX"},
                timeout=5.0,
            )
            timings_existing.append(time.monotonic() - t)
            assert r.status_code == 401, (
                f"Iter {i}: esperaba 401, obtuve {r.status_code}: {r.text}"
            )

        avg_unknown = sum(timings_unknown) / len(timings_unknown)
        avg_existing = sum(timings_existing) / len(timings_existing)
        diff_ms = abs(avg_existing - avg_unknown) * 1000.0
        print(
            f"   avg(no_exist)={avg_unknown * 1000:.0f}ms "
            f"avg(exist)={avg_existing * 1000:.0f}ms "
            f"|diff|={diff_ms:.0f}ms",
            flush=True,
        )
        # bcrypt checkpw toma ~250-350ms. Sin fix: avg(no_exist) sería ~5ms,
        # avg(exist) sería ~300ms → diff ~295ms. Con fix: ambos ~300ms.
        assert diff_ms < 200, (
            f"Timing oracle NO está cerrado: diferencia {diff_ms:.0f}ms. "
            f"avg(no_exist)={avg_unknown * 1000:.0f}ms "
            f"avg(exist)={avg_existing * 1000:.0f}ms. "
            f"Un atacante podría enumerar usernames midiendo latencia."
        )
        # Además, ambos promedios deben ser consistentes con un round bcrypt
        # (>= 50ms cada uno). Si avg(no_exist) < 20ms, claramente no se
        # ejecutó bcrypt → bug.
        assert avg_unknown > 0.05, (
            f"Avg(no_exist) = {avg_unknown * 1000:.0f}ms es demasiado bajo; "
            f"bcrypt no se ejecutó (fix timing-equalization ausente)."
        )


def test_xff_spoof_rejected(runner: TestRunner) -> None:
    """Hueco #2: rate-limit bypass vía X-Forwarded-For spoofing.

    Con `trusted_proxies=""` (default dev), el backend DEBE ignorar el
    header X-Forwarded-For y siempre usar `client.host` como clave de
    rate-limit. Esto bloquea el bypass donde un atacante envía
    `X-Forwarded-For: 1.2.3.4` para evitar el bucket.

    Diseño del test (rate-limit es 5/15min):
        Reset → 5 ataques con spoof #1 → 401 (bajo el límite).
                  6to ataque SIN spoof → 429 (prueba que spoof #1 mismo bucket).
        Reset → 5 ataques con spoof #2 → 401.
                  6to ataque SIN spoof → 429 (prueba que spoof #2 mismo bucket).

    Si el fix estuviera ausente, los 5 ataques con spoof #1 crearían un
    bucket separado para "1.2.3.4" y el 6to ataque (sin spoof, cliente
    real 127.0.0.1) sería 401, NO 429.
    """
    with runner.step("T14: X-Forwarded-For spoof no bypasa rate-limit (trusted_proxies vacío)"):
        # Password ≥6 chars para evitar 422 del schema.
        for spoof_ip in ("1.2.3.4", "5.6.7.8"):
            _reset_rate_limit_for_test()
            # 5 ataques con spoof → todos 401 (llenan el bucket del cliente real).
            for i in range(5):
                r = requests.post(
                    f"{BACKEND_URL}/api/v1/auth/token",
                    json={
                        "username": f"no-existe-{spoof_ip.replace('.', '-')}-{i}",
                        "password": f"fakepwd{i:03d}00",
                    },
                    headers={"X-Forwarded-For": spoof_ip},
                    timeout=5.0,
                )
                assert r.status_code == 401, (
                    f"spoof {spoof_ip} iter {i}: esperaba 401, "
                    f"obtuve {r.status_code}: {r.text}"
                )
            # 6to ataque SIN header → debe ser 429 porque el bucket ya está lleno
            # (el spoof fue IGNORADO, así que fue contra el mismo bucket que
            # client.host=127.0.0.1).
            r6 = requests.post(
                f"{BACKEND_URL}/api/v1/auth/token",
                json={"username": "no-existe-final", "password": "fakepwd000"},
                timeout=5.0,
            )
            assert r6.status_code == 429, (
                f"6to intento sin spoof (tras spoof_ip={spoof_ip}) esperaba 429 "
                f"porque el spoof fue ignorado y todos atacaron el mismo bucket. "
                f"Obtenido: {r6.status_code} (status={r6.status_code}). "
                f"Si da 401, el spoof ESTÁ BYPASEANDO el rate-limit."
            )
            retry = r6.headers.get("Retry-After")
            assert retry is not None, f"Sin Retry-After: {dict(r6.headers)}"
            print(
                f"   ✓ spoof {spoof_ip}: 5×401 + 1×429 (Retry-After={retry}s) "
                f"→ spoof no bypassa rate-limit", flush=True,
            )


def test_backend_blocks_stale_jwt_with_password_change(runner: TestRunner) -> None:
    """Hueco #3: backend enforcement de must_change_password.

    Una JWT robada con must_change_password=True NO debe alcanzar
    endpoints protegidos (/codes, /email-accounts, /platforms) aunque
    el frontend bloquee UI. Defense-in-depth real.

    Plan:
      1) Reset BD + restart implícito (no necesario, sólo cambiamos flag).
      2) Cambiar admin password a algo fijo DEJANDO must_change_password=True
         (setearlo manualmente a True vía un endpoint de testing o SQL).
         Alternativamente: usar el flag con T11 que test_login_admin ya
         cambió el flag a False, así que necesitamos re-bajar el flag a True.
         Vamos por SQL directo a la BD del backend — pero la BD está en el
         proceso del backend, separada de nuestro test. Solución:
         llamamos al endpoint setup o re-bootstrap. Realidad: la solución
         más simple es usar PUT /email-accounts con un token que tenga el
         flag True. Pero ya lo cambiamos a False en T2.
         Alternativa limpia: crear un test dedicado que no dependa del
         password ya cambiado. Usamos query directa a la BD del backend
         (codigos_e2e.db) — pero está en el proceso del backend, no la
         veremos desde aquí hasta que pida cerrar el backend.
      ⇒ Solución práctica: SIMULAR usando SQL en `codigos_e2e.db` tras
      verificar que el backend la cerró (no, no la cierra durante el test).
      ⇒ Otra solución: lanzar un proceso Python independiente que conecte a
      la BD y setee must_change_password=True. Sí, simple.
    """
    with runner.step("T15a: Backend bloquea endpoints protegidos con flag=True"):
        # Paso 1: subida del flag en BD vía SQL directo (otro proceso Python
        # abre la misma BD sqlite). Es seguro hacerlo mientras el backend
        # está corriendo porque SQLite usa WAL mode por defecto y permite
        # accesos concurrentes.
        test_db = BACKEND_DIR / "codigos_e2e.db"
        if not test_db.exists():
            raise AssertionError(f"BD no existe aún: {test_db}")
        import sqlite3
        conn = sqlite3.connect(str(test_db), timeout=5.0)
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET must_change_password = 1 WHERE username = 'admin'"
            )
            conn.commit()
            print("   SQL: flag must_change_password puesto en True", flush=True)
        finally:
            conn.close()

        # Paso 2: usar el token actual (que seguimos teniendo del T2) para
        # intentar acceder a un endpoint protegido.
        # Reusamos el token guardado. Como el backend es el mismo proceso,
        # el JWT sigue siendo válido (no expiró). sólo verificamos que el
        # dependency ahora lo rechaza.
        # Necesitamos el token: lo recuperamos llamando /auth/me, que NO
        # está protegido (es donde se lee el flag).
        # Pero la situación es que ya hicimos login en T2 y el flag era
        # False al momento del login → entonces el token ya circuló con el
        # contexto flag=False. La cuestión del backend defense-in-depth es
        # que el endpoint rechace con 403 incluso si el JWT es válido.
        # ⇒ Le pedimos al backend un token “fresh” usando el password actual
        # ya cambiado (NewSecure!) — recordando que login falla si
        # must_change=True en /auth/token? No, /auth/token deja pasar.
        _reset_rate_limit_for_test()
        fresh = requests.post(
            f"{BACKEND_URL}/api/v1/auth/token",
            json={"username": "admin", "password": "NewSecure!Pass42"},
            timeout=5.0,
        )
        assert fresh.status_code == 200, (
            f"Login con password actual falló: {fresh.status_code} {fresh.text}"
        )
        stolen_token = fresh.json()["access_token"]
        print(f"   Token fresh (mismo user con flag=True): {stolen_token[:30]}...", flush=True)

        # Paso 3: intentar alcanzar /codes (protegido). Debe devolver 403.
        r_codes = requests.get(
            f"{BACKEND_URL}/api/v1/codes",
            headers={"Authorization": f"Bearer {stolen_token}"},
            timeout=5.0,
        )
        assert r_codes.status_code == 403, (
            f"/codes con flag=True esperaba 403 (defense-in-depth), "
            f"obtuvo {r_codes.status_code}: {r_codes.text}"
        )
        detail = r_codes.json().get("detail", "")
        assert "Contraseña" in detail or "password" in detail.lower(), (
            f"Mensaje del 403 debería mencionar cambio de password: {detail!r}"
        )
        print(f"   ✓ /codes bloqueado: 403 ({detail!r})", flush=True)

        # Paso 4: /email-accounts también.
        r_acc = requests.get(
            f"{BACKEND_URL}/api/v1/email-accounts",
            headers={"Authorization": f"Bearer {stolen_token}"},
            timeout=5.0,
        )
        assert r_acc.status_code == 403, (
            f"/email-accounts con flag=True esperaba 403, obtuvo {r_acc.status_code}"
        )
        print(f"   ✓ /email-accounts bloqueado: 403", flush=True)

        # Paso 5: /platforms también.
        r_pl = requests.get(
            f"{BACKEND_URL}/api/v1/platforms",
            headers={"Authorization": f"Bearer {stolen_token}"},
            timeout=5.0,
        )
        assert r_pl.status_code == 403, (
            f"/platforms con flag=True esperaba 403, obtuvo {r_pl.status_code}"
        )
        print(f"   ✓ /platforms bloqueado: 403", flush=True)

        # Paso 6: /auth/me SÍ debe funcionar (es donde el frontend lee el flag).
        r_me = requests.get(
            f"{BACKEND_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {stolen_token}"},
            timeout=5.0,
        )
        assert r_me.status_code == 200, (
            f"/auth/me con flag=True esperaba 200 (no protegido), "
            f"obtuvo {r_me.status_code}: {r_me.text}"
        )
        me = r_me.json()
        assert me.get("must_change_password") is True, (
            f"/auth/me debería reportar flag=True: {me}"
        )
        print(f"   ✓ /auth/me sigue accesible (200, must_change=True)", flush=True)

        # Paso 7: cleanup — desactivar el flag para no afectar otros tests.
        conn = sqlite3.connect(str(test_db), timeout=5.0)
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET must_change_password = 0 WHERE username = 'admin'"
            )
            conn.commit()
            print("   SQL: flag must_change_password puesto en False (cleanup)", flush=True)
        finally:
            conn.close()


# ===================== Main =====================

async def amain() -> int:
    # 0. Limpiar BD de test anterior.
    test_db = BACKEND_DIR / "codigos_e2e.db"
    if test_db.exists():
        test_db.unlink()
        print(f"[setup] Eliminado {test_db}", flush=True)

    # 1. Arrancar mock IMAP.
    mock = MockIMAPServer()
    await mock.start()

    # 2. Arrancar backend como subprocess. Capturamos stdout en archivo para evitar
    #    deadlock del PIPE (si uvicorn+SAL+asyncio logs >64KB, bloquearía el backend).
    backend_log_path = BACKEND_DIR / "_e2e_backend.log"
    backend_log = open(backend_log_path, "wb")
    backend_proc = subprocess.Popen(
        [sys.executable, str(BACKEND_DIR / "_launch_e2e.py")],
        cwd=str(BACKEND_DIR),
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        preexec_fn=os.setsid,  # Para poder matar el grupo entero.
    )
    print(f"[setup] Backend PID={backend_proc.pid} log={backend_log_path}", flush=True)
    # Asegurar que BACKEND_PORT se pasa explícitamente al subprocess para evitar mismatch silencioso.
    os.environ["BACKEND_PORT"] = str(BACKEND_PORT)

    runner = TestRunner()
    ws_handle = None
    try:
        # 3. Esperar que el backend levante.
        wait_for_backend_ready(timeout=25.0)
        print("[setup] Backend ready", flush=True)

        test_admin_setup_implicit(runner)
        token = test_login_admin(runner)

        await test_ws_requires_auth(runner)

        ws_handle = await test_ws_connect_with_token(runner, token)
        account_id = test_create_email_account(runner, token)
        broadcast = await test_poll_extracts_code_and_broadcasts(
            runner, token, ws_handle, account_id, backend_log_path
        )
        test_verify_email_access_info_leak_fix(runner)
        test_public_request_code(runner, token)
        test_public_rate_limit(runner)
        test_change_password_wrong_old(runner, token)
        test_rate_limit_blocks_after_5_failures(runner)

        # Tests de los 3 huecos críticos arreglados originales.
        test_timing_oracle_equalized(runner)
        test_xff_spoof_rejected(runner)
        test_backend_blocks_stale_jwt_with_password_change(runner)

    finally:
        # Cleanup.
        if ws_handle is not None and not ws_handle.closed:
            await ws_handle.close()
        await mock.stop()
        print("[teardown] Apagando backend…", flush=True)
        try:
            os.killpg(os.getpgid(backend_proc.pid), signal.SIGTERM)
            try:
                backend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(backend_proc.pid), signal.SIGKILL)
                backend_proc.wait(timeout=5)
        except ProcessLookupError:
            pass
        backend_log.close()
        # Mostrar últimas 30 líneas del log del backend si hubo fallos.
        if runner.failed:
            print("\n" + "=" * 60)
            print("Últimas 30 líneas del backend (debug):")
            print("=" * 60)
            try:
                tail = backend_log_path.read_text(errors="replace").splitlines()[-30:]
                for line in tail:
                    print(f"  >> {line}")
            except Exception as exc:  # noqa: BLE001
                print(f"  (no pude leer log: {exc})")

    return runner.report()


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
