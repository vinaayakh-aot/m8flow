/** Shared imperative handle BpmnCanvas, DmnCanvas, TextFileCanvas, and
 * FormSchemaCanvas expose,
 * so the page-level Download/Save controls can pull the current file contents
 * and manage dirty-tracking without any canvas needing to know about
 * downloading or the save API. */
export type DiagramCanvasHandle = {
  saveXML: () => Promise<string>;
  /** Call after a successful save so the canvas's dirty-tracking treats the
   * current command-stack position as the new "clean" baseline. */
  markSaved: () => void;
};
