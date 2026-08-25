# M8Flow

Host for running and cataloguing BPMN process models. This glossary is the shared language for catalog and runtime concepts — not an implementation spec.

## Language

**Process model**:
A named BPMN definition and its accompanying files in a tenant catalog.
_Avoid_: process (alone), process instance, workflow, edit process instance

**Process instance**:
One execution of a process model.
_Avoid_: process (alone), run (as the noun for the entity), process model

**Process-model overview**:
The designer page for one process model: identity, stats, recent instances, and files. It is not the canvas that edits BPMN or forms.
_Avoid_: edit process instance page, process instance page, ProcessModelShow, modeler

**Process modeler**:
The canvas for editing a process model's BPMN, DMN, and form files.
_Avoid_: overview, editor (alone)

**Process instance viewer**:
The read-only canvas that shows one process instance's diagram, including live task-state.
_Avoid_: modeler, current events, events page, ReactDiagramEditor

**Properties panel**:
The side panel of element fields shown while designing a process model (or a DMN file).
_Avoid_: inspector, attributes panel, settings

**Process group**:
A folder of process models in a tenant catalog.
_Avoid_: folder, directory, tenant

**Created by**:
The user who created a catalog object (process model or template). The mockup label "Owner" is this person, not a separate role.
_Avoid_: owner
