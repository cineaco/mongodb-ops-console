# Create MongoDB databases / users / roles from a URI

`mongodb-create-entities.yml` creates **users** and **custom roles** (and, by
extension, the **databases** they belong to) on an *already-running* MongoDB
deployment described by a connection URI. It works for both **standalone** and
**replica-set** deployments and discovers the primary on its own.

This is distinct from the deployment playbooks (`mongodb-playbook.yml`), which are
inventory-group driven. Here a single URI drives the connection, and each host
self-identifies as primary rather than relying on group membership.

## How it works

1. **Parse the URI** — pymongo (in `/opt/mongodb-venv`) parses `mongodb_uri` into
   connection facts (user, password, port, authSource, TLS). The URI is passed via
   an environment variable and the task is `no_log`.
2. **Detect the primary** — every targeted host asks its own `mongod`
   `db.hello().isWritablePrimary`. On a replica set exactly one node answers true;
   on a standalone the single node answers true. The run fails fast if no primary
   is reachable.
3. **Create roles, then users** — only on the primary, using the
   `community.mongodb` modules (`mongodb_role`, `mongodb_user`). Roles are created
   first so users can reference them in the same run.
4. **Validate / summarize** — confirms on the primary and prints a summary.

The replica-set primary propagates the new users/roles to secondaries via normal
replication; you do not run anything on the secondaries.

## Requirements

- Run against this directory's `inventory/` (the inventory used to deploy the
  cluster). The playbook targets `all` by default so the current primary is in
  scope regardless of which node it is.
- `mongosh` on the hosts (already installed by the `mongodb` role) — used for
  primary detection.
- The `community.mongodb` collection and pymongo in `/opt/mongodb-venv` (already
  provisioned by the `mongodb` role).

## Inputs

| Variable | Source | Description |
|----------|--------|-------------|
| `mongodb_uri` | `--extra-vars` / vault | **Required.** Privileged connection string. Not committed. |
| `mongodb_databases` | `entities.yml` | Optional, advisory. Typo-guard for referenced DBs. |
| `mongodb_roles` | `entities.yml` | Optional. Custom roles to create. |
| `mongodb_users` | `entities.yml` | Optional. Users to create. |
| `mongo_target_hosts` | `--extra-vars` | Optional. Host pattern to target (default `all`). |
| `mongodb_port` | defaults | Fallback port when the URI omits one (default `37017`). |

See [`entities.example.yml`](../entities.example.yml) for the full schema of the
entity lists. Copy it to `entities.yml` and edit.

> **Databases are not materialized.** MongoDB drops empty databases, so a database
> only persists once a user or role (or data) lands in it. The `mongodb_databases`
> list is advisory: when non-empty, every `db` referenced by a user/role must be in
> it, otherwise the run fails early (catches typos).

## Usage

Replica set:

```bash
ansible-playbook -i inventory/ mongodb-create-entities.yml \
  -e @entities.yml \
  -e mongodb_uri='mongodb://admin:pw@h1:37017,h2:37017,h3:37017/?replicaSet=rs0&authSource=admin'
```

Standalone:

```bash
ansible-playbook -i inventory/ mongodb-create-entities.yml \
  -e @entities.yml \
  -e mongodb_uri='mongodb://admin:pw@h1:37017/?authSource=admin'
```

Narrow the scope when you already know the primary:

```bash
ansible-playbook -i inventory/ mongodb-create-entities.yml \
  -e @entities.yml -e mongodb_uri='...' -e mongo_target_hosts=primary
```

### Keeping the URI out of the shell history / logs

Put it in a vault file instead of `--extra-vars`:

```bash
ansible-vault create secrets.yml      # add: mongodb_uri: 'mongodb://admin:pw@...'
ansible-playbook -i inventory/ mongodb-create-entities.yml \
  -e @entities.yml -e @secrets.yml --ask-vault-pass
```

## Idempotency

All entities use `state: present`. Users use `update_password: on_create`, so
re-running does not rewrite existing passwords or report spurious changes. Re-runs
are safe and should report `changed: false` once everything exists.

## Tags

`parse`, `detect`, `roles`, `users`, `validate` — e.g. `--tags roles` to (re)create
only roles. `parse` and `detect` always run as prerequisites where needed.

## Scope / limitations

- Standard `mongodb://` URIs only. `mongodb+srv://` (DNS-SRV / Atlas) is not
  supported.
- Creates/ensures entities; it does not drop or rename existing users/roles.
- Designed for a replica set or standalone, not a sharded `mongos` front end.
