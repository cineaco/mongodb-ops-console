# Design: URI-driven MongoDB entity creation playbook

**Date:** 2026-06-26
**Status:** Approved (pending spec review)
**Location:** `utils/ansible/mongodb-ansible-playbook/`

## Problem

The existing playbooks in this directory are **inventory-group driven**: you declare which
host is `primary`/`percona_primary` in the inventory, and creation tasks are gated on group
membership. There is no self-contained way to point at an *already-running* MongoDB deployment
— described only by a connection URI — and create databases, users, or roles on it, letting
the playbook discover the primary on its own.

This design adds an operational playbook that:

- Accepts a standard MongoDB connection URI (standalone **or** replica set).
- Runs on the DB hosts via inventory; each host self-identifies whether it is the writable
  primary, and only that node performs the creates.
- Creates **multiple entities in one run**: custom roles and users (databases are implied,
  not materialized — see "Database semantics").
- Uses the `community.mongodb` collection, consistent with the existing `mongodb` role and its
  pymongo virtualenv at `/opt/mongodb-venv`.

## Confirmed decisions

These were settled during brainstorming and are fixed for this spec:

1. **Execution model** — runs *on the DB hosts via inventory* (not from a remote control node).
2. **Operation granularity** — *multiple entities per run* via lists (roles + users).
3. **Tooling** — *`community.mongodb` modules* (`mongodb_role`, `mongodb_user`, `mongodb_info`,
   `mongodb_shell`), not raw `mongosh` shell-outs for the creates.
4. **Primary detection** — *local self-identification*: each host queries its own `mongod` with
   `hello()`; the one reporting `isWritablePrimary: true` runs the creates. Standalone returns
   `true` on its single node, so the same path covers both topologies.
5. **Database semantics** — *implied by user/role only*. Empty databases are **not** materialized
   (MongoDB drops empty DBs anyway). An optional `mongodb_databases` list is kept purely as a
   typo-guard / summary aid.
6. **Inputs** — a dedicated, committed example vars file (`entities.example.yml`) for the
   entity lists; `mongodb_uri` (carrying admin credentials) supplied at runtime via
   `--extra-vars` or an Ansible Vault file, never committed.

## Scope

**In scope:** standard `mongodb://` URIs with a host list, optional `replicaSet`, `authSource`,
and TLS options; creating custom roles and users; idempotent re-runs; clear failure when no
primary is reachable.

**Out of scope (YAGNI):** `mongodb+srv://` (DNS-SRV / Atlas-style) URIs; dropping/altering
existing entities; sharded-cluster `mongos` routing; materializing empty databases.

## File layout

New files, following the existing convention where the `mongodb` role lives at the top level of
the playbook directory (Ansible resolves roles from the playbook directory; there is no
`ansible.cfg`).

```
mongodb-create-entities.yml          # the playbook: hosts: "{{ mongo_target_hosts | default('all') }}", become
mongodb_entities/
  defaults/main.yml                  # empty entity lists; default port + authSource fallbacks
  tasks/main.yml                     # orchestration (includes the task files below in order)
  tasks/parse-uri.yml                # pymongo parse_uri -> mongo_conn fact (no_log)
  tasks/detect-primary.yml           # hello() -> is_primary fact + ">=1 primary" assertion
  tasks/create-roles.yml             # community.mongodb.mongodb_role loop (primary only)
  tasks/create-users.yml             # community.mongodb.mongodb_user loop (primary only)
  tasks/validate.yml                 # mongodb_info verify + summary debug
entities.example.yml                 # documented example inputs (copy -> entities.yml)
docs/CREATE_ENTITIES.md              # usage documentation
```

## Components

### 1. Playbook — `mongodb-create-entities.yml`

```yaml
- name: Create MongoDB databases/users/roles from a connection URI
  hosts: "{{ mongo_target_hosts | default('all') }}"
  gather_facts: true
  become: true
  roles:
    - mongodb_entities
```

`hosts` defaults to `all` because this inventory is dedicated to a single deployment and
self-identification requires the current primary to be in scope. Override with
`-e mongo_target_hosts=primary` when desired.

### 2. `tasks/parse-uri.yml`

- Pass `mongodb_uri` to `/opt/mongodb-venv/bin/python -c` via an **environment variable**
  (not on the command line, to avoid leaking secrets in `ps`).
- The snippet runs `pymongo.uri_parser.parse_uri(os.environ["MONGODB_URI"])` and prints JSON.
- `register` the result, `no_log: true`, parse with `from_json` into fact **`mongo_conn`**:
  - `user`, `password` — from the parsed URI (may be empty for unauthenticated dev clusters).
  - `port` — first node's port, else `mongodb_port` default (`37017`).
  - `authsource` — `options.authsource` else parsed `database` else `admin`.
  - `replicaset` — `options.replicaset` (informational; detection does not depend on it).
  - `tls` — `options.tls` or `options.ssl` (bool).
- Runs on each targeted host (tiny local command); each host needs `mongo_conn` for its own
  local module calls.

### 3. `tasks/detect-primary.yml`

