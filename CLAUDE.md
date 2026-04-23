# CLAUDE.md — SAP Knowledge Tool

## 1. Projektübersicht

Das SAP Knowledge Tool ist ein internes MVP, das SAP-bezogene Dokumente in strukturiertes, überprüfbares Wissen umwandelt.

**Kernworkflow:**
1. Nutzer lädt ein Dokument hoch (`.docx`, `.xlsx`, `.pdf`).
2. Das Backend parst die Datei und extrahiert SAP-Kandidaten (Tabellennamen, Felder, Relationen) regelbasiert per Regex.
3. Extrahierte Items werden mit `verification_status = pending` in der Datenbank gespeichert.
4. Reviewer sichten die Items im UI und markieren sie als `verified`, `rejected` oder `needs_revision`.

**Zielgruppe:** Interne SAP-Berater und Reviewer, die Dokumentenwissen strukturiert erfassen wollen.

---

## 2. Architektur & Tech-Stack

```
project-root/
├── backend/      Python FastAPI + SQLAlchemy
└── frontend/     React 18 + TypeScript + Vite
```

### Backend
| Komponente | Technologie |
|---|---|
| Framework | FastAPI + Uvicorn |
| ORM / DB | SQLAlchemy, SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT via python-jose, Passwort-Hashing mit bcrypt |
| Dokument-Parsing | python-docx, openpyxl, pypdf |
| Konfiguration | pydantic-settings, `.env`-Datei |

### Frontend
| Komponente | Technologie |
|---|---|
| Framework | React 18.3 + TypeScript 5.6 |
| Build | Vite 5.4 |
| Routing | react-router-dom 6 |
| Styling | Plain CSS (kein CSS-Framework) |
| State | React Hooks (useState, useEffect, useCallback) |

### Datenmodell-Kern: `KnowledgeItem`
- `item_type`: `table_mention` | `field_mention` | `relationship_hint`
- `verification_status`: `pending` → `verified` | `rejected` | `needs_revision`
- `confidence`: Float 0.0–1.0 (Frontend zeigt Prozent)
- `sap_module`: Inferred (FI, MM, SD, CO, …) oder manuell gesetzt
- `extracted_data`: JSON-Blob mit Tabellen, Feldern, Join-Infos

---

## 3. Wichtigste Dateien und ihre Funktion

### Backend
| Datei | Funktion |
|---|---|
| `backend/app/main.py` | FastAPI-Einstiegspunkt: CORS, Routes, DB-Bootstrap, Admin-Erstellung |
| `backend/app/core/config.py` | Settings via pydantic-settings (DB-URL, JWT-Secret, Bootstrap-Admin) |
| `backend/app/core/database.py` | SQLAlchemy Engine & Session-Setup |
| `backend/app/models/knowledge_item.py` | Kern-Datenmodell mit Status-Enum und extracted_data JSON |
| `backend/app/models/document.py` | Hochgeladenes Dokument, 1:N zu KnowledgeItem |
| `backend/app/models/user.py` | User-Modell mit Rollen (admin/reviewer) |
| `backend/app/parsers/factory.py` | Wählt Parser nach Dateiendung |
| `backend/app/parsers/docx_parser.py` | Word-Dokumente: Text + Tabellen + Sektions-Kontext |
| `backend/app/parsers/xlsx_parser.py` | Excel: strukturierte Spalten-Extraktion |
| `backend/app/parsers/pdf_parser.py` | PDF: Text-Extraktion seitenweise |
| `backend/app/services/import_service.py` | Orchestriert Upload → Parsing → Extraktion → DB-Insert |
| `backend/app/services/extraction_service.py` | Regelbasierte Erkennung (Regex), Confidence-Scores |
| `backend/app/services/sap_module_inference_service.py` | Mappt erkannte Entities auf SAP-Module |
| `backend/app/api/routes/knowledge_items.py` | CRUD + verify/reject/needs-revision/backfill Endpoints |
| `backend/app/api/routes/imports.py` | `POST /api/import/files` — Datei-Upload-Endpoint |
| `backend/app/api/routes/auth.py` | Login, Token-Refresh |
| `backend/app/api/routes/users.py` | Admin: User-Verwaltung |

### Frontend
| Datei | Funktion |
|---|---|
| `frontend/src/App.tsx` | Routing, Auth-State, rollenbasierte Zugriffskontrolle |
| `frontend/src/pages/FolderImportPage.tsx` | Datei-Upload-Formular + Ergebnis-Anzeige |
| `frontend/src/pages/ReviewListPage.tsx` | Haupt-Review-Dashboard mit Filter/Suche |
| `frontend/src/pages/KnowledgeItemDetailPage.tsx` | Einzelitem-Ansicht mit Review-Aktionen |
| `frontend/src/pages/LoginPage.tsx` | JWT-Login-UI |
| `frontend/src/pages/UserManagementPage.tsx` | Admin-only: User CRUD |
| `frontend/src/api/client.ts` | Basis-HTTP-Client mit JWT Bearer Token |
| `frontend/src/api/knowledgeItems.ts` | API-Client für Knowledge-Item-Endpoints |
| `frontend/src/api/imports.ts` | API-Client für Datei-Upload |
| `frontend/src/api/auth.ts` | Login/Logout/User-Fetch |
| `frontend/src/types/api.ts` | TypeScript-Typen passend zu Backend-Schemas |

