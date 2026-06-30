// Web Worker hosting the pyodide engine so all CPU-bound mahjong analysis runs
// off the main thread, keeping the trainer UI responsive while the engine thinks.
// Pyodide >=0.28 only ships a module build, so this is a module worker.
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v314.0.0/full/pyodide.mjs';

let pyodide = null;

const PY_FILES = [
  'training_engine.py', 'tile_acceptance_calculator.py', 'tiles_utils.py',
  'acceptance.py', 'pattern_generator.py', 'group_finder.py', 'mahjong_objects.py', 'mcr_scorer.py',
  'hand_types/__init__.py', 'hand_types/all_pungs.py', 'hand_types/all_types.py', 'hand_types/common.py',
  'hand_types/basic.py', 'hand_types/knitted.py', 'hand_types/precompute.py', 'hand_types/seven_pairs.py',
  'hand_types/three_group_pattern.py'
];

async function init() {
  pyodide = await loadPyodide();
  for (const f of PY_FILES) {
    if (f.includes('/')) {
      try { pyodide.FS.mkdirTree('/home/pyodide/' + f.substring(0, f.lastIndexOf('/'))); } catch (e) {}
    }
    const resp = await fetch('./' + f);
    pyodide.FS.writeFile('/home/pyodide/' + f, await resp.text());
  }
  await pyodide.runPythonAsync("import sys\nsys.path.append('/home/pyodide')\nimport training_engine");
  postMessage({ type: 'ready' });
}

const initPromise = init().catch(err => {
  postMessage({ type: 'fatal', error: String(err) });
});

self.onmessage = async (event) => {
  const { id, fn, args } = event.data;
  await initPromise;
  try {
    pyodide.globals.set('_args', pyodide.toPy(args));
    const result = await pyodide.runPythonAsync(`training_engine.${fn}(*_args)`);
    postMessage({ type: 'result', id, result });
  } catch (err) {
    postMessage({ type: 'error', id, error: String(err) });
  }
};
