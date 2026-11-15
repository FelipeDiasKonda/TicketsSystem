# 005 - Manual demo seed

Status: approved and implemented on 2026-11-14.

## Requirement and scope

Create a repeatable manual seed with three employee and three support accounts.
Names are Funcionário 1-3 / Suporte 1-3; emails are funcionario1-3@gmail.com and
suporte1-3@gmail.com. All use the same user-specified demonstration password,
stored only in the ignored local environment as SEED_PASSWORD.

The user clarified that exactly three demo tickets are required: one per
employee, covering TI, Instalações and RH. No tickets are seeded for support.

## Acceptance criteria and plan

- Add a manual CLI at app.db.seed with business logic in services/seed.py.
- The seed is never part of normal application startup or migrations.
- Read SEED_PASSWORD from settings, require 12-128 characters, store Argon2id hashes,
  and never print or version the password.
- Create or refresh only the six specified accounts: name, role, password, active
  state. Revoke their old sessions to match the reset credentials.
- Create three open tickets with fixed [DEMO] titles and varied priorities.
- Identify existing demo tickets by requester and fixed title; sequential reruns
  do not duplicate or reset those tickets, including their current status/content.
- Preserve all other users, sessions and tickets.
- Use one transaction: a failure rolls back the entire operation.
- Test creation, repeat runs, login/visibility, refreshing demo users, preservation
  of unrelated data, invalid password configuration and transaction rollback.
- Document the Docker command and account emails. No schema changes required.

## Verification

- Full backend regression suite: 79 tests passed, including seed repetition,
  independent password salts, login and visibility for all six demo accounts,
  preservation of unrelated data, session revocation and full transaction rollback.
- Ruff and Compose configuration validation passed.
- The specified password is configured in ignored root/backend .env files; example
  values are empty. The seed has not been run against the user's live database.
