"""Run every scenario path in-process on the same engine m8flow-core uses.

    m8flow-backend/.venv/bin/python -I perf/seed/validate.py [--verbose]

Per diagram it checks that the host would accept the XML (the same
unsupported-construct guard the catalog applies on save), that no human task
sits inside a sub-process (m8flow-core never raises a work item for one),
that it parses to
exactly one executable process, and that every path in scenarios.py reaches
its expected end event(s). Workflows are serialized and restored between
steps, as core does, and timers are refreshed the way the scheduler does.
Service tasks get canned node-wire responses, so no stack is needed.

Also prints the BPMN coverage matrix (element -> diagrams that use it).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from lxml import etree
from m8flow_backend.catalog import _reject_unsupported_constructs
from SpiffWorkflow.bpmn.script_engine.python_engine import PythonScriptEngine
from SpiffWorkflow.bpmn.serializer.workflow import BpmnWorkflowSerializer
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.spiff.parser.process import SpiffBpmnParser
from SpiffWorkflow.spiff.serializer.config import SPIFF_CONFIG
from SpiffWorkflow.util.task import TaskState

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenarios import BY_KEY
from scenarios import Path as ScenarioPath

GENERATED = HERE / "generated"
SERIALIZER = BpmnWorkflowSerializer(registry=BpmnWorkflowSerializer.configure(SPIFF_CONFIG), version="5")
BPMN_NS = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"


class CannedServiceEngine(PythonScriptEngine):
    """Answers service tasks with the node-wire v2 response envelope."""

    def evaluate(self, task, expression, external_context=None):
        if expression in (None, ""):
            return None  # left for the connector profile to fill (host behaviour)
        return super().evaluate(task, expression, external_context)

    def call_service(self, task, operation_name, operation_params, **kwargs):
        params = {k: v["value"] for k, v in operation_params.items()}
        if operation_name == "postgres_v2/DoSQL":
            sql = params["schema"]["sql"]
            if sql.lstrip().upper().startswith("SELECT COUNT"):
                body = {"body": [[3, 376.5]]}
            elif params["schema"].get("fetch_results"):
                body = {"body": [[42]]}
            else:
                body = {"body": {"result": "ok"}}
        elif operation_name == "http/GetRequestV2":
            body = {"args": params.get("params") or {}, "url": params["url"]}
        elif operation_name == "http/PostRequestV2":
            body = {"json": params.get("data"), "url": params["url"]}
        else:
            raise AssertionError(f"no canned response for {operation_name}")
        return json.dumps({"command_response": {"body": body, "mimetype": "application/json", "http_status": 200},
                           "error": None, "command_response_version": 2})


HUMAN_TAGS = ("userTask", "manualTask", "task")


def reject_nested_human_tasks(xml: str) -> None:
    """m8flow-core raises work items only for top-level human tasks: one inside an
    embedded sub-process or transaction leaves the instance waiting forever."""
    root = etree.fromstring(xml.encode())
    for container in ("subProcess", "transaction"):
        for sp in root.iter(f"{BPMN_NS}{container}"):
            for tag in HUMAN_TAGS:
                for el in sp.iter(f"{BPMN_NS}{tag}"):
                    raise AssertionError(f"human task {el.get('id')!r} is inside {container} {sp.get('id')!r}; "
                                         "m8flow-core never raises a work item for it")


def load_spec(model_dir: Path, bpmn_file: str):
    xml = (model_dir / bpmn_file).read_text()
    _reject_unsupported_constructs(xml)
    reject_nested_human_tasks(xml)
    parser = SpiffBpmnParser(validator=None)
    parser.add_bpmn_str(xml.encode(), filename=bpmn_file)
    dmns = sorted(model_dir.glob("*.dmn"))
    assert len(dmns) <= 1, "the host loads only one DMN per model"
    for dmn in dmns:
        parser.add_dmn_str(dmn.read_bytes(), filename=dmn.name)
    ids = parser.get_process_ids()
    assert len(ids) == 1, f"core needs exactly one executable process, got {ids}"
    return parser.get_spec(ids[0]), parser.get_subprocess_specs(ids[0])


def run_path(spec, subprocesses, path: ScenarioPath, verbose: bool, max_wait: float = 20) -> list[str]:
    wf = BpmnWorkflow(spec, subprocesses, script_engine=CannedServiceEngine())
    queues = {k: list(v) if isinstance(v, list) else None for k, v in path.answers.items()}
    seen: list[str] = []
    deadline = time.time() + max_wait
    while not wf.completed:
        wf.run_all(halt_on_manual=True)
        wf = SERIALIZER.deserialize_json(SERIALIZER.serialize_json(wf))
        wf.script_engine = CannedServiceEngine()
        ready = wf.get_tasks(state=TaskState.READY, manual=True)
        for task in ready:
            bpmn_id = task.task_spec.bpmn_id
            if bpmn_id not in path.answers:
                raise AssertionError(f"unexpected human task {bpmn_id!r} (lane {task.task_spec.lane})")
            queue = queues[bpmn_id]
            answer = (queue.pop(0) if len(queue) > 1 else queue[0]) if queue is not None else path.answers[bpmn_id]
            if verbose:
                print(f"      {bpmn_id:<22} lane={task.task_spec.lane!s:<15} {answer}")
            seen.append(bpmn_id)
            task.data.update(answer)
            task.complete()
        if not ready and not wf.completed:
            if time.time() > deadline:
                waiting = [t.task_spec.bpmn_id for t in wf.get_tasks(state=TaskState.WAITING)]
                raise AssertionError(f"stuck waiting on {waiting}")
            time.sleep(0.2)
            wf.refresh_waiting_tasks()
    ends = {t.task_spec.bpmn_id for t in wf.get_tasks(state=TaskState.COMPLETED)
            if t.task_spec.bpmn_id and type(t.task_spec).__name__ == "EndEvent"}
    missing = set(path.expect_end) - ends
    if missing:
        raise AssertionError(f"expected end {sorted(missing)}, reached {sorted(ends)}")
    unused = set(path.answers) - set(seen)
    if unused:
        raise AssertionError(f"answers given for tasks never reached: {sorted(unused)}")
    return seen


def coverage(model_dir: Path, bpmn_file: str, matrix: dict[str, set[str]], label: str) -> None:
    root = etree.parse(str(model_dir / bpmn_file)).getroot()
    for el in root.iter():
        if not isinstance(el.tag, str) or not el.tag.startswith(BPMN_NS):
            continue
        tag = el.tag[len(BPMN_NS):]
        parent = el.getparent()
        ptag = parent.tag[len(BPMN_NS):] if parent is not None and parent.tag.startswith(BPMN_NS) else ""
        if tag.endswith("EventDefinition"):
            name = f"{ptag} + {tag.replace('EventDefinition', '')}"
            if ptag == "boundaryEvent":
                name += " (non-interrupting)" if parent.get("cancelActivity") == "false" else " (interrupting)"
            if tag == "timerEventDefinition":
                name += f" [{el[0].tag[len(BPMN_NS):]}]"
            matrix[name].add(label)
        elif tag in {"startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent"}:
            if not any(c.tag.endswith("EventDefinition") for c in el):
                matrix[f"{tag} (none)"].add(label)
        elif tag in {"process", "definitions", "extensionElements", "incoming", "outgoing", "script", "text",
                     "conditionExpression", "condition", "timeDuration", "timeDate", "timeCycle", "documentation",
                     "flowNodeRef", "sourceRef", "targetRef", "dataInputRefs", "dataOutputRefs", "inputSet",
                     "outputSet", "categoryValue", "loopCondition"}:
            continue
        else:
            matrix[tag].add(label)
        if tag == "sequenceFlow" and el.find(f"{BPMN_NS}conditionExpression") is not None:
            matrix["sequenceFlow (conditional)"].add(label)
        if el.get("default"):
            matrix["default flow"].add(label)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    models = [(p, f"{p.name}.bpmn") for p in sorted((GENERATED / "templates").iterdir()) if p.is_dir()]
    models += [(p, f"{p.name}.bpmn") for p in sorted((GENERATED / "connectors").iterdir()) if p.is_dir()]
    matrix: dict[str, set[str]] = defaultdict(set)
    failures = 0
    for model_dir, bpmn_file in models:
        key = model_dir.name
        print(f"{key}")
        try:
            spec, subs = load_spec(model_dir, bpmn_file)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL load: {exc}")
            failures += 1
            continue
        coverage(model_dir, bpmn_file, matrix, key)
        for path in BY_KEY.get(key, []):
            try:
                if args.verbose:
                    print(f"  - {path.name}")
                seen = run_path(spec, subs, path, args.verbose)
                print(f"  ok   {path.name} ({len(seen)} human tasks)")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  FAIL {path.name}: {exc}")
        if key not in BY_KEY:
            print("  ok   parses (no runnable path: timer-started)")

    print("\nBPMN coverage")
    for name in sorted(matrix):
        print(f"  {name:<52} {', '.join(sorted(matrix[name]))}")
    print(f"\n{'FAILED' if failures else 'PASSED'}: {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
