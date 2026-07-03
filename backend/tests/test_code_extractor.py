"""Unit tests para code_extractor.py — guess_platform y extract_code_from_body.

Ejecutar:
    cd backend && python -m pytest tests/test_code_extractor.py -v
"""
from unittest.mock import MagicMock

import pytest

from app.services.code_extractor import (
    PLATFORM_PATTERNS,
    extract_code_from_body,
    guess_platform,
    _is_sequential,
    _looks_like_false_positive,
)


# ===================== Helpers =====================


def _make_platform(name: str, **kwargs):
    p = MagicMock()
    p.name = name
    p.sender_pattern = kwargs.get("sender_pattern")
    p.subject_pattern = kwargs.get("subject_pattern")
    p.code_pattern = kwargs.get("code_pattern")
    p.id = hash(name) % 10000
    return p


# ===================== guess_platform =====================


def test_guess_platform_by_sender_pattern():
    platforms = [_make_platform("netflix", sender_pattern=r"@(netflix\.com)")]
    result = guess_platform("info@netflix.com", "Tu código", platforms)
    assert result is not None
    assert result.name == "netflix"


def test_guess_platform_by_subject_pattern():
    platforms = [_make_platform("netflix", subject_pattern=r"(c[oó]digo|verificaci[oó]n)")]
    result = guess_platform("some@unknown.com", "Tu código de verificación", platforms)
    assert result is not None
    assert result.name == "netflix"


def test_guess_platform_hardcoded_match():
    platforms = [_make_platform("netflix")]
    result = guess_platform("info@netflix.com", "Bienvenido", platforms)
    assert result is not None
    assert result.name == "netflix"


def test_guess_platform_no_match():
    platforms = [_make_platform("netflix")]
    result = guess_platform("unknown@example.com", "Hello", platforms)
    assert result is None


def test_guess_platform_empty_platforms():
    result = guess_platform("info@netflix.com", "code", [])
    assert result is None


# ===================== extract_code_from_body =====================


def test_extract_code_with_platform_pattern():
    platform = _make_platform("netflix", code_pattern=r"\b(\d{6})\b")
    body = "Tu código de verificación es 482916. No lo compartas."
    code = extract_code_from_body(body, platform)
    assert code == "482916"


def test_extract_code_priority_keyword():
    body = "Tu código de verificación es: 482916. No lo compartas."
    code = extract_code_from_body(body)
    assert code == "482916"


def test_extract_code_from_otp_context():
    body = "Your OTP is 739201"
    code = extract_code_from_body(body)
    assert code == "739201"


def test_extract_code_from_pin_context():
    body = "Su PIN: 5821"
    code = extract_code_from_body(body)
    # 4 dígitos, debe estar en contexto de palabra clave
    assert code is not None

def test_extract_code_english():
    body = "Your verification code is 374651"
    code = extract_code_from_body(body)
    assert code == "374651"


# ===================== Falsos positivos =====================


def test_rejects_year():
    body = "Bienvenido a nuestra plataforma en 2024"
    code = extract_code_from_body(body)
    assert code is None


def test_rejects_invoice_number():
    body = "Factura #482916 emitida correctamente"
    code = extract_code_from_body(body)
    assert code is None


def test_rejects_order_number():
    body = "Su orden #284613 ha sido procesada"
    code = extract_code_from_body(body)
    assert code is None


def test_rejects_total_amount():
    body = "Total: $123456"
    code = extract_code_from_body(body)
    assert code is None


def test_rejects_sequential_digits():
    """123456 is sequential, should be rejected."""
    body = "Cualquier número 123456 es secuencial"
    code = extract_code_from_body(body)
    assert code is None, f"Expected None for sequential, got {code}"


def test_rejects_repeated_digits():
    """111111 is all repeated, should be rejected."""
    body = "Su código 111111 no es real"
    code = extract_code_from_body(body)
    assert code is None, f"Expected None for repeated, got {code}"


def test_rejects_phone_number():
    body = "Teléfono: 555-123-4567"
    code = extract_code_from_body(body)
    assert code is None


def test_rejects_zip_code():
    body = "Código postal: 123456"
    code = extract_code_from_body(body)
    assert code is None


def test_rejects_reference_number():
    body = "Ref: 789012 para su trámite"
    code = extract_code_from_body(body)
    assert code is None


# ===================== Casos reales con contexto =====================


def test_netflix_email():
    body = "Hola! Tu código de verificación de Netflix es: 778899. No lo compartas con nadie."
    platform = _make_platform("netflix", code_pattern=r"\b(\d{6})\b")
    code = extract_code_from_body(body, platform)
    assert code == "778899", f"Expected 778899, got {code}"


def test_amazon_otp():
    body = "Your Amazon OTP is 382910. It expires in 10 minutes."
    code = extract_code_from_body(body)
    assert code == "382910"


def test_code_after_colon():
    body = "Verification code: 918273"
    code = extract_code_from_body(body)
    assert code == "918273"


def test_code_dash_prefix():
    body = "código - 462738"
    code = extract_code_from_body(body)
    assert code == "462738"


def test_code_in_html_like_text():
    body = "<p>Su código de verificación es <strong>573829</strong></p>"
    code = extract_code_from_body(body)
    assert code == "573829"


# ===================== _is_sequential =====================


def test_is_sequential_ascending():
    assert _is_sequential("123456") is True


def test_is_sequential_descending():
    assert _is_sequential("654321") is True


def test_is_sequential_step_2():
    assert _is_sequential("135790") is False


def test_is_sequential_short():
    assert _is_sequential("12") is False


def test_not_sequential():
    assert _is_sequential("482916") is False


# ===================== _looks_like_false_positive =====================


def test_false_positive_year():
    assert _looks_like_false_positive("2024", "en 2024", 3, 7) is True


def test_false_positive_with_context_before():
    text = "Factura 123456 del mes"
    assert _looks_like_false_positive("123456", text, 8, 14) is True


def test_false_positive_with_context_after():
    text = "Order number 123456"
    assert _looks_like_false_positive("123456", text, 13, 19) is True


def test_not_false_positive():
    text = "Tu código es 482916"
    assert _looks_like_false_positive("482916", text, 12, 18) is False


def test_false_positive_phone():
    text = "Phone: 5551234567"
    assert _looks_like_false_positive("5551234567", text, 7, 17) is True
