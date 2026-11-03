# BPMN support

This page lists the BPMN 2.0 elements you can use in an m8flow process model,
and the ones the catalog rejects when you save a BPMN file.

## Rejected constructs

The catalog checks every BPMN file you save, create, copy, or import. If the
file contains one of the following constructs, the save fails with the
`unsupported_bpmn` error:

| Construct | BPMN element |
|---|---|
| Call activity | `callActivity` |
| Message events and message correlation | `messageEventDefinition`, `correlationKey`, `correlationProperty` |
| Compensation | `compensateEventDefinition` |
| Multi-instance activities | `multiInstanceLoopCharacteristics` |
| Event subprocess | `subProcess` with `triggeredByEvent="true"` |

An ordinary embedded `subProcess` is allowed.

## Supported elements

The engine runs the following elements:

| Category | Elements |
|---|---|
| Events | Start event, end event, intermediate catch and throw events, boundary events (interrupting and non-interrupting) |
| Event definitions | Timer (date, duration, and cycle), signal, escalation, error, conditional, terminate, cancel |
| Tasks | Task, user task, manual task, script task, service task, business rule task, send task |
| Gateways | Exclusive, parallel, inclusive, event-based |
| Structure | Embedded subprocess, transaction, standard loop, pools, lanes, sequence flows with conditions |
| Data | Data objects, process data inputs and outputs |

## Known limitations

The following constructs pass the save check but don't run as modeled:

| Construct | What happens | Workaround |
|---|---|---|
| A user task, manual task, or plain task inside an embedded subprocess or transaction | Nobody is offered the task, so the instance waits forever. | Put human tasks at the top level of the process. Use subprocesses for automated steps. |
| A timer behind an event-based gateway | No timer job is scheduled. The timer fires only when something else advances the instance after it's due. | Use a boundary timer on the task that waits instead. |
| A repeating timer start event (a cycle such as `R/PT1M`) | When the schedule fires, the engine replays every cycle since 1970 in one run. The scheduler worker never finishes, and no timer in any tenant fires. | Don't publish a process model with a repeating timer start event. |
| Link events | The instance stops at the link throw event. | Use sequence flows. |
| Data stores | The engine has no data store implementation, so the task fails. | Use data objects, or a service task that reads and writes the data. |

Timers fire through Celery beat, up to `M8FLOW_SCHEDULER_POLL_SECONDS` after
they're due. See [About process execution](../explanation/process-execution.md#timers).

## Tasks in m8flow

A plain **task** (`bpmn:task`) waits for a person to submit it, even without
a form. The task goes to the lane's group, or to the
process initiator when there's no lane.

Several task types take m8flow-specific settings in the properties panel:

- **User task.** Binds to a form schema file (JSON Schema) and an optional UI
  schema file in the same process model. The lane decides who can complete the
  task.
- **Script task.** Runs a Python script against the instance data. You can
  store unit tests for it on the task and run them from the process-model
  overview.
- **Service task.** Calls a connector operator, such as `http/PostRequestV2`.
  Parameters can contain `M8FLOW_SECRET:<key>` sentinels, and the optional
  `m8flow_profile` parameter selects a connector profile.
- **Business rule task.** Evaluates a DMN decision table stored in the same
  process model.

## Files in a process model

A process model folder can hold the following files:

| Extension | Opens in | Purpose |
|---|---|---|
| `.bpmn` | Process modeler | Process diagrams. One file is the primary diagram that starts. |
| `.dmn` | DMN editor | Decision tables |
| `.json` | Form editor or code editor | Form schema, UI schema, example data, and BPMN unit tests (`test_*.json`) |
| `.md` | Markdown editor | Instructions and notes |

You can also upload `.txt`, `.xml`, `.svg`, `.html`, and `.css` files. The
names `process_model.json` and `process_group.json` are reserved for m8flow
metadata.

## Related pages

- [About process execution](../explanation/process-execution.md)
- [Call an external service from a process](../how-to/call-external-services.md)
