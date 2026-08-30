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

**Catalog**:
The tenant's tree of process groups and process models.
_Avoid_: templates gallery, process instances, connector catalog

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
The post-login step that chooses the active tenant when a shared-realm user belongs to organizations. It is not the tenant registry or tenant admin.
_Avoid_: Tenants page, All Tenants, tenant switcher

**Tenant registry**:
The platform list of tenants (id, name, slug, status) that a super-admin manages. It is not the tenant selection gate, the tenant switcher, or tenant admin.
_Avoid_: All Tenants as the entity, tenant-admin, Tenant Management

**Tenant admin**:
The per-tenant surface for members, groups, and role grants. A tenant-admin uses it for the active tenant; a super-admin can use it for any tenant. It is not the tenant registry, tenant selection gate, or tenant switcher.
_Avoid_: Tenants page, All Tenants, tenant-admin as the tenant registry

**Tenant switcher**:
The super-admin shell control that filters which tenant's data is shown (all tenants vs one). It does not set the active-tenant cookie.
_Avoid_: tenant selection gate, selected tenant as a browser-storage value

**Accept invitation**:
The public path where an invited person sets a password and becomes a shared-realm user in an organization. Distinct from creating, resending, or revoking invitations. The emailed URL uses the designer origin.
_Avoid_: invitation admin, tenant invite UI

**Invitation management**:
The super-admin path that creates, lists, resends, and revokes invitations for a tenant. Distinct from Accept invitation. A tenant-admin cannot do this.
_Avoid_: Accept invitation, tenant invite UI as the public path

**Service account**:
A tenant-scoped machine credential for API access, not a human Keycloak login.
_Avoid_: NATS API key, manage-token, spoke-realm client

**Secret**:
A tenant-scoped named credential stored by the host. After create, the value is never shown again on list or show.
_Avoid_: environment variable, service account, NATS API key, Keycloak client secret

**Secret key**:
The `\w+` name of a secret (for example `SMTP_PASSWORD`). It is not the value and not the internal numeric id.
_Avoid_: secret name as a display title, secret id as what the user types

**Secret sentinel**:
The BPMN and Jinja token `M8FLOW_SECRET:<secret key>` that the host replaces with the stored value at runtime.
_Avoid_: SPIFF_SECRET, env-var interpolation

**Secret backend**:
The store that holds secret values for a tenant: the Postgres `secret` table by default, or HashiCorp Vault KV v2 when enabled.
_Avoid_: connector proxy, Keycloak

**Configuration**:
The designer Setup surface whose product job is secrets (list, create, show, update, delete). It is not Authentications, Connectors, or tenant admin.
_Avoid_: settings, preferences, Authentications
