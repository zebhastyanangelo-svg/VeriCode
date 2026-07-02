import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.auth import get_current_user
from app.auth.dependencies import require_no_password_change
from app.core import cache as app_cache
from app.core.headers import cache_control_headers, etag_headers
from app.db.database import get_db
from app.models import Platform
from app.schemas import PlatformCreate, PlatformUpdate, PlatformOut

router = APIRouter(
    prefix="/platforms",
    tags=["platforms"],
    dependencies=[Depends(require_no_password_change)],
)


@router.get("", response_model=List[PlatformOut])
async def list_platforms(
    response: Response,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Lista de plataformas (admin).

    Cacheado 60s in-process. Se invalida con `bump_version(NS_PLATFORMS)`
    en cada POST/PUT/DELETE — esos handlers también invalidan el cache
    público porque ambos comparten el mismo namespace.
    """
    def _compute():
        return db.query(Platform).order_by(Platform.name).all()

    payload = app_cache.get_or_compute(
        app_cache.NS_PLATFORMS, ttl_seconds=60, compute_fn=_compute,
    )
    cache_control_headers(response, max_age_seconds=30, private=True)
    etag_headers(response, app_cache.NS_PLATFORMS)
    return payload


@router.post("", response_model=PlatformOut, status_code=status.HTTP_201_CREATED)
async def create_platform(
    data: PlatformCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _check():
        return db.query(Platform).filter(Platform.name == data.name).first()

    existing = await asyncio.to_thread(_check)
    if existing:
        raise HTTPException(status_code=400, detail="Esta plataforma ya existe")

    platform = Platform(**data.model_dump())
    db.add(platform)
    await asyncio.to_thread(db.commit)

    def _refresh():
        db.refresh(platform)
        app_cache.bump_version(app_cache.NS_PLATFORMS)
        return platform
    return await asyncio.to_thread(_refresh)


@router.put("/{platform_id}", response_model=PlatformOut)
async def update_platform(
    platform_id: int,
    data: PlatformUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        return db.query(Platform).filter(Platform.id == platform_id).first()

    platform = await asyncio.to_thread(_query)
    if not platform:
        raise HTTPException(status_code=404, detail="Plataforma no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(platform, key, value)

    await asyncio.to_thread(db.commit)

    def _refresh():
        db.refresh(platform)
        app_cache.bump_version(app_cache.NS_PLATFORMS)
        return platform
    return await asyncio.to_thread(_refresh)


@router.delete("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform(
    platform_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        platform = db.query(Platform).filter(Platform.id == platform_id).first()
        if not platform:
            raise HTTPException(status_code=404, detail="Plataforma no encontrada")
        db.delete(platform)
        db.commit()
        app_cache.bump_version(app_cache.NS_PLATFORMS)

    await asyncio.to_thread(_query)