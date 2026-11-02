"""Clear run data from the perf tenant, keeping the seed itself.

    python3 perf/reset.py            # terminate + delete every instance, empty the perf_* ledger tables
    python3 perf/reset.py --dry-run  # show what would be removed

Instances go through the backend API (terminate when still active, then
DELETE), so their tasks, work items and events are removed the supported way.
Only the perf tenant is touched: the tenant comes from seed/scenario.json and
every call carries its active-tenant cookie. Users, templates, process models
and the connector profile stay, so load.py can run again immediately.

The ledger tables that the seeded workflows write through the postgres_v2
connector are emptied with psql in the m8flow-db service of the compose project
named by M8FLOW_COMPOSE_PROJECT (default "m8flow", the dev stack). For the perf
reference stack pass --env-file perf/stack/.env.perf, which sets it to m8flow-perf.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "seed"))

from seed import REPO, Backend, Config, HttpError, password_token

FINISHED = {"complete", "completed", "terminated", "error"}
LEDGER_TABLES = ("perf_purchase_commitments", "perf_customer_ledger")


def list_instances(api: Backend) -> list[dict]:
    instances, page = [], 1
    while True:
        result = api("GET", f"/v1.0/m8flow/process-instances?per_page=100&page={page}&sort=oldest")
        instances.extend(result["results"])
        if page >= result["pagination"]["pages"]:
            return instances
        page += 1


def purge_instances(api: Backend, dry_run: bool) -> None:
    instances = list_instances(api)
    by_status: dict[str, int] = {}
    for inst in instances:
        by_status[inst["status"]] = by_status.get(inst["status"], 0) + 1
    print(f"instances: {len(instances)} {by_status}")
    if dry_run:
        return
    failed = []
    for inst in instances:
        try:
            if inst["status"] not in FINISHED:
                api("POST", f"/v1.0/m8flow/process-instances/{inst['id']}/terminate")
            api("DELETE", f"/v1.0/m8flow/process-instances/{inst['id']}")
        except HttpError as exc:
            if exc.status != 404:
                failed.append(f"{inst['id']} ({inst['status']}): {exc.status} {exc.body[:120]}")
    left = len(list_instances(api))
    print(f"deleted {len(instances) - len(failed)}, {left} left")
    for line in failed[:20]:
        print(f"  FAIL {line}")
    if failed:
        raise SystemExit(1)


def empty_ledger(cfg: Config, env_file: Path, dry_run: bool) -> None:
    # The project must match the stack the API calls went to; without -p compose
    # falls back to the base file's "m8flow" (the dev stack).
    project = cfg.get("M8FLOW_COMPOSE_PROJECT", "m8flow")
    compose = ["docker", "compose", "-p", project, "--env-file", str(env_file),
               "-f", str(REPO / "docker/m8flow-docker-compose.yml"),
               "exec", "-T", "m8flow-db", "psql", "-U", cfg.get("POSTGRES_USER", "postgres"),
               "-d", cfg.get("POSTGRES_DB", "postgres"), "-tA", "-c"]
    existing = subprocess.run(
        [*compose, f"SELECT tablename FROM pg_tables WHERE tablename IN ({', '.join(repr(t) for t in LEDGER_TABLES)})"],
        check=True, capture_output=True, text=True).stdout.split()
    if not existing:
        print("ledger: no perf_* tables yet")
        return
    counts = {t: subprocess.run([*compose, f"SELECT count(*) FROM {t}"], check=True, capture_output=True,
                                text=True).stdout.strip() for t in existing}
    print(f"ledger rows: {json.dumps(counts)}")
    if not dry_run:
        subprocess.run([*compose, f"TRUNCATE {', '.join(existing)} RESTART IDENTITY"], check=True,
                       capture_output=True)
        print(f"ledger: emptied {', '.join(existing)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-ledger", action="store_true", help="leave the perf_* ledger tables alone")
    ap.add_argument("--env-file", type=Path, default=REPO / ".env")
    args = ap.parse_args()

    cfg = Config(args.env_file)
    scenario = json.loads((HERE / "seed" / "scenario.json").read_text())
    admin = next(f"{u['prefix']}" for u in scenario["users"] if "Administrators" in u["groups"] and u["count"] == 1)
    token = password_token(cfg, cfg.realm, admin, cfg.user_password or admin, secret=cfg.client_secret,
                           scope="openid organization")
    purge_instances(Backend(cfg, token, scenario["tenant"]["slug"]), args.dry_run)
    if not args.keep_ledger:
        empty_ledger(cfg, args.env_file, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
