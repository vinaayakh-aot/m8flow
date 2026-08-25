/**
 * "Node-Wire Connectors" tabs (Action / Config / Parameters) on Service Tasks
 * — ported from `Connector Panel Variations.dc.html`'s "1C · Tabs" mockup.
 *
 * bpmn-js-spiffworkflow's own `ExtensionsPropertiesProvider` already
 * contributes a `service_task_properties` group (operator select + response
 * variable + a flat parameters list, all stacked vertically — no tabs). This
 * provider registers *after* it (see `Modeler.ts`'s `_m8flowModules` order,
 * same trick `externalFormPropertiesProvider.ts` uses) and replaces that
 * group in place with a tabbed version, reusing the vendored field
 * components (`ServiceTaskOperatorSelect`, `ServiceTaskResultTextInput`,
 * `ServiceTaskParameterArray`) for the actual moddle read/write logic rather
 * than re-deriving it — same reasoning as `externalFormPropertiesProvider.ts`.
 *
 * Only the Action and Parameters tabs correspond to real, already-wired
 * functionality (operator/response-variable fields; per-operation
 * parameters, now populated for real since the backend's
 * `connectors_grouped()` stopped hardcoding `parameters: []`). Parameters
 * are rendered as "1A · Stacked cards"' param list (bordered card, mono
 * name above a compact input, separated by a top border) rather than
 * `@bpmn-io/properties-panel`'s `ListGroup` — the library default renders
 * each parameter as a collapsed accordion item (name behind a toggle arrow,
 * value hidden until expanded), which doesn't match any mockup and made
 * every parameter two clicks away from being visible. The Config
 * tab is genuinely new: the mockup depicts a per-connector *named config
 * profile* picker ("Production API" / "Sandbox"), but no such concept
 * exists anywhere in the backend today — connector credentials are a single
 * flat set of tenant Secrets per connector (`CONNECTOR_METADATA[key].
 * configFields` in `connectors_controller.py`), not multiple named
 * profiles. Rather than fabricate a working-looking dropdown backed by
 * nothing, the Config tab here is deliberately modest: it names the
 * connector the selected operator belongs to and states, honestly, that its
 * credentials are managed centrally (Setup → Connectors) rather than
 * per-task — reference 1A/1D's Config card for the *visual* structure
 * (tenant/connector context above a note), not 1C's specific profile
 * dropdown, which has no backing data source yet.
 *
 * No JSX here (unlike the vendored `.jsx` files) — this file isn't matched
 * by `vite/index.js`'s `spiffworkflowPreactJsxPlugin` (scoped to
 * `node_modules/bpmn-js-spiffworkflow/**​/*.jsx`), so JSX here would compile
 * through the *host* app's own React transform instead of Preact's,
 * producing React vnodes the properties panel (a Preact tree) can't render
 * — confirmed as a real, previously-hit failure mode in that file's own
 * alias comments. `preact`'s `h()` hyperscript sidesteps the JSX-transform
 * question entirely: `preact`/`preact/hooks` are aliased to one canonical
 * instance host-wide (not scoped to `.jsx` files), so plain `h()` calls
 * resolve to the same Preact instance the panel itself uses.
 */
import { h } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { is } from 'bpmn-js/lib/util/ModelUtil';
// @ts-expect-error missing type declarations
import { TextFieldEntry } from '@bpmn-io/properties-panel';
// @ts-expect-error missing type declarations
import { useService } from 'bpmn-js-properties-panel';
// @ts-expect-error missing type declarations
import { ServiceTaskOperatorSelect, ServiceTaskParameterArray, ServiceTaskResultTextInput } from 'bpmn-js-spiffworkflow/app/spiffworkflow/extensions/propertiesPanel/SpiffExtensionServiceProperties';

const LOW_PRIORITY = 500;
const SERVICE_TASK_GROUP_ID = 'service_task_properties';
// Matches bpmn-js-spiffworkflow's own (unexported) SERVICE_TASK_OPERATOR_ELEMENT_NAME —
// `${SPIFFWORKFLOW_XML_NAMESPACE}:ServiceTaskOperator` with SPIFFWORKFLOW_XML_NAMESPACE === 'spiffworkflow'.
const SERVICE_TASK_OPERATOR_ELEMENT_NAME = 'spiffworkflow:ServiceTaskOperator';

type ServiceTaskTabId = 'action' | 'config' | 'parameters';

