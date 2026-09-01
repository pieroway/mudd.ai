# Developer Workflow

Primary local interface: Windows `.bat` files where practical.

Suggested scripts under `scripts\dev\`:
- branch-new.bat
- branch-status.bat
- sync-main.bat
- commit.bat
- finish-feature.bat
- merge-main.bat
- test-unit.bat
- test-integration.bat
- test-e2e.bat
- test-all.bat
- build.bat
- deploy-local.bat
- up.bat
- down.bat
- logs.bat
- status.bat
- db-shell.bat
- db-migrate.bat
- db-reset.bat
- seed.bat
- doctor.bat
- help.bat

Prefer `main` for a new repo unless an established branch already exists.

Branch prefixes: feature, fix, refactor, test, docs, chore.

Use meaningful Conventional Commit-style messages. Commit at coherent boundaries, not after every tiny edit. Do not push automatically unless authorized.

Batch scripts must propagate non-zero failure exit codes.
