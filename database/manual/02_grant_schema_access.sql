-- Run this after connecting to the retailpulse database as postgres.
GRANT ALL PRIVILEGES ON DATABASE retailpulse TO retailpulse;
GRANT ALL ON SCHEMA public TO retailpulse;
ALTER SCHEMA public OWNER TO retailpulse;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO retailpulse;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO retailpulse;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO retailpulse;
