from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps.auth import require_reviewer_or_admin
from app.api.routes.auth import router as auth_router
from app.api.routes.imports import router as imports_router
from app.api.routes.knowledge_items import router as knowledge_items_router
from app.api.routes.users import router as users_router
from app.core.bootstrap import ensure_bootstrap_admin
from app.core.database import SessionLocal
from app.models.base import Base
from app.models.sap_module_lookup_cache import SapModuleLookupCache  # noqa: F401
from app.models.user import User  # noqa: F401
from app.core.database import engine
from app.core.schema_upgrade import ensure_runtime_schema_compatibility

app = FastAPI(title="SAP Knowledge Tool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema_compatibility(engine)
    db = SessionLocal()
    try:
        ensure_bootstrap_admin(db)
    finally:
        db.close()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "SAP Knowledge Tool API is running"}


app.include_router(imports_router, prefix="/api", dependencies=[Depends(require_reviewer_or_admin)])
app.include_router(knowledge_items_router, prefix="/api", dependencies=[Depends(require_reviewer_or_admin)])
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
