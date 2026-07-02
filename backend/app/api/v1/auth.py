import asyncio
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.auth import (
    DUMMY_BCRYPT_HASH,
    create_access_token, get_password_hash, verify_password,
    get_current_user,
)
from app.auth.dependencies import client_ip
from app.config import settings
from app.db.database import get_db
from app.models import User
from app.schemas import LoginResponse, PasswordChange, Token, UserCreate
from app.services.rate_limit import (
    check_login_allowed, record_login_failure, record_login_success,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=LoginResponse)
async def login(
    form_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    ip = client_ip(request)

    allowed, retry_after = check_login_allowed(ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiados intentos. Probá de nuevo en {retry_after} segundos.",
            headers={"Retry-After": str(retry_after)},
        )

    def _query():
        return db.query(User).filter(User.username == form_data.username).first()

    user = await asyncio.to_thread(_query)

    if user is None:
        verify_password(form_data.password, DUMMY_BCRYPT_HASH)
        record_login_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    if not verify_password(form_data.password, user.password_hash):
        record_login_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    record_login_success(ip)

    access_token = create_access_token(
        data={"sub": user.username, "is_admin": user.is_admin},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        must_change_password=user.must_change_password,
        is_admin=user.is_admin,
    )


@router.get("/me")
async def get_me(
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    def _query():
        return (
            db.query(User)
            .filter(User.username == payload.get("sub"))
            .first()
        )

    user = await asyncio.to_thread(_query)
    must_change = user.must_change_password if user else False
    return {
        "sub": payload.get("sub"),
        "is_admin": payload.get("is_admin", False),
        "exp": payload.get("exp"),
        "must_change_password": must_change,
    }


@router.post("/change-password")
async def change_password(
    body: PasswordChange,
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    def _query():
        return (
            db.query(User)
            .filter(User.username == payload.get("sub"))
            .first()
        )

    user = await asyncio.to_thread(_query)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual es incorrecta",
        )

    if body.old_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser diferente de la actual",
        )

    user.password_hash = get_password_hash(body.new_password)
    user.must_change_password = False
    await asyncio.to_thread(db.commit)

    return {"message": "Contraseña actualizada", "must_change_password": False}


@router.post("/setup")
async def setup_admin(
    request: Request,
    db: Session = Depends(get_db),
    x_bootstrap_token: str | None = Header(default=None),
):
    if settings.vericode_env == "production" and not settings.bootstrap_token:
        raise HTTPException(status_code=404, detail="Not Found")

    if settings.bootstrap_token:
        if not x_bootstrap_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bootstrap token requerido",
                headers={"WWW-Authenticate": "Bootstrap"},
            )
        if not secrets.compare_digest(x_bootstrap_token, settings.bootstrap_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bootstrap token inválido",
            )

    def _lookup():
        return db.query(User).filter(User.username == "admin").first()

    existing = await asyncio.to_thread(_lookup)
    if existing:
        if not existing.is_admin:
            existing.is_admin = True
            await asyncio.to_thread(db.commit)
        return {
            "message": "Admin ya existe",
            "username": existing.username,
            "must_change_password": existing.must_change_password,
        }

    try:
        temp_password = secrets.token_urlsafe(18)
        admin = User(
            username="admin",
            password_hash=get_password_hash(temp_password),
            is_admin=True,
            must_change_password=True,
        )
        db.add(admin)
        await asyncio.to_thread(db.commit)

        def _refresh():
            db.refresh(admin)
            return admin

        await asyncio.to_thread(_refresh)
        return {
            "message": "Admin creado. Guardá el password temporal y cambialo en el primer login.",
            "username": admin.username,
            "temporary_password": temp_password,
            "must_change_password": True,
        }
    except IntegrityError:
        await asyncio.to_thread(db.rollback)
        return {"message": "Admin ya existe (carrera)", "username": "admin"}


@router.post("/_test/reset-rate-limit")
def test_reset_rate_limit():
    if settings.vericode_env == "production":
        raise HTTPException(status_code=404, detail="Not Found")
    from app.services.rate_limit import reset_login_limiter
    reset_login_limiter()
    return {"message": "Rate-limit reseteado"}