---

## 4. Entwicklungsworkflow (lokales Starten)

### Voraussetzungen
- Python 3.10+
- Node.js 18+

### Backend starten

```bash
cd backend
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Optional: .env anlegen
cp .env.example .env

uvicorn app.main:app --reload --port 8000
```

Backend läuft unter: `http://localhost:8000/api`
API-Docs (Swagger): `http://localhost:8000/docs`

### Frontend starten (zweites Terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend läuft unter: `http://localhost:5173`

### Standard-Admin-Zugangsdaten (lokal)
- Benutzername: `admin`
- Passwort: `admin123`
- **Sofort ändern** in `.env` via `BOOTSTRAP_ADMIN_PASSWORD` für jede Nicht-Dev-Umgebung.

### Umgebungsvariablen (Backend `.env`)
| Variable | Default | Beschreibung |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./sap_knowledge.db` | PostgreSQL: `postgresql+psycopg2://user:pw@host:5432/db` |
| `AUTH_SECRET_KEY` | `change-me-in-production` | JWT-Signing-Secret — in Prod unbedingt setzen |
| `BOOTSTRAP_ADMIN_USERNAME` | `admin` | Initialer Admin-User |
| `BOOTSTRAP_ADMIN_PASSWORD` | `admin123` | Initiales Admin-Passwort |
| `USE_LLM_ENHANCEMENT` | `false` | LLM-Hybrid-Schritt aktivieren (`true`/`false`) |
| `ANTHROPIC_API_KEY` | _(leer)_ | API-Key für Claude — erforderlich wenn `USE_LLM_ENHANCEMENT=true` |

---

## 5. Code-Konventionen

### Allgemein
- **Sprache im Code:** Englisch (Variablen, Funktionen, Kommentare, Commit-Messages).
- **Sprache in der UI:** Deutsch (Labels, Buttons, Fehlermeldungen für Endnutzer).
- Kommentare nur wenn das *Warum* nicht offensichtlich ist — kein Beschreiben des *Was*.

### Backend (Python)
- PEP 8, snake_case für Funktionen und Variablen, PascalCase für Klassen.
- Pydantic-Schemas für alle API-Request/Response-Typen.
- Services (`services/`) kapseln Geschäftslogik — kein Datenbankcode direkt in Routes.
- Neue Parsers müssen `base.py:DocumentParser` implementieren und in `factory.py` registriert werden.
- Neue Endpoints gehören in `api/routes/`, nicht in `main.py`.

### Frontend (TypeScript/React)
- Strikte TypeScript-Typen — kein `any`.
- API-Calls ausschließlich über Funktionen in `src/api/` — niemals direktes `fetch` in Komponenten.
- Komponenten-State über React Hooks, kein globaler State-Manager.
- Kein CSS-Framework einführen ohne Absprache.

### Git
- Branch-Namensschema: `feature/<kurzbeschreibung>`, `fix/<kurzbeschreibung>`
- Commit-Messages auf Englisch, im Imperativ: `feat: add PDF pagination`, `fix: correct confidence rounding`

---

## 6. Was Claude niemals tun soll

- **Niemals direkt auf `main` pushen** — immer über einen Feature-Branch und Pull Request.
- **Niemals verifizierte Knowledge Items löschen** — nur `rejected`-Items dürfen per Cleanup-Endpoint entfernt werden.
- **Niemals `AUTH_SECRET_KEY` oder Passwörter in Code-Dateien hardcoden** — ausschließlich über `.env`.
- **Niemals die Datenbank ohne explizite Nutzerbestätigung droppen oder migrieren** — Schema-Änderungen erfordern Alembic-Migrations (noch nicht implementiert).
- **Niemals Mock-Daten oder Seed-Daten in die Produktionsdatenbank schreiben.**
- **Niemals den Bootstrap-Admin `admin123` in Nicht-Dev-Umgebungen belassen** — immer auf sicheres Passwort hinweisen.
- **Niemals Abhängigkeiten upgraden ohne Test** — insbesondere `bcrypt` (Pin auf 4.3.0 ist intentional).
- **Niemals CORS-Wildcards (`*`) einführen** — erlaubte Origins explizit in `main.py` pflegen.
- **Niemals Extraktion auf LLM-basiert umstellen ohne expliziten Auftrag** — die regelbasierte Logik ist bewusst gewählt und getestet.
- **Keine UI-Frameworks (z.B. Material UI, Tailwind) ohne Rücksprache** hinzufügen.
