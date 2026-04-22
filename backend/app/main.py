from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.imports import router as imports_router
from app.api.routes.knowledge_items import router as knowledge_items_router
from app.models.base import Base
from app.models.sap_module_lookup_cache import SapModuleLookupCache  # noqa: F401
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


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "SAP Knowledge Tool API is running"}


app.include_router(imports_router, prefix="/api")
app.include_router(knowledge_items_router, prefix="/api")
