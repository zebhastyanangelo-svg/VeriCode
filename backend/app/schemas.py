from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models import EmailType, ProviderType


class Token(BaseModel):
    access_token: str
    token_type: str


class LoginResponse(Token):
    """Respuesta extendida del endpoint /auth/token.

    `must_change_password` indica al frontend que debe mostrar la pantalla
    obligatoria antes de permitir acceso al panel (cambio de credencial
    inicial o pendiente por admin).
    """

    must_change_password: bool = False
    is_admin: bool = False


class TokenData(BaseModel):
    username: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6)


class PasswordChange(BaseModel):
    """Payload para POST /auth/change-password. Valida constraints básicas;

    la comparación old vs new se hace en el endpoint.
    """

    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    must_change_password: bool

    class Config:
        from_attributes = True


class EmailAccountCreate(BaseModel):
    email: str
    email_type: EmailType = EmailType.custom
    imap_host: Optional[str] = None
    imap_port: int = 993
    username: Optional[str] = None
    password: str
    notes: Optional[str] = None
    platform_id: Optional[int] = None


class EmailAccountUpdate(BaseModel):
    email: Optional[str] = None
    email_type: Optional[EmailType] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    platform_id: Optional[int] = None


class EmailAccountOut(BaseModel):
    id: int
    email: str
    email_type: EmailType
    imap_host: Optional[str] = None
    imap_port: int
    username: Optional[str] = None
    is_active: bool
    last_checked: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    platform_id: Optional[int] = None

    class Config:
        from_attributes = True


class PlatformCreate(BaseModel):
    name: str
    display_name: Optional[str] = None
    provider_type: ProviderType = ProviderType.streaming
    code_pattern: Optional[str] = None
    sender_pattern: Optional[str] = None
    subject_pattern: Optional[str] = None
    icon: Optional[str] = None


class PlatformUpdate(BaseModel):
    display_name: Optional[str] = None
    provider_type: Optional[ProviderType] = None
    code_pattern: Optional[str] = None
    sender_pattern: Optional[str] = None
    subject_pattern: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None


class PlatformOut(BaseModel):
    id: int
    name: str
    display_name: Optional[str] = None
    provider_type: ProviderType
    code_pattern: Optional[str] = None
    sender_pattern: Optional[str] = None
    subject_pattern: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class VerificationCodeOut(BaseModel):
    id: int
    email_account_id: int
    platform_id: Optional[int] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    code: str
    is_read: bool
    is_delivered: bool
    delivered_to: Optional[str] = None
    delivered_at: Optional[datetime] = None
    received_at: datetime
    created_at: datetime
    email: Optional[str] = None
    platform_name: Optional[str] = None
    platform_icon: Optional[str] = None

    class Config:
        from_attributes = True


class VerificationCodeSearch(BaseModel):
    q: Optional[str] = None
    platform_id: Optional[int] = None
    email_account_id: Optional[int] = None
    is_delivered: Optional[bool] = None
    limit: int = 50
    offset: int = 0
