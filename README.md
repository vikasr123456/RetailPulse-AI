# RetailPulse AI — Enterprise Retail Intelligence Platform

**AI-DRIVEN DEMAND FORECASTING FOR INDIAN RETAIL USING TIME SERIES LEARNING MODELS**

RetailPulse AI is an enterprise-style retail intelligence platform that connects retail data ingestion, data quality, demand analysis, ARIMA/LSTM forecasting, model evaluation, inventory risk, replenishment, reports, role governance and a grounded Retail Copilot.

> **Important:** This repository contains demo/development data and representative catalog data. It is not affiliated with Google or any of the global brands shown in the demo catalog.

---

## 1. Product architecture

```text
                         RETAILPULSE AI
                              │
                ┌─────────────┴─────────────┐
                │                           │
          DATA CONTROL PLANE           AI INTELLIGENCE
                │                           │
      CSV / Excel ingestion          ARIMA + LSTM
                │                           │
       Validate → Clean              Evaluation
                │                           │
             Analyze                 Forecast Studio
                │                           │
             Import                     Risk
                │                           │
          PostgreSQL                Inventory Advisor
                │                           │
      ┌─────────┼─────────┐         Restock Center
      │         │         │               │
   Products   Sales    Inventory          │
      │         │         │               │
      └─────────┴─────────┴───────┬───────┘
                                  │
                           DECISION LAYER
                                  │
                    Reports · Alerts · Scenarios
                                  │
                           Retail Copilot
                                  │
                           Business Actions
```

---

# 2. Technology stack

### Frontend

- React
- Vite
- React Router
- Responsive enterprise UI
- CSS-based ambient 3D effects
- Charts and KPI surfaces

### Backend

- Python 3.11
- FastAPI
- SQLAlchemy
- Pydantic
- PostgreSQL
- Psycopg
- Statsmodels / ARIMA
- TensorFlow / Keras / LSTM

### Database

- PostgreSQL 16+
- Tenant/store-aware relational model
- Product master
- Sales history
- Inventory
- Forecasts
- Forecast values
- Alerts
- Model metrics
- Data quality scores
- Audit logs

---

# 3. Project structure

```text
retailpulse-ai/
├── backend/
│   ├── app/
│   │   ├── forecasting/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── services.py
│   │   ├── auth.py
│   │   ├── db.py
│   │   ├── config.py
│   │   └── main.py
│   ├── scripts/
│   │   ├── migrate_enterprise_db.py
│   │   ├── seed_demo.py
│   │   └── seed_international_catalog.py
│   ├── tests/
│   ├── seed.py
│   └── requirements.txt
├── frontend/
│   ├── src/main.jsx
│   ├── src/styles.css
│   └── package.json
├── database/
│   └── manual/
│       ├── 01_create_role_and_database.sql
│       ├── 02_grant_schema_access.sql
│       └── 03_verify.sql
├── retailpulse_demo_2year.csv
├── DATABASE_MANUAL_SETUP.md
└── docker-compose.yml
```

---

# 4. Recommended Windows setup — manual PostgreSQL

If you want to run the database yourself with **PostgreSQL + pgAdmin**, follow:

**[`DATABASE_MANUAL_SETUP.md`](DATABASE_MANUAL_SETUP.md)**

The short version is:

```text
Install PostgreSQL
      ↓
Start PostgreSQL service
      ↓
Create role: retailpulse
      ↓
Create database: retailpulse
      ↓
Grant public schema access
      ↓
Create backend/.env
      ↓
Run SQLAlchemy migration
      ↓
Seed development data
      ↓
Start FastAPI
      ↓
Start React
```

### Database credentials for local development

```text
Host:     localhost
Port:     5432
Database: retailpulse
User:     retailpulse
Password: retailpulse
```

For a real deployment, **change the password** and use a secret manager.

---

# 5. Manual database — fastest path

### Step 1 — create the environment

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2 — configure PostgreSQL

```powershell
copy .env.example .env
```

Set:

```env
DATABASE_URL=postgresql+psycopg://retailpulse:retailpulse@localhost:5432/retailpulse
SECRET_KEY=replace-with-a-long-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### Step 3 — build the application schema

```powershell
python scripts/migrate_enterprise_db.py
```

### Step 4 — seed development data

```powershell
python seed.py
```

### Step 5 — optionally add the representative international catalog

```powershell
python scripts/seed_international_catalog.py
```

### Step 6 — start backend

```powershell
uvicorn app.main:app --reload --port 8000
```

### Step 7 — start frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

---

# 6. Docker database alternative

If you do not want to install PostgreSQL manually:

```powershell
docker compose up -d postgres
```

Then continue from the backend migration step.

---

# 7. Demo accounts

```text
OWNER     owner@retailpulse.ai / owner123
MANAGER   manager@retailpulse.ai / manager123
STAFF     staff@retailpulse.ai / staff123
ANALYST   analyst@retailpulse.ai / analyst123
CUSTOMER  customer@retailpulse.ai / customer123
```

These are development credentials only.

---

# 8. Dataset workflow

Use:

```text
retailpulse_demo_2year.csv
```

It contains:

```text
8,772 rows
12 products
2024-01-01 → 2025-12-31
0 missing values
0 duplicate rows
```

Columns:

```text
date
product_id
product_name
category
units_sold
inventory
```

Application workflow:

```text
UPLOAD
  ↓
VALIDATE
  ↓
CLEAN
  ↓
ANALYZE
  ↓
IMPORT
  ↓
POSTGRESQL VERIFICATION
  ↓
PRODUCT MASTER
  ↓
FORECASTING
  ↓
INVENTORY
  ↓
REPORTS
  ↓
COPILOT
```

---

# 9. Enterprise UI

The UI is intentionally designed as an **AI retail operating platform**.

Core screens:

- Command Center
- Global Product Catalog
- Data Intelligence
- Forecast Studio
- ARIMA Lab
- LSTM Lab
- Model Evaluation
- Seasonality & Anomalies
- Inventory Intelligence
- Restock Center
- Scenario Planner
- Action Center
- Reports & Analytics
- Retail Copilot
- Settings & Access

The left navigation is independently scrollable so all features remain reachable on smaller laptop displays.

---

# 10. Database verification

After migration, verify from Python:

```powershell
python -c "from app.db import engine; print(engine.connect().exec_driver_sql('select current_database(), current_user').fetchone())"
```

Expected:

```text
('retailpulse', 'retailpulse')
```

In pgAdmin, verify tables under:

```text
Databases
└── retailpulse
    └── Schemas
        └── public
            └── Tables
```

Expected application tables include:

```text
tenants
stores
users
products
sales
inventory
forecasts
forecast_values
alerts
model_metrics
data_quality_scores
audit_logs
```

---

# 11. Development database reset

`backend/seed.py` is a **destructive development reset**.

On PostgreSQL it performs:

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
```

and then recreates the SQLAlchemy schema and demo data.

Use it only when you intentionally want a fresh development database.

**Never run it against production.**

---

# 12. API documentation

Once FastAPI is running:

```text
http://127.0.0.1:8000/docs
```

Health endpoint:

```text
http://127.0.0.1:8000/api/v1/health
```

---

# 13. Testing

Backend tests:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

Frontend production build:

```powershell
cd frontend
npm install
npm run build
```

Smoke test:

```powershell
cd ..
python e2e/smoke_test.py
```

---

# 14. Windows TensorFlow note

TensorFlow installations can fail because of Windows path-length limitations.

Prefer a short project directory:

```text
C:\RetailPulse
```

instead of a deeply nested Downloads path.

If Windows long paths are disabled, enable them before reinstalling TensorFlow.

---

# 15. Production hardening roadmap

For a real commercial deployment, the next engineering layer should include:

1. Alembic versioned migrations
2. Managed PostgreSQL
3. Redis + Celery/background workers
4. Object storage for uploaded datasets
5. Production identity provider / OAuth / SSO
6. Secret manager
7. TLS everywhere
8. Rate limiting
9. Structured logging
10. OpenTelemetry metrics/tracing
11. Database backups and point-in-time recovery
12. Row-level tenant isolation
13. Immutable audit logs
14. Model registry
15. Forecast drift monitoring
16. Data drift monitoring
17. CI/CD
18. Containerized deployment
19. Kubernetes or managed container platform
20. Automated security scanning

---

# 16. Product positioning

RetailPulse AI should be demonstrated as:

> **An AI-powered retail operating platform that transforms transactional data into demand forecasts, inventory risk signals, replenishment recommendations, business reports and grounded decision intelligence.**

The strongest product story is:

```text
OBSERVE
  ↓
UNDERSTAND
  ↓
FORECAST
  ↓
ASSESS RISK
  ↓
RECOMMEND ACTION
  ↓
EXECUTE
  ↓
MEASURE
```

The UI should support this workflow instead of becoming a collection of decorative dashboards.


## Simple User Experience

RetailPulse includes **Simple mode** for non-technical shop users. It provides larger labels, plain-language navigation, direct Sunny answers, optional browser voice input and data-backed charts.
#   R e t a i l P u l s e - A I 
 
 