// Per-element active-tab store, module-level — same pattern bpmn-js-spiffworkflow's
// own SpiffExtensionServiceProperties.js already uses for per-element parameter
// memory (`previouslyUsedServiceTaskParameterValuesHash`). Tab entries are separate
// preact components (see the Group/Entry render loop this replaces — no per-entry
// wrapper, so there's no single parent to hold this as local state); a tiny
// external pub-sub is the simplest way for the tab strip's click handler to notify
// the sibling content entries to re-render.
const activeTabByElementId = new Map<string, ServiceTaskTabId>();
const tabChangeListeners = new Set<() => void>();

function setActiveServiceTaskTab(elementId: string, tab: ServiceTaskTabId): void {
  activeTabByElementId.set(elementId, tab);
  tabChangeListeners.forEach((listener) => listener());
}

function useActiveServiceTaskTab(elementId: string): ServiceTaskTabId {
  const [, forceUpdate] = useState(0);
  useEffect(() => {
    const listener = () => forceUpdate((n: number) => n + 1);
    tabChangeListeners.add(listener);
    return () => {
      tabChangeListeners.delete(listener);
    };
  }, []);
  return activeTabByElementId.get(elementId) ?? 'action';
}

function getServiceTaskOperatorModdleElement(element: any): any {
  const { extensionElements } = element.businessObject;
  if (!extensionElements) {
    return null;
  }
  return (
    extensionElements.values.find((ee: any) => ee.$type === SERVICE_TASK_OPERATOR_ELEMENT_NAME) ?? null
  );
}

function getServiceTaskParameterCount(element: any): number {
  const operatorElement = getServiceTaskOperatorModdleElement(element);
  const parameters = operatorElement?.parameterList?.parameters;
  return Array.isArray(parameters) ? parameters.length : 0;
}

