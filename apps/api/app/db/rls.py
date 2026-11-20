"""Migration helpers for Row-Level Security, grants and append-only tables (docs/data-model.md §4).

Used from Alembic revisions so every tenant table gets exactly the same policy.
"""

from alembic import op

APP_ROLE = "oglos_app"
PLATFORM_ROLE = "oglos_platform"


def enable_tenant_rls(table: str, column: str = "hospital_id") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_isolation ON {table}
            USING ({column} = NULLIF(current_setting('app.hospital_id', true), '')::uuid)
            WITH CHECK ({column} = NULLIF(current_setting('app.hospital_id', true), '')::uuid)"""
    )


def disable_tenant_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def grant_crud(table: str) -> None:
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}, {PLATFORM_ROLE}")


def grant_append_only(table: str) -> None:
    """INSERT + SELECT only for the app; a trigger also blocks UPDATE/DELETE for any role."""
    op.execute(f"GRANT SELECT, INSERT ON {table} TO {APP_ROLE}, {PLATFORM_ROLE}")
    op.execute(
        f"""CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION forbid_update_delete()"""
    )


def drop_append_only(table: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
