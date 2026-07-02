import re
from typing import Optional

from app.models import Platform


PLATFORM_PATTERNS = {
    "netflix": {
        "senders": ["netflix.com"],
        "subjects": ["código", "code", "verificación", "verification", "confirmación", "confirmation"],
    },
    "disney_plus": {
        "senders": ["disneyplus.com", "disney.com"],
        "subjects": ["código", "code", "verificación", "verification"],
    },
    "hbo_max": {
        "senders": ["hbomax.com", "hbo.com"],
        "subjects": ["código", "code", "verificación", "verification"],
    },
    "prime_video": {
        "senders": ["amazon.com", "primevideo.com"],
        "subjects": ["código", "code", "verificación", "verification", "otp"],
    },
    "spotify": {
        "senders": ["spotify.com"],
        "subjects": ["código", "code", "verificación", "verification"],
    },
    "chatgpt": {
        "senders": ["openai.com", "chatgpt.com"],
        "subjects": ["código", "code", "verificación", "verification", "login"],
    },
    "claude": {
        "senders": ["anthropic.com", "claude.ai"],
        "subjects": ["código", "code", "verificación", "verification"],
    },
    "midjourney": {
        "senders": ["midjourney.com"],
        "subjects": ["código", "code", "verificación", "verification"],
    },
    "paramount": {
        "senders": ["paramountplus.com", "paramount.com"],
        "subjects": ["código", "code", "verificación", "verification"],
    },
}

# Cualquier código de 6 dígitos rodeado de palabras clave "código"/"code"/"otp"/"pin"
# puede ser un falso positivo si parece un año (2020-2099) o un número de orden aislado.
YEAR_RANGE = re.compile(r"^(19|20)\d{2}$")


def guess_platform(sender: str, subject: str, platforms: list[Platform]) -> Optional[Platform]:
    """Solo devuelve plataformas EXISTENTES en BD (con id).
    NUNCA crea objetos Platform sin id."""
    sender_lower = (sender or "").lower()
    subject_lower = (subject or "").lower()

    # 1. Patrones configurados en BD (sender_pattern / subject_pattern)
    for platform in platforms:
        if platform.sender_pattern and re.search(platform.sender_pattern, sender_lower, re.IGNORECASE):
            return platform
        if platform.subject_pattern and re.search(platform.subject_pattern, subject_lower, re.IGNORECASE):
            return platform

    # 2. Diccionario hardcodeado -> buscar match por nombre en BD
    for key, patterns in PLATFORM_PATTERNS.items():
        sender_match = any(s in sender_lower for s in patterns["senders"])
        subject_match = any(s in subject_lower for s in patterns["subjects"])
        if sender_match or subject_match:
            for platform in platforms:
                if platform.name == key:
                    return platform
            return None

    return None


# Patrones ordenados de mayor a menor especificidad.
PRIORITY_CODE_PATTERNS = [
    r'(?:c[oó]digo|code|otp|pin)\s*(?:de\s*)?(?:verificaci[oó]n|verification)?\s*[:\-]?\s*(\d{4,8})',
    r'(?:verification|security)\s*code\s*[:\-]?\s*(\d{4,8})',
    r'(\d{4,8})\s*(?:es|is)\s*(?:tu|tu|el|the)?\s*(?:c[oó]digo|code)',
    r'tu\s*c[oó]digo\s*(?:de\s*verificaci[oó]n|es)?\s*[:\-]?\s*(\d{4,8})',
]
FALLBACK_CODE_PATTERN = r"\b(\d{6})\b"


def extract_code_from_body(body: str, platform: Optional[Platform] = None) -> Optional[str]:
    """Extrae un código del cuerpo del correo. Si la plataforma define su
    propio regex y matchea algo razonable, lo usa. Si no, busca con patrones
    específicos y como último recurso un número de 6 dígitos rodeado de
    boundaries."""
    if not body:
        return None

    candidate = None

    # 1. Pattern propio de la plataforma
    if platform and platform.code_pattern:
        m = re.search(platform.code_pattern, body)
        if m:
            value = m.group(1) if m.lastindex else m.group(0)
            candidate = value

    # 2. Patterns prioritarios con keyword (más confiable)
    if not candidate:
        for pattern in PRIORITY_CODE_PATTERNS:
            m = re.search(pattern, body, re.IGNORECASE)
            if m:
                candidate = m.group(1)
                break

    # 3. Fallback: 6 dígitos sueltos. Filtrar años / números comunes.
    if not candidate:
        for m in re.finditer(FALLBACK_CODE_PATTERN, body):
            value = m.group(1)
            if not _looks_like_false_positive(value, body, m.start(), m.end()):
                candidate = value
                break

    if not candidate:
        return None

    # Validación final: descartar 4 dígitos que parezcan años.
    if len(candidate) == 4 and YEAR_RANGE.match(candidate):
        return None

    return candidate


def _looks_like_false_positive(value: str, text: str, start: int, end: int) -> bool:
    """Filtra falsos positivos comunes: años, números de orden aislados,
    importes sin contexto, prefijos telefónicos."""
    if len(value) == 4 and YEAR_RANGE.match(value):
        return True

    # Contexto: si el número está pegado a palabras como "order #N",
    # "factura N", "importe", es probable que no sea código.
    context_before = text[max(0, start - 40):start].lower()
    context_after = text[end:min(len(text), end + 40)].lower()

    false_positive_keywords = [
        "order", "orden", "factura", "importe", "total", "subtotal",
        "invoice", "zip", "postal", "phone", "tel", "ruc", "cuit",
    ]
    if any(k in context_before for k in false_positive_keywords):
        return True
    if any(k in context_after for k in false_positive_keywords):
        return True

    return False
