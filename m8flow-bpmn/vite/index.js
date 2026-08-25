/**
 * Vite plugin for hosts that mount m8flow-bpmn with the properties panel /
 * bpmn-js-spiffworkflow. Owns the Preact single-instance aliases and the
 * Spiff JSX transform (ticket 12).
 *
 * Plain JS so Vite can import this from vite.config without a TS loader.
 */
import path from 'node:path';
import { createRequire } from 'node:module';
import { transform } from 'esbuild';

const require = createRequire(import.meta.url);

function resolvePropertiesPanelPreact(...segments) {
  const panelRoot = path.dirname(require.resolve('@bpmn-io/properties-panel/package.json'));
  return path.join(panelRoot, 'preact', ...segments);
}

function spiffworkflowPreactJsxPlugin() {
  const SPIFFWORKFLOW_JSX = /node_modules\/bpmn-js-spiffworkflow\/.*\.jsx$/;
  return {
    name: 'm8flow-bpmn-spiffworkflow-preact-jsx',
    enforce: 'pre',
    async transform(code, id) {
      if (!SPIFFWORKFLOW_JSX.test(id)) return null;
      const result = await transform(code, {
        loader: 'jsx',
        jsx: 'automatic',
        jsxImportSource: 'preact',
        sourcefile: id,
        sourcemap: true,
      });
      return { code: result.code, map: result.map };
    },
  };
}

/**
 * @param {{ alias?: Record<string, string> }} [options]
 */
export default function m8flowBpmnVitePlugin(options = {}) {
  const preactRoot = resolvePropertiesPanelPreact();
  return {
    plugins: [spiffworkflowPreactJsxPlugin()],
    resolve: {
      alias: {
        preact: preactRoot,
        'preact/hooks': resolvePropertiesPanelPreact('hooks'),
        'preact/compat': resolvePropertiesPanelPreact('compat'),
        'preact/jsx-runtime': resolvePropertiesPanelPreact('jsx-runtime'),
        ...options.alias,
      },
    },
    optimizeDeps: {
      include: ['classnames', '@bpmn-io/properties-panel'],
      exclude: ['m8flow-bpmn'],
      esbuildOptions: {
        jsx: 'automatic',
        jsxImportSource: 'preact',
      },
    },
  };
}
