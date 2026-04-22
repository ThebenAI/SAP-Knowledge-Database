from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User, UserRole


def ensure_bootstrap_admin(db: Session) -> None:
    has_user = db.query(User.id).first()
    if has_user is not None:
        return
    settings = get_settings()
    try:
        password_hash = hash_password(settings.bootstrap_admin_password)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid bootstrap admin password in config: {exc}"
        ) from exc
    admin = User(
        username=settings.bootstrap_admin_username.strip(),
        password_hash=password_hash,
        role=UserRole.admin,
        is_active=True,
    )
    db.add(admin)
    db.commit()
