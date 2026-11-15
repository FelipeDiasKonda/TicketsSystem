# 007 - Sequential ticket status workflow and board

Status: approved and implemented on 2026-11-15.

## Scope and acceptance criteria

- Support alone can move open -> in_progress -> resolved -> closed. No skipping,
  backwards movement, reopening, or changes to closed tickets.
- PATCH /api/tickets/{id}/status accepts status and expected_status. Validate roles,
  CSRF, current status and next step; return 404 for missing tickets and 409 for
  stale/invalid transitions. Messages from the backend remain English.
- Use a conditional database update and record history in the same transaction.
  History stores previous/new status, actor, UTC time and event kind. Record new
  ticket creation, and baseline existing tickets as migration-time snapshots,
  without inventing earlier changes or actors.
- Add a Lista/Quadro switch. Employees retain read-only access to their own tickets.
- List exposes current/next status in a select for support; closed is read-only.
- Board shows four columns, per-column counts and independent load-more pagination.
  Do not group only the first page of the global list.
- Support can drag a card only to the next column. Provide a normal button for
  keyboard/touch operation. Do not move cards until the server confirms.
- Disable concurrent actions while a request is pending. Show failures and reload
  stale data on conflicts. Preserve filters/order in both views and while switching.
- All four columns remain visible. A status filter makes other columns empty but
  available as valid drop targets; a moved ticket may leave the active filter.
- Full history display/details are deferred; history is persisted now.

## Plan and verification

Add history model/migration, transition schema/service/endpoint, extend CSRF headers
to PATCH, implement status controls and the board, document behavior. Test the full
transition matrix, permission checks, CSRF, conflicts, transaction rollback,
creation/seed history, migration preservation and per-column pagination. Run the
full backend suite, Ruff, frontend build and available browser checks.

## Results

- Full backend suite: 146 tests passed, including the complete 16-case transition
  matrix, stale requests, two truly concurrent conditional updates (one succeeds,
  one conflicts), history rollback, creation/seed history and snapshot migration.
- Ruff, TypeScript/Vite production build and Compose configuration passed.
  The local Node 18 warning remains; Docker uses the required Node 22.
- Chrome browser smoke passed against an isolated in-memory FastAPI/SQLite fixture:
  list selection, blocked skipping, native drag/drop, keyboard alternative,
  independent column pagination beyond 20 cards, conflicts/reload, preserved filters,
  read-only employee views and mobile layout. Screenshots were visually inspected.
- MySQL offline SQL generation for revision 0003 passed. The live Docker engine
  still denies access in this session; no migration or status change was applied
  to the user's live database. Run docker compose up --build -d to apply it.
- Complete history display remains deferred to the ticket details feature.
