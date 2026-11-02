# Performance seed: Northwind Traders

A reproducible, realistic tenant for performance testing an m8flow stack. It is
separate from the Playwright e2e suite: it uses its own tenant and users and never
touches the `m8flow` tenant.

| What | Contents |
|---|---|
| Tenant | `northwind` (Northwind Traders) |
| Users | 19 Keycloak users across the six default groups (`--scale` multiplies them) |
| Templates | 4 complex templates (procurement, onboarding, insurance claims, IT incidents) |
| Process models | 10 built from the templates, plus 3 node-wire connector scenarios |
| Connector profile | `postgres_v2/default`, pointing at the stack's own database |

## Quick start

Start the stack (`docker compose --env-file .env -f docker/m8flow-docker-compose.yml up -d`),
then, from the repository root:

```sh
python3 perf/seed/seed.py                      # seed the tenant (idempotent)
python3 perf/load.py --instances 200 --concurrency 10 --report run.json
python3 perf/reset.py                          # clear instances + ledger rows, keep the seed
perf/snapshot.sh save northwind-baseline       # keep this state
perf/snapshot.sh restore northwind-baseline --yes   # back to it in seconds
```

`seed.py` and `load.py` use only the Python standard library. They read
`M8FLOW_KEYCLOAK_MASTER_CLIENT_SECRET` and the other settings from `.env` (see the
docstring at the top of `seed/seed.py`). Seeded users sign in with password = username
unless you set `PERF_SEED_PASSWORD`.

## Reference stack

`perf/stack/up.sh` runs the seeded tenant as a second compose project,
`m8flow-perf`, next to the dev stack. Its ports are the dev ports plus 1000, and its
telemetry goes to the observability stack, which must already be running:

```sh
perf/stack/up.sh             # build the perf designer, start, wait for health, seed
perf/stack/up.sh status      # services and URLs
perf/stack/up.sh down        # stop (data kept)
perf/stack/up.sh destroy     # stop and delete its volumes and process models
python3 perf/load.py  --env-file perf/stack/.env.perf --instances 200 --concurrency 10
python3 perf/reset.py --env-file perf/stack/.env.perf
```

| Service | URL |
|---|---|
| Designer | http://localhost:7853 |
| Backend | http://localhost:7840 |
| Keycloak | http://localhost:7842 (admin console at `/admin`) |
| Grafana (shared) | http://localhost:6868 |

`perf/stack/.env.perf` is regenerated from `sample.env` on every run and git ignores
it. `perf/stack/compose.perf.yml` overrides the parts of the base compose file that
would clash with the dev stack:

- the env file
- the process-model mount (`perf/stack/data/`)
- fixed container names
- the designer image (`m8flow-designer:perf`, because the backend URL is built into it)

In Grafana you can separate the two stacks:

| Signal | Filter |
|---|---|
| Logs | `compose_project="m8flow-perf"` |
| Metrics | `job="m8flow-perf/m8flow-backend"` |
| Traces | `service.namespace="m8flow-perf"` |

`snapshot.sh` still targets the dev stack only.

## Layout

| Path | Purpose |
|---|---|
| `seed/templates.py` | The four templates: diagrams, DMN decision tables and form schemas |
| `seed/connectors.py` | The stand-alone node-wire connector models |
| `seed/bpmn_builder.py` | Small builder that renders those definitions to BPMN XML with diagram layout |
| `seed/build.py` | Writes `seed/generated/` (files plus importable template ZIPs). Re-run after editing the sources |
| `seed/generated/` | Build output, checked in so seeding needs no build step |
| `seed/scenario.json` | Tenant, users, groups, connector profile, process groups and process models |
| `seed/scenarios.py` | Named paths through each model (form answers per task and the expected end event) |
| `seed/validate.py` | Runs every path in-process on the same engine m8flow-core uses, and prints the coverage matrix |
| `seed/seed.py` | Seeds a running stack through the Keycloak admin API and the backend API |
| `load.py` | Load driver: starts instances and completes their tasks as the right users |
| `reset.py` | Terminates and deletes every perf-tenant instance and empties the `perf_*` ledger tables; the seed stays |
| `snapshot.sh` | Saves and restores both databases, process models and template storage |

## The scenario

Each human task sits in a lane named after a default group, so any member of that
group can complete it.

| Template | Lanes | What it models |
|---|---|---|
| Purchase Requisition to Purchase Order | Submitters, Approvers, Administrators | A DMN decides the approval route (auto, manager or director). Approvals have SLA timers. Budget control runs in parallel, with a PostgreSQL ledger through node-wire. The purchase order is sent to a Supplier pool |
| Employee Onboarding | Administrators, Approvers, Support, Submitters | HR, IT and the new hire work in parallel. A signal triggers an event-based gateway. IT provisioning is a looping sub-process that escalates a laptop backorder. Equipment is routed through an inclusive gateway. A timer waits for the start date and a conditional event waits for the workspace |
| Insurance Claim Handling | Submitters, Support, Approvers, Administrators | A DMN triages the claim. Supporting documents are requested in a loop. A fraud ruling ends in an error event. Claims over the adjuster's authority escalate to a senior adjuster. Payout is a transaction that cancels on payment failure |
| IT Incident Management | Submitters, Support, Approvers | A DMN sets the priority. An SLA race runs on an event-based gateway. Diagnosis has reminder timers. Emergency changes need approval. The process declares data inputs and outputs |

