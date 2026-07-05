import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Index, Integer, String, Text, JSON
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class EmailType(str, enum.Enum):
    gmail = "gmail"
    outlook = "outlook"
    yahoo = "yahoo"
    custom = "custom"


class ProviderType(str, enum.Enum):
    streaming = "streaming"
    ai = "ai"
    google = "google"
    other = "other"


class User(Base):
    """Usuario administrador para acceder al panel.
    Se persiste en BD para sobrevivir reinicios (antes era un dict en memoria)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    # Forzá cambio de password en el próximo login. Se activa en:
    # - Auto-seeds (seed_admin en main.py)
    # - /auth/setup (bootstrap inicial o reset)
    # - /auth/change-password la limpia tras cambio exitoso.
    must_change_password = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    __table_args__ = (
        Index('ix_email_account_is_active', 'is_active'),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    email_type = Column(Enum(EmailType), default=EmailType.custom, nullable=False)
    imap_host = Column(String(255), nullable=True)
    imap_port = Column(Integer, default=993)
    username = Column(String(255), nullable=True)
    password_encrypted = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    last_checked = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    codes = relationship("VerificationCode", back_populates="email_account", cascade="all, delete-orphan")
    platform = relationship("Platform", back_populates="email_accounts")


class Platform(Base):
    __tablename__ = "platforms"

    __table_args__ = (
        Index('ix_platform_is_active', 'is_active'),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(100), nullable=True)
    provider_type = Column(Enum(ProviderType), default=ProviderType.streaming)
    code_pattern = Column(String(500), nullable=True)
    sender_pattern = Column(String(500), nullable=True)
    subject_pattern = Column(String(500), nullable=True)
    icon = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    codes = relationship("VerificationCode", back_populates="platform")
    email_accounts = relationship("EmailAccount", back_populates="platform")


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    __table_args__ = (
        Index('ix_vc_lookup', 'email_account_id', 'platform_id', 'is_delivered', 'received_at'),
        Index('ix_vc_dupcheck', 'email_account_id', 'code', 'subject'),
        Index('ix_vc_email_account_id', 'email_account_id'),
        Index('ix_vc_platform_id', 'platform_id'),
        Index('ix_vc_received_at', 'received_at'),
        Index('ix_vc_is_delivered', 'is_delivered'),
    )

    id = Column(Integer, primary_key=True, index=True)
    email_account_id = Column(Integer, ForeignKey("email_accounts.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=True)
    sender = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=True)
    code = Column(String(100), nullable=False)
    raw_body = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    is_delivered = Column(Boolean, default=False)
    delivered_to = Column(String(255), nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    email_account = relationship("EmailAccount", back_populates="codes")
    platform = relationship("Platform", back_populates="codes")
