# MongoDB Ops Console

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](backend/pyproject.toml)
[![React](https://img.shields.io/badge/React-19.0-61dafb.svg)](frontend/package.json)
[![Tests](https://img.shields.io/badge/Tests-86%20passed-success.svg)](backend/tests/)

A multi-user web dashboard for MongoDB cluster lifecycle management. Replaces manual YAML editing and CLI `ansible-playbook` commands with a guided UI that handles cluster registration, live monitoring, day-2 operations, and full deployment from a single browser window.

---

## ⚡ Quickstart

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-org/mongodb-ops-console.git
   cd mongodb-ops-console
   ```

2. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   # Generate a 32-byte Base64 MASTER_KEY and set JWT_SECRET in .env
   ```

3. **Launch with Docker Compose**:
   ```bash
   docker compose up -d
   ```

4. **Access Dashboard & CLI Utility**:
   - Web Console: `http://localhost`
   - API Docs: `http://localhost:8000/api/docs`
   - CLI Utility:
     ```bash
     cd backend
     uv sync
     uv run mgops login --url http://localhost:8000
     uv run mgops status
     ```

For details on contributing, security policy, and licensing, see [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [LICENSE](LICENSE).

---

## 💻 `mgops` CLI Utility

MongoDB Ops Console includes a dedicated command-line interface `mgops` built with **Typer**, **Rich**, and **HTTPX**.

### Common CLI Commands

```bash
# Authentication & Status
mgops login --username admin --password admin
mgops status
mgops whoami

# Cluster & Host Management
mgops clusters list
mgops clusters get <cluster_id>
mgops clusters hosts <cluster_id>

# Real-time Log Streaming
mgops logs show <job_id> --follow

# Day-2 Operations
mgops ops restart-node --cluster-id <id> --hostname mongo-primary-1
mgops ops rolling-restart --cluster-id <id>
mgops ops backup --cluster-id <id>
mgops ops create-user --cluster-id <id> --username appuser --password secret --db appdb

# Alerts & Audit Logs
mgops alerts list --unresolved
mgops audit list --limit 10

# Output Formatting for Scripting & CI/CD
mgops clusters list --output json | jq .
mgops status --output yaml
```

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Design Decisions -- Questionnaire of Choices](#2-design-decisions----questionnaire-of-choices)
3. [Technical Stack and Use Cases](#3-technical-stack-and-use-cases)
4. [Architecture Diagram](#4-architecture-diagram)
5. [Data Flow Diagrams](#5-data-flow-diagrams)
6. [Database Schema](#6-database-schema)
7. [API Reference](#7-api-reference)
8. [Frontend Pages and Components](#8-frontend-pages-and-components)
9. [Hosting and Deployment Guide](#9-hosting-and-deployment-guide)
10. [Development Guide](#10-development-guide)
11. [Phase-by-Phase Summary](#11-phase-by-phase-summary)

---

## 1. Project Overview

### What It Is

The MongoDB Dashboard is a multi-user web application for managing the complete lifecycle of MongoDB replica set clusters. It provides:

- **Cluster registry** -- define clusters, hosts, and credentials through a web UI instead of editing Ansible inventory files by hand.
- **Live monitoring** -- background polling collects replica set health, server performance, and storage metrics every 30 seconds with time-series charts and threshold-based alerting.
- **Day-2 operations** -- restart nodes, rotate passwords, manage application users, run PBM backups/restores, and execute mongodump-to-S3 -- all via an async job queue triggered from the UI.
- **Full deployment** -- a guided topology wizard generates Ansible inventory from the cluster registry and runs `ansible-playbook` as a subprocess with real-time log streaming via Server-Sent Events.

### What It Replaced

Before the dashboard, deploying and managing MongoDB clusters required:

1. Manually editing `inventory/hosts` and `inventory/group_vars/all.yml` YAML files.
2. Running `ansible-playbook -i inventory/ mongodb-playbook.yml --tags "..."` from the command line.
3. SSH-ing into nodes for day-2 tasks (restarts, backups, user management).
4. No centralized audit trail of who changed what and when.

The dashboard wraps all of this behind authenticated, role-controlled API endpoints and a React frontend, while preserving the same Ansible playbook underneath.

### Journey

The project was designed and built across 4 phases:

| Metric | Count |
|--------|-------|
| Phases | 4 |
| Implementation tasks | 51 (18 + 11 + 13 + 9) |
| Implementation steps | 254 (113 + 56 + 56 + 29) |
| Backend test functions | 86 across 20 test files |
| Frontend source modules | 34 files |
| Total project files | ~120 (backend + frontend + infra) |

---

## 2. Design Decisions -- Questionnaire of Choices

Every design choice was made through a structured brainstorming process. Below are the 27 questions across all 4 phases, the options considered, what was chosen, and why.

### Phase 1 -- Foundation (9 Questions)

**Q1. User type: single admin or multi-user?**

| Option | Description |
|--------|-------------|
| Single admin | One hardcoded admin account |
| Multi-user with roles | Multiple users with RBAC |

**Chosen: Multi-user with roles.** Teams need multiple operators and viewers with different permission levels. A single admin account would require credential sharing.

**Q2. Cluster management approach: pure Ansible, pure API, or hybrid?**

| Option | Description |
|--------|-------------|
| Pure Ansible | Generate inventory and run ansible-playbook for everything |
| Pure PyMongo/SSH | Bypass Ansible, manage clusters directly |
| Hybrid SSH + PyMongo | Use Ansible for deployment, SSH/PyMongo for day-2 ops |

**Chosen: Hybrid SSH + PyMongo.** Ansible is ideal for initial deployment (idempotent, declarative), but day-2 operations like password rotation or single-node restart are faster and more targeted via direct SSH commands and PyMongo calls.

**Q3. Lifecycle scope: deploy-only or full lifecycle?**

| Option | Description |
|--------|-------------|
| Deploy only | Just run the playbook |
| Deploy + monitor | Add health checks |
| Full lifecycle | Deploy + monitor + day-2 ops + backups |

**Chosen: Full lifecycle.** The goal is to eliminate all CLI work. Deploy-only would still require SSH access for routine tasks.

**Q4. Backend framework?**

| Option | Description |
|--------|-------------|
| Flask | Lightweight, synchronous |
| Django | Batteries-included, ORM built-in |
| FastAPI | Async, auto-OpenAPI, Pydantic validation |

**Chosen: Python 3.11+ / FastAPI.** Async support is critical for background pollers and SSH operations. Auto-generated OpenAPI docs accelerate frontend development. Pydantic v2 provides type-safe request/response validation.

**Q5. Database?**

| Option | Description |
|--------|-------------|
| SQLite | Zero-config, single-file |
| MySQL | Traditional RDBMS |
| PostgreSQL | Advanced types (JSONB, INET, TIMESTAMPTZ), mature ecosystem |

**Chosen: PostgreSQL 15.** JSONB for storing flexible cluster configuration. INET type for IP addresses. TIMESTAMPTZ for correct timezone handling. Partial unique indexes for alert deduplication.

**Q6. Secrets encryption?**

| Option | Description |
|--------|-------------|
| HashiCorp Vault | External secrets manager |
| AWS Secrets Manager | Cloud-native |
| Application-layer AES-256-GCM | Encrypt in the app, store in PostgreSQL |

**Chosen: AES-256-GCM with a master key.** No external dependency. Secrets are encrypted before storage with a 32-byte master key loaded from an environment variable. Each secret gets a unique 12-byte random nonce. Secrets are immutable -- rotation means creating a new secret and updating references.

**Q7. Authentication?**

| Option | Description |
|--------|-------------|
| OIDC/SSO | Delegate to identity provider |
| API keys | Static tokens |
| Local auth with argon2id + JWT | Username/password with secure hashing |

**Chosen: Local auth with argon2id + JWT.** No external identity provider dependency. argon2id is the current best practice for password hashing. JWT access tokens (short-lived, in memory) + revocable refresh tokens (httpOnly cookie) provide the standard SPA security pattern.

**Q8. Authorization model?**

| Option | Description |
|--------|-------------|
| Simple admin/non-admin | Two levels |
| 3-role RBAC (admin/operator/viewer) | Three levels |
| Per-resource ACLs | Fine-grained per-cluster permissions |

**Chosen: 3-role RBAC.** Admin manages users and destructive operations. Operator performs day-to-day cluster management. Viewer has read-only access. Per-resource ACLs add complexity without enough benefit for a team-sized deployment.

**Q9. Audit logging scope?**

| Option | Description |
|--------|-------------|
| Auth events only | Just logins |
| Auth + write operations | Logins + all creates/updates/deletes |
| Full request logging | Every API call |

**Chosen: Auth + write operations.** Every login (success and failure) and every state-changing action is recorded with user, IP, action, resource type, and resource ID. Read operations are not audited to avoid noise. `audit_logs.user_id` is nullable to record failed logins where the user may not exist.

### Phase 2 -- Monitoring (6 Questions)

**Q10. What metrics to collect?**

| Option | Description |
|--------|-------------|
| Health only | Replica set state, member up/down |
| Health + performance | Add connections, ops/sec, memory, cache, storage |
| Health + performance + slow queries | Add profiler data |

**Chosen: Health + performance metrics.** Six alert-worthy metrics: replication_lag, connections, disk_usage, memory, cache_pressure, member_down. Slow query analysis deferred to avoid scope creep.

**Q11. Collection method?**

| Option | Description |
|--------|-------------|
| Push-based agent | Install exporter on each node |
| Pull-based poller | Dashboard connects to clusters periodically |
| Hybrid poller + on-demand refresh | Background poll + manual refresh button |

**Chosen: Hybrid poller + on-demand refresh.** Background poller runs every 30 seconds via FastAPI lifespan hook. On-demand refresh endpoint lets operators get immediate data. No agent installation required on managed nodes.

**Q12. Alerting?**

| Option | Description |
|--------|-------------|
| In-app only | Alert badges and tables |
| Slack only | Webhook notifications |
| In-app + Slack | Both channels |

**Chosen: In-app + Slack.** In-app alerts for day-to-day monitoring with the dashboard open. Slack notifications for when operators are away from the dashboard. 15-minute debounce prevents notification storms.

**Q13. Metric retention?**

| Option | Description |
|--------|-------------|
| 24 hours | Minimal storage |
| 7 days | Covers a full work week |
| 30 days | Full month of history |

**Chosen: 7-day retention.** Covers a full work week of trends. Nightly cleanup task deletes old rows. Downsampled queries (1h/6h/24h/7d) keep chart performance fast.

**Q14. Alert thresholds: global or per-cluster?**

| Option | Description |
|--------|-------------|
| Global only | Same thresholds everywhere |
| Per-cluster only | Must configure each cluster |
| Global defaults + per-cluster overrides | Sensible defaults, optional customization |

**Chosen: Per-cluster threshold overrides.** Global defaults from environment variables. Per-cluster overrides stored in `clusters.config` JSONB under the `alert_thresholds` key. Merge logic: `{**global_defaults, **cluster_overrides}`.

**Q15. Cluster status auto-update?**

| Option | Description |
|--------|-------------|
| Manual only | Operators set status |
| Auto from poller | Poller determines healthy/degraded/failed |

**Chosen: Auto from poller.** After each poll cycle, `clusters.status` is automatically updated based on replica set state and active alerts. No manual intervention needed.

### Phase 3 -- Day-2 Operations (7 Questions)

**Q16. Execution model?**

| Option | Description |
|--------|-------------|
| Synchronous (wait for response) | API blocks until operation completes |
| Async job queue | API creates a job, worker executes, frontend polls |

**Chosen: Hybrid SSH + PyMongo via async job queue.** Operations can take seconds (restart) to hours (PBM restore). Synchronous execution would cause timeouts. The job queue (pending -> running -> success/failed) with 2-second frontend polling provides responsive feedback.

**Q17. SSH library?**

| Option | Description |
|--------|-------------|
| paramiko | Traditional, synchronous |
| asyncssh | Native asyncio support |
| subprocess + ssh | Shell out to ssh command |

**Chosen: asyncssh.** Native asyncio integration with the FastAPI event loop. SSH keys decrypted from the secrets vault in memory, never written to disk. Connection per operation, no persistent pools.

**Q18. Job execution model?**

| Option | Description |
|--------|-------------|
| Celery | External task queue with Redis/RabbitMQ broker |
| In-process asyncio task | Background task in FastAPI lifespan |

**Chosen: Async job queue (in-process).** No external broker dependency. Background asyncio task polls the jobs table every 2 seconds. Sequential execution (one job at a time) prevents resource contention. Stale job detection on startup marks interrupted jobs as failed.

**Q19. Which operations to support?**

| Option | Description |
|--------|-------------|
| 5 basic (restart, password, backup, restore, list) | Minimal set |
| 9 operations (extended + mongodump) | Full operational coverage |

**Chosen: 9 operations.** restart_node, rolling_restart, rotate_admin_password, create_app_user, delete_app_user, pbm_backup, pbm_restore, pbm_list, mongodump_s3. Covers all routine operational tasks that previously required SSH access.

**Q20. RBAC per operation?**

| Option | Description |
|--------|-------------|
| All operations require admin | Simple but restrictive |
| Flat operator+ for all | No differentiation |
| Tiered by risk level | Destructive ops require admin, routine ops allow operator |

**Chosen: Tiered RBAC.** Operator+ can: restart single node, manage app users, run backups, list backups, mongodump. Admin only: rolling restart, rotate admin password, PBM restore. Risk-proportionate access control.

**Q21. Backup strategy?**

| Option | Description |
|--------|-------------|
| PBM only | Percona Backup for MongoDB |
| mongodump only | Native MongoDB tool |
| Both PBM + mongodump | Full coverage |

**Chosen: Both PBM + mongodump.** PBM provides point-in-time restore for Percona clusters. mongodump-to-S3 provides a portable backup format that works with any MongoDB deployment. Different tools for different recovery scenarios.

**Q22. S3 authentication for mongodump?**

| Option | Description |
|--------|-------------|
| IAM role only | Requires EC2 instance role |
| Explicit credentials only | Requires storing AWS keys |
| Choice per cluster | IAM or explicit, configurable |

**Chosen: S3 auth choice per cluster.** `s3_auth_method` in cluster config: `iam_role` (no credentials needed, uses host IAM role) or `secret` (references an `s3_credential` type secret in the vault). Per-job params can override cluster defaults.

### Phase 4 -- Full Deployment (5 Questions)

**Q23. Ansible execution method?**

| Option | Description |
|--------|-------------|
| ansible-runner library | Python API for Ansible |
| Subprocess in Docker container | Shell out to ansible-playbook |

**Chosen: Subprocess in Docker container.** `asyncio.create_subprocess_exec` avoids shell injection. ansible-core installed in the API Docker image. Playbook directory volume-mounted read-only at `/playbook`. Simpler than ansible-runner and provides direct stdout capture.

**Q24. Inventory generation?**

| Option | Description |
|--------|-------------|
| Write to shared filesystem | Persistent inventory files |
| Temp files per deployment | Generate, use, delete |

**Chosen: Temp files per deploy.** `tempfile.mkdtemp()` creates `/tmp/deploy-{job_id}/` with hosts INI, `group_vars/all.yml`, and SSH key files (mode 0600). Entire directory deleted in a `finally` block after deployment. No persistent credential files on disk.

**Q25. Log delivery?**

| Option | Description |
|--------|-------------|
| Poll for logs | Frontend polls an endpoint |
| WebSocket streaming | Bidirectional connection |
| SSE (Server-Sent Events) | Unidirectional server push |

**Chosen: SSE log streaming.** `GET /api/jobs/{job_id}/logs` returns `text/event-stream`. Subprocess stdout is read line-by-line and pushed to an `asyncio.Queue` per job. Frontend uses native `EventSource` API. Simpler than WebSockets for unidirectional data. Full log stored in `jobs.result.log` after completion for replay.

**Q26. Wizard design?**

| Option | Description |
|--------|-------------|
| Single form | One long form page |
| Full guided wizard | Multi-step form with validation per step |

**Chosen: Full guided wizard.** 7 steps: Basics -> Hosts -> SSH Keys -> Admin Credentials -> Configuration -> Review -> Deploy. Host fields auto-generated based on selected topology. "Create & Deploy" triggers deployment immediately; "Create Only" saves as pending. Step-by-step reduces cognitive load for complex topology configurations.

**Q27. Deployment scope?**

| Option | Description |
|--------|-------------|
| Full deploy only | Always run all tags |
| Full deploy + partial re-runs | Select specific tags for re-execution |

**Chosen: Full deploy + partial re-runs.** Initial deployment uses all tags (install, config, replication, security, summary). Re-run operation lets admins select specific tags for targeted changes (e.g., just `monitoring` or `backup`). Matches how the underlying Ansible playbook already supports tag-based partial runs.

---

## 3. Technical Stack and Use Cases

### Backend

| Technology | Version | Use Case |
|------------|---------|----------|
| Python | 3.11+ | Runtime -- required for asyncio task groups and modern type hints |
| FastAPI | >=0.115.0 | Web framework -- async routes, auto-OpenAPI, dependency injection, lifespan hooks for background tasks |
| SQLAlchemy | 2.0 (async) | ORM -- async session with asyncpg driver, mapped_column declarative models |
| Alembic | >=1.13.0 | Database migrations -- autogenerated revisions, runs on container startup before uvicorn binds |
| Pydantic | v2 (>=2.7.0) | Request/response validation -- type-safe schemas, field-level error messages, `repr=False` for sensitive fields |
| pydantic-settings | >=2.3.0 | Configuration -- loads all settings from environment variables with type coercion and validation |
| argon2-cffi | >=23.1.0 | Password hashing -- argon2id algorithm, library defaults, wrapped in `run_in_threadpool` |
| python-jose | >=3.3.0 | JWT tokens -- access token creation/verification, RS256/HS256 |
| cryptography | >=43.0.0 | Secrets encryption -- AES-256-GCM encrypt/decrypt with 32-byte master key |
| PyMongo | >=4.7.0 | MongoDB connection -- sync driver used in `run_in_threadpool` for monitoring and user operations |
| asyncssh | >=2.14.0 | SSH operations -- async SSH connections for node restart, backup, and deployment commands |
| httpx | >=0.27.0 | HTTP client -- Slack webhook notifications, also used as async test client |
| slowapi | >=0.1.9 | Rate limiting -- 5 req/min per IP on login endpoint, configurable |
| pyyaml | >=6.0 | YAML generation -- inventory `group_vars/all.yml` for Ansible deployment |
| ansible-core | latest | Deployment execution -- installed in Docker image, runs `ansible-playbook` as subprocess |
| asyncpg | >=0.30.0 | PostgreSQL driver -- async driver for SQLAlchemy |
| aiosqlite | >=0.20.0 | Test database -- in-memory SQLite for fast unit tests |
| pytest | >=8.2.0 | Testing -- async test support, fixtures, parameterized tests |
| pytest-asyncio | >=0.23.0 | Async test support -- `asyncio_mode = "auto"` for async test functions |
| testcontainers | >=4.4.0 | Integration tests -- spins up real PostgreSQL container for end-to-end API tests |
| uvicorn | >=0.30.0 | ASGI server -- runs FastAPI with standard extras (websockets, httptools) |

### Frontend

| Technology | Version | Use Case |
|------------|---------|----------|
| React | 19 | UI framework -- component-based SPA with hooks |
| TypeScript | ~6.0 | Type safety -- compile-time type checking for all components and API calls |
| Vite | 8 | Build tool -- fast HMR in development, optimized production builds |
| TanStack Query | >=5.97.0 | Server state -- caching, refetching, polling (30s for metrics, 2s for job status) |
| React Router | v7 | Client routing -- protected routes, nested layouts, route params |
| Tailwind CSS | 4 | Styling -- utility-first CSS, responsive design, dark mode support |
| recharts | >=3.8.0 | Charts -- time-series line charts for ops/sec, connections, memory, cache |
| axios | >=1.15.0 | HTTP client -- interceptors for JWT injection and automatic token refresh on 401 |
| react-hook-form | >=7.72.0 | Form management -- controlled forms with validation, multi-step wizard state |
| zod | >=4.3.0 | Schema validation -- frontend form validation matching backend Pydantic schemas |
| EventSource (native) | -- | SSE client -- real-time deployment log streaming from `GET /api/jobs/{id}/logs` |

### Infrastructure

| Technology | Version | Use Case |
|------------|---------|----------|
| Docker Compose | 3.9 | Orchestration -- three services (db, api, web) with health checks and volume mounts |
| PostgreSQL | 15-alpine | Database -- JSONB config storage, INET types, partial unique indexes, TIMESTAMPTZ |
| nginx | latest | Reverse proxy -- serves React SPA, proxies `/api/*` to FastAPI, TLS termination |
| uvicorn | >=0.30.0 | Application server -- runs inside the API container with ProxyHeadersMiddleware |

---

## 4. Architecture Diagram

```
 +---------------------------------------------------------------+
 |                        Browser (React SPA)                     |
 |  Login | Clusters | Monitoring | Operations | Wizard | Alerts  |
 +-------------------------------+-------------------------------+
                                 |
                      HTTPS (JWT in Authorization header)
                      SSE (EventSource for log streaming)
                                 |
                                 v
 +---------------------------------------------------------------+
 |                    nginx (reverse proxy)                       |
 |  - Serves React build for all non-API routes                  |
 |  - Proxies /api/* to FastAPI container                        |
 |  - TLS termination (optional)                                 |
 +-------------------------------+-------------------------------+
                                 |
                            HTTP :8000
                                 |
                                 v
 +---------------------------------------------------------------+
 |               FastAPI Backend (Python 3.11+)                   |
 |                                                                |
 |  +------------------+  +-------------------+  +--------------+ |
 |  | API Layer        |  | Service Layer     |  | Background   | |
 |  | - auth_router    |  | - auth_service    |  | Tasks        | |
 |  | - user_router    |  | - user_service    |  | - poller     | |
 |  | - cluster_router |  | - cluster_service |  |   (30s loop) | |
 |  | - host_router    |  | - host_service    |  | - job_worker | |
 |  | - secret_router  |  | - secret_service  |  |   (2s poll)  | |
 |  | - metrics_router |  | - monitor_service |  | - cleanup    | |
 |  | - alert_router   |  | - alert_service   |  |   (24h)      | |
 |  | - job_router     |  | - job_service     |  |              | |
 |  | - audit_router   |  | - audit_service   |  |              | |
 |  | - log_stream     |  | - ssh_service     |  |              | |
 |  +------------------+  +-------------------+  +--------------+ |
 |                                                                |
 |  +------------------+  +-------------------+                   |
 |  | Operations       |  | Deployment        |                   |
 |  | - restart_ops    |  | - inventory_gen   |                   |
 |  | - user_ops       |  | - deploy_ops      |                   |
 |  | - backup_ops     |  | - ansible subprocess                 |
 |  +------------------+  +-------------------+                   |
 +--------+----------------+----------------+--------------------+
          |                |                |
          v                v                v
 +----------------+  +-----------+  +-------------------+
 | PostgreSQL 15  |  | MongoDB   |  | SSH Hosts         |
 | - users        |  | Clusters  |  | - systemctl       |
 | - clusters     |  | (PyMongo) |  | - pbm             |
 | - secrets      |  |           |  | - mongodump       |
 | - metrics      |  |           |  | - ansible-playbook|
 | - alerts       |  |           |  |   (subprocess)    |
 | - jobs         |  |           |  |                   |
 | - audit_logs   |  |           |  |                   |
 +----------------+  +-----------+  +-------------------+
```

---

## 5. Data Flow Diagrams

### Flow 1: User Authentication

```
Browser                        FastAPI                        PostgreSQL
  |                               |                               |
  |  POST /api/auth/login         |                               |
  |  { username, password }       |                               |
  |------------------------------>|                               |
  |                               |  SELECT user WHERE username   |
  |                               |------------------------------>|
  |                               |  user row (password_hash)     |
  |                               |<------------------------------|
  |                               |                               |
  |                               |  argon2.verify(password,      |
  |                               |    password_hash)             |
  |                               |                               |
  |                               |  [If fail] INSERT audit_log   |
  |                               |    (login_failed, username,   |
  |                               |     IP, user_agent)           |
  |                               |  Return 401                   |
  |                               |                               |
  |                               |  [If pass] Create JWT access  |
  |                               |    token (60 min TTL)         |
  |                               |  Create refresh token         |
  |                               |    (7 day TTL)                |
  |                               |  INSERT refresh_tokens        |
  |                               |    (sha256 hash)              |
  |                               |------------------------------>|
  |                               |                               |
  |                               |  INSERT audit_log             |
  |                               |    (login, user_id, IP)       |
  |                               |------------------------------>|
  |                               |                               |
  |  { access_token, user }       |                               |
  |  Set-Cookie: refresh_token    |                               |
  |<------------------------------|                               |
  |                               |                               |
  |  [Subsequent requests]        |                               |
  |  Authorization: Bearer <jwt>  |                               |
  |------------------------------>|                               |
  |                               |  jose.decode(jwt) -> user_id  |
  |                               |  SELECT user + role           |
  |                               |  require_role() check         |
  |                               |                               |
  |  [On 401] POST /api/auth/     |                               |
  |    refresh (cookie auto-sent) |                               |
  |------------------------------>|                               |
  |  New access_token             |                               |
  |<------------------------------|                               |
```

### Flow 2: Create Cluster + Hosts

```
Browser                        FastAPI                        PostgreSQL
  |                               |                               |
  |  POST /api/secrets            |                               |
  |  { name, type: "ssh_key",    |                               |
  |    value: "-----BEGIN..." }   |                               |
  |------------------------------>|                               |
  |                               |  crypto.encrypt(value)        |
  |                               |    -> ciphertext, nonce, tag  |
  |                               |  INSERT secrets               |
  |                               |------------------------------>|
  |                               |  INSERT audit_log (create,    |
  |                               |    secret)                    |
  |                               |------------------------------>|
  |  { id, name, type }           |                               |
  |  (no plaintext returned)      |                               |
  |<------------------------------|                               |
  |                               |                               |
  |  POST /api/clusters           |                               |
  |  { name, topology: "pss",    |                               |
  |    mongodb_version: "8.0",    |                               |
  |    config: {...} }            |                               |
  |------------------------------>|                               |
  |                               |  INSERT clusters              |
  |                               |------------------------------>|
  |                               |  INSERT audit_log (create,    |
  |                               |    cluster)                   |
  |  { id, name, status:          |                               |
  |    "pending", ... }           |                               |
  |<------------------------------|                               |
  |                               |                               |
  |  POST /api/clusters/{id}/     |                               |
  |    hosts                      |                               |
  |  { hostname, ip_address,      |                               |
  |    role: "primary",           |                               |
  |    ssh_key_secret_id }        |                               |
  |------------------------------>|                               |
  |                               |  Verify secret exists         |
  |                               |  INSERT cluster_hosts         |
  |                               |------------------------------>|
  |                               |  INSERT audit_log (create,    |
  |                               |    host)                      |
  |  { id, hostname, role, ... }  |                               |
  |<------------------------------|                               |
```

### Flow 3: Monitoring (Background Poller)

```
Poller (30s loop)              FastAPI Services               PostgreSQL
  |                               |                               |
  |  For each cluster             |                               |
  |  (status != 'pending'):       |                               |
  |                               |                               |
  |  1. Get cluster + admin       |                               |
  |     credentials secret_id     |                               |
  |------------------------------>|  SELECT cluster, secret       |
  |                               |------------------------------>|
  |                               |  crypto.decrypt(ciphertext)   |
  |                               |    -> admin password          |
  |                               |                               |
  |  2. Connect PyMongo to        |                               |
  |     primary:37017             |                               |
  |     (in threadpool)           |                               |
  |                               |                               |
  |  3. Run rs.status()           |     MongoDB Cluster           |
  |     + serverStatus()          |  +-----------------------+    |
  |     + dbStats()               |->| rs_state, members,    |    |
  |                               |  | connections, ops,     |    |
  |                               |  | memory, cache, disk   |    |
  |                               |<-+-----------------------+    |
  |                               |                               |
  |  4. Parse metrics             |                               |
  |  5. Compute ops/sec rates     |                               |
  |     (delta from previous)     |                               |
  |                               |                               |
  |  6. Store snapshot            |  INSERT cluster_metrics       |
  |------------------------------>|------------------------------>|
  |                               |                               |
  |  7. Check thresholds          |                               |
  |     for 6 metrics:            |                               |
  |     - replication_lag         |                               |
  |     - connections             |                               |
  |     - disk_usage              |                               |
  |     - memory                  |                               |
  |     - cache_pressure          |                               |
  |     - member_down             |                               |
  |                               |                               |
  |  8. Alert lifecycle:          |                               |
  |     - Breached + no active    |  INSERT cluster_alerts        |
  |       -> create alert         |------------------------------>|
  |     - Breached + active       |  UPDATE last_triggered_at     |
  |       -> update alert         |------------------------------>|
  |     - Normal + active         |  UPDATE status='resolved'     |
  |       -> resolve alert        |------------------------------>|
  |                               |                               |
  |  9. Update cluster status     |  UPDATE clusters.status       |
  |     healthy/degraded/failed   |------------------------------>|
  |                               |                               |
  | 10. Slack (new alerts only)   |  POST to SLACK_WEBHOOK_URL    |
  |     with 15min debounce       |------> Slack                  |
  |                               |                               |
  | 11. Close PyMongo connection  |                               |
```

### Flow 4: Day-2 Operation (PBM Backup Example)

```
Browser                 FastAPI API             Job Worker              SSH Host
  |                        |                        |                      |
  |  POST /api/clusters/   |                        |                      |
  |    {id}/ops/pbm-backup |                        |                      |
  |  {}                    |                        |                      |
  |----------------------->|                        |                      |
  |                        |  INSERT jobs            |                      |
  |                        |  (status: pending,      |                      |
  |                        |   operation: pbm_backup)|                      |
  |                        |  INSERT audit_log       |                      |
  |  { job_id, status:     |                        |                      |
  |    "pending" }         |                        |                      |
  |<-----------------------|                        |                      |
  |                        |                        |                      |
  |  [Poll every 2s]       |                        |                      |
  |  GET /api/jobs/{id}    |                        |                      |
  |----------------------->|                        |                      |
  |                        |                        |  [Worker picks up]   |
  |                        |                        |  UPDATE status=      |
  |                        |                        |    running           |
  |                        |                        |                      |
  |                        |                        |  Decrypt SSH key     |
  |                        |                        |  from secrets vault  |
  |                        |                        |                      |
  |                        |                        |  asyncssh.connect()  |
  |                        |                        |--------------------->|
  |                        |                        |                      |
  |                        |                        |  "pbm backup"        |
  |                        |                        |--------------------->|
  |                        |                        |  exit_code=0         |
  |                        |                        |<---------------------|
  |                        |                        |                      |
  |                        |                        |  Poll "pbm status"   |
  |                        |                        |  every 5s until done |
  |                        |                        |<--->                 |
  |                        |                        |                      |
  |                        |                        |  UPDATE status=      |
  |                        |                        |    success           |
  |                        |                        |  result: { backup_   |
  |                        |                        |    name, duration }  |
  |                        |                        |                      |
  |  GET /api/jobs/{id}    |                        |                      |
  |----------------------->|                        |                      |
  |  { status: "success",  |                        |                      |
  |    result: {...} }     |                        |                      |
  |<-----------------------|                        |                      |
```

### Flow 5: Full Deployment (Wizard -> Ansible)

```
Browser                 FastAPI API         Job Worker          Subprocess
  |                        |                    |                    |
  |  [Wizard Step 1-6]     |                    |                    |
  |  Creates cluster,      |                    |                    |
  |  hosts, secrets via     |                    |                    |
  |  existing CRUD APIs     |                    |                    |
  |                        |                    |                    |
  |  [Wizard Step 7]       |                    |                    |
  |  POST /api/clusters/   |                    |                    |
  |    {id}/ops/deploy     |                    |                    |
  |  { tags: [install,     |                    |                    |
  |    config, replication, |                    |                    |
  |    security, summary] } |                    |                    |
  |----------------------->|                    |                    |
  |                        |  INSERT jobs       |                    |
  |                        |  (deploy, pending) |                    |
  |  { job_id }            |                    |                    |
  |<-----------------------|                    |                    |
  |                        |                    |                    |
  |  EventSource           |                    |  [Worker picks up] |
  |  GET /api/jobs/{id}/   |                    |                    |
  |    logs                |                    |  1. Check no other |
  |----------------------->|                    |     deploy running |
  |  text/event-stream     |                    |                    |
  |<-----------------------|                    |  2. Set cluster    |
  |                        |                    |     status =       |
  |                        |                    |     'deploying'    |
  |                        |                    |                    |
  |                        |                    |  3. Generate temp  |
  |                        |                    |     inventory:     |
  |                        |                    |   /tmp/deploy-{id}/|
  |                        |                    |     hosts          |
  |                        |                    |     group_vars/    |
  |                        |                    |       all.yml      |
  |                        |                    |     keys/*.pem     |
  |                        |                    |     (mode 0600)    |
  |                        |                    |                    |
  |                        |                    |  4. asyncio.create_|
  |                        |                    |     subprocess_exec|
  |                        |                    |------------------->|
  |                        |                    |  ansible-playbook  |
  |                        |                    |  -i /tmp/deploy-.. |
  |                        |                    |  --tags install,...|
  |                        |                    |                    |
  |                        |                    |  5. Read stdout    |
  |  data: PLAY [Install   |  Queue.put(line)  |     line by line   |
  |    and Configure] ***  |<-------------------|<-------------------|
  |  data: TASK [Gather    |  Queue.put(line)  |                    |
  |    Facts] ****         |<-------------------|<-------------------|
  |  data: ok: [primary]   |  Queue.put(line)  |                    |
  |  ...                   |<-------------------|<-------------------|
  |                        |                    |                    |
  |                        |                    |  6. Process exits  |
  |                        |                    |<-------------------|
  |                        |                    |                    |
  |                        |                    |  7. Store full log |
  |                        |                    |     in jobs.result |
  |                        |                    |                    |
  |                        |                    |  8. Update cluster |
  |                        |                    |     status =       |
  |                        |                    |     healthy/failed |
  |                        |                    |     last_deployed_ |
  |                        |                    |     at = now()     |
  |                        |                    |                    |
  |  event: done           |  Queue.put(None)  |  9. shutil.rmtree  |
  |  (close EventSource)   |<-------------------|     (cleanup)      |
  |                        |                    |                    |
  |  [Terminal shows        |                    |                    |
  |   success/failure       |                    |                    |
  |   banner]              |                    |                    |
```

---

## 6. Database Schema

### Entity Relationship Diagram

```
  +----------+      +------------+      +---------------+
  |  roles   |      |   users    |      | refresh_tokens|
  |----------|      |------------|      |---------------|
  | id (PK)  |<-----| role_id    |<-----| user_id (FK)  |
  | name     |      | id (PK)    |      | id (PK)       |
  | desc     |      | username   |      | token_hash    |
  +----------+      | email      |      | expires_at    |
                    | pass_hash  |      | revoked_at    |
                    | disabled   |      +---------------+
                    | created_at |
                    | last_login |
                    +-----+------+
                          |
          +---------------+---------------+----------------+
          |               |               |                |
          v               v               v                v
  +---------------+ +----------+ +-------------+ +------------+
  | audit_logs    | | secrets  | |  clusters   | |   jobs     |
  |---------------| |----------| |-------------| |------------|
  | id (PK, BIG) | | id (PK)  | | id (PK)     | | id (PK)    |
  | user_id (FK?) | | name     | | name        | | cluster_id |
  | username      | | type     | | topology    | | operation  |
  | action        | | cipher   | | version     | | status     |
  | resource_type | | nonce    | | port        | | params     |
  | resource_id   | | auth_tag | | rs_name     | | result     |
  | ip_address    | | created_ | | config (J)  | | created_by |
  | user_agent    | |   by(FK) | | status      | | started_at |
  | occurred_at   | +----+-----+ | admin_cred  | | completed  |
  +---------------+      |      |   _secret_id | +-----+------+
                         |      | created_by   |       |
                         |      +------+-------+       |
                         |             |               |
                         +<-----+------+               |
                                |                      |
                    +-----------+----------+           |
                    |                      |           |
                    v                      v           |
           +---------------+    +------------------+  |
           | cluster_hosts |    | cluster_metrics  |  |
           |---------------|    |------------------|  |
           | id (PK)       |    | id (PK, BIG)     |  |
           | cluster_id(FK)|    | cluster_id (FK)  |  |
           | hostname      |    | collected_at     |  |
           | ip_address    |    | rs_state         |  |
           | role          |    | members_up/total |  |
           | ssh_user      |    | replication_lag  |  |
           | ssh_port      |    | connections      |  |
           | ssh_key_      |    | ops counters     |  |
           |   secret_id   |    | memory/cache     |  |
           +-------+-------+    | storage          |  |
                   |            +------------------+  |
                   |                                   |
                   +----->  secrets (FK)               |
                                                      |
                                            +------------------+
                                            | cluster_alerts   |
                                            |------------------|
                                            | id (PK)          |
                                            | cluster_id (FK)  |
                                            | metric           |
                                            | severity         |
                                            | message          |
                                            | threshold_value  |
                                            | actual_value     |
                                            | status           |
                                            | first_triggered  |
                                            | last_triggered   |
                                            | resolved_at      |
                                            | notified_at      |
                                            +------------------+
```

### 9 Tables

| Table | PK Type | Description |
|-------|---------|-------------|
| `roles` | SERIAL | 3 seeded rows: admin, operator, viewer |
| `users` | UUID | Dashboard user accounts with argon2id password hash |
| `refresh_tokens` | UUID | Revocable JWT refresh tokens (sha256 hash stored) |
| `secrets` | UUID | AES-256-GCM encrypted credentials (SSH keys, passwords, S3 creds) |
| `clusters` | UUID | MongoDB cluster registry with JSONB config snapshot |
| `cluster_hosts` | UUID | Hosts belonging to clusters with role-based group assignment |
| `cluster_metrics` | BIGSERIAL | Time-series metric snapshots from PyMongo polling |
| `cluster_alerts` | UUID | Threshold-based alerts with lifecycle (active -> resolved) |
| `audit_logs` | BIGSERIAL | Immutable log of auth events and all write operations |
| `jobs` | UUID | Async operation queue (day-2 ops + deployments) |

### Key Design Decisions

- **UUIDs for entity tables** -- prevents enumeration attacks, safe for distributed systems. BIGSERIAL for high-write tables (metrics, audit) for write throughput.
- **JSONB for `clusters.config`** -- stores the full effective `group_vars` configuration. Flexible schema accommodates different topology parameters without column sprawl. Source of truth for deployment inventory generation.
- **Immutable secrets** -- `secrets` has no `updated_at` column. Rotation = create new secret, update the reference, optionally delete the old one. The audit log preserves the history of which secret was active when.
- **Nullable `audit_logs.user_id`** -- failed login attempts where the username does not match any user still get recorded. The `username` field is denormalized for this purpose.
- **No credentials in `jobs.params`** -- job parameters reference secrets by ID (`password_secret_id`, `ssh_key_secret_id`), never by value. The job worker decrypts at execution time.
- **Partial unique index on alerts** -- `UNIQUE (cluster_id, metric) WHERE status = 'active'` ensures only one active alert per metric per cluster, enabling deduplication at the database level.

---

## 7. API Reference

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/login` | Public | Authenticate with username/password, returns JWT + refresh token |
| POST | `/api/auth/refresh` | Public (cookie) | Exchange refresh token for new access token |
| POST | `/api/auth/logout` | Authenticated | Revoke current refresh token |
| GET | `/api/auth/me` | Authenticated | Get current user profile and role |

### Users

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/users` | admin | List all users |
| POST | `/api/users` | admin | Create new user with role assignment |
| GET | `/api/users/{id}` | admin | Get user details |
| PATCH | `/api/users/{id}` | admin | Update user role, disabled status, or password |
| DELETE | `/api/users/{id}` | admin | Delete user (cascades refresh tokens) |

### Clusters

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/clusters` | viewer+ | List all clusters |
| POST | `/api/clusters` | operator+ | Create new cluster with topology and config |
| GET | `/api/clusters/{id}` | viewer+ | Get cluster details including JSONB config |
| PATCH | `/api/clusters/{id}` | operator+ | Update cluster fields or merge into config JSONB |
| DELETE | `/api/clusters/{id}` | admin | Delete cluster (cascades hosts, metrics, alerts, jobs) |

### Cluster Hosts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/clusters/{id}/hosts` | viewer+ | List hosts for a cluster |
| POST | `/api/clusters/{id}/hosts` | operator+ | Add host with role, IP, SSH key reference |
| PATCH | `/api/clusters/{id}/hosts/{host_id}` | operator+ | Update host details |
| DELETE | `/api/clusters/{id}/hosts/{host_id}` | operator+ | Remove host from cluster |

### Secrets

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/secrets` | operator+ | List secret metadata only (no plaintext ever returned) |
| POST | `/api/secrets` | operator+ | Create secret (plaintext in body, encrypted server-side) |
| DELETE | `/api/secrets/{id}` | operator+ | Delete secret (only if no FK references) |

### Metrics

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/clusters/{id}/metrics/latest` | viewer+ | Latest metric snapshot with computed ops/sec rates |
| GET | `/api/clusters/{id}/metrics?range=1h\|6h\|24h\|7d` | viewer+ | Downsampled time-series for charts |
| POST | `/api/clusters/{id}/metrics/refresh` | operator+ | Trigger immediate poll, return latest snapshot |

### Alerts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/clusters/{id}/alerts?status=active\|resolved` | viewer+ | Per-cluster alert list |
| PATCH | `/api/clusters/{id}/alerts/{alert_id}` | operator+ | Manually resolve an alert |
| GET | `/api/alerts?status=active\|resolved&limit=50` | viewer+ | Global alerts across all clusters |
| GET | `/api/alerts/count` | viewer+ | Count of active alerts (for sidebar badge) |

### Jobs / Operations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/clusters/{id}/jobs?status=&limit=20` | viewer+ | List jobs for a cluster |
| GET | `/api/jobs/{job_id}` | viewer+ | Get job status and result |
| POST | `/api/jobs/{job_id}/cancel` | operator+ | Cancel a pending job |
| POST | `/api/clusters/{id}/ops/restart-node` | operator+ | Restart single MongoDB node via SSH |
| POST | `/api/clusters/{id}/ops/rolling-restart` | admin | Rolling restart all nodes (secondaries first) |
| POST | `/api/clusters/{id}/ops/rotate-password` | admin | Rotate admin password via PyMongo |
| POST | `/api/clusters/{id}/ops/create-user` | operator+ | Create application user via PyMongo |
| POST | `/api/clusters/{id}/ops/delete-user` | operator+ | Delete application user via PyMongo |
| POST | `/api/clusters/{id}/ops/pbm-backup` | operator+ | Trigger PBM backup via SSH |
| POST | `/api/clusters/{id}/ops/pbm-restore` | admin | Restore from PBM timestamp via SSH |
| POST | `/api/clusters/{id}/ops/pbm-list` | operator+ | List PBM backups via SSH |
| POST | `/api/clusters/{id}/ops/mongodump-s3` | operator+ | mongodump piped to S3 via SSH |
| POST | `/api/clusters/{id}/ops/deploy` | admin | Full Ansible deployment |
| POST | `/api/clusters/{id}/ops/rerun` | admin | Re-run playbook with selected tags |

### Audit Logs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/audit-logs?limit=50&cursor=` | viewer+ | Paginated audit log with filters |

### Log Streaming

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/jobs/{job_id}/logs` | viewer+ | SSE stream of deployment logs (text/event-stream) |

### Conventions

- **Pagination:** Cursor-based with `?limit=50&cursor=<opaque>`.
- **Filtering:** Query params (e.g., `?role=admin`, `?topology=pss`, `?status=active`).
- **Errors:** RFC 7807 problem+json format: `{ type, title, status, detail }`.
- **Validation:** Pydantic models per endpoint. 422 with field-level errors on validation failure.
- **Rate limiting:** 5 requests/minute per IP on `/api/auth/login`. 429 with `Retry-After` header.
- **OpenAPI docs:** Available at `/api/docs` (Swagger UI) and `/api/openapi.json`. Disable in production with `EXPOSE_OPENAPI_DOCS=false`.

---

## 8. Frontend Pages and Components

### Pages

| Route | Access | Page Component | Description |
|-------|--------|----------------|-------------|
| `/login` | Public | `LoginPage` | Username/password form, redirects to `/clusters` on success |
| `/` | Authenticated | -- | Redirects to `/clusters` |
| `/clusters` | viewer+ | `ClustersPage` | Sortable, paginated cluster list with status badges |
| `/clusters/new` | operator+ | `ClusterNewPage` | 7-step topology wizard (DeploymentWizard) |
| `/clusters/:id` | viewer+ | `ClusterDetailPage` | Tabbed detail: Overview, Monitoring, Alerts, Operations |
| `/users` | admin | `UsersPage` | User CRUD with role assignment |
| `/secrets` | operator+ | `SecretsPage` | Secret metadata list, create new, delete unused |
| `/alerts` | viewer+ | `AlertsPage` | Global alerts across all clusters |
| `/audit` | viewer+ | `AuditPage` | Paginated audit log with filter toolbar |
| `/account` | Authenticated | `AccountPage` | Change own password |

### Components

| Component | Location | Description |
|-----------|----------|-------------|
| `Layout` | `components/Layout.tsx` | Top bar with user menu, left sidebar navigation with route links |
| `RequireRole` | `components/RequireRole.tsx` | Route guard wrapper, hides routes/buttons based on user role |
| `MonitoringTab` | `components/MonitoringTab.tsx` | 4 stat cards (RS state, lag, connections, disk) + 4 recharts LineCharts (ops/sec, connections, memory, cache) with range selector |
| `AlertsTab` | `components/AlertsTab.tsx` | Per-cluster alerts table with severity badges, resolve button |
| `AlertBadge` | `components/AlertBadge.tsx` | Red count badge in sidebar showing active alert count, auto-refreshes every 30s |
| `OperationsTab` | `components/OperationsTab.tsx` | 3x3 grid of action cards (role-filtered) + recent jobs table with auto-refresh |
| `OperationModal` | `components/OperationModal.tsx` | Per-operation form (host picker, secret picker, datetime picker, etc.) + job status poller |
| `JobStatusBadge` | `components/JobStatusBadge.tsx` | Colored status indicator: gray (pending), blue (running), green (success), red (failed) |
| `DeploymentWizard` | `components/DeploymentWizard.tsx` | 7-step form: Basics, Hosts (auto-generated by topology), SSH Keys, Admin Creds, Config toggles, Review, Deploy |
| `LogStream` | `components/LogStream.tsx` | Dark terminal-like pre block with auto-scroll, EventSource connection to SSE endpoint |

### Frontend Architecture

- **Auth flow:** Access token stored in memory (not localStorage). Refresh token in httpOnly cookie. Axios interceptor adds `Authorization: Bearer` header. On 401, interceptor calls `/api/auth/refresh` and retries once.
- **Server state:** TanStack Query manages caching, refetching, and background polling. Metrics refetch every 30s. Job status refetches every 2s during active operations.
- **Form validation:** react-hook-form + zod schemas. Validation runs client-side before submission; server-side Pydantic provides the authoritative check.
- **RBAC in UI:** `/api/auth/me` response includes the role. `RequireRole` wrapper hides routes and buttons. Authoritative checks always happen on the server.

---

## 9. Hosting and Deployment Guide

### Prerequisites

- Docker Engine 20.10+ and Docker Compose v2
- At least 2 GB RAM and 10 GB disk
- A domain name (for TLS) or localhost for development
- Network access from the dashboard host to the managed MongoDB nodes (SSH port 22 and MongoDB port 37017)

### Quick Start (5 minutes)

```bash
# 1. Clone the repository
git clone <repo-url>
cd database-ansible-playbook/dashboard

# 2. Create .env file
cp .env.example .env

# 3. Generate a MASTER_KEY (32-byte base64-encoded)
python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"
# Paste the output as MASTER_KEY in .env

# 4. Generate a JWT_SECRET (random string)
python3 -c "import secrets;print(secrets.token_urlsafe(32))"
# Paste the output as JWT_SECRET in .env

# 5. Set the database password
# Edit DB_PASSWORD in .env

# 6. Start the stack
docker-compose up -d --build

# 7. Seed the initial admin user
docker-compose exec api python -m app.seed admin your-secure-password

# 8. Open in browser
# http://localhost (or your domain)
```

### Environment Variables

#### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string. Set automatically by docker-compose: `postgresql+asyncpg://dashboard:${DB_PASSWORD}@db:5432/dashboard` |
| `MASTER_KEY` | Base64-encoded 32-byte key for AES-256-GCM secret encryption. Generate with `python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"`. App refuses to start if missing or wrong length. |
| `JWT_SECRET` | Random string used to sign JWT access tokens. Generate with `python3 -c "import secrets;print(secrets.token_urlsafe(32))"`. |
| `DB_PASSWORD` | PostgreSQL password used in docker-compose for both the db service and DATABASE_URL. |

#### Authentication and Authorization

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_ACCESS_TTL_MINUTES` | `60` | Access token lifetime in minutes |
| `JWT_REFRESH_TTL_DAYS` | `7` | Refresh token lifetime in days |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | `5` | Max login attempts per IP per minute (429 after) |

#### API Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed CORS origins |
| `EXPOSE_OPENAPI_DOCS` | `true` | Show Swagger UI at `/api/docs`. Set `false` in production |
| `LOG_LEVEL` | `INFO` | Python logging level (DEBUG, INFO, WARNING, ERROR) |

#### Monitoring Poller

| Variable | Default | Description |
|----------|---------|-------------|
| `POLLER_ENABLED` | `true` | Enable/disable background metric polling without restart |
| `POLLER_INTERVAL_SECONDS` | `30` | Seconds between poll cycles |
| `POLLER_TIMEOUT_SECONDS` | `10` | PyMongo connection timeout per cluster |
| `METRICS_RETENTION_DAYS` | `7` | Days to keep metric snapshots before cleanup |

#### Alert Thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_DEBOUNCE_MINUTES` | `15` | Minutes between Slack re-notifications for the same alert |
| `ALERT_REPLICATION_LAG_WARNING` | `5.0` | Replication lag warning threshold (seconds) |
| `ALERT_REPLICATION_LAG_CRITICAL` | `10.0` | Replication lag critical threshold (seconds) |
| `ALERT_CONNECTIONS_WARNING` | `500` | Connection count warning threshold |
| `ALERT_CONNECTIONS_CRITICAL` | `800` | Connection count critical threshold |
| `ALERT_DISK_USAGE_WARNING` | `70` | Disk usage warning threshold (percent) |
| `ALERT_DISK_USAGE_CRITICAL` | `85` | Disk usage critical threshold (percent) |
| `ALERT_MEMORY_WARNING` | `80` | Memory usage warning threshold (percent) |
| `ALERT_MEMORY_CRITICAL` | `90` | Memory usage critical threshold (percent) |
| `ALERT_CACHE_DIRTY_WARNING` | `20` | WiredTiger cache dirty pages warning (percent) |
| `ALERT_MEMBER_DOWN_CRITICAL` | `1` | Number of down members that triggers critical alert |

#### Slack Notifications

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_WEBHOOK_URL` | (empty) | Slack incoming webhook URL. Empty = Slack disabled |
| `SLACK_CHANNEL` | (empty) | Slack channel override (uses webhook default if empty) |

#### Deployment (Ansible)

| Variable | Default | Description |
|----------|---------|-------------|
| `PLAYBOOK_PATH` | `/playbook` | Path to the Ansible playbook directory inside the container |
| `DEPLOY_TIMEOUT_SECONDS` | `1800` | Maximum deployment duration before subprocess is killed (30 min) |

### Production Deployment

#### Single Server

The default `docker-compose.yml` runs all three services on one host:

```bash
# Build and start in detached mode
docker-compose up -d --build

# Check service health
docker-compose ps
docker-compose logs -f api
```

#### With TLS

Configure nginx to terminate TLS by mounting certificate files:

```yaml
# docker-compose.override.yml
services:
  web:
    volumes:
      - /etc/letsencrypt/live/yourdomain.com/fullchain.pem:/etc/nginx/ssl/cert.pem:ro
      - /etc/letsencrypt/live/yourdomain.com/privkey.pem:/etc/nginx/ssl/key.pem:ro
    ports:
      - "443:443"
      - "80:80"
```

Update the nginx config to redirect HTTP to HTTPS and configure the SSL server block.

#### Behind a Load Balancer

If TLS is terminated at the load balancer, ensure:

1. The load balancer passes `X-Forwarded-For` and `X-Forwarded-Proto` headers.
2. `CORS_ALLOWED_ORIGINS` includes the public domain.
3. uvicorn's `ProxyHeadersMiddleware` (enabled by default) trusts the proxy IP for correct client IP in audit logs.

### Backup Strategy

- **PostgreSQL:** Run `pg_dump` daily from a sidecar container or cron job:
  ```bash
  docker-compose exec db pg_dump -U dashboard dashboard > backup-$(date +%Y%m%d).sql
  ```
- **MASTER_KEY:** Back up the `.env` file separately. Without the master key, encrypted secrets cannot be decrypted.
- **Recovery:** Restore the PostgreSQL dump and the same `.env` file to a fresh instance.

### Upgrading

```bash
# Pull latest code
git pull

# Rebuild and restart (Alembic migrations run automatically on API startup)
docker-compose up -d --build

# Verify
docker-compose logs api | grep "Application startup complete"
```

### Monitoring the Dashboard Itself

- **Health check:** `curl http://localhost:8000/api/auth/me` (returns 401 if running, connection refused if down)
- **PostgreSQL:** `docker-compose exec db pg_isready -U dashboard`
- **Logs:** `docker-compose logs -f api` for structured JSON logs with request IDs
- **Metrics:** The `cluster_metrics` table grows at ~2880 rows/cluster/day (one every 30s). Monitor PostgreSQL disk usage accordingly.

---

## 10. Development Guide

### Local Setup -- Backend

```bash
cd dashboard/backend

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Set environment variables (or create a .env file in backend/)
export DATABASE_URL="sqlite+aiosqlite:///./test.db"
export MASTER_KEY=$(python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())")
export JWT_SECRET="dev-secret-change-me"

# Run Alembic migrations (for PostgreSQL; SQLite uses auto-create)
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### Local Setup -- Frontend

```bash
cd dashboard/frontend

# Install dependencies
npm install

# Start dev server (proxies /api to localhost:8000 via Vite)
npm run dev

# Build for production
npm run build
```

### Running Tests

```bash
# Backend tests (uses aiosqlite in-memory by default)
cd dashboard/backend
pytest tests/ -v

# With coverage
coverage run -m pytest tests/ -v
coverage report --show-missing

# Single test file
pytest tests/test_auth.py -v

# Frontend lint
cd dashboard/frontend
npm run lint
```

### Project Structure

```
dashboard/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                           # FastAPI app factory + lifespan
│   │   ├── seed.py                           # CLI: python -m app.seed <user> <pass>
│   │   ├── core/
│   │   │   ├── config.py                     # Pydantic BaseSettings (all env vars)
│   │   │   ├── database.py                   # Async engine + session factory
│   │   │   ├── security.py                   # JWT create/verify, password hash/verify
│   │   │   ├── crypto.py                     # AES-256-GCM encrypt/decrypt
│   │   │   ├── dependencies.py               # get_db, get_current_user, require_role
│   │   │   └── exceptions.py                 # Problem+JSON exception handlers
│   │   ├── models/
│   │   │   ├── base.py                       # SQLAlchemy DeclarativeBase
│   │   │   ├── role.py                       # Role (admin/operator/viewer)
│   │   │   ├── user.py                       # User with argon2id hash
│   │   │   ├── refresh_token.py              # Revocable refresh tokens
│   │   │   ├── secret.py                     # AES-256-GCM encrypted secrets
│   │   │   ├── cluster.py                    # Cluster registry with JSONB config
│   │   │   ├── cluster_host.py               # Hosts with role-based grouping
│   │   │   ├── cluster_metric.py             # Time-series metric snapshots
│   │   │   ├── cluster_alert.py              # Threshold-based alerts
│   │   │   ├── job.py                        # Async job queue
│   │   │   └── audit_log.py                  # Immutable audit trail
│   │   ├── services/
│   │   │   ├── auth_service.py               # Login, refresh, logout
│   │   │   ├── user_service.py               # User CRUD
│   │   │   ├── secret_service.py             # Create, list, delete (with encryption)
│   │   │   ├── cluster_service.py            # Cluster CRUD
│   │   │   ├── cluster_host_service.py       # Host CRUD nested under cluster
│   │   │   ├── audit_service.py              # Record + query audit events
│   │   │   ├── monitor_service.py            # PyMongo metric collection + thresholds
│   │   │   ├── alert_service.py              # Alert lifecycle + Slack notification
│   │   │   ├── poller.py                     # Background 30s metric polling loop
│   │   │   ├── cleanup_service.py            # Nightly metric retention cleanup
│   │   │   ├── job_service.py                # Job CRUD + operation registry
│   │   │   ├── ssh_service.py                # asyncssh connection wrapper
│   │   │   ├── job_worker.py                 # Background job executor (2s poll)
│   │   │   ├── inventory_generator.py        # Generates Ansible INI + group_vars YAML
│   │   │   └── operations/
│   │   │       ├── restart_ops.py            # restart_node, rolling_restart
│   │   │       ├── user_ops.py               # rotate_password, create/delete user
│   │   │       ├── backup_ops.py             # pbm_backup/restore/list, mongodump_s3
│   │   │       └── deploy_ops.py             # ansible-playbook subprocess + SSE
│   │   └── api/
│   │       ├── schemas/                      # Pydantic request/response models
│   │       │   ├── auth.py
│   │       │   ├── user.py
│   │       │   ├── secret.py
│   │       │   ├── cluster.py
│   │       │   ├── cluster_host.py
│   │       │   ├── metrics.py
│   │       │   ├── alert.py
│   │       │   ├── job.py
│   │       │   └── audit.py
│   │       ├── auth_router.py                # /api/auth/*
│   │       ├── user_router.py                # /api/users/*
│   │       ├── secret_router.py              # /api/secrets/*
│   │       ├── cluster_host_router.py        # /api/clusters/{id}/hosts/*
│   │       ├── metrics_router.py             # /api/clusters/{id}/metrics/*
│   │       ├── alert_router.py               # /api/clusters/{id}/alerts/* + /api/alerts
│   │       ├── job_router.py                 # /api/clusters/{id}/jobs/* + /api/clusters/{id}/ops/*
│   │       ├── audit_router.py               # /api/audit-logs
│   │       └── log_stream_router.py          # /api/jobs/{id}/logs (SSE)
│   ├── alembic/                              # Database migrations
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── alembic.ini
│   ├── tests/
│   │   ├── conftest.py                       # Fixtures: async client, test DB, seed data
│   │   ├── test_crypto.py                    # AES-256-GCM round-trip
│   │   ├── test_auth.py                      # Login, refresh, logout, RBAC
│   │   ├── test_users.py                     # User CRUD + permissions
│   │   ├── test_secrets.py                   # Secret encryption + no-plaintext-return
│   │   ├── test_clusters.py                  # Cluster CRUD + JSONB merge
│   │   ├── test_cluster_hosts.py             # Host CRUD + FK validation
│   │   ├── test_audit.py                     # Audit log emission + filtering
│   │   ├── test_monitor_service.py           # Metric parsing, threshold checking
│   │   ├── test_alert_service.py             # Alert lifecycle, Slack debounce
│   │   ├── test_metrics_api.py               # Metrics endpoints + downsampling
│   │   ├── test_alerts_api.py                # Alert endpoints + RBAC
│   │   ├── test_ssh_service.py               # Mock asyncssh connections
│   │   ├── test_job_service.py               # Job CRUD + status transitions
│   │   ├── test_operations.py                # All 9 operation handlers
│   │   ├── test_job_worker.py                # Worker lifecycle + stale detection
│   │   ├── test_jobs_api.py                  # Job API + RBAC per operation
│   │   ├── test_inventory_generator.py       # INI + YAML + SSH key file generation
│   │   ├── test_deploy_ops.py                # Mock subprocess, log capture, cleanup
│   │   ├── test_deploy_api.py                # Deploy/rerun API + concurrent protection
│   │   └── test_log_stream.py                # SSE event format
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── entrypoint.sh                        # Runs Alembic then uvicorn
├── frontend/
│   ├── src/
│   │   ├── main.tsx                          # React entry point
│   │   ├── App.tsx                           # Route definitions + auth provider
│   │   ├── index.css                         # Tailwind imports
│   │   ├── api/
│   │   │   ├── client.ts                     # Axios instance with JWT interceptors
│   │   │   ├── auth.ts                       # Login, refresh, logout, me
│   │   │   ├── clusters.ts                   # Cluster CRUD
│   │   │   ├── users.ts                      # User CRUD
│   │   │   ├── secrets.ts                    # Secret list, create, delete
│   │   │   ├── metrics.ts                    # Latest + range metrics
│   │   │   ├── alerts.ts                     # Alerts + count
│   │   │   ├── audit.ts                      # Audit log queries
│   │   │   └── jobs.ts                       # Job polling, trigger operations
│   │   ├── hooks/
│   │   │   └── useAuth.ts                    # Auth context: login/logout, token state
│   │   ├── components/
│   │   │   ├── Layout.tsx                    # App shell with sidebar
│   │   │   ├── RequireRole.tsx               # RBAC route guard
│   │   │   ├── MonitoringTab.tsx             # Stat cards + recharts
│   │   │   ├── AlertsTab.tsx                 # Per-cluster alerts
│   │   │   ├── AlertBadge.tsx                # Sidebar alert count
│   │   │   ├── OperationsTab.tsx             # Action cards grid
│   │   │   ├── OperationModal.tsx            # Operation form + job poller
│   │   │   ├── JobStatusBadge.tsx            # Status indicator
│   │   │   ├── DeploymentWizard.tsx          # 7-step topology wizard
│   │   │   └── LogStream.tsx                 # SSE terminal viewer
│   │   └── pages/
│   │       ├── LoginPage.tsx
│   │       ├── ClustersPage.tsx
│   │       ├── ClusterNewPage.tsx
│   │       ├── ClusterDetailPage.tsx
│   │       ├── UsersPage.tsx
│   │       ├── SecretsPage.tsx
│   │       ├── AlertsPage.tsx
│   │       ├── AuditPage.tsx
│   │       └── AccountPage.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
├── nginx/
│   └── default.conf                          # Reverse proxy config
├── docker-compose.yml
└── README.md                                 # This file
```

---

## 11. Phase-by-Phase Summary

### Phase 1 -- Foundation (18 tasks, 113 steps)

| Task | What Was Built |
|------|----------------|
| Task 1 | Backend project scaffold: pyproject.toml, FastAPI app factory, Pydantic settings, async database engine |
| Task 2 | ORM models for all 7 tables (roles, users, refresh_tokens, secrets, clusters, cluster_hosts, audit_logs) + Alembic migrations |
| Task 3 | AES-256-GCM crypto helper (encrypt/decrypt with master key) + JWT create/verify + argon2id password hashing |
| Task 4 | FastAPI dependencies (get_db, get_current_user, require_role) + audit service for recording all state changes |
| Task 5 | Auth service (login with rate limiting, refresh with token rotation, logout with revocation) + auth router |
| Task 6 | User service (CRUD, admin-only) + user router with RBAC enforcement |
| Task 7 | Secret service (create with encryption, list metadata only, delete with FK check) + secret router |
| Task 8 | Cluster service (CRUD with JSONB config merge) + cluster router |
| Task 9 | Cluster host service (CRUD nested under cluster, role validation) + host router |
| Task 10 | Audit log router with cursor-based pagination and filtering + tests |
| Task 11 | Docker Compose (db + api + web), entrypoint.sh (Alembic on startup), nginx reverse proxy config |
| Task 12 | Frontend scaffold: React + Vite + TypeScript + Tailwind CSS setup |
| Task 13 | Frontend auth: LoginPage, axios interceptors with JWT/refresh flow, useAuth hook |
| Task 14 | Frontend shell: Layout component with sidebar, route wiring, RequireRole guard |
| Task 15 | Frontend ClustersPage with TanStack Query: list, create, detail view |
| Task 16 | Frontend remaining pages: UsersPage, SecretsPage, AuditPage, AccountPage |
| Task 17 | Admin seed CLI command (`python -m app.seed`) + README |
| Task 18 | Full test suite execution and verification |

### Phase 2 -- Monitoring (11 tasks, 56 steps)

| Task | What Was Built |
|------|----------------|
| Task 1 | Poller/alert config settings added to BaseSettings + PyMongo dependency |
| Task 2 | ORM models for cluster_metrics and cluster_alerts + Alembic migration with partial unique index |
| Task 3 | Alert service: create/update/resolve lifecycle, Slack webhook with debounce, severity escalation |
| Task 4 | Monitor service: PyMongo connection, rs.status() + serverStatus() + dbStats parsing, ops/sec rate computation, threshold checking |
| Task 5 | Background poller (30s asyncio loop) + cleanup service (nightly metric retention) in FastAPI lifespan |
| Task 6 | Metrics router: /latest with computed rates, /range with downsampled time-series, /refresh for on-demand poll |
| Task 7 | Alert router: per-cluster alerts, manual resolve, global alerts, active count endpoint |
| Task 8 | Frontend: recharts dependency + metrics.ts and alerts.ts API helpers |
| Task 9 | MonitoringTab: 4 stat cards + 4 LineCharts with range selector and auto-refresh |
| Task 10 | AlertsTab + AlertBadge + AlertsPage + ClusterDetailPage with tabbed navigation |
| Task 11 | Full test suite execution and verification |

### Phase 3 -- Day-2 Operations (13 tasks, 56 steps)

| Task | What Was Built |
|------|----------------|
| Task 1 | asyncssh dependency + Job ORM model + Alembic migration with status index |
| Task 2 | Job service: CRUD, operation registry, RBAC tier mapping, status transitions |
| Task 3 | SSH service: asyncssh connect/run/disconnect, in-memory key decryption, timeout handling |
| Task 4 | Restart operations: restart_node (SSH systemctl) + rolling_restart (secondaries-first + stepDown) |
| Task 5 | User operations: rotate_admin_password (PyMongo updateUser) + create/delete app user |
| Task 6 | Backup operations: pbm_backup, pbm_restore, pbm_list (SSH + JSON parse), mongodump_s3 (pipe to S3) |
| Task 7 | Job worker: background asyncio task, 2s poll, sequential execution, stale job detection on startup |
| Task 8 | Job router: generic job endpoints + 9 convenience operation endpoints with tiered RBAC |
| Task 9 | Frontend: jobs.ts API helper + JobStatusBadge component |
| Task 10 | OperationModal: per-operation forms (host picker, secret picker, datetime picker) + job status poller |
| Task 11 | OperationsTab: 3x3 action card grid (role-filtered) + recent jobs table with auto-refresh |
| Task 12 | Updated .env.example and README |
| Task 13 | Full test suite execution and verification |

### Phase 4 -- Full Deployment (9 tasks, 29 steps)

| Task | What Was Built |
|------|----------------|
| Task 1 | Config (PLAYBOOK_PATH, DEPLOY_TIMEOUT_SECONDS) + pyyaml dependency + ansible-core in Dockerfile + playbook volume mount |
| Task 2 | Inventory generator: hosts INI with role-to-group mapping, group_vars/all.yml from JSONB config, SSH key temp files (mode 0600) |
| Task 3 | Deploy operation handler: asyncio.create_subprocess_exec, stdout line-by-line to asyncio.Queue, temp dir cleanup in finally block |
| Task 4 | SSE log stream router: GET /api/jobs/{id}/logs returns text/event-stream, supports live streaming and completed log replay |
| Task 5 | Deploy + rerun API endpoints with concurrent deployment protection (one deploy per cluster at a time) |
| Task 6 | Frontend: LogStream component (dark terminal with auto-scroll + EventSource) + jobs.ts additions for deploy/rerun |
| Task 7 | DeploymentWizard: 7-step form (Basics, Hosts by topology, SSH Keys, Admin Creds, Config toggles, Review, Deploy) |
| Task 8 | Rerun card in OperationsTab: tag checkboxes + LogStream in OperationModal |
| Task 9 | Full test suite execution and verification |

### Final Statistics

| Metric | Value |
|--------|-------|
| Total phases | 4 |
| Total implementation tasks | 51 |
| Total implementation steps | 254 |
| Backend test files | 20 |
| Backend test functions | 86 |
| Backend Python modules | ~60 |
| Frontend source files | 34 |
| API endpoints | 40+ |
| Database tables | 9 (+ 1 roles seed table) |
| Supported topologies | 8 (PSS, PSA, PSP, mixed PSS, Percona PSS, Percona PSA, single-node, standalone) |
| Day-2 operations | 9 (+ deploy + rerun = 11 total) |
| Alert metrics | 6 (replication lag, connections, disk, memory, cache, member down) |
| Environment variables | 30+ |
