# Backend errors and structured logs

Approved scope: central application error types, HTTP error handlers and structured
logs for routes/services. Keep existing status codes and the frontend's `detail`
contract. No database migration or frontend changes.

## Responsibilities

- `app/core/errors.py` defines application error categories and feature-specific
  subclasses, each with an internal code and default English message.
- `app/api/error_handlers.py` maps categories to HTTP statuses and renders errors.
  Authentication, access, missing resources, conflicts, invalid inputs and database
  health preserve their prior 401/403/404/409/422/503 statuses and messages.
- `code` is an internal diagnostic identifier, not an HTTP number. It appears in
  logs; responses keep `{"detail":"message"}`. Validation keeps its existing
  `detail` list with only `loc`, `msg` and `type`.
- Endpoints delegate to services and no longer repeat business-error catches.
  Dependencies use the shared authentication/access errors. Services still own
  rollback and re-raise failures; handlers do not manipulate DB sessions.
- Unexpected failures return a generic JSON 500. Middleware handles failures
  before the server can emit raw SQL/driver exception text. Existing SQL failure
  tests assert safe 500 responses and unchanged database state.

## Logging

`app/core/observability.py` configures standard-library logging once per process.
Application records are JSON on stderr, visible alongside server logs in Docker.
The implementation adds no dependencies.

Each HTTP request that reaches the router receives a server-generated identifier,
returned as `X-Request-ID`. A context variable carries it into service calls.
Completion records include method, matched route template, endpoint module/file,
operation, HTTP status, allowed parameters and duration in milliseconds. Unmatched
paths are labeled `<unmatched>` instead of copying arbitrary URL content.

Service decorators record start, completion/failure, defining module/file,
operation, allowed parameters and duration. They preserve the original function
signature/result and re-raise the original exception. Expected business failures
use WARNING; unexpected failures use ERROR. Final request failures record a safe
stack as file/function/line locations without exception text, SQL, local variables
or chained exception strings.

Only numeric ticket IDs/page sizes/page numbers and known filter/sort values are
logged. Request bodies, credentials, email addresses, cookies, session tokens,
free-form comments/descriptions and returned values are not copied into logs.
Incoming correlation IDs are not trusted or echoed. Existing Uvicorn access logs
remain separate from application JSON records.

## Acceptance and verification

- Preserve existing response JSON/messages/statuses, permissions and workflow.
- Associate request and service records through the same request ID; reset context
  after every request and avoid repeated logger handlers on app recreation.
- Observe successful calls, business failures, validation and unexpected errors.
- Preserve rollback of failed status/assignment audit writes and explicitly roll
  back failed ticket/session creation.
- Test log allowlists and credential exclusion, safe SQL failure responses, error
  mapping, ASGI handling, migration compatibility and concurrent updates.

ASGI tests for the new async fixture routes run entirely in memory without an
event loop or network I/O; the driver rejects actual async suspension. They test
the real middleware and handlers. The original TestClient regression suites remain
the verification path for synchronous endpoints/database dependencies. This
session's TestClient run was blocked in Windows asyncio socket-pair creation;
that full regression suite must be run in an environment with working sockets.

Session result: 43 selected tests passed (central errors/logging, in-memory ASGI,
service integration, migrations and concurrent status/assignment updates). Ruff
and whitespace checks passed. No live database data or frontend code was changed.
