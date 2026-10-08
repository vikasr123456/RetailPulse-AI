-- Run this script while connected to the PostgreSQL server as the postgres administrator.
-- pgAdmin: Query Tool -> connect to the 'postgres' database -> Run.
-- psql: \i database/manual/01_create_role_and_database.sql

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'retailpulse') THEN
        CREATE ROLE retailpulse LOGIN PASSWORD 'retailpulse';
    ELSE
        ALTER ROLE retailpulse WITH LOGIN PASSWORD 'retailpulse';
    END IF;
END
$$;

SELECT 'CREATE DATABASE retailpulse OWNER retailpulse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'retailpulse')\gexec

ALTER DATABASE retailpulse OWNER TO retailpulse;
