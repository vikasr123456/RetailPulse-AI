# RetailPulse AI — Manual PostgreSQL Setup (Windows)

This guide is for running PostgreSQL yourself instead of using Docker.
It is the recommended developer workflow if you want to inspect the database in pgAdmin or psql.

> **Warning:** `python seed.py` is a development reset. It deletes the PostgreSQL `public` schema with `CASCADE` and recreates it. Never run it against a production database with real customer data.

## A. Install PostgreSQL

Install PostgreSQL 16+ for Windows and remember the password of the PostgreSQL administrator (`postgres`). Keep the default port **5432** unless you intentionally changed it.

You can use either:

- **pgAdmin 4** — graphical database administration
- **psql** — PostgreSQL command line

## B. Start PostgreSQL

If PostgreSQL was installed as a Windows service, start it from:

`Win + R` → `services.msc` → PostgreSQL → Start

Or from an elevated PowerShell (service name varies):

```powershell
Get-Service *postgres*
Start-Service postgresql-x64-16
```

Check the port:

```powershell
netstat -ano | findstr :5432
```

## C. Create the RetailPulse database manually

### Option 1 — pgAdmin

1. Open **pgAdmin 4**.
2. Connect to your local PostgreSQL server.
3. Open the `postgres` database.
4. Open **Tools → Query Tool**.
5. Run:

```sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'retailpulse') THEN
        CREATE ROLE retailpulse LOGIN PASSWORD 'retailpulse';
    ELSE
        ALTER ROLE retailpulse WITH LOGIN PASSWORD 'retailpulse';
    END IF;
END
$$;

CREATE DATABASE retailpulse OWNER retailpulse;
```

If the database already exists, do not run `CREATE DATABASE` again. Instead, open the existing `retailpulse` database and continue with the grants below.

Then connect to the **retailpulse** database and run:

```sql
GRANT ALL PRIVILEGES ON DATABASE retailpulse TO retailpulse;
GRANT ALL ON SCHEMA public TO retailpulse;
ALTER SCHEMA public OWNER TO retailpulse;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO retailpulse;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO retailpulse;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO retailpulse;
```

The same SQL is stored in:

```text
database/manual/01_create_role_and_database.sql
database/manual/02_grant_schema_access.sql
database/manual/03_verify.sql
```

### Option 2 — psql

Open PowerShell and run:

```powershell
psql -U postgres -h localhost -p 5432 -d postgres
```

Enter the PostgreSQL administrator password.

Then:

```sql
CREATE ROLE retailpulse LOGIN PASSWORD 'retailpulse';
CREATE DATABASE retailpulse OWNER retailpulse;
\c retailpulse
GRANT ALL ON SCHEMA public TO retailpulse;
ALTER SCHEMA public OWNER TO retailpulse;
\q
```

If the role/database already exists, use `ALTER ROLE` and connect to the existing database instead of creating duplicates.

## D. Configure the backend

From the project:

```powershell
cd backend
copy .env.example .env
```

Open `backend/.env` and use:

```env
DATABASE_URL=postgresql+psycopg://retailpulse:retailpulse@localhost:5432/retailpulse
SECRET_KEY=change-this-to-a-long-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

Do not commit `.env` to Git.

## E. Install Python dependencies

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## F. Create the application schema

The database itself is created manually in PostgreSQL. The application tables are created by SQLAlchemy:

```powershell
python scripts/migrate_enterprise_db.py
```

You should see:

```text
Enterprise database schema is ready.
```

## G. Verify the database

Run:

```powershell
python -c "from app.db import engine; print(engine.url.render_as_string(hide_password=True)); print(engine.connect().exec_driver_sql('select current_database(), current_user').fetchone())"
```

Expected shape:

```text
postgresql+psycopg://retailpulse@localhost:5432/retailpulse
('retailpulse', 'retailpulse')
```

Then open pgAdmin and confirm tables such as:

```text
audit_logs
alerts
data_quality_scores
forecast_values
forecasts
inventory
model_metrics
products
sales
stores
tenants
users
```

## H. Seed development data

For a clean demo database:

```powershell
python seed.py
```

This creates the demo tenant, store, roles, products and sales history.

Demo accounts:

```text
OWNER     owner@retailpulse.ai / owner123
MANAGER   manager@retailpulse.ai / manager123
STAFF     staff@retailpulse.ai / staff123
ANALYST   analyst@retailpulse.ai / analyst123
CUSTOMER  customer@retailpulse.ai / customer123
```

### Enterprise catalog seed

To add the representative global catalog after the schema exists:

```powershell
python scripts/seed_international_catalog.py
```

The catalog is demo data and is not affiliated with or endorsed by any listed brand.

## I. Start the backend

```powershell
uvicorn app.main:app --reload --port 8000
```

Health:

```text
http://127.0.0.1:8000/api/v1/health
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

## J. Start the frontend

Open a second PowerShell:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## K. Manual dataset workflow

1. Sign in as OWNER.
2. Open **Data Intelligence**.
3. Select `retailpulse_demo_2year.csv`.
4. Click **Analyze & Import Dataset**.
5. Confirm the replacement dialog.
6. Wait for database verification.
7. Open **Products** and confirm the imported products.
8. Open **Reports & Analytics**.
9. Test daily, weekly, monthly and yearly reports.
10. Test Forecast Studio, ARIMA, LSTM and Model Evaluation.

For the included dataset, the expected source data is:

```text
8,772 rows
12 products
2024-01-01 through 2025-12-31
0 missing values
0 duplicate rows
```

## L. Full database reset during development

If foreign-key errors appear because an old phase left incompatible tables, run:

```powershell
python seed.py
```

The current PostgreSQL reset drops and recreates the `public` schema with `CASCADE` before rebuilding the SQLAlchemy schema.

Again: **development only**.

## M. Common errors

### `connection refused`

PostgreSQL is not running or port 5432 is different.

```powershell
netstat -ano | findstr :5432
```

### `password authentication failed`

Check `backend/.env` and make sure the username/password match the PostgreSQL role.

### `database "retailpulse" does not exist`

Create it manually using the steps above.

### `permission denied for schema public`

Run:

```sql
GRANT ALL ON SCHEMA public TO retailpulse;
ALTER SCHEMA public OWNER TO retailpulse;
```

### `cannot drop table products because other objects depend on it`

Do not manually delete tables one by one. For the development reset use:

```powershell
python seed.py
```

### TensorFlow installation fails on Windows long paths

Enable Windows long-path support and/or use a shorter project path such as:

```text
C:\RetailPulse
```

Avoid deeply nested `Downloads` paths when installing TensorFlow.

## N. Production database rule

For production, do **not** use `seed.py`. Use proper versioned migrations (Alembic), backups, least-privilege database credentials, TLS, secret management and a separate production database.
