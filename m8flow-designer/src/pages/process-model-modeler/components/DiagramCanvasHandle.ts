/** Shared imperative handle both BpmnCanvas and DmnCanvas expose, so the
 * page-level Download/Save controls can pull the current diagram's XML and
 * manage dirty-tracking without either canvas needing to know about
 * downloading or the save API. */
export type DiagramCanvasHandle = {
  saveXML: () => Promise<string>;
  /** Call after a successful save so the canvas's dirty-tracking treats the
   * current command-stack position as the new "clean" baseline. */
  markSaved: () => void;
};
