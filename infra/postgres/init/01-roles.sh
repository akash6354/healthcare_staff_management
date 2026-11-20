#!/bin/sh
# Creates the three OGLOS database roles (see docs/architecture.md §2).
# Runs once, on first start of an empty data volume.
set -eu
psql -v ON_ERROR_STOP=1 --username postgres --dbname oglos <<SQL
CREATE ROLE oglos_owner LOGIN PASSWORD '${OGLOS_OWNER_PASSWORD}';
CREATE ROLE oglos_app LOGIN PASSWORD '${OGLOS_APP_PASSWORD}' NOBYPASSRLS;
CREATE ROLE oglos_platform LOGIN PASSWORD '${OGLOS_PLATFORM_PASSWORD}' BYPASSRLS;
GRANT CONNECT ON DATABASE oglos TO oglos_app, oglos_platform;
ALTER DATABASE oglos OWNER TO oglos_owner;
ALTER SCHEMA public OWNER TO oglos_owner;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- test database used by pytest (same roles)
CREATE DATABASE oglos_test OWNER oglos_owner;
GRANT CONNECT ON DATABASE oglos_test TO oglos_app, oglos_platform;
SQL
psql -v ON_ERROR_STOP=1 --username postgres --dbname oglos_test <<SQL
ALTER SCHEMA public OWNER TO oglos_owner;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SQL
