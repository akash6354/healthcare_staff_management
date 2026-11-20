---
name: new-module
description: Step-by-step recipe for adding a new OGLOS module or feature on top of the task engine (model → migration → service → router → policy → tests → UI → i18n → seed → docs). Use when starting any new module, entity or endpoint group.
---

# Adding an OGLOS module

Read first: `CLAUDE.md`, `docs/architecture.md`, `docs/data-model.md`, `docs/state-machine.md`, `docs/ui-direction.md`.
If the change touches more than 3 files, enter plan mode and show the plan first. Any business rule you are not sure about goes to `docs/open-questions.md` with a working default; don't invent it.

## Steps

1. **Design note.** Add the module's tables to `docs/data-model.md`, its endpoints to `docs/api.md`, and its permissions to the matrix in `docs/security.md`. If it creates tasks, decide the `kind`, `source`, template defaults and whether it needs a 1:1 detail table (don't add columns to `tasks` for one module).
2. **Models** in `apps/api/app/modules/<module>/models.py`. Every tenant table has `hospital_id`, composite FKs to tenant tables, and timestamps. No patient data.
3. **Migration** (`make migrate-new name=<module>_init`): reversible `upgrade`/`downgrade`; call `enable_tenant_rls()` for each tenant table; append-only tables get `REVOKE UPDATE, DELETE`. Never edit an applied migration.
4. **Schemas** (`schemas.py`): Pydantic v2, `extra="forbid"`, length caps, enums; errors as codes plus `message_key`.
5. **Service** (`service.py`): all business logic. Task status changes only via `tasks.state_machine.transition()`; audit events in the same transaction; settings come from `hospital_settings` with defaults (configurable platform, decision 1).
6. **Router** (`router.py`): thin. Each route has `@requires(permission, scope)`; register the router behind the module switch (`hospital_modules`).
7. **Policy**: add permissions to `app/policy/permissions.py` and the role map; update the matrix test.
8. **Jobs** (if any) in `apps/worker`: timer state in Postgres, idempotent, per-hospital `SET LOCAL` context.
9. **Tests** (pytest + httpx): happy path, 403 per missing permission, **cross-tenant 404** for read/list/update/delete/file, validation 422, state machine guards, and a PII-in-logs check.
10. **UI**: use tokens/components from `packages/ui`; follow `docs/ui-direction.md` and the **frontend-design** skill (and the **dataviz** skill for any chart or status display). Status = colour + icon + label.
11. **i18n**: every staff-facing string in `packages/i18n/{en,kn,hi}`. Kannada/Hindi may start machine-assisted but must be marked `needs_review` in the catalogue.
12. **Seed**: extend `make seed` (Sunrise Multispeciality, synthetic only) so the feature appears in the demo.
13. **Screens**: Playwright screenshots at 1440 and 390 → critique against ui-direction §8–9 → fix → save under `docs/screens/`.
14. **Compliance**: new personal fields → `docs/compliance/data-inventory.md`; run the **compliance-check** and **security-review** skills.
15. **Finish**: `make lint && make test` green; small commits (`feat(<module>): …`); dependency justifications in the commit message.
