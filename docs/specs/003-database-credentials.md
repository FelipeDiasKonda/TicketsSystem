# 003 - Database credential configuration

Status: approved and implemented; live MySQL rotation pending Docker access.

## Requirement and approved plan

Remove working passwords from version-controlled examples and Python defaults.
Generate independent random local passwords; rotate existing MySQL accounts
without deleting data. Update setup instructions and verify the configuration.
Changing the working tree does not remove previous Git commits. Rotation, rather
than history rewriting, invalidates the previously committed credentials.

## Acceptance criteria

- Example password values are empty; no runtime password defaults exist in Python.
- Backend requires a non-empty password and redacts it in settings representations.
- PowerShell setup generates independent 256-bit passwords using the OS CSPRNG.
- Root and backend .env files, including rotation recovery state, are Git-ignored.
- Rotation sends secrets only through stdin, updates MySQL accounts atomically,
  verifies new credentials, and only then synchronizes active local configuration.
- Interrupted rotation is retryable using the ignored .env.rotation recovery file.
- No volumes, databases, tables, or user data are deleted.
- Run backend regression tests, lint and Compose validation. If Docker is blocked,
  retain pending credentials and provide the exact command to finish rotation.

## Validation and local state

- Full backend regression suite: 32 tests passed. Ruff passed.
- Example passwords are empty and old passwords are absent from versionable files.
- Active and pending .env files are ignored by Git.
- Compose configuration validates with the existing local environment.
- Backend configuration tests require passwords and verify redaction.
- PowerShell tests run in temporary project copies with a simulated Docker client:
  generation/idempotency, successful rotation, failure preservation, and retry after
  database update succeeded but local synchronization was interrupted.
- Actual Docker access was denied on the engine pipe. No live MySQL ALTER USER
  succeeded. Active .env was deliberately preserved; new random passwords remain
  in ignored .env.rotation. Run scripts/Rotate-DatabaseCredentials.ps1 from the
  user's terminal, then recreate containers. The old passwords remain valid in
  the existing database until that step succeeds.
