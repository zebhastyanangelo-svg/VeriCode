import asyncio
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session, joinedload

from app.auth.auth import get_current_user
from app.auth.dependencies import (
    require_no_password_change,
    validate_websocket_auth,
)
from app.core import cache as app_cache
from app.core.headers import cache_control_headers, etag_headers
from app.db.database import get_db
from app.models import VerificationCode
from app.schemas import VerificationCodeOut

router = APIRouter(prefix="/codes", tags=["codes"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    def register(self, websocket: WebSocket):
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

    async def send_new_code(self, code_data: dict):
        await self.broadcast({
            "type": "new_code",
            "data": code_data,
        })

    async def send_error(self, websocket: WebSocket, detail: str):
        try:
            await websocket.send_json({"type": "error", "detail": detail})
        except Exception:
            pass


manager = ConnectionManager()


def _to_out(c) -> dict:
    return VerificationCodeOut(
        id=c.id,
        email_account_id=c.email_account_id,
        platform_id=c.platform_id,
        sender=c.sender,
        subject=c.subject,
        code=c.code,
        is_read=c.is_read,
        is_delivered=c.is_delivered,
        delivered_to=c.delivered_to,
        delivered_at=c.delivered_at,
        received_at=c.received_at,
        created_at=c.created_at,
        email=c.email_account.email if c.email_account else None,
        platform_name=c.platform.display_name if c.platform else None,
        platform_icon=c.platform.icon if c.platform else None,
    )


@router.get("", response_model=List[VerificationCodeOut],
            dependencies=[Depends(require_no_password_change)])
async def list_codes(
    q: str = Query(None, description="Buscar por código, remitente o asunto"),
    platform_id: int = Query(None),
    email_account_id: int = Query(None),
    is_delivered: bool = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        query = db.query(VerificationCode).options(
            joinedload(VerificationCode.email_account),
            joinedload(VerificationCode.platform),
        )
        if q:
            like = f"%{q}%"
            query = query.filter(
                VerificationCode.code.ilike(like) |
                VerificationCode.sender.ilike(like) |
                VerificationCode.subject.ilike(like)
            )
        if platform_id is not None:
            query = query.filter(VerificationCode.platform_id == platform_id)
        if email_account_id is not None:
            query = query.filter(VerificationCode.email_account_id == email_account_id)
        if is_delivered is not None:
            query = query.filter(VerificationCode.is_delivered == is_delivered)
        return query.order_by(VerificationCode.received_at.desc()).offset(offset).limit(limit).all()

    codes = await asyncio.to_thread(_query)
    return [_to_out(c) for c in codes]


@router.get("/recent", response_model=List[VerificationCodeOut],
            dependencies=[Depends(require_no_password_change)])
async def recent_codes(
    minutes: int = Query(5, description="Últimos N minutos"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        since = datetime.utcnow() - timedelta(minutes=minutes)
        return db.query(VerificationCode).options(
            joinedload(VerificationCode.email_account),
            joinedload(VerificationCode.platform),
        ).filter(
            VerificationCode.received_at >= since
        ).order_by(VerificationCode.received_at.desc()).limit(50).all()

    codes = await asyncio.to_thread(_query)
    return [_to_out(c) for c in codes]


@router.get("/stats",
            dependencies=[Depends(require_no_password_change)])
async def code_stats(
    response: Response,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Agregaciones del dashboard (total/unread/undelivered/last_hour).

    Cacheado in-process por 30s con stale-while-revalidate **sin lock**
    (ver `core.cache`). Invalidado por `bump_version(NS_CODES_STATS)` en
    mark_delivered / mark_read. El polling IMAP NO invalida — los
    contadores pueden quedar stale hasta 30s después de un código nuevo,
    pero el WS ya entregó el código al cliente por canal independiente;
    los contadores se reconcilian dentro del TTL.

    Cache-Control: private, max-age=5 para que el navegador no sirva el
    mismo snapshot más de 5s; el backend igual sirve 30s y el cliente se
    Reconcilia con invalidateQueries de React Query.
    """
    def _compute_stats():
        row = db.query(
            func.count().label('total'),
            func.sum((VerificationCode.is_read == False).cast(Integer)).label('unread'),
            func.sum((VerificationCode.is_delivered == False).cast(Integer)).label('undelivered'),
            func.sum((VerificationCode.received_at >= datetime.utcnow() - timedelta(hours=1)).cast(Integer)).label('last_hour'),
        ).one()
        return {
            "total": row.total,
            "unread": row.unread or 0,
            "undelivered": row.undelivered or 0,
            "last_hour": row.last_hour or 0,
        }

    payload = app_cache.get_or_compute(
        app_cache.NS_CODES_STATS,
        ttl_seconds=30,
        compute_fn=_compute_stats,
    )
    cache_control_headers(response, max_age_seconds=5, private=True)
    etag_headers(response, app_cache.NS_CODES_STATS)
    return payload


@router.put("/{code_id}/deliver",
           dependencies=[Depends(require_no_password_change)])
async def mark_delivered(
    code_id: int,
    delivered_to: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        code = db.query(VerificationCode).filter(VerificationCode.id == code_id).first()
        if not code:
            raise HTTPException(status_code=404, detail="Código no encontrado")
        code.is_delivered = True
        code.delivered_to = delivered_to
        code.delivered_at = datetime.utcnow()
        db.commit()
        return {"message": "Código marcado como entregado"}

    result = await asyncio.to_thread(_query)
    # Invalida stats (undelivered--> delivered cambia el contador).
    app_cache.bump_version(app_cache.NS_CODES_STATS)
    return result


@router.put("/{code_id}/read",
           dependencies=[Depends(require_no_password_change)])
async def mark_read(
    code_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    def _query():
        code = db.query(VerificationCode).filter(VerificationCode.id == code_id).first()
        if not code:
            raise HTTPException(status_code=404, detail="Código no encontrado")
        code.is_read = True
        db.commit()
        return {"message": "Código marcado como leído"}

    result = await asyncio.to_thread(_query)
    # Invalida stats (unread--> read cambia el contador).
    app_cache.bump_version(app_cache.NS_CODES_STATS)
    return result


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        await websocket.accept()
        payload, error = await validate_websocket_auth(token, db)
        if error is not None:
            await manager.send_error(websocket, error["detail"])
            await websocket.close(code=error["code"])
            return
    finally:
        try:
            db.close()
        except Exception:
            pass

    websocket.username = payload.get("sub", "unknown")
    manager.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


async def broadcast_new_code(code_data: dict):
    await manager.send_new_code(code_data)