// Mirrors connectors_controller.py's _humanize_connector_key fallback (same
// "strip a trailing _v<N>, title-case the rest" rule), applied client-side since
// the operator id ("http/GetRequestV2") is all that's on the moddle element —
// no round trip needed just to render a label.
function humanizeConnectorKey(key: string): string {
  return key
    .replace(/_v\d+$/i, '')
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function ServiceTaskTabStrip(props: any) {
  const { element, translate } = props;
  const elementId = element.businessObject.id;
  const activeTab = useActiveServiceTaskTab(elementId);
  const parameterCount = getServiceTaskParameterCount(element);

  const tabs: { id: ServiceTaskTabId; label: string; badge?: number }[] = [
    { id: 'action', label: translate('Action') },
    { id: 'config', label: translate('Config') },
    { id: 'parameters', label: translate('Parameters'), badge: parameterCount },
  ];

  return h(
    'div',
    { class: 'm8flow-service-task-tabs', role: 'tablist' },
    tabs.map((tab) =>
      h(
        'button',
        {
          type: 'button',
          role: 'tab',
          key: tab.id,
          'aria-selected': activeTab === tab.id,
          class: `m8flow-service-task-tab${activeTab === tab.id ? ' active' : ''}`,
          onClick: () => setActiveServiceTaskTab(elementId, tab.id),
        },
        tab.label,
        tab.badge !== undefined
          ? h('span', { class: 'm8flow-service-task-tab-badge' }, String(tab.badge))
          : null,
      ),
    ),
  );
}

function ServiceTaskActionTab(props: any) {
  const { element } = props;
  const activeTab = useActiveServiceTaskTab(element.businessObject.id);
  if (activeTab !== 'action') {
    return null;
  }
  return h(
    'div',
    { class: 'm8flow-service-task-tab-panel' },
    h(ServiceTaskOperatorSelect, props),
    h(ServiceTaskResultTextInput, props),
  );
}

function ServiceTaskConfigTab(props: any) {
  const { element, translate } = props;
  const activeTab = useActiveServiceTaskTab(element.businessObject.id);
  if (activeTab !== 'config') {
    return null;
  }

  const operatorElement = getServiceTaskOperatorModdleElement(element);
  if (!operatorElement) {
    return h(
      'p',
      { class: 'bio-properties-panel-description m8flow-service-task-tab-panel' },
      translate('Choose an action first — its connector configuration will show here.'),
    );
  }

  const connectorKey = String(operatorElement.id).split('/')[0];
  const connectorName = humanizeConnectorKey(connectorKey);

  return h(
    'div',
    { class: 'm8flow-service-task-tab-panel' },
    h('div', { class: 'm8flow-service-task-config-connector' }, connectorName),
    h(
      'p',
      { class: 'bio-properties-panel-description m8flow-service-task-config-note' },
      translate(
        'Credentials and endpoint configuration for this connector are managed centrally under Setup → Connectors, not per task.',
      ),
    ),
  );
}

// One parameter row — name (mono, bold) above its value input, no accordion
// chrome. Mirrors bpmn-js-spiffworkflow's own (unexported)
// ServiceTaskParameterTextField's get/set logic exactly (same
// `element.updateModdleProperties` write, same `.value` read) rather than
// reaching into ServiceTaskParameterArray's returned entries to find that
// component — it isn't part of the module's exports, and duplicating six
// lines of already-proven read/write logic here is simpler than depending
// on an internal shape.
function ServiceTaskParameterRow(props: any) {
  const { element, commandStack, name, serviceTaskParameterModdleElement } = props;
  const debounce = useService('debounceInput');

  const getValue = () => serviceTaskParameterModdleElement.value;
  const setValue = (value: string) => {
    commandStack.execute('element.updateModdleProperties', {
      element,
      moddleElement: serviceTaskParameterModdleElement,
      properties: { value },
    });
  };

  return h(
    'div',
    { class: 'm8flow-service-task-param-row' },
    h('div', { class: 'm8flow-service-task-param-name' }, name),
    h(TextFieldEntry, {
      element,
      id: `serviceTaskParameter-${name}-textField`,
      getValue,
      setValue,
      debounce,
    }),
  );
}

// "1A · Stacked cards" reference (Connector Panel Variations.dc.html) for the
// visual structure — a single bordered card, sunken header, param rows
// separated by a top border, name in mono type above a compact input. The
// mockup's card repeats a "Parameters" title + count inside the card, which
// this tab omits: the tab strip above already shows both.
function ServiceTaskParametersTab(props: any) {
  const { element, moddle, translate, commandStack } = props;
  const activeTab = useActiveServiceTaskTab(element.businessObject.id);
  if (activeTab !== 'parameters') {
    return null;
  }

  // Pure data transform, no hooks of its own — safe to call directly. Reused
  // only for its moddle traversal (getServiceTaskParameterModdleElements,
  // unexported); the rows below render their own markup, not this array's
  // ListGroup-shaped `entries`.
  const { items } = ServiceTaskParameterArray({ element, moddle, translate, commandStack });

  if (items.length === 0) {
    return h(
      'p',
      { class: 'bio-properties-panel-description m8flow-service-task-tab-panel' },
      translate('This action has no parameters.'),
    );
  }

  return h(
    'div',
    { class: 'm8flow-service-task-tab-panel m8flow-service-task-params-card' },
    items.map((item: any) =>
      h(ServiceTaskParameterRow, {
        key: item.id,
        element,
        commandStack,
        name: item.label,
        serviceTaskParameterModdleElement: item.entries[0].serviceTaskParameterModdleElement,
      }),
    ),
  );
}

function createServiceTaskConnectorGroup(element: any, translate: any, moddle: any, commandStack: any) {
  const sharedProps = { element, moddle, commandStack, translate };
  return {
    id: SERVICE_TASK_GROUP_ID,
    label: translate('Node-Wire Connectors'),
    entries: [
      { id: 'service_task_tabs', component: ServiceTaskTabStrip, ...sharedProps },
      { id: 'service_task_action_tab', component: ServiceTaskActionTab, ...sharedProps },
      { id: 'service_task_config_tab', component: ServiceTaskConfigTab, ...sharedProps },
      { id: 'service_task_parameters_tab', component: ServiceTaskParametersTab, ...sharedProps },
    ],
  };
}

export function ServiceTaskConnectorPanelProvider(
  this: any,
  propertiesPanel: any,
  translate: any,
  moddle: any,
  commandStack: any,
) {
  this.getGroups = function (element: any) {
    return function (groups: any[]) {
      if (!is(element, 'bpmn:ServiceTask')) {
        return groups;
      }
      const tabbedGroup = createServiceTaskConnectorGroup(element, translate, moddle, commandStack);
      const existingIndex = groups.findIndex((g) => g && g.id === SERVICE_TASK_GROUP_ID);
      if (existingIndex === -1) {
        groups.push(tabbedGroup);
      } else {
        // Replace in place (not filter+push) so the group keeps its original
        // position — between "Instructions" and "Input/Output Management",
        // matching bpmn-js-spiffworkflow's own createServiceGroup ordering.
        groups.splice(existingIndex, 1, tabbedGroup);
      }
      return groups;
    };
  };
  propertiesPanel.registerProvider(LOW_PRIORITY, this);
}

(ServiceTaskConnectorPanelProvider as any).$inject = ['propertiesPanel', 'translate', 'moddle', 'commandStack'];

export const serviceTaskConnectorPanelModule = {
  __init__: ['serviceTaskConnectorPanelProvider'],
  serviceTaskConnectorPanelProvider: ['type', ServiceTaskConnectorPanelProvider],
};
