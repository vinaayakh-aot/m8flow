"""Run every scenario path against every model of the perf tenant and report failures.

    python3 perf/suite.py --env-file perf/stack/.env.perf     # the reference stack
    python3 perf/suite.py --skip-timers                       # phase A only
    python3 perf/suite.py --only-timers                       # phase B only

Phase A runs every path of a model's template (not just the mix load.py uses)
against each seeded model, plus the connector scenarios. Each instance must
complete, offer every task its path expects, and complete its expected end
events (checked through the instance's event history).

Phase B covers what only a timer can reach, on the same seeded models: the
templates use timers of seconds, so seed/scenarios.py TIMER_PATHS (boundary
timers, an event-based gateway's timer branch, a future timer date, an SLA
race) finish in under a minute each. It then watches the published heartbeat
model, whose timer start event fires every minute, start and finish instances
on its own.

Finally it gathers scheduler diagnostics from the stack: overdue rows in
scheduler_job and whether a Celery beat container is running (the only thing
that fires timers that are not already due when reached). Writes
perf/reports/suite-<timestamp>.md and exits 1 if anything failed.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "seed"))

from load import Metrics, Sessions, run_instance
from scenarios import BY_KEY, TIMER_PATHS
from seed import REPO, Backend, Config, expand_users

HEARTBEAT = "integrations:db-heartbeat"


class Result:
    """ok is True (pass), False (fail) or None (skipped, with the reason in detail)."""

    def __init__(self, phase: str, model: str, path: str, ok: bool | None, detail: str = "", seconds: float = 0.0):
        self.phase, self.model, self.path, self.ok, self.detail, self.seconds = phase, model, path, ok, detail, seconds


def run_paths(sessions: Sessions, users: dict, items: list[tuple[str, str, object]], phase: str,
              concurrency: int, timeout: float) -> list[Result]:
    """Paths of one model run one after another (a model's first start must not race
    itself); different models run in parallel."""
    by_model: dict[str, list] = defaultdict(list)
    for route_id, label, path in items:
        by_model[route_id].append((label, path))

    def run_model(route_id: str) -> list[Result]:
        out = []
        for label, path in by_model[route_id]:
            began = time.time()
            try:
                run_instance(sessions, Metrics(), (route_id, label, path, 1), users, random.Random(7), False,
                             timeout, 1.0)
                out.append(Result(phase, route_id, path.name, True, seconds=time.time() - began))
            except Exception as exc:  # noqa: BLE001 - every failure is a finding
                out.append(Result(phase, route_id, path.name, False, str(exc)[:400], time.time() - began))
            mark = "ok  " if out[-1].ok else "FAIL"
            print(f"  {mark} {route_id} :: {path.name} ({out[-1].seconds:.0f}s)", flush=True)
        return out

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        return [r for rs in pool.map(run_model, sorted(by_model)) for r in rs]


def instances_of(api: Backend, route_id: str) -> list[dict]:
    identifier = route_id.replace(":", "/")
    found, page = [], 1
    while True:
        res = api("GET", f"/v1.0/m8flow/process-instances?per_page=100&page={page}"
                         f"&search={urllib.parse.quote(route_id.split(':')[1])}")
        found += [r for r in res["results"] if r.get("process_model_identifier") == identifier]
        if page >= res["pagination"]["pages"]:
            return found
        page += 1


def heartbeat_check(api: Backend, wait: float) -> Result:
    """The published heartbeat (timer start, every minute) starts and completes instances by itself."""
    name = "timer start event starts and completes instances"
    status = api("GET", f"/v1.0/m8flow/process-models/{HEARTBEAT}").get("status")
    if status != "published":
        return Result("B", HEARTBEAT, name, None,
                      f"skipped: model is {status}. A cycle timer start replays every missed cycle since 1970 "
                      "in m8flow-core and wedges the scheduler; publish it only once core is fixed")
    before = {i["id"] for i in instances_of(api, HEARTBEAT)}
    time.sleep(wait)
    new = [i for i in instances_of(api, HEARTBEAT) if i["id"] not in before]
    statuses: dict[str, int] = defaultdict(int)
    for inst in new:
        statuses[inst["status"]] += 1
    ok = bool(new) and set(statuses) <= {"complete", "completed"}
    detail = f"{len(new)} instance(s) started by the timer in {wait:.0f}s: {dict(statuses) or 'none'}"
    return Result("B", HEARTBEAT, name, ok, detail, wait)


# --------------------------------------------------------------------------- diagnostics
def scheduler_diagnostics(cfg: Config, env_file: Path, tenant_slug: str) -> list[str]:
    project = cfg.get("M8FLOW_COMPOSE_PROJECT", "m8flow")
    lines = []
    sql = ("SELECT job_type, count(*), min(run_at)::text FROM scheduler_job "
           "WHERE run_at < now() - interval '1 minute' AND m8f_tenant_id = "
           f"(SELECT id FROM m8flow_tenant WHERE slug = '{tenant_slug}') GROUP BY 1")
    cmd = ["docker", "compose", "-p", project, "--env-file", str(env_file), "-f",
           str(REPO / "docker/m8flow-docker-compose.yml"), "exec", "-T", "m8flow-db", "psql", "-U",
           cfg.get("POSTGRES_USER", "postgres"), "-d", cfg.get("POSTGRES_DB", "postgres"), "-tA", "-c", sql]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    rows = [r for r in out.stdout.strip().splitlines() if r]
    if out.returncode != 0:
        lines.append(f"could not read scheduler_job: {out.stderr.strip()[:200]}")
    elif rows:
        for row in rows:
            job_type, count, oldest = row.split("|")
            lines.append(f"overdue scheduler jobs: {count} x {job_type}, oldest due {oldest}")
    else:
        lines.append("no overdue scheduler jobs")
    ps = subprocess.run(["docker", "ps", "--no-trunc", "--filter", f"label=com.docker.compose.project={project}",
                         "--format", "{{.Names}}|{{.Command}}"], capture_output=True, text=True, check=False)
    beat = [line.split("|")[0] for line in ps.stdout.splitlines() if " beat" in line or " -B" in line]
    lines.append(f"containers running Celery beat: {', '.join(beat) if beat else 'none'}")
    return lines


def write_report(results: list[Result], diagnostics: list[str], target: str) -> Path:
    out_dir = HERE / "reports"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"suite-{stamp}.md"
    failed = [r for r in results if r.ok is False]
    skipped = [r for r in results if r.ok is None]
    passed = len(results) - len(failed) - len(skipped)
    lines = [f"# Perf suite {stamp} UTC", "", f"Target: {target}", "",
             f"{passed} passed, {len(failed)} failed, {len(skipped)} skipped.", "",
             "| Phase | Model | Path | Result | Detail |", "|---|---|---|---|---|"]
    for r in results:
        detail = r.detail.replace("|", "\\|").replace("\n", " ")
        result = "SKIP" if r.ok is None else "PASS" if r.ok else "**FAIL**"
        lines.append(f"| {r.phase} | `{r.model}` | {r.path} | {result} | {detail} |")
    lines += ["", "## Scheduler diagnostics", ""] + [f"- {d}" for d in diagnostics]
    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", type=Path, default=REPO / ".env")
    ap.add_argument("--concurrency", type=int, default=4, help="models run in parallel (paths of a model run in turn)")
    ap.add_argument("--timeout", type=float, default=150, help="per-instance timeout in seconds")
    ap.add_argument("--skip-timers", action="store_true", help="phase A only")
    ap.add_argument("--only-timers", action="store_true", help="phase B only")
    ap.add_argument("--skip-internet", action="store_true", help="leave out partner-api-check (httpbin.org)")
    ap.add_argument("--heartbeat-wait", type=float, default=75, help="seconds to watch the heartbeat schedule")
    args = ap.parse_args()

    cfg = Config(args.env_file)
    scenario = json.loads((HERE / "seed" / "scenario.json").read_text())
    slug = scenario["tenant"]["slug"]
    users = expand_users(scenario, 1)
    by_group: dict[str, list[str]] = defaultdict(list)
    for user in users:
        for group in user["groups"]:
            by_group[group].append(user["username"])
    user_index = {"by_group": dict(by_group), "known": {u["username"] for u in users}}
    sessions = Sessions(cfg, slug)
    admin = sessions.api("nw-admin")
    print(f"target {cfg.backend} tenant {slug}", flush=True)

    results: list[Result] = []
    if not args.only_timers:
        items = []
        for model in scenario["template_models"]:
            for path in BY_KEY[model["template"]]:
                items.append((f"{model['group']}:{model['id']}", model["id"], path))
        for model in scenario["connector_models"]:
            if model["source"] == "partner-api-check" and args.skip_internet:
                continue
            for path in BY_KEY.get(model["source"], []):
                items.append((f"{model['group']}:{model['source']}", model["source"], path))
        print(f"\nphase A: {len(items)} path runs over {len({i[0] for i in items})} models", flush=True)
        results += run_paths(sessions, user_index, items, "A", args.concurrency, args.timeout)

    if not args.skip_timers:
        items = []
        for model in scenario["template_models"]:
            for path in TIMER_PATHS.get(model["template"], []):
                items.append((f"{model['group']}:{model['id']}", model["id"], path))
        print(f"\nphase B: {len(items)} timer path runs over {len({i[0] for i in items})} models", flush=True)
        results += run_paths(sessions, user_index, items, "B", args.concurrency, args.timeout)
        print(f"  watching the heartbeat schedule for {args.heartbeat_wait:.0f}s", flush=True)
        heartbeat = heartbeat_check(admin, args.heartbeat_wait)
        results.append(heartbeat)
        mark = "skip" if heartbeat.ok is None else "ok  " if heartbeat.ok else "FAIL"
        print(f"  {mark} {heartbeat.model} :: {heartbeat.path} -- {heartbeat.detail}", flush=True)

    diagnostics = scheduler_diagnostics(cfg, args.env_file, slug)
    report = write_report(results, diagnostics, f"{cfg.backend} (tenant {slug})")
    failed = [r for r in results if r.ok is False]
    skipped = [r for r in results if r.ok is None]
    print(f"\n{len(results) - len(failed) - len(skipped)} passed, {len(failed)} failed, {len(skipped)} skipped")
    for r in failed + skipped:
        print(f"  {'SKIP' if r.ok is None else 'FAIL'} [{r.phase}] {r.model} :: {r.path}\n       {r.detail}")
    print("\n" + "\n".join(diagnostics))
    print(f"\nreport: {report}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
