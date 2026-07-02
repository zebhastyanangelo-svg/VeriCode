import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.auth import encrypt_password, get_current_user
from app.auth.dependencies import require_no_password_change
from app.core import cache as app_cache
from app.core.headers import cache_control_headers, etag_headers
from app.db.database import get_db
from app.models import EmailAccount, VerificationCode
from app.schemas import (
    EmailAccountCreate, EmailAccountUpdate, EmailAccountOut,
)
from app.services.imap_poller import poller_instance as poller

router = APIRouter(
    prefix="/email-accounts",
    tags=["email-accounts"],
    dependencies=[Depends(require_no_password_change)],
)


@router.get("", response_model=List[EmailAccountOut])
async def list_accounts(
    response: Response,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Lista de cuentas de correo (admin).

    Cacheado 30s. Se invalida con `bump_version(NS_EMAIL_ACCOUNTS)` en
    cada POST/PUT/DELETE — también invalida el cache público porque
    comparten namespace.
    """
    def _compute():
        return db.query(EmailAccount).order_by(EmailAccount.email).all()

    payload = app_cache.get_or_compute(
        app_cache.NS_EMAIL_ACCOUNTS, ttl_seconds=30, compute_fn=_compute,
    )
    cache_control_headers(response, max_age_seconds=15, private=True)
    etag_headers(response, app_cache.NS_EMAIL_ACCOUNTS)
    return payload


@router.post("", response_model=EmailAccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: EmailAccountCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _check():
        return db.query(EmailAccount).filter(EmailAccount.email == data.email).first()

    existing = await asyncio.to_thread(_check)
    if existing:
        raise HTTPException(status_code=400, detail="Esta cuenta ya existe")

    account = EmailAccount(
        email=data.email,
        email_type=data.email_type,
        imap_host=data.imap_host,
        imap_port=data.imap_port,
        username=data.username or data.email,
        password_encrypted=encrypt_password(data.password),
        notes=data.notes,
        platform_id=data.platform_id,
    )
    db.add(account)
    await asyncio.to_thread(db.commit)

    def _refresh():
        db.refresh(account)
        app_cache.bump_version(app_cache.NS_EMAIL_ACCOUNTS)
        return account
    return await asyncio.to_thread(_refresh)


@router.get("/{account_id}", response_model=EmailAccountOut)
async def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        return db.query(EmailAccount).filter(EmailAccount.id == account_id).first()

    account = await asyncio.to_thread(_query)
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return account


@router.put("/{account_id}", response_model=EmailAccountOut)
async def update_account(
    account_id: int,
    data: EmailAccountUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        return db.query(EmailAccount).filter(EmailAccount.id == account_id).first()

    account = await asyncio.to_thread(_query)
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_encrypted"] = encrypt_password(update_data.pop("password"))

    for key, value in update_data.items():
        setattr(account, key, value)

    await asyncio.to_thread(db.commit)

    def _refresh():
        db.refresh(account)
        app_cache.bump_version(app_cache.NS_EMAIL_ACCOUNTS)
        return account
    return await asyncio.to_thread(_refresh)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        db.delete(account)
        db.commit()
        app_cache.bump_version(app_cache.NS_EMAIL_ACCOUNTS)

    await asyncio.to_thread(_query)


@router.post("/{account_id}/test")
async def test_connection(
    account_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        return db.query(EmailAccount).filter(EmailAccount.id == account_id).first()

    account = await asyncio.to_thread(_query)
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    mail = await poller.connect_account(account)
    if not mail:
        raise HTTPException(status_code=400, detail="No se pudo conectar al servidor IMAP")
    try:
        await asyncio.to_thread(mail.logout)
    except Exception:
        pass
    return {"message": "Conexión exitosa", "email": account.email}


@router.post("/{account_id}/poll")
async def poll_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        return db.query(EmailAccount).filter(EmailAccount.id == account_id).first()

    account = await asyncio.to_thread(_query)
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    await poller.process_account(account_id, db)

    def _recent():
        return db.query(VerificationCode).filter(
            VerificationCode.email_account_id == account_id,
        ).order_by(VerificationCode.received_at.desc()).limit(5).all()

    new_codes = await asyncio.to_thread(_recent)
    return {
        "message": "Verificación completada",
        "email": account.email,
        "recent_codes": [
            {"id": c.id, "code": c.code, "received_at": c.received_at.isoformat()}
            for c in new_codes
        ],
    }