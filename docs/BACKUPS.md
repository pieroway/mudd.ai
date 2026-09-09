# Database backup and recovery

Run these commands from the repository root in Windows PowerShell. Docker Desktop
must be running. No local PostgreSQL installation is needed. Backups include the
whole application database: world, characters, accounts, authentication sessions,
NPC memories, AI allowances, and migration version. Redis is ephemeral and excluded.

## Create and verify a backup

```powershell
.\scripts\database.ps1 -Action Backup
.\scripts\database.ps1 -Action Verify -Archive .\backups\<filename>.dump
```

Backup uses `pg_dump -Fc` in the running PostgreSQL container, copies the binary
archive without shell redirection, and writes a SHA-256 sidecar. It checks the
archive's table of contents before publishing it. Verify checks the checksum,
restores into a disposable PostgreSQL 16 container with no network access and
temporary storage, then reads migration and game-table counts. It removes that
container afterward. Verification does not call AI or touch the running game.
The image `postgres:16-alpine` must be locally available or downloadable.

Archives default to `backups/`, excluded from Git. Keep the `.dump` and `.sha256`
files together. Treat them as private: they contain password hashes, session data,
and private NPC conversations. Store them on encrypted, access-controlled storage.
Checksums detect accidental damage; they do not authenticate untrusted archives.
Restore only your own trusted backups.

Use `-CopyDirectory 'E:\MuddBackups'` for a verified second copy. This does not
encrypt or upload backups; configure encryption and off-machine storage separately.
A second folder on the same drive does not protect against drive failure.
Both directories retain the newest backup from seven distinct UTC dates and four
Monday-based weeks (overlapping selections are kept once). Pruning runs only after
successful backup/copy completion and only matches this tool's archive names with
sidecars. Failed and incomplete files are not counted as recovery points.

The default container is `mudai_postgres`. For a production-like stack, pass its
PostgreSQL container name using `-Container` and use a separate `-BackupDirectory`.
Never mix environments in one backup directory. Database credentials are read
inside the container; no password is placed in command arguments.

## Nightly automation

```powershell
.\scripts\schedule-backup.ps1
# Or customize before registration:
.\scripts\schedule-backup.ps1 -Time '03:00' -CopyDirectory 'E:\MuddBackups'
Get-ScheduledTaskInfo -TaskName MuddAI-DatabaseBackup
```

Registration creates a task for the current Windows user, daily at 03:00 local
time. It requires that user to be signed in and Docker Desktop running. Missed
starts run when available, with three retries at 15-minute intervals after failure.
Concurrent runs are suppressed. Existing tasks are not silently replaced; use
Task Scheduler to edit/remove an existing task before registering again.
`LastTaskResult` should be zero, and archive timestamps should advance. This first
version has no email alerts or unattended service-account setup. A sleeping or
logged-out PC is not an always-on backup server.

Take a manual backup before deployment migrations and bulk world edits. Deployment
scripts are not changed to require an existing database, preserving first-run setup.
Nightly backups can lose up to a day of changes; failed/missed jobs extend that gap.

## Restore safely

```powershell
.\scripts\database.ps1 -Action Restore -Archive .\backups\<filename>.dump `
    -TargetDatabase muddb_recovered -ConfirmRestore
```

Restore creates a **new** database on the selected container and refuses an existing
name. It restores in one transaction, excluding original ownership and grants; the
container's configured PostgreSQL user owns the restored objects. On failure, an
empty new database may remain for operator inspection. There is no automatic drop.

For recovery: stop backend writes, take a final backup if possible, restore and
verify the new database, then deliberately update the backend's database connection
to use it. The development Compose file currently hardcodes `muddb`, so cutover
requires changing that backend connection configuration. Use application code
compatible with the recorded migration version; startup runs migrations, so take
care when starting newer code. Complete the project's deployment gate before
deploying code changes. Keep the original database until recovery is confirmed.
Consider invalidating restored authentication sessions before reopening access.

This restores the entire database to backup time, not just room changes. PostgreSQL
roles and other cluster-wide settings are not included. Preserve Compose files,
the matching Git revision, and encrypted environment/credential configuration
separately. Do not copy a live PostgreSQL data directory as a substitute for a dump.

## Test the tooling

```powershell
.\scripts\test-backup.ps1
```

This creates only disposable fixture databases and checks backup/copy, full restore,
data preservation, checksum rejection, existing-target protection, confirmation,
and retention. Also run Verify on real backups periodically; a readable archive
alone does not prove recovery works. Older backups predating NPC tables may restore
successfully but fail the current game-table verification query.

## Validation record

September 8, 2026 (America/Toronto): fixture integration checks passed (exit 0),
including checksum rejection, existing-target refusal, and retention. Fixed a
Windows PowerShell parameter-default issue and a PostgreSQL initialization-server
readiness race during verification. The actual scheduled backup restored in an
isolated container (exit 0): migration `0010`, 5 rooms, 11 players, 2 NPC memories.
Task `MuddAI-DatabaseBackup` was registered for 03:00 local time; its manual test
run returned `LastTaskResult=0`. Local archives are in `backups/`; no second-copy
destination has been configured. The application was not redeployed or modified.