- `community.mongodb.mongodb_shell` evaluating `db.hello().isWritablePrimary` against the local
  `mongod` (`login_host: 127.0.0.1`, port from `mongo_conn`). `hello`/`isMaster` is allowed
  pre-auth, so this works whether or not auth is enabled.
- `set_fact: is_primary` (bool) from the result.
- A `run_once` assertion fails fast with an actionable message if **no** targeted host reports
  primary (e.g. election in progress, or inventory does not include the current primary). It
  aggregates `is_primary` across `ansible_play_hosts` via `hostvars`.

### 4. `tasks/create-roles.yml`

- Loop `mongodb_roles` with `community.mongodb.mongodb_role`, `when: is_primary | bool`.
- Created **before** users so users may reference custom roles in the same run.
- Per-role fields: `name`, `db` (-> module `database`), optional `privileges`, optional inherited
  `roles`. `state: present`.

### 5. `tasks/create-users.yml`

- Loop `mongodb_users` with `community.mongodb.mongodb_user`, `when: is_primary | bool`.
- Per-user fields: `name`, `db` (-> module `database`), `password`, `roles`. `state: present`.
- `update_password: on_create` so re-runs are clean (no spurious `changed` from re-asserting
  passwords). `no_log: true` on the task to keep passwords out of logs.

### 6. `tasks/validate.yml`

- `community.mongodb.mongodb_info` (filter `users`, `roles`) on the primary to confirm presence.
- Final `debug` summary listing created roles/users (and, if `mongodb_databases` provided, the
  databases they belong to).

### Shared connection parameters (all create/verify tasks)

```yaml
login_host: 127.0.0.1
login_port: "{{ mongo_conn.port }}"
login_user: "{{ mongo_conn.user | default(omit, true) }}"
login_password: "{{ mongo_conn.password | default(omit, true) }}"
login_database: "{{ mongo_conn.authsource }}"
ssl: "{{ mongo_conn.tls | default(false) }}"        # TLS only if URI requests it
vars:
  ansible_python_interpreter: /opt/mongodb-venv/bin/python
```

## Input data model

`entities.example.yml` (copy to `entities.yml`, or supply via vault):

```yaml
mongodb_databases:            # OPTIONAL, advisory only — not materialized.
  - appdb                     # If set: typo-guard — every user/role db must be in this list.

mongodb_roles:
  - name: appReadWrite
    db: appdb
    privileges:
      - resource: { db: appdb, collection: "" }
        actions: [find, insert, update, remove]
    roles: []                 # inherited roles, optional

mongodb_users:
  - name: appuser
    db: appdb                 # database the user is defined in
    password: "{{ vault_appuser_password }}"
    roles:
      - { db: appdb, role: readWrite }
      - appReadWrite           # custom role created above
```

`defaults/main.yml` sets `mongodb_databases: []`, `mongodb_roles: []`, `mongodb_users: []`, and
`mongodb_port: 37017` so partial inputs are safe.

### Optional typo-guard

If `mongodb_databases` is non-empty, an early `assert` checks that every `db` referenced by
`mongodb_users`/`mongodb_roles` is in the list. If `mongodb_databases` is empty, the check is
skipped.

## Invocation

```bash
ansible-playbook -i inventory/ mongodb-create-entities.yml \
  -e @entities.yml \
  -e mongodb_uri='mongodb://admin:pw@h1:37017,h2:37017,h3:37017/?replicaSet=rs0&authSource=admin'

# standalone
ansible-playbook -i inventory/ mongodb-create-entities.yml \
  -e @entities.yml \
  -e mongodb_uri='mongodb://admin:pw@h1:37017/?authSource=admin'

# narrow scope
ansible-playbook -i inventory/ mongodb-create-entities.yml -e @entities.yml \
  -e mongodb_uri='...' -e mongo_target_hosts=primary
```

## Error handling

- **No primary reachable** — `run_once` assertion fails with guidance (check cluster health /
  inventory scope).
- **URI parse failure** — the pymongo `parse_uri` call exits non-zero; the parse task fails with
  the parser's message.
- **Entity create failure** — module surfaces the MongoDB error; the play stops on that host.
- **Idempotency** — `state: present` everywhere; `update_password: on_create` for users.
- **Secret hygiene** — `no_log: true` on URI parsing and user creation; credentials only ever
  come from the runtime `mongodb_uri` / vault, never committed.

## Testing / verification

- `ansible-playbook --syntax-check` on the new playbook.
- `ansible-lint` on the new role (if available in the environment).
- Dry inspection: confirm `is_primary` resolves to exactly one host on a replica set and to the
  single host on a standalone.
- Functional (against a test deployment): run with sample `entities.yml`, then verify with
  `mongosh` / `mongodb_info` that the role and user exist on the primary and replicate to
  secondaries; re-run to confirm `changed: false` (no spurious changes).

## Documentation

`docs/CREATE_ENTITIES.md` covering the data model, invocation, vault usage, and the standalone
vs replica-set behavior. A short pointer added to the directory `README.md`/`CLAUDE.md` if
appropriate during implementation.
