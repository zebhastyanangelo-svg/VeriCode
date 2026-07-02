"""
Rate-limit in-memory con sliding window.

Diseñado para un único proceso uvicorn. NO usar con múltiples workers
(uWSGI/Gunicorn con --workers > 1) sin reemplazarlo por Redis u otro store
compartido, porque cada worker tendría su propio contador y los límites
serían por-worker en lugar de globales.

API:
    limiter = SlidingWindowLimiter(max_attempts=5, window_seconds=900)
    if not limiter.allow(ip, key="login"):
        raise HTTPException(429, "Demasiados intentos, intentá en X seg")
    limiter.record_failure(ip, key="login")  # sólo se llama en fallos
    limiter.record_success(ip, key="login")  # limpia el contador
"""
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class _State:
    timestamps: deque  # de floats (epoch seconds)


class SlidingWindowLimiter:
    """Limita la cantidad de *fallos* consecutivos dentro de una ventana móvil.

    `allow()` siempre devuelve True hasta que la ventana tenga `max_attempts`
    timestamps. `record_failure()` agrega uno nuevo. `record_success()`
    limpia el historial (asume "logró pasar", por lo que el contador
    anterior no debe penalizarlo).
    """

    def __init__(self, max_attempts: int, window_seconds: int, *, sweep_every: int = 100):
        if max_attempts <= 0 or window_seconds <= 0:
            raise ValueError("max_attempts y window_seconds deben ser > 0")
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._buckets: dict[tuple[str, str], _State] = defaultdict(
            lambda: _State(timestamps=deque())
        )
        self._lock = threading.Lock()
        self._sweep_counter = 0
        self._sweep_every = sweep_every

    def _cleanup_locked(self, key_state: _State, now: float) -> None:
        cutoff = now - self.window_seconds
        q = key_state.timestamps
        while q and q[0] < cutoff:
            q.popleft()

    def _maybe_sweep_locked(self) -> None:
        # Limpia buckets vacíos cada N requests para no acumular memoria
        # de IPs que ya no atacan.
        self._sweep_counter += 1
        if self._sweep_counter < self._sweep_every:
            return
        self._sweep_counter = 0
        empty = [k for k, s in self._buckets.items() if not s.timestamps]
        for k in empty:
            del self._buckets[k]

    def remaining_locked(self, key_state: _State, now: float) -> int:
        return max(0, self.max_attempts - len(key_state.timestamps))

    def retry_after_seconds(self, ip: str, key: str) -> int:
        """Segundos hasta que se libere al menos un slot, o 0 si no hay bloqueo."""
        with self._lock:
            state = self._buckets[(ip, key)]
            now = time.monotonic()
            self._cleanup_locked(state, now)
            if len(state.timestamps) < self.max_attempts:
                return 0
            # Cuando el más viejo salga de la ventana, hay lugar.
            return max(0, int(self.window_seconds - (now - state.timestamps[0])))

    def allow(self, ip: str, key: str) -> bool:
        with self._lock:
            state = self._buckets[(ip, key)]
            now = time.monotonic()
            self._cleanup_locked(state, now)
            self._maybe_sweep_locked()
            return len(state.timestamps) < self.max_attempts

    def record_failure(self, ip: str, key: str) -> None:
        with self._lock:
            state = self._buckets[(ip, key)]
            now = time.monotonic()
            self._cleanup_locked(state, now)
            state.timestamps.append(now)

    def record_success(self, ip: str, key: str) -> None:
        with self._lock:
            # Borrar toda la ventana porque logró autenticarse.
            self._buckets[(ip, key)].timestamps.clear()


# Singleton del módulo para /auth/token. Configuración viene de settings.
from app.config import settings  # noqa: E402

_login_limiter = SlidingWindowLimiter(
    max_attempts=settings.auth_rate_limit_max_attempts,
    window_seconds=settings.auth_rate_limit_window_minutes * 60,
)


def check_login_allowed(ip: str) -> tuple[bool, int]:
    """Devuelve (permitido, retry_after_seconds)."""
    return _login_limiter.allow(ip, "login"), _login_limiter.retry_after_seconds(ip, "login")


def record_login_failure(ip: str) -> None:
    _login_limiter.record_failure(ip, "login")


def record_login_success(ip: str) -> None:
    _login_limiter.record_success(ip, "login")


def reset_login_limiter() -> None:
    """Para tests: limpia el estado entre corridas."""
    _login_limiter._buckets.clear()
