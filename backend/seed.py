"""Script opcional para sembrar plataformas por defecto.

ADVERTENCIA: desde la versión con admin auto-seed, este script solo agrega
plataformas si la tabla está vacía. Los usuarios ahora se crean en el
`lifespan` de `app.main` automáticamente."""

from app.db.database import SessionLocal, Base, engine
from app.models import Platform
from app.auth.auth import get_password_hash
from app.models import User

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    # Asegurar admin si la BD está vacía (idempotente con el lifespan)
    if db.query(User).count() == 0:
        admin = User(username="admin", password_hash=get_password_hash("admin123"), is_admin=True)
        db.add(admin)
        db.commit()
        print("✅ Admin creado: admin / admin123")

    existing = db.query(Platform).count()
    if existing == 0:
        platforms = [
            Platform(name="netflix", display_name="Netflix", provider_type="streaming", icon="netflix"),
            Platform(name="disney_plus", display_name="Disney+", provider_type="streaming", icon="disney"),
            Platform(name="hbo_max", display_name="HBO Max", provider_type="streaming", icon="hbo"),
            Platform(name="prime_video", display_name="Prime Video", provider_type="streaming", icon="prime"),
            Platform(name="spotify", display_name="Spotify", provider_type="streaming", icon="spotify"),
            Platform(name="chatgpt", display_name="ChatGPT", provider_type="ai", icon="openai"),
            Platform(name="claude", display_name="Claude AI", provider_type="ai", icon="anthropic"),
            Platform(name="midjourney", display_name="Midjourney", provider_type="ai", icon="midjourney"),
            Platform(name="paramount", display_name="Paramount+", provider_type="streaming", icon="paramount"),
            Platform(name="google", display_name="Google", provider_type="google", icon="google"),
        ]
        for p in platforms:
            db.add(p)
        db.commit()
        print(f"✅ {len(platforms)} plataformas creadas")
    else:
        print(f"ℹ️  {existing} plataformas ya existen")

    existing_accounts = db.query(Platform).count()
    print(f"✅ Seed completado.")
finally:
    db.close()


if __name__ == "__main__":
    pass  # Cuerpo ejecutado al cargar como script (para evitar side-effects al import)
