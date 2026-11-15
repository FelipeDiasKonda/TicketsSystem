# Ticket details, assignment and activity

Approved scope: a modal opened from list rows or board cards, with full title,
description, requester name, category, priority, creation date, status and assignee.
The bottom contains Comments and History tabs. Existing list/board filters and
pagination remain in place. Dragging a card must not open the modal.

## Access and behavior

- Employees may read and comment on their own tickets. Support may access all.
- Foreign tickets return the same 404 as missing tickets. Authentication is required.
- Only support may assign to themselves, another active support member or nobody.
  Other support members retain permission to manage assigned tickets.
- Status updates reuse the existing strict forward-only workflow and endpoint.
- Comments are plain text, trimmed, 1–5,000 characters; author and UTC date are
  set by the backend. Comments remain allowed after closure. No edit/delete/upload.
- Both activity tabs are paged in the database (20 by default, maximum 100),
  newest first, with deterministic tie breakers.
- History combines creation, status transitions and assignment changes, with
  actor and UTC date. Legacy snapshots remain explicitly identified; the known
  creation date/requester are shown separately, without fabricating transitions.
- Assignment and its audit entry commit atomically. An expected assignment version
  prevents lost updates and detects a change away and back to the same assignee.
  Stale requests return 409. Repeating an unchanged assignment creates no audit
  entry but still checks/increments the version.
- All writes require the existing CSRF header and origin validation.
- Backend messages are English. UI messages and field labels are Portuguese.

## Contracts

| Method | Route | Result |
|---|---|---|
| GET | `/api/tickets/{id}` | Full details, assignee, assignment version |
| GET | `/api/tickets/support-members` | Active support IDs/names; support only |
| PATCH | `/api/tickets/{id}/assignee` | Updated details; support and CSRF required |
| GET | `/api/tickets/{id}/comments?page=1&page_size=20` | Paged comments |
| POST | `/api/tickets/{id}/comments` | Created comment; CSRF required |
| GET | `/api/tickets/{id}/history?page=1&page_size=20` | Paged combined timeline |

Assignment body: `{"assignee_id":null,"expected_assignment_version":0}`.
Comment body: `{"body":"Message"}`. Unknown write fields are rejected.
Existing creation/list/status response contracts are preserved.

## Implementation and acceptance

Migration `0004` adds nullable assignee and assignment version to tickets and
creates comment/assignment-history tables without removing existing tickets,
users, sessions or status history. Endpoints handle HTTP concerns, schemas
validate contracts, services own visibility/transactions and models persist data.

The native dialog traps focus, closes via its button or Escape, locks background
scroll and restores focus. If a mutation refreshed away the original trigger,
focus returns to the active view button. Ticket title buttons support keyboard
opening; tabs support arrow keys/Home/End. Lists/cards refresh after status or
assignment changes. Conflict handling keeps the modal open and reloads details
and activity without losing the comment draft. Request cleanup ignores stale
responses after closure. Text is rendered using React text nodes.

Checks: HTTP tests for access, CSRF, validation and error codes; database/service
tests for activity pagination, snapshots, active assignees, rollback and concurrent
assignment; migration upgrade/model comparison/downgrade; TypeScript/Vite build;
Ruff; isolated browser smoke for focus, tabs, role controls, comments, assignment,
drag interaction and mobile layout. Browser tests use SQLite and intercepted API
traffic, never application data.

Validation in this session: 19 service/migration/concurrency tests passed; Ruff
and frontend build passed. HTTP TestClient execution is blocked while Windows
creates its asyncio socket pair; the full HTTP suite and browser smoke therefore
remain unverified here. Docker access was denied. Local Node is 18.16.1 (build
completed with a Vite warning); the project requires Node >=22.12 and its Docker
frontend image uses Node 22. No live database was modified.

## Approved UI adjustment: inline assignment

The assignee name (or unassigned label) is a button for support users. Clicking
it opens a compact menu anchored to that field with self-assignment, removal and
active support member choices. The separate assignment block is removed.
Selecting an option calls the existing assignment endpoint, closes the menu and
updates the name after the API confirms. Employee views keep plain text.
The menu supports Enter/Space, arrows, Home/End, Escape, outside clicks and Tab.
Escape closes the menu before the ticket dialog. Loading and retry feedback stay
inside the menu. Existing conflict and audit handling are retained.
Build/type checking and the updated optional browser smoke cover this adjustment;
interactive browser validation remains subject to the Windows socket limitation
noted above.
