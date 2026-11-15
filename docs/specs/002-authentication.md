# 002 - Login and registration

Status: approved and implemented on 2026-11-13.

## Scope

Single-company internal portal, without a company entity. Registration accepts
name, email, password, password confirmation, and an explicit choice of employee
or support. Both roles can register freely for this prototype. This is a deliberate
demo simplification: anyone choosing support will gain support permissions.
No invitations, provisioning command, password recovery, or email verification.
Ticket functionality will be implemented under a separate specification.

## Implementation plan

1. Add Alembic migrations for users and database-backed sessions.
2. Add SQLAlchemy models, Pydantic schemas, authentication services and dependencies.
3. Add POST /api/auth/register, POST /api/auth/login, POST /api/auth/logout,
   and GET /api/auth/me.
4. Build login/registration screens, session restoration, protected home and logout.
5. Integrate migrations with Docker startup, update documentation, and run checks.

## Decisions and acceptance criteria

- Roles are employee/support; invalid values and unexpected registration fields fail.
- Name is trimmed (2-100 characters), email is validated and normalized to lowercase,
  and the database enforces uniqueness. Duplicate email returns 409.
- Password is 12-128 characters, is confirmed at registration, and stored as Argon2id.
  Passwords, password hashes and session tokens never appear in user responses.
- Registration returns 201 and starts a session. Login returns 200 and rotates
  the current session. Invalid credentials and inactive accounts return the same 401.
- Session lifetime is 8 hours by default. Only a hash of the random token is stored.
- Cookie is HttpOnly, SameSite=Lax, and Secure under HTTPS in production. Local
  HTTP development uses Secure=false. Authentication responses use Cache-Control=no-store.
- Mutating auth requests require X-CSRF-Protection: 1. Supplied Origin must match
  the configured frontend origins. Credentialed CORS permits only those origins.
- GET /me requires a valid unexpired session and active user. Logout deletes the
  session and cookie; it is idempotent and returns 204.
- Backend dependencies enforce authentication and support role for future routes.
- Frontend restores the session on reload, displays the current profile, validates
  forms, shows actionable API failures, and prevents repeated submits.
- Existing health endpoints keep their responses and remain public.
- Migrations run before the API starts in Docker. MySQL data remains persistent.

## Verification plan

API integration tests with an isolated SQL database cover both roles, normalization,
duplicates, validation, credentials, cookies, restoration, expiry, inactive users,
logout/revocation, CSRF, CORS, and role authorization. Test migration upgrade and
downgrade. Run Ruff, pytest, frontend build, Compose config, and Docker/MySQL smoke
checks when the engine is available. Record actual results before completion.

## Results

- API/migration tests: 24 passed with an isolated SQLite database.
- Ruff: passed.
- Frontend: TypeScript and Vite build passed. Local Node 18 emits a version warning;
  Docker uses Node 22 as required by Vite.
- Compose configuration: validated.
- Live Docker/MySQL verification: blocked by permission denied on the Docker
  Desktop Linux engine pipe in this session. Container startup is not verified.
- No ticket workflows are included; only authentication and role dependencies.
