/**
 * Custom BPMN palette matching Process Modeler.dc.html's exact 8-entry,
 * 2-column floating palette (Pan, Lasso select, Connect, Task, Start event,
 * End event, Gateway, Data object) — replaces bpmn-js's own default
 * PaletteProvider (which additionally offers space-tool, intermediate
 * event, data store, sub-process, participant, and group — not in the
 * mockup) via the documented override pattern: an `additionalModules`
 * entry providing the same `paletteProvider` DI key wins over the core
 * module's registration.
 *
 * Reuses bpmn-font's own icon classes (bpmn-icon-*) for the same shapes the
 * mockup draws — real bpmn.io icons, not new assets — and the same
 * create.start()/elementFactory contract bpmn-js's own PaletteProvider
 * uses, so drag-to-place and click-to-place behave identically to stock
 * bpmn-js; only which entries render (and their CSS, see diagram-chrome.css)
 * changes.
 */
function CustomPaletteProvider(
  this: any,
  palette: any,
  create: any,
  elementFactory: any,
  lassoTool: any,
  handTool: any,
  globalConnect: any,
  translate: any,
) {
  this._create = create;
  this._elementFactory = elementFactory;
  this._lassoTool = lassoTool;
  this._handTool = handTool;
  this._globalConnect = globalConnect;
  this._translate = translate;

  palette.registerProvider(this);
}

CustomPaletteProvider.$inject = [
  'palette',
  'create',
  'elementFactory',
  'lassoTool',
  'handTool',
  'globalConnect',
  'translate',
];

CustomPaletteProvider.prototype.getPaletteEntries = function getPaletteEntries(this: any) {
  const { _create: create, _elementFactory: elementFactory, _translate: translate } = this;

  function createAction(type: string, group: string, className: string, title: string) {
    function createListener(event: unknown) {
      const shape = elementFactory.createShape({ type });
      create.start(event, shape);
    }
    return {
      group,
      className,
      title,
      action: { dragstart: createListener, click: createListener },
    };
  }

  const entries: Record<string, unknown> = {
    'hand-tool': {
      group: 'tools',
      className: 'bpmn-icon-hand-tool',
      title: translate('Activate hand tool'),
      action: { click: (event: unknown) => this._handTool.activateHand(event) },
    },
    'lasso-tool': {
      group: 'tools',
      className: 'bpmn-icon-lasso-tool',
      title: translate('Activate lasso tool'),
      action: { click: (event: unknown) => this._lassoTool.activateSelection(event) },
    },
    'global-connect-tool': {
      group: 'tools',
      className: 'bpmn-icon-connection-multi',
      title: translate('Activate global connect tool'),
      action: { click: (event: unknown) => this._globalConnect.start(event) },
    },
    'create.task': createAction('bpmn:Task', 'activity', 'bpmn-icon-task', translate('Create task')),
    'create.start-event': createAction(
      'bpmn:StartEvent',
      'event',
      'bpmn-icon-start-event-none',
      translate('Create start event'),
    ),
    'create.end-event': createAction(
      'bpmn:EndEvent',
      'event',
      'bpmn-icon-end-event-none',
      translate('Create end event'),
    ),
    'create.exclusive-gateway': createAction(
      'bpmn:ExclusiveGateway',
      'gateway',
      'bpmn-icon-gateway-none',
      translate('Create gateway'),
    ),
    'create.data-object': createAction(
      'bpmn:DataObjectReference',
      'data-object',
      'bpmn-icon-data-object',
      translate('Create data object reference'),
    ),
  };
  return entries;
};

export const customPaletteModule = {
  __init__: ['paletteProvider'],
  paletteProvider: ['type', CustomPaletteProvider],
};
