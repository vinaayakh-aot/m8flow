"""Drive the seeded Northwind tenant with realistic process traffic.

    python3 perf/load.py --instances 200 --concurrency 10

Each virtual user loop starts an instance of a weighted-random model as a
requester, then completes every human task as one of the users the task is
waiting for (lane group members), with the answers from
perf/seed/scenarios.py, until the instance reaches its end. Latencies are
recorded per API operation and per instance; a summary is printed and
written as JSON.

--leave-open F starts instances but leaves a fraction F of them at their
first human task, to build the open-task backlog a real tenant carries.
Run perf/seed/seed.py first (with the same --scale).
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "seed"))

from scenarios import BY_KEY
from seed import REPO, Backend, Config, HttpError, expand_users, password_token

DONE = {"complete", "completed"}
FAILED = {"error", "suspended", "terminated"}


class Metrics:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.samples: dict[str, list[float]] = defaultdict(list)
        self.errors: dict[str, int] = defaultdict(int)
        self.outcomes: dict[str, int] = defaultdict(int)

    def timed(self, op: str, fn, *args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        except Exception:
            with self.lock:
                self.errors[op] += 1
            raise
        finally:
            with self.lock:
                self.samples[op].append((time.perf_counter() - start) * 1000)

    def count(self, outcome: str) -> None:
        with self.lock:
            self.outcomes[outcome] += 1

    def summary(self, wall_seconds: float) -> dict:
        ops = {}
        for op, values in sorted(self.samples.items()):
            ordered = sorted(values)
            ops[op] = {"count": len(values), "errors": self.errors.get(op, 0),
                       "mean_ms": round(statistics.fmean(values), 1), "p50_ms": _pct(ordered, 0.50),
                       "p95_ms": _pct(ordered, 0.95), "p99_ms": _pct(ordered, 0.99), "max_ms": round(ordered[-1], 1)}
        finished = self.outcomes.get("completed", 0)
        return {"wall_seconds": round(wall_seconds, 1), "outcomes": dict(self.outcomes),
                "instances_per_minute": round(finished / wall_seconds * 60, 2) if wall_seconds else 0,
                "operations": ops}


def _pct(ordered: list[float], p: float) -> float:
    return round(ordered[min(len(ordered) - 1, int(p * len(ordered)))], 1)


class Sessions:
    """Per-user tokens (password grant), refreshed on 401 or near expiry."""

    def __init__(self, cfg: Config, slug: str) -> None:
        self.cfg, self.slug = cfg, slug
        self.lock = threading.Lock()
        self.tokens: dict[str, tuple[str, float]] = {}

    def api(self, username: str, fresh: bool = False) -> Backend:
        with self.lock:
            cached = self.tokens.get(username)
            if fresh or cached is None or cached[1] < time.time():
                token = password_token(self.cfg, self.cfg.realm, username, self.cfg.user_password or username,
                                       secret=self.cfg.client_secret, scope="openid organization")
                if cached is None:
                    # first sign-in finalizes the tenant binding (see seed.warm_sessions)
                    Backend(self.cfg, token, self.slug)("GET", "/v1.0/onboarding")
                cached = (token, time.time() + 240)
                self.tokens[username] = cached
        return Backend(self.cfg, cached[0], self.slug)

    def call(self, username: str, method: str, path: str, **kw):
        try:
            return self.api(username)(method, path, **kw)
        except HttpError as exc:
            if exc.status != 401:
                raise
            return self.api(username, fresh=True)(method, path, **kw)


def build_mix(scenario: dict, include_internet: bool, only: set[str] | None) -> list[tuple[str, str, object, int]]:
    """(route id, model key, path, weight) for every runnable model path."""
    mix = []
    for model in scenario["template_models"]:
        allowed = set(model.get("paths", []))
        for path in BY_KEY[model["template"]]:
            if not allowed or path.name in allowed:
                mix.append((f"{model['group']}:{model['id']}", model["id"], path, path.weight))
    for model in scenario["connector_models"]:
        if model["source"] == "partner-api-check" and not include_internet:
            continue
        for path in BY_KEY.get(model["source"], []):
            mix.append((f"{model['group']}:{model['source']}", model["source"], path, path.weight))
    if only:
        mix = [m for m in mix if m[1] in only]
    if not mix:
        raise SystemExit("no runnable model paths selected")
    return mix


def pick_completer(task: dict, starter: str, by_group: dict[str, list[str]], known: set[str], rng: random.Random) -> str:
    waiting = task.get("waiting_for") or {}
    candidates = [u for u in waiting.get("usernames") or [] if u in known]
    if candidates:
        return rng.choice(candidates)
    lane = task.get("lane_name") or waiting.get("label")
    if lane in by_group:
        return rng.choice(by_group[lane])
    return starter


def run_instance(sessions: Sessions, metrics: Metrics, mix_item, users: dict, rng: random.Random,
                 leave_open: bool, timeout: float, poll: float) -> str:
    """Run one instance; a failed instance is terminated so it does not linger as noise."""
    started: list[int] = []
    try:
        return _drive_instance(sessions, metrics, mix_item, users, rng, leave_open, timeout, poll, started)
    except Exception:
        if started:
            admin = users["by_group"]["Administrators"][0]
            try:
                sessions.call(admin, "POST", f"/v1.0/m8flow/process-instances/{started[0]}/terminate")
            except Exception as exc:  # noqa: BLE001 - best effort; the original failure is what matters
                print(f"  warn: could not terminate instance {started[0]}: {exc}", file=sys.stderr)
        raise


def _drive_instance(sessions: Sessions, metrics: Metrics, mix_item, users: dict, rng: random.Random,
                    leave_open: bool, timeout: float, poll: float, started: list[int]) -> str:
    route_id, _, path, _ = mix_item
    starter = rng.choice(users["by_group"]["Submitters"])
    began = time.perf_counter()
    created = metrics.timed("start_instance", sessions.call, starter, "POST",
                            f"/v1.0/m8flow/process-models/{route_id}/start")
    instance_id = created["id"]
    started.append(instance_id)
    occurrences: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    first_seen: dict[int, float] = {}
    deadline = time.time() + timeout
    while True:
        pending = metrics.timed("pending_tasks", sessions.call, starter, "GET",
                                f"/v1.0/m8flow/process-instances/{instance_id}/pending-tasks")["results"]
        if pending and leave_open:
            return "left_open"
        if not pending:
            instance = metrics.timed("get_instance", sessions.call, starter, "GET",
                                     f"/v1.0/m8flow/process-instances/{instance_id}")
            status = instance.get("status")
            if status in DONE:
                metrics.samples["instance_end_to_end"].append((time.perf_counter() - began) * 1000)
                _check_outcome(sessions, starter, instance_id, path, seen)
                return "completed"
            if status in FAILED:
                raise RuntimeError(f"instance {instance_id} ({route_id}, {path.name}) ended {status}")
            if time.time() > deadline:
                raise TimeoutError(f"instance {instance_id} still {status} with no open task after {timeout}s "
                                   f"(waiting on a timer or the scheduler)")
            time.sleep(poll)
            continue
        submitted = 0
        for task in pending:
            # standard-loop iterations are reported as "<bpmn id> [child]"
            name = task["task_name"].removesuffix(" [child]")
            seen.add(name)
            first_seen.setdefault(task["id"], time.time())
            if _held(path, name, seen, time.time() - first_seen[task["id"]]):
                continue
            answer = path.answers.get(name)
            if answer is None:
                raise RuntimeError(f"no answer for task {name!r} on path {path.name!r} ({route_id})")
            if isinstance(answer, list):
                answer = answer[min(occurrences[name], len(answer) - 1)]
            occurrences[name] += 1
            user = pick_completer(task, starter, users["by_group"], users["known"], rng)
            try:
                metrics.timed("submit_task", sessions.call, user, "POST",
                              f"/v1.0/m8flow/task-review/{task['id']}/submit", json_body=_resolve(answer))
                submitted += 1
            except HttpError as exc:
                if exc.status != 409:  # 409: already completed (raced another poll)
                    raise RuntimeError(f"submit {name} (lane {task.get('lane_name')}) as {user}: "
                                       f"{exc.status} {exc.body[:200]}") from None
        if not submitted:
            if time.time() > deadline:
                held = sorted({t["task_name"] for t in pending})
                raise TimeoutError(f"instance {instance_id} still waiting after {timeout}s; open tasks {held} "
                                   f"(the timer meant to release them never fired)")
            time.sleep(poll)


def _held(path, name: str, seen: set[str], pending_for: float) -> bool:
    rule = path.hold.get(name)
    if not rule:
        return False
    kind, _, arg = rule.partition(":")
    if kind == "seen":
        return arg not in seen
    if kind == "after":
        return pending_for < float(arg)
    raise ValueError(f"unknown hold rule {rule!r}")


def _resolve(answer: dict) -> dict:
    """Replace "@now+<n>s" values with an ISO-8601 UTC timestamp n seconds ahead."""
    out = {}
    for key, value in answer.items():
        if isinstance(value, str) and value.startswith("@now+") and value.endswith("s"):
            at = datetime.now(UTC) + timedelta(seconds=float(value[5:-1]))
            value = at.isoformat(timespec="seconds")
        out[key] = value
    return out


def _check_outcome(sessions: Sessions, user: str, instance_id: int, path, seen: set[str]) -> None:
    """The path's tasks were all offered, and its end events and expected elements completed."""
    missing_tasks = set(path.answers) - seen
    events = sessions.call(user, "GET", f"/v1.0/m8flow/process-instances/{instance_id}/events?per_page=500")
    rows = events["results"] if isinstance(events, dict) else events
    completed = {r.get("task_identifier") for r in rows if r.get("event_type") == "task_completed"}
    missing = sorted((set(path.expect_end) | set(path.expect_completed)) - completed)
    problems = []
    if missing_tasks:
        problems.append(f"tasks never offered: {sorted(missing_tasks)}")
    if missing:
        problems.append(f"never completed: {missing}")
    if problems:
        raise RuntimeError(f"instance {instance_id} completed the wrong way: " + "; ".join(problems))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--leave-open", type=float, default=0.0, help="fraction of instances left at their first task")
    ap.add_argument("--models", help="comma-separated model ids to run (default: all)")
    ap.add_argument("--include-internet", action="store_true", help="also run partner-api-check (httpbin.org)")
    ap.add_argument("--scale", type=int, default=1, help="the --scale seed.py was run with")
    ap.add_argument("--timeout", type=float, default=300, help="per-instance timeout in seconds")
    ap.add_argument("--poll", type=float, default=1.0, help="seconds between polls while an instance waits")
    ap.add_argument("--no-warmup", action="store_true", help="skip the one-start-per-model warm-up")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed for a repeatable mix")
    ap.add_argument("--report", type=Path, default=None, help="write the JSON summary here")
    ap.add_argument("--env-file", type=Path, default=REPO / ".env")
    args = ap.parse_args()

    cfg = Config(args.env_file)
    scenario = json.loads((HERE / "seed" / "scenario.json").read_text())
    users = expand_users(scenario, args.scale)
    by_group: dict[str, list[str]] = defaultdict(list)
    for user in users:
        for group in user["groups"]:
            by_group[group].append(user["username"])
    user_index = {"by_group": dict(by_group), "known": {u["username"] for u in users}}
    mix = build_mix(scenario, args.include_internet, set(args.models.split(",")) if args.models else None)

    rng = random.Random(args.seed)
    plan = rng.choices(mix, weights=[m[3] for m in mix], k=args.instances)
    open_flags = [rng.random() < args.leave_open for _ in plan]
    sessions = Sessions(cfg, scenario["tenant"]["slug"])
    metrics = Metrics()
    failures: list[str] = []

    if not args.no_warmup:
        # The first start of a never-run model persists its task definitions; two
        # concurrent first starts race on that insert (500, unique violation on
        # m8f_task_definition_tenant_process_key). Start each model once, alone,
        # so the measured phase reflects steady state. --no-warmup reproduces it.
        # Each warm-up instance runs to completion, unmeasured, so none is left open.
        warm = {}
        for item in plan:
            warm.setdefault(item[0], item)
        for item in warm.values():
            run_instance(sessions, Metrics(), item, user_index, random.Random(rng.random()), False,
                         args.timeout, args.poll)
        print(f"warm-up: ran one instance of each of {len(warm)} models", flush=True)

    print(f"running {args.instances} instances over {len({m[0] for m in plan})} models, "
          f"concurrency {args.concurrency}", flush=True)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(run_instance, sessions, metrics, item, user_index,
                               random.Random(rng.random()), leave, args.timeout, args.poll): item
                   for item, leave in zip(plan, open_flags)}
        for n, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            try:
                metrics.count(future.result())
            except Exception as exc:  # noqa: BLE001
                metrics.count("failed")
                failures.append(f"{item[0]} [{item[2].name}]: {exc}")
            if n % max(1, args.instances // 10) == 0:
                print(f"  {n}/{args.instances} done", flush=True)
    summary = metrics.summary(time.perf_counter() - started)
    summary["failures"] = failures[:50]

    print(f"\noutcomes: {summary['outcomes']}  ({summary['instances_per_minute']} completed instances/min, "
          f"{summary['wall_seconds']}s wall)")
    print(f"{'operation':<22}{'count':>7}{'err':>5}{'mean':>9}{'p50':>9}{'p95':>9}{'p99':>9}{'max':>9}  (ms)")
    for op, s in summary["operations"].items():
        print(f"{op:<22}{s['count']:>7}{s['errors']:>5}{s['mean_ms']:>9}{s['p50_ms']:>9}{s['p95_ms']:>9}"
              f"{s['p99_ms']:>9}{s['max_ms']:>9}")
    for failure in failures[:10]:
        print(f"  FAIL {failure}")
    if args.report:
        args.report.write_text(json.dumps(summary, indent=2) + "\n")
        print(f"report: {args.report}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
