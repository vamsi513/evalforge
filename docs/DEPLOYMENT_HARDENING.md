# Deployment Hardening

This document defines practical production readiness controls for EvalForge.

## Health and Availability

- Liveness endpoint: `GET /health/live`
- Readiness endpoint: `GET /health/ready`
  - readiness returns `503` when the database check fails

Recommended container probes:

- liveness: `GET /health/live`
- readiness: `GET /health/ready`

## SLOs (Initial Targets)

- API availability: `99.5%` monthly
- P95 API latency (non-LLM endpoints): `< 300ms`
- Schedule run success rate: `>= 98%`
- Failed release-gate alert delivery attempts logged at least once per failed run

## Backup and Restore Runbook

Use the scripts under `scripts/ops/` with Postgres credentials exported.

Required environment variables:

- `PGHOST`
- `PGPORT`
- `PGUSER`
- `PGPASSWORD`
- `PGDATABASE`

### Backup

```bash
bash scripts/ops/backup_postgres.sh backups
```

Output: timestamped `.dump` file in `backups/`.

### Restore

```bash
bash scripts/ops/restore_postgres.sh backups/<file>.dump
```

## Incident Steps (Minimal)

1. Check readiness: `curl -sS http://<api>/health/ready`
2. Check recent schedule runs: `GET /api/v1/release-gates/schedules/{id}/runs`
3. If DB issue, fail over/restore from latest verified dump.
4. Re-run blocked schedule manually via:
   `POST /api/v1/release-gates/schedules/{id}/run`

## Security Baseline

- Keep `PLATFORM_API_KEY` enabled in production.
- Use `DEFAULT_USER_ROLE=viewer`.
- Grant elevated access with explicit `X-User-Role` per caller identity.
- Run API container as non-root (Dockerfile default).