| Process group | Process models (template) |
|---|---|
| `procurement` | `it-hardware-requisitions`, `office-supplies-requisitions`, `marketing-services-requisitions` (purchase requisition) |
| `human-resources` | `engineering-onboarding`, `sales-onboarding`, `contractor-onboarding` (employee onboarding) |
| `claims` | `auto-claims`, `property-claims` (insurance claim) |
| `it-service-management` | `service-desk-incidents`, `infrastructure-incidents` (IT incident) |
| `integrations` | `customer-ledger`, `db-heartbeat`, `partner-api-check` (connector scenarios) |

Each model runs the paths that fit it (`paths` in `scenario.json`). For example,
office supplies are always auto-approved and sales hires always hit the laptop
backorder.

### Node-wire connector scenarios

| Model | Connector | Notes |
|---|---|---|
| `customer-ledger` | `postgres_v2/DoSQL` (create table, insert, aggregate) | Works offline with no credentials (uses the `default` profile) |
| `db-heartbeat` | Timer start event and `postgres_v2/DoSQL` | Seeded as **draft**. Publish it to start a probe every 15 minutes |
| `partner-api-check` | `http/GetRequestV2` and `http/PostRequestV2` to httpbin.org | Needs internet access, because the proxy's SSRF guard blocks every in-stack host. `load.py` skips it unless you pass `--include-internet` |

The purchase-requisition template also writes to PostgreSQL. The ledger tables
(`perf_purchase_commitments`, `perf_customer_ledger`) live in the m8flow database,
so snapshots capture them.

## BPMN coverage

`m8flow-backend/.venv/bin/python -I perf/seed/validate.py` (it needs the backend's engine) prints the full matrix. It covers every construct
that the host accepts and m8flow-core runs:

- **Tasks:** user, manual, plain task, script, service, business rule (DMN), send
- **Gateways:** exclusive (with default flows and conditions), parallel, inclusive, event-based
- **Containers:** embedded sub-process, transaction
- **Start and end events:**
  - start: none, timer cycle
  - end: none, terminate, error, escalation, cancel
- **Intermediate events:**
  - catch: timer (duration and date), signal, conditional
  - throw: signal, escalation
- **Boundary events:**
  - interrupting: timer, error, escalation, cancel
  - non-interrupting: timer cycle, escalation
- **Loops and data:** standard loop, data objects with input and output associations, process I/O specification
- **Structure:** lanes, collaboration with a partner pool, messages and message flows, text annotations and associations, groups
- **Extensions:** forms, end-user instructions, pre- and post-scripts

These are left out on purpose:

| Construct | Reason |
|---|---|
| Call activity, message events and correlation, multi-instance, compensation, event sub-process | The host rejects them on save |
| Complex gateway, ad-hoc sub-process, link events, data stores, receive task, signal start | m8flow-core cannot run them |
| A human task inside a sub-process or transaction | m8flow-core never raises a work item for it, so the instance stalls. `validate.py` fails any diagram that does this |

## Load driver

```sh
python3 perf/load.py --instances 500 --concurrency 20 --seed 42 --report run.json
python3 perf/load.py --models auto-claims,property-claims --instances 100
python3 perf/load.py --instances 300 --leave-open 0.3   # also build an open-task backlog
```

Each instance starts as a random requester. The driver then completes every pending
task as one of the users the task is waiting for, using the answers in
`scenarios.py`, and records latency for each operation:

- `start_instance`
- `pending_tasks`
- `submit_task`
- `get_instance`
- `instance_end_to_end`

It prints p50, p95, p99 and max for each, and `--report` writes them as JSON.

Before measuring, it runs one unmeasured instance per model. Without that warm-up,
two concurrent first starts of a model collide (see below). A failed instance is
terminated so it doesn't linger. Paths that only a long timer can finish (3-day
approval overdue, 2-day document chase, SLA breach) are modelled but never driven.

## Recreating quickly

`perf/snapshot.sh save <name>` stores both `pg_dump`s, `data/process_models` and the
backend's template storage under `perf/snapshots/<name>/`, which git ignores.

`restore <name> --yes` stops the app services, recreates both databases from the
dumps, puts the files back, flushes Redis and restarts the services. It replaces the
data of **every** tenant on that stack.

To change a template, edit `seed/templates.py`, then run `seed/build.py`,
`seed/validate.py` (with the backend virtualenv) and `seed/seed.py --refresh`. Refresh imports a new template
version and overwrites the model files, keeping each model's own process id.

## Platform behaviour this seed works around

The seed hit these behaviours in the platform. Each one is worth tracking on its own.

1. **Tenant binding finishes on first login.** `POST /tenants/{id}/members` syncs
   groups and roles, but the user can't start instances ("does not belong to
   tenant") until their first authenticated request. `seed.py` signs every user in
   once (`GET /v1.0/onboarding` and `/v1.0/tasks`).
2. **The Support group (role `integrator`) can't list or submit tasks.** The
   `m8flow` tenant's stock `integrator` user behaves the same way. The seed grants
   the perf tenant's Support group the `reviewer` role (`group_roles` in
   `scenario.json`) so the support desk can work Support-lane tasks.
3. **Human tasks inside sub-processes are never offered.** See *BPMN coverage* above.
4. **First-start race.** Two concurrent first starts of a never-run model fail with a
   500 (unique violation on `m8f_task_definition_tenant_process_key`).
5. **Deadlocks under concurrent task traffic.** With about 6 concurrent workers,
   `POST /task-review/{id}/submit` and process starts sometimes fail with a 500.
   PostgreSQL detects a deadlock on `UPDATE m8f_group SET name=…, identifier=…`,
   because lane-group assignment rewrites the group row with unchanged values.
   Expect this to show up in error counts at higher concurrency.
6. **Standard-loop iterations are named `<bpmn id> [child]`** in task lists.
   `load.py` strips the suffix.
