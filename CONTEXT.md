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

**Shared realm**:
The Keycloak realm where tenant users authenticate. Organizations in this realm map to tenants.
_Avoid_: spoke realm, tenant realm

**Master realm**:
The Keycloak realm for platform / super-admin sign-in.
_Avoid_: admin realm, spoke realm

**Active tenant**:
The organization a shared-realm user is working in for the current session.
_Avoid_: localStorage tenant, selected tenant as a browser-storage value

**Tenant selection gate**:
The post-login step that chooses the active tenant when a shared-realm user belongs to organizations. It is not the tenant registry or tenant-admin UI.
_Avoid_: Tenants page, All Tenants, tenant switcher

**Tenant registry**:
The platform list of tenants (id, name, slug, status) that a super-admin manages. It is not the tenant selection gate, the tenant switcher, or tenant-admin RBAC.
_Avoid_: All Tenants as the entity, tenant-admin

**Tenant switcher**:
The super-admin shell control that filters which tenant's data is shown (all tenants vs one). It does not set the active-tenant cookie.
_Avoid_: tenant selection gate, selected tenant as a browser-storage value

**Accept invitation**:
The public path where an invited person sets a password and becomes a shared-realm user in an organization. Distinct from creating, resending, or revoking invitations. The emailed URL uses the designer origin.
_Avoid_: invitation admin, tenant invite UI

**Service account**:
A tenant-scoped machine credential for API access, not a human Keycloak login.
_Avoid_: NATS API key, manage-token, spoke-realm client
