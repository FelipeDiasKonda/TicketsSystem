# TicketsSystem

## Workflow

Follow specification-driven development (SDD) for every implementation:

1. Receive the requirement and inspect the current code.
2. Present the specification, scope, acceptance criteria, and implementation/test plan.
3. Wait for the user's approval or adjustments before implementing.
4. Implement the approved scope, run the planned checks, and report results and limitations.

## Backend architecture

- `app/main.py`: application factory, middleware, and registration of the central router.
- `app/api/routes/router.py`: aggregate feature routers; register `/api` in `main.py`.
- `app/api/routes/endpoints/`: HTTP endpoints grouped by feature.
- `app/core/`: settings and application lifespan.
- `app/db/`: database connection and sessions.
- Add `schemas/`, `models/`, and `services/` as features need request/response contracts,
  persistence entities, and business logic. Keep business logic out of endpoints.
- Preserve existing API contracts during structural refactors.
