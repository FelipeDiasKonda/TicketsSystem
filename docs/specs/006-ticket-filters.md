# 006 - Ticket filtering and ordering

Status: approved and implemented on 2026-11-14.

## Requirement and approved scope

Filter the ticket list by status, category and priority, independently or combined
with AND. Order by creation date or priority in either direction. Preserve user
visibility, authentication, pagination, response shape and default newest-first order.

## API contract

GET /api/tickets retains page (default 1) and page_size (default 20, maximum 100).
Optional parameters: status, category and priority use existing enum values.
Omit a filter to include all its values; invalid enum values return 422.
sort accepts created_desc (default), created_asc, priority_desc and priority_asc.
Date sorting uses ticket ID in the same direction to resolve equal timestamps.
Priority uses low < medium < high < urgent, with creation date descending and ID
descending as tie-breakers in both priority directions.

## Acceptance criteria and plan

- Add validated query schemas, thin endpoint integration and SQL-level conditions.
- Apply authorization scope and all filters to both the count and item queries.
- Filter and order before pagination, ensuring stable ordering across pages.
- Add four labeled select controls and a clear-filters action above the table.
- Changes reset page to 1; clearing resets all filters and newest-first order.
- Preserve active selections while navigating pages and refreshing after creation.
- If a created ticket does not match active filters, clarify that in the confirmation.
- Empty results and counts reflect the filtered query; keep controls available.
- Continue cancelling stale requests so old results cannot replace newer filters.
- No schema migration or status update capability is part of this change.
- Test every filter, combinations, invalid input, ordering/ties, filtered pagination,
  count, visibility and compatibility with the unfiltered endpoint.
- Run full backend tests, Ruff, frontend production build and Compose validation.

## Results

- Full backend suite: 117 tests passed, covering all filter enum values,
  combined filters, filtered totals, empty results, pagination, all four sorts,
  timestamp/priority ties, invalid input and employee visibility.
- Ruff, TypeScript/Vite production build and Compose configuration passed.
  Local Node 18 emits a Vite version warning; Docker uses Node 22.
- Direct read-only MySQL queries validated all four sort modes, combined filters,
  business priority ordering and employee scope. No live records were modified.
- Docker engine access remains denied in this session; container recreation was
  not executed. Browser interaction was not automated; UI verification is limited
  to the production build. No migration or credential changes were required.
