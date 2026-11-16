# Explicit environment configuration

Approved scope: move all `Settings` defaults into ENV examples. Keep type/range
validation in Python; reject absent required settings instead of silently using
hardcoded values. Preserve existing credentials and database data.

## Configuration contract

All fields in `Settings` are required: app name, DB host/port/name/user/password,
CORS origins, session cookie name, session duration, secure-cookie flag and seed
password. Nonempty strings, valid port range (1–65535), session duration (1–168)
and nonempty CORS lists are validated. Existing password redaction is retained.

`SEED_PASSWORD` must be explicitly defined but may be empty. Empty/whitespace
means disabled (`None`); the manual seed still requires a 12–128 character
password when executed. No secret default is committed.

The root `.env.example` supplies safe settings for Docker, including `db:3306`.
Compose maps `MYSQL_DATABASE`, `MYSQL_USER` and `MYSQL_PASSWORD` to the backend's
`DATABASE_NAME`, `DATABASE_USER` and `DATABASE_PASSWORD`, keeping one source for
shared credentials. Other Settings fields are forwarded explicitly. Required
variables have no Compose fallback; only seed permits an explicitly empty value.

`backend/.env.example` supplies settings for Python running on the host, with
`127.0.0.1:3306`. Database ports exposed on the host remain distinct from the
internal container port. If frontend ports change, configure CORS explicitly.

The optional initialization script completes missing keys from the root example,
preserves existing values and retains its explicit password-generation behavior.
Backend synchronization includes app/CORS/session/seed settings and reads the
local DB hostname from the backend example. Credential rotation continues to
verify new passwords before updating active files.

Current developer `.env` files are completed only for missing keys. Existing
values (including credentials) remain unchanged. Nothing is written to the live
database and no migration is needed.

## Verification

Tests configure every setting explicitly using isolated values before importing
the application; optional browser smoke scripts share this setup. Tests cover
each missing variable, dotenv reading, environment precedence, invalid values,
secret redaction, disabled seed, script completion and credential preservation.

Result: 82 selected configuration/script/logging/service/migration/concurrency
tests passed, as did Ruff and whitespace checks. Compose configuration was
validated quietly using temporary credentials; deleting APP_NAME was rejected.
The developer backend ENV was validated without printing its values. The full
TestClient HTTP suite remains subject to the previously observed Windows socket
limitation.
