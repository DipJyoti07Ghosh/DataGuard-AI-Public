# 🛡️ DataGuard AI

**Industry Data Profiling & Data Quality Assistant**

An intelligent assistant that accepts datasets, automatically profiles them, performs data-quality checks, detects PII, classifies column-level risk using ML, detects anomalies, compares dataset versions for drift, and provides AI-powered natural-language explanations and remediation suggestions.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Recharts |
| Backend | Python + FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy 2.x + Alembic |
| Profiling | pandas + openpyxl |
| Quality | Great Expectations (Phase 5+) |
| PII | Microsoft Presidio (Phase 6+) |
| ML | scikit-learn (Phase 7+) |
| LLM | Ollama local models (Phase 12+) |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 16+ (Running on localhost:5432)

### 1. Database Setup

In **pgAdmin 4** or `psql`, ensure the user and database exist:

```sql
CREATE USER dataguard WITH PASSWORD 'dataguard_dev';
CREATE DATABASE dataguard_ai OWNER dataguard;
GRANT ALL PRIVILEGES ON DATABASE dataguard_ai TO dataguard;
```

Apply Alembic migrations:

```powershell
cd backend
.\venv\Scripts\alembic.exe upgrade head
```

### 2. Run Backend (FastAPI)

```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API Docs (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 3. Run Frontend (React + Vite)

```powershell
cd frontend
npm run dev
```

- Web Application: [http://localhost:5173](http://localhost:5173)
- Dataset Explorer: [http://localhost:5173/datasets](http://localhost:5173/datasets)
- Dataset Upload: [http://localhost:5173/upload](http://localhost:5173/upload)

---

## Dataset Versioning Architecture

DataGuard AI organizes uploads around **Logical Datasets** with sequential **Snapshot Versions**:

```
Customer Data (Dataset)
  ├── Version 1 (clean_sample.csv - 200 rows x 16 cols)
  ├── Version 2 (quality_issues_v1.csv - 257 rows x 16 cols)
  └── Version 3 (special_columns.csv - 3 rows x 5 cols)
```

- **Storage**: Physical files are safely saved in `backend/uploads/<uuid>_<sanitized_name>.<ext>` to prevent collisions and path traversal.
- **Metadata**: Row/column counts, detected dtypes, encodings, sheet names, nullability, and version numbers are persisted in PostgreSQL JSONB fields.
- **Downstream Ready**: `DatasetVersion` serves as the primary foreign key for Phase 4 profiling, Phase 5 quality issues, Phase 6 PII findings, and Phase 10 drift comparison.

---

## Project Status

| Phase | Description | Status |
|---|---|---|
| 0 | Repository inspection & planning | ✅ Complete |
| 1 | Project foundation | ✅ Complete |
| 2 | Dataset upload & ingestion | ✅ Complete |
| 3 | PostgreSQL database & versioning | ✅ Complete |
| 4 | Automated profiling | ⬜ Next Phase |
| 5 | Data quality engine | ⬜ Pending |
| 6 | PII detection | ⬜ Pending |
| 7 | ML risk classification | ⬜ Pending |
| 8 | Anomaly detection | ⬜ Pending |
| 9 | Quality scoring & remediation | ⬜ Pending |
| 10 | Version comparison & drift | ⬜ Pending |
| 11 | RAG pipeline | ⬜ Pending |
| 12 | Ollama LLM assistant | ⬜ Pending |
| 13 | Dashboard & visualizations | ⬜ Pending |
| 14 | AI chat interface | ⬜ Pending |
| 15 | Reports & export | ⬜ Pending |
| 16 | Integration testing | ⬜ Pending |
| 17 | Final polish & documentation | ⬜ Pending |

---

## License

Private — All rights reserved.
