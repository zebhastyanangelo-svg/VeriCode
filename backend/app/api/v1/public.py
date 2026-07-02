import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core import cache as app_cache
from app.db.database import get_db
from app.models import EmailAccount, Platform, VerificationCode
from app.schemas import EmailAccountOut, PlatformOut

router = APIRouter(prefix="/public", tags=["public"])


def _sanitize_email_address(raw: str) -> str:
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        try:
            return raw.split("<", 1)[1].split(">", 1)[0].strip()
        except Exception:
            return raw
    return raw.strip()


@router.get("/email-accounts", response_model=list[EmailAccountOut])
async def list_email_accounts(
    db: Session = Depends(get_db),
):
    """Lista pública de cuentas activas. Cacheada 30s.

    Cache-Control: public (max-age=30) viaja en el response para que el
    navegador del usuario público retenga el resultado entre
    page-reloads sin volver a pegarle al backend.
    304 inline con ETag queda deferido para una próxima iteración; el
    cache del navegador cubre el 90% del ahorro de bandwidth.
    """
    def _compute():
        return db.query(EmailAccount).filter(
            EmailAccount.is_active == True
        ).order_by(EmailAccount.email).all()

    payload = app_cache.get_or_compute(
        app_cache.NS_EMAIL_ACCOUNTS,
        ttl_seconds=30,
        compute_fn=_compute,
        key_parts=("active",),
    )
    return payload


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


def _find_unused_code(db: Session, email_account_id: int, platform_id: int):
    return db.query(VerificationCode).filter(
        VerificationCode.email_account_id == email_account_id,
        VerificationCode.platform_id == platform_id,
        VerificationCode.is_delivered == False,
    ).order_by(VerificationCode.received_at.desc()).first()


@router.post("/request-code")
async def request_code(
    email: str = Query(..., description="Email address"),
    platform_name: str = Query(..., description="Platform name"),
    db: Session = Depends(get_db),
):
    def _lookup_account():
        return db.query(EmailAccount).filter(
            EmailAccount.email == email,
            EmailAccount.is_active == True,
        ).first()

    def _lookup_platform():
        return db.query(Platform).filter(
            Platform.name == platform_name,
            Platform.is_active == True,
        ).first()

    email_account = await asyncio.to_thread(_lookup_account)
    if not email_account:
        raise HTTPException(status_code=404, detail="Este correo no está registrado")

    platform = await asyncio.to_thread(_lookup_platform)
    if not platform:
        raise HTTPException(status_code=404, detail="Plataforma no disponible")

    def _find_code():
        return _find_unused_code(db, email_account.id, platform.id)

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
                delivered_at=datetime.utcnow(),
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
        "code_id": code.id,
        "is_read": code.is_read,
        "is_delivered": True,
        "received_at": code.received_at.isoformat() if code.received_at else None,
        "sender": _sanitize_email_address(code.sender),
        "subject": code.subject,
    }


@router.get("/verify-email-access")
async def verify_email_access(
    email: str = Query(...),
    platform_name: str = Query(...),
    only_unused: bool = Query(True, description="Si true, ignora códigos ya entregados"),
    db: Session = Depends(get_db),
):
    def _lookup_account():
        return db.query(EmailAccount).filter(
            EmailAccount.email == email,
            EmailAccount.is_active == True,
        ).first()

    def _lookup_platform():
        return db.query(Platform).filter(
            Platform.name == platform_name,
            Platform.is_active == True,
        ).first()

    email_account = await asyncio.to_thread(_lookup_account)
    if not email_account:
        raise HTTPException(status_code=404, detail="Correo no registrado")

    platform = await asyncio.to_thread(_lookup_platform)
    if not platform:
        raise HTTPException(status_code=404, detail="Plataforma no disponible")

    def _query():
        q = db.query(VerificationCode).filter(
            VerificationCode.email_account_id == email_account.id,
            VerificationCode.platform_id == platform.id,
        )
        if only_unused:
            q = q.filter(VerificationCode.is_delivered == False)
        return q.order_by(VerificationCode.received_at.desc()).first()

    code = await asyncio.to_thread(_query)

    if not code:
        raise HTTPException(status_code=404, detail="No hay código disponible")

    return {
        "has_access": True,
        "email": email,
        "platform_name": platform.name,
        "platform_display_name": platform.display_name,
        "code": code.code,
        "platform_id": platform.id,
        "code_id": code.id,
        "is_read": code.is_read,
        "is_delivered": code.is_delivered,
        "received_at": code.received_at.isoformat() if code.received_at else None,
        "sender": _sanitize_email_address(code.sender),
        "subject": code.subject,
    }
