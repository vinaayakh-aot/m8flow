/**
 * Pad/palette agreement for dropped BPMN constructs.
 *
 * Catalog `_reject_unsupported_constructs` 400s on call activity, message
 * events, compensation events, multi-instance, and event subprocess.
 * Data-store persist is also dropped. The palette already omits data store;
 * this replaces stock `replaceMenuProvider` so the pad cannot morph or
 * toggle a dropped construct into existence.
 *
 * A second `popupMenu.registerProvider` updater does *not* work: stock
 * ReplaceMenuProvider already owns `bpmn-replace`, and a trailing updater
 * never sees those entries in the live modeler. Override the DI key the
 * same way `customPalette` replaces `paletteProvider`.
 *
 * Multi-instance header toggles that are already *active* stay so a leftover
 * shape can be turned back into a plain task. Inactive MI toggles are hidden.
 */
import inherits from 'inherits-browser';
// @ts-expect-error missing type declarations
import ReplaceMenuProvider from 'bpmn-js/lib/features/popup-menu/ReplaceMenuProvider';

export const DROPPED_REPLACE_ACTIONS = [
  'replace-with-data-store-reference',
  'replace-with-call-activity',
  'replace-with-event-subprocess',
  'replace-with-message-start',
  'replace-with-message-intermediate-catch',
  'replace-with-message-intermediate-throw',
  'replace-with-message-end',
  'replace-with-message-boundary',
  'replace-with-non-interrupting-message-boundary',
  'replace-with-non-interrupting-message-start',
  'replace-with-compensation-intermediate-throw',
  'replace-with-compensation-end',
  'replace-with-compensation-boundary',
  'replace-with-compensation-start',
] as const;

export const DROPPED_REPLACE_HEADER_ACTIONS = [
  'toggle-parallel-mi',
  'toggle-sequential-mi',
] as const;

export function omitDroppedReplaceEntries<T extends Record<string, unknown>>(
  entries: T | undefined | null,
): T {
  if (!entries) {
    return entries as T;
  }
  let changed = false;
  const next = { ...entries };
  for (const action of DROPPED_REPLACE_ACTIONS) {
    if (action in next) {
      delete next[action];
      changed = true;
    }
  }
  return changed ? next : entries;
}

export function omitDroppedReplaceHeaderEntries<T extends Record<string, unknown>>(
  entries: T | undefined | null,
): T {
  if (!entries) {
    return entries as T;
  }
  let changed = false;
  const next = { ...entries };
  for (const action of DROPPED_REPLACE_HEADER_ACTIONS) {
    const entry = next[action] as { active?: boolean } | undefined;
    if (entry && !entry.active) {
      delete next[action];
      changed = true;
    }
  }
  return changed ? next : entries;
}

export function DroppedConstructReplaceMenuProvider(this: any, ...args: unknown[]) {
  ReplaceMenuProvider.apply(this, args);
}

inherits(DroppedConstructReplaceMenuProvider, ReplaceMenuProvider);

(DroppedConstructReplaceMenuProvider as any).$inject = ReplaceMenuProvider.$inject;

DroppedConstructReplaceMenuProvider.prototype.getPopupMenuEntries = function getPopupMenuEntries(
  this: any,
  target: unknown,
) {
  return omitDroppedReplaceEntries(
    ReplaceMenuProvider.prototype.getPopupMenuEntries.call(this, target),
  );
};

DroppedConstructReplaceMenuProvider.prototype.getPopupMenuHeaderEntries =
  function getPopupMenuHeaderEntries(this: any, target: unknown) {
    return omitDroppedReplaceHeaderEntries(
      ReplaceMenuProvider.prototype.getPopupMenuHeaderEntries.call(this, target),
    );
  };

export const droppedConstructReplaceFilterModule = {
  __init__: ['replaceMenuProvider'],
  replaceMenuProvider: ['type', DroppedConstructReplaceMenuProvider],
};
