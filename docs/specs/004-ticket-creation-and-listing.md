# 004 - Ticket creation and listing

Status: approved and implemented on 2026-11-14.

## Requirement

Employees and support staff can open tickets with title, description, category,
and priority. Support sees all tickets in a table; employees see only their own.
Maintain the endpoint/router, schema, service, model, and migration architecture.

## Approved scope and acceptance criteria

- Authenticated employees and support can POST /api/tickets (201).
- Title: trimmed, 3-150 characters. Description: trimmed, 10-5000 characters.
- Categories: it (TI), facilities (Instalações), hr (RH).
- Priorities: low (Baixa), medium (Média), high (Alta), urgent (Urgente).
- Backend sets requester to the authenticated user, status to open (Aberto),
  and creation timestamp to UTC. Clients cannot supply these fields.
- GET /api/tickets returns only the employee's tickets or all tickets for support,
  including tickets opened by support. No client-side filter can broaden access.
- Page defaults to 1; page_size defaults to 20, maximum 100. Results are ordered
  by creation descending, then ID descending to break timestamp ties.
- Return items, total (within the permitted scope), page, and page_size.
- Table: number, title, requester, category, priority, status, creation date.
- New-ticket form validates fields, disables repeat submission, shows confirmation,
  and refreshes the first page. Loading, empty and failure states are visible.
- Existing cookie authentication/CSRF protection applies. New backend messages
  are English; interface labels remain Portuguese.
- Add Alembic revision 0002; keep users, sessions and their data intact.
- Status updates, filtering, alternative ordering, detail view and history remain
  outside this specification and require a subsequent approved plan.

## Plan

1. Add the Ticket model, enums, and migration, with requester/date indexes.
2. Add validated schemas, creation/listing services and thin endpoints; register router.
3. Add frontend API/types, create form and paginated table in the authenticated home.
4. Update documentation and test both roles, isolation, invalid inputs, CSRF,
   pagination/order, migration upgrade/downgrade and preservation of existing users.
5. Run full regression suite, Ruff, frontend build and available Docker checks.

## Results

- Full backend suite: 69 tests passed, including authorization, input validation,
  pagination/order, committed data, migration consistency and preservation of
  existing users/sessions across upgrade and ticket-only downgrade.
- Ruff passed after formatting. TypeScript and Vite production build passed.
  Local Node 18 emits a Vite version warning; the Docker image uses Node 22.
- Compose configuration validates. Offline MySQL SQL generation for revision 0002
  includes the ticket table, requester foreign key and indexes.
- Live container/MySQL verification is pending: Docker engine access was denied
  in this session. Browser interaction was not automated; UI validation is limited
  to the production build. Manual multi-account and restart checks are in README.
