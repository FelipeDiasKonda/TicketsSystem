# 001 - Backend architecture

Status: approved and implemented on 2026-11-13.

## Requirement

Adopt the reference FastAPI organization: application factory, central router,
feature endpoints, settings/lifespan in core, and database infrastructure in db.
Use SDD for subsequent implementations, with user approval before code changes.

## Approved scope and plan

1. Move existing health endpoints into `app/api/routes/endpoints/health.py`.
2. Aggregate feature routers in `app/api/routes/router.py` and register `/api` in main.
3. Move settings to `app/core/config.py`, lifespan to `app/core/lifespan.py`,
   and database infrastructure to `app/db/database.py`.
4. Update imports, documentation, and Docker configuration where necessary.
5. Run regression tests, Ruff, frontend build, and available Docker checks.

Future feature requirements will introduce schemas, models, and services as needed.
No ticket functionality, persistence changes, or API behavior changes are included.

## Acceptance criteria

- `app.main:app` remains the Uvicorn entry point, backed by `create_app()`.
- GET `/api/health` returns HTTP 200 with status `ok` and version `0.0.0`, without a DB.
- GET `/api/health/db` executes `SELECT 1` and returns HTTP 200 with database `mysql`.
- Database errors return HTTP 503 with detail `Database unavailable`, without secrets.
- OpenAPI retains both paths and the existing `health` tag; `/docs` remains available.
- CORS configuration and environment variable names remain unchanged.
- Database engine is disposed during shutdown.
- Existing Docker entry point, healthchecks, and source mounts support the new layout.

## Validation

Automated checks cover both health responses, safe database failure, and OpenAPI
route registration. Ruff and frontend build are also required. A fake DB session
checks the API contract; real MySQL connectivity requires the Compose stack.

Results:

- Pytest: 4 tests passed (one dependency deprecation warning).
- Ruff: all checks passed.
- Frontend: TypeScript and Vite production build passed. Local Node 18 emitted
  a version warning; the Dockerfile uses Node 22 as required by Vite.
- Docker Compose configuration validation passed.
- Container startup and real MySQL connectivity could not be checked because
  the Docker Desktop Linux engine was not running.
- No Docker edits were necessary: the entry point remains `app.main:app`,
  and the existing app directory copy/mount includes the reorganized packages.
