#!/usr/bin/env python3
"""Unit tests para `_production_guards()` y `is_production()` en `app.main`
/ `app.config`.

Crítico: cubre el bug detectado por el code-reviewer en el que comparar
`settings.vericode_env == "production"` directo dejaba al sistema en modo
inseguro cuando el operador seteaba `VERICODE_ENV=Production` (cualquier
variante ortográfica). El test asegura que **cualquier** variante
dispara los guards.

Standalone runner (sin pytest). Cada test monkey-patchea el singleton
`settings` con un nuevo `Settings()` que lee env controlados vía
`patch.dict(os.environ, ...)`.

Run:
    cd backend
    python tests/test_production_guards.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
class _SettingsOverride:
    """Context manager que reemplaza el singleton `settings` por uno
    nuevo con env vars controladas.

    Pydantic-settings v2 lee env durante `__init__`, así que creamos un
    Settings() nuevo bajo el patch.dict os.environ y luego parcheamos
    los tres lugares donde está referenciado:

      - `app.main.settings` (lo que _production_guards lee)
      - `app.config.settings` (lo que `is_production()` lee, si está
        importado)
    """

    def __init__(self, env_overrides: dict) -> None:
        # clear=False para preservar PATH/USER/etc del proceso real.
        self._env_patch = patch.dict(os.environ, env_overrides, clear=False)
        self._main_patch = None
        self._config_patch = None

    def __enter__(self):
        self._env_patch.start()
        from app.config import Settings

        fresh = Settings()
        # Patch el singleton referenciado en main.py y config.py.
        self._main_patch = patch("app.main.settings", fresh)
        self._config_patch = patch("app.config.settings", fresh)
        self._main_patch.start()
        self._config_patch.start()
        return fresh

    def __exit__(self, *args):
        if self._main_patch:
            self._main_patch.stop()
        if self._config_patch:
            self._config_patch.stop()
        self._env_patch.stop()


# Configuración "buena" para producción: si alguno de estos cambia, debe
# disparar el guard apropiado.
PROD_GOOD: dict = {
    "VERICODE_ENV": "production",
    "BOOTSTRAP_TOKEN": "good-bt-12345678abcdef",
    "SECRET_KEY": "good-not-default-32chars-or-more-padding-x",
    "CORS_ORIGINS": "https://app.tu-dominio.com",
    "FERNET_KEY": "Tm90LXRoZS1kZXYtZmVybmV0LWtleS1qdXN0LXRoZS1mYXV4LXBhcNzc2dvcmQ=",
}


def _expect_raise(env: dict, expected_substr: str) -> None:
    """Assert _production_guards() raises RuntimeError con substring esperado."""
    with _SettingsOverride(env):
        from app.main import _production_guards

        try:
            _production_guards()
        except RuntimeError as e:
            assert expected_substr in str(e), (
                f"Esperaba {expected_substr!r} en el error, obtuve:\n  {e}"
            )
            return
    raise AssertionError(
        f"Debería haber raised con {expected_substr!r} pero pasó silencioso. "
        f"Env: {env}"
    )


def _expect_pass(env: dict) -> None:
    """Assert _production_guards() NO raises."""
    with _SettingsOverride(env):
        from app.main import _production_guards
        _production_guards()  # sin raise


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
def test_dev_mode_is_noop() -> None:
    """Dev mode ignora cualquier config fea — guards es no-op."""
    _expect_pass({
        "VERICODE_ENV": "development",
        "BOOTSTRAP_TOKEN": "",
        "SECRET_KEY": "CHANGE-ME-bad-pal",
        "CORS_ORIGINS": "*",
    })


def test_prod_good_config_passes() -> None:
    """En prod con defaults sanos, guards pasa."""
    _expect_pass(PROD_GOOD)


def test_prod_empty_bootstrap_raises() -> None:
    """Prod + BOOTSTRAP_TOKEN='' → raise con 'BOOTSTRAP_TOKEN' en el mensaje."""
    _expect_raise({**PROD_GOOD, "BOOTSTRAP_TOKEN": ""}, "BOOTSTRAP_TOKEN")


def test_prod_cors_star_raises() -> None:
    """Prod + CORS_ORIGINS='*' → raise."""
    _expect_raise({**PROD_GOOD, "CORS_ORIGINS": "*"}, "CORS_ORIGINS")


def test_prod_cors_empty_raises() -> None:
    """Prod + CORS_ORIGINS='' → raise."""
    _expect_raise({**PROD_GOOD, "CORS_ORIGINS": ""}, "CORS_ORIGINS")


def test_prod_change_me_secret_raises() -> None:
    """Prod + SECRET_KEY con prefijo CHANGE-ME → raise."""
    _expect_raise(
        {**PROD_GOOD, "SECRET_KEY": "CHANGE-ME-bad-secret-key"},
        "SECRET_KEY",
    )


def test_prod_capitalized_env_triggers_guards() -> None:
    """🚨 CRITICAL: VERICODE_ENV='Production' (capital P) debe disparar guards.

    Sin este test, una regresión del case-sensitive podría pasar
    silenciosamente y dejar al sistema en el peor estado posible:
    admin auto-creado con password default en prod.
    """
    _expect_raise(
        {**PROD_GOOD, "VERICODE_ENV": "Production", "BOOTSTRAP_TOKEN": ""},
        "BOOTSTRAP_TOKEN",
    )


def test_prod_uppercase_env_triggers_guards() -> None:
    """VERICODE_ENV='PRODUCTION' (todo mayúsculas) → triggers."""
    _expect_raise(
        {**PROD_GOOD, "VERICODE_ENV": "PRODUCTION", "BOOTSTRAP_TOKEN": ""},
        "BOOTSTRAP_TOKEN",
    )


def test_prod_alternate_alias_prod() -> None:
    """VERICODE_ENV='prod' → triggers (alias ortográfico)."""
    _expect_raise(
        {**PROD_GOOD, "VERICODE_ENV": "prod", "BOOTSTRAP_TOKEN": ""},
        "BOOTSTRAP_TOKEN",
    )


def test_is_production_helper() -> None:
    """`is_production()` case-insensitive + aliases."""
    from app.config import is_production

    for variant in ("production", "Production", "PRODUCTION", "Prod", "prod"):
        with _SettingsOverride({**PROD_GOOD, "VERICODE_ENV": variant}):
            assert is_production(), (
                f"is_production() False con VERICODE_ENV={variant!r}. "
                f"Esto es exactamente el bug que estamos testeando."
            )
    with _SettingsOverride({**PROD_GOOD, "VERICODE_ENV": "development"}):
        assert not is_production(), (
            "is_production() True con VERICODE_ENV='development' (regresión)."
        )


def test_seed_admin_no_auto_create_in_prod() -> None:
    """Sanity: `seed_admin()` no auto-crea en prod aunque la tabla esté vacía.

    Esto previene la regresión donde VERICODE_ENV='Production' por error
    auto-crea admin/admin123. No podemos ejecutar seed_admin() directamente
    (afecta la BD), pero validamos que is_production() devuelve True
    cuando lo espera.
    """
    from app.config import is_production

    with _SettingsOverride({**PROD_GOOD, "VERICODE_ENV": "Production"}):
        assert is_production(), (
            "Bug crítico: 'Production' no marcado como producción en "
            "seed_admin() — admin podría auto-crearse."
        )


# --------------------------------------------------------------------------
# Standalone runner
# --------------------------------------------------------------------------
def main() -> int:
    tests = sorted(
        [(name, fn) for name, fn in globals().items() if name.startswith("test_")]
    )
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {name}: [{type(e).__name__}] {e}")
            failed += 1
    print(f"\n{'=' * 50}")
    print(f"Result: {passed}/{passed + failed}")
    if failed:
        print("FAIL — posible regresión del fail-fast. Investigar antes de mergear.")
        return 1
    print("PASS — fail-fast activo en todas las variantes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
