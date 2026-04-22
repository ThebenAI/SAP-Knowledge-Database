# SAP Knowledge Tool (MVP)

## 1) Project Overview

SAP Knowledge Tool is an internal MVP for turning SAP-related documents into structured, reviewable knowledge.

Core workflow:
1. Upload a `.docx`, `.xlsx`, or `.pdf` document.
2. Parse the document by file type into raw candidate content with source references.
3. Extract SAP knowledge candidates (table mentions, field mentions, relationship hints).
4. Store extracted items in the database with `verification_status = pending`.
5. Review items in the UI and mark them as `verified`, `rejected`, or `needs_revision`.

Stack:
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL-ready (default local SQLite for quick start)
- Frontend: React + Vite + TypeScript

## 2) Backend Setup Instructions

From repository root:

```bash
cd backend
python -m venv .venv
```

Activate venv:
- Windows PowerShell:
```bash
.venv\Scripts\Activate.ps1
```
- macOS/Linux:
```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 3) Frontend Setup Instructions

From repository root:

```bash
cd frontend
npm install
```

## 4) Environment Variables

Backend supports:

- `DATABASE_URL`
  - Default: `sqlite:///./sap_knowledge.db`
  - PostgreSQL example: `postgresql+psycopg2://user:password@localhost:5432/sap_knowledge`
- `UPLOAD_DIR`
  - Default: `uploaded_documents`

You can create `backend/.env` from `backend/.env.example`.

## 5) How to Run Both Apps Locally

### Start backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Backend API base URL:
- `http://localhost:8000/api`

### Start frontend

In a second terminal:

```bash
cd frontend
npm run dev
```

Frontend URL:
- `http://localhost:5173`

## 6) Example Test Flow (One Uploaded File)

1. Open `http://localhost:5173/upload`.
2. Upload one SAP document (for example a `.pdf`).
3. Confirm response shows:
   - `document_id`
   - `filename`
   - `knowledge_items_created` (greater than or equal to 0)
4. Open `http://localhost:5173/review`.
5. Filter `verification_status = pending`.
6. Open an item detail page.
7. Confirm detail shows:
   - `verification_status`
   - `source_ref` (e.g. `page:3`, `paragraph:7`, `sheet:Mapping:row:4`)
   - `confidence` (percent format)
   - `extracted_data` JSON
8. Submit one review action with reviewer and optional comment.
9. Confirm item status and review metadata update.

## 7) Current Limitations of the MVP

- Extraction is rules/pattern based and intentionally simple (no LLM/NLP pipeline yet).
- No authentication/authorization; reviewer identity is free-text input.
- Basic parser handling only for `.docx`, `.xlsx`, `.pdf`.
- No asynchronous job queue for large file processing.
- No deduplication/versioning of extracted knowledge items.
- No document preview in UI; only stored references and extracted content.

## 8) Next Recommended Improvements

1. Add Alembic migrations for schema/version management.
2. Add authentication and role-based review permissions.
3. Add async processing (Celery/RQ/BackgroundTasks) for large files.
4. Improve extraction quality with richer SAP-specific heuristics and validation.
5. Add pagination/sorting to review list.
6. Add audit trail for review status transitions.
7. Add test suite (unit + integration + API contract tests).
8. Add document-source viewer jump links where possible.

---

## API Notes

### Allowed `verification_status` values
- `pending`
- `verified`
- `rejected`
- `needs_revision`

### Allowed `item_type` values
- `table_mention`
- `field_mention`
- `relationship_hint`

### Confidence format (standardized)
- Stored as decimal float in the backend, range `0.00` to `1.00`.
- Frontend displays confidence as percentage (for example `0.75` -> `75%`).

---

## Local Test Checklist (Short)

- [ ] Start backend (`uvicorn app.main:app --reload --port 8000`)
- [ ] Start frontend (`npm run dev`)
- [ ] Upload one `.docx`, one `.xlsx`, and one `.pdf`
- [ ] Verify knowledge items are created after each upload
- [ ] Filter pending items on review list
- [ ] Open one knowledge item detail page
- [ ] Verify one item (with reviewer + optional comment)
- [ ] Reject one item (with reviewer + optional comment)
- [ ] Mark one item as `needs_revision` (with reviewer + optional comment)
