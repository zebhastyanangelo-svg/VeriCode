import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.auth.dependencies import client_ip
from app.core import cache as app_cache
from app.db.database import get_db
from app.models import EmailAccount, Platform, VerificationCode
from app.schemas import PlatformOut
from app.services.rate_limit import check_public_allowed, record_public_request

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/ping")
async def ping():
    """Health-check mínimo. Sin auth, sin DB. Usado por el frontend como
    keep-alive cada 5 min para evitar que Render free tier duerma el backend."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


def _sanitize_email_address(raw: str) -> str:
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        try:
            return raw.split("<", 1)[1].split(">", 1)[0].strip()
        except Exception:
            return raw
    return raw.strip()


@router.get("/platforms", response_model=list[PlatformOut])
async def list_platforms(
    db: Session = Depends(get_db),
):
    """Lista pública de plataformas activas. Cacheada 60s + 304 ETag."""
    def _compute():
        return db.query(Platform).filter(
            Platform.is_active == True
        ).order_by(Platform.name).all()

    payload = app_cache.get_or_compute(
        app_cache.NS_PLATFORMS,
        ttl_seconds=60,
        compute_fn=_compute,
        key_parts=("active",),
    )
    return payload


async def _check_public_rate_limit(ip: str) -> None:
    allowed, retry_after = check_public_allowed(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiadas solicitudes. Intentá de nuevo en {retry_after} segundos.",
            headers={"Retry-After": str(retry_after)},
        )


def _lookup_account_uniform(db: Session, email: str):
    """Busca cuenta activa. Devuelve None sin lanzar excepción."""
    return db.query(EmailAccount).filter(
        EmailAccount.email == email,
        EmailAccount.is_active == True,
    ).first()


def _lookup_platform_uniform(db: Session, platform_name: str):
    """Busca plataforma activa. Devuelve None sin lanzar excepción."""
    return db.query(Platform).filter(
        Platform.name == platform_name,
        Platform.is_active == True,
    ).first()


@router.post("/request-code")
async def request_code(
    request: Request,
    email: str = Query(..., description="Email address"),
    platform_name: str = Query(..., description="Platform name"),
    db: Session = Depends(get_db),
    ip: str = Depends(client_ip),
):
    ip = ip or request.client.host if request.client else "unknown"
    await _check_public_rate_limit(ip)
    record_public_request(ip)

    now = datetime.utcnow()

    email_account = _lookup_account_uniform(db, email)
    platform = _lookup_platform_uniform(db, platform_name)

    if not email_account or not platform:
        raise HTTPException(
            status_code=404,
            detail="No hay código disponible para esta combinación de correo y plataforma",
        )

    def _find_code():
        return db.query(VerificationCode).filter(
            VerificationCode.email_account_id == email_account.id,
            VerificationCode.platform_id == platform.id,
            VerificationCode.is_delivered == False,
            (VerificationCode.expires_at.is_(None)) | (VerificationCode.expires_at > now),
        ).order_by(VerificationCode.received_at.desc()).first()

    code = await asyncio.to_thread(_find_code)
    if not code:
        raise HTTPException(
            status_code=404,
            detail="No hay código de verificación disponible para esta cuenta y plataforma",
        )

    def _claim():
        result = db.execute(
            update(VerificationCode)
            .where(
                VerificationCode.id == code.id,
                VerificationCode.is_delivered == False,
            )
            .values(
                is_delivered=True,
                delivered_to=email,
                delivered_at=now,
            )
        )
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="El código ya fue entregado a otro solicitante",
            )
        db.commit()

    await asyncio.to_thread(_claim)

    return {
        "message": "Código verificación encontrado",
        "code": code.code,
        "platform_name": platform.name,
        "platform_display_name": platform.display_name,
        "platform_id": platform.id,
        "platform_icon": platform.icon,
        "code_id": code.id,
        "is_read": code.is_read,
        "is_delivered": True,
        "received_at": code.received_at.isoformat() if code.received_at else None,
        "sender": _sanitize_email_address(code.sender),
        "subject": code.subject,
    }


@router.get("/verify-email-access")
async def verify_email_access(
    request: Request,
    email: str = Query(...),
    platform_name: str = Query(...),
    only_unused: bool = Query(True, description="Si true, ignora códigos ya entregados"),
    db: Session = Depends(get_db),
    ip: str = Depends(client_ip),
):
    ip = ip or request.client.host if request.client else "unknown"
    await _check_public_rate_limit(ip)
    record_public_request(ip)

    now = datetime.utcnow()

    email_account = _lookup_account_uniform(db, email)
    platform = _lookup_platform_uniform(db, platform_name)

    # Respuesta uniforme: no revelar si el correo está registrado o no.
    if not email_account or not platform:
        return {
            "has_access": False,
            "detail": "No hay código disponible para esta combinación",
        }

    def _query():
        q = db.query(VerificationCode).filter(
            VerificationCode.email_account_id == email_account.id,
            VerificationCode.platform_id == platform.id,
        ).filter(
            (VerificationCode.expires_at.is_(None)) | (VerificationCode.expires_at > now),
        )
        if only_unused:
            q = q.filter(VerificationCode.is_delivered == False)
        return q.order_by(VerificationCode.received_at.desc()).first()

    code = await asyncio.to_thread(_query)

    if not code:
        return {
            "has_access": False,
            "detail": "No hay código disponible para esta combinación",
        }

    return {
        "has_access": True,
        "detail": "Código disponible",
        "platform_name": platform.name,
        "platform_display_name": platform.display_name,
        "code_id": code.id,
        "is_read": code.is_read,
        "is_delivered": code.is_delivered,
        "received_at": code.received_at.isoformat() if code.received_at else None,
    }


@router.post("/_test/reset-rate-limit")
def test_reset_public_rate_limit():
    from app.config import settings as s
    if s.vericode_env == "production":
        from fastapi import HTTPException as HE
        raise HE(status_code=404, detail="Not Found")
    from app.services.rate_limit import reset_public_limiter
    reset_public_limiter()
    return {"message": "Public rate-limit reseteado"}
