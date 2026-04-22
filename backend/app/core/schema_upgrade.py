from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_table_columns(engine: Engine, table_name: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def ensure_runtime_schema_compatibility(engine: Engine) -> None:
    if not str(engine.url).startswith("sqlite"):
        return

    columns = _sqlite_table_columns(engine, "knowledge_items")
    if not columns:
        return

    statements: list[str] = []
    if "sap_module" not in columns:
        statements.append("ALTER TABLE knowledge_items ADD COLUMN sap_module VARCHAR(64)")
    if "sap_module_source" not in columns:
        statements.append("ALTER TABLE knowledge_items ADD COLUMN sap_module_source VARCHAR(16)")
    if "links_note" not in columns:
        statements.append("ALTER TABLE knowledge_items ADD COLUMN links_note TEXT")

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_knowledge_items_sap_module ON knowledge_items (sap_module)"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_knowledge_items_sap_module_source ON knowledge_items (sap_module_source)")
        )
