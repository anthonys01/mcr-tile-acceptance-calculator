// Web Worker hosting a Pyodide engine that runs the Monte-Carlo rollout
// evaluator (rollout_evaluator / web_evaluator) entirely on the user's machine.
//
// Pyodide has no multiprocessing, so the desktop tool's CPU-core parallelism is
// reproduced by spawning MANY of these workers (one Pyodide each). analyzer.html
// hands each worker a slice of (choice, rollout) pairs via `run_chunk`; Common
// Random Numbers make the result independent of which worker runs which pair.
//
// Pyodide >=0.28 ships module-only, so this is a module worker.
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v314.0.0/full/pyodide.mjs';

let pyodide = null;

// Bump on every release so browsers re-fetch the Python sources instead of
// serving stale cached copies. Keep in sync with analyzer.html's worker URL.
const APP_VERSION = "2026-07-31-1";

const PY_FILES = [
  'web_evaluator.py', 'rollout_evaluator.py', 'shanten_oracle.py', 'discard_policy.py',
  'tile_acceptance_calculator.py', 'tiles_utils.py', 'acceptance.py',
  'pattern_generator.py', 'group_finder.py', 'hand_scorer.py',
  'mahjong_objects.py', 'mahjong_core.py', 'mahjong_hand.py', 'mahjong_context.py',
  'mahjong_yaku.py', 'mcr_scorer.py',
  'hand_types/__init__.py', 'hand_types/all_pungs.py', 'hand_types/all_types.py',
  'hand_types/common.py', 'hand_types/basic.py', 'hand_types/knitted.py',
  'hand_types/precompute.py', 'hand_types/seven_pairs.py',
  'hand_types/three_group_pattern.py'
];

async function init() {
  pyodide = await loadPyodide();
  for (const f of PY_FILES) {
    if (f.includes('/')) {
      try { pyodide.FS.mkdirTree('/home/pyodide/' + f.substring(0, f.lastIndexOf('/'))); } catch (e) {}
    }
    const resp = await fetch('./' + f + '?v=' + APP_VERSION, { cache: 'no-cache' });
    pyodide.FS.writeFile('/home/pyodide/' + f, await resp.text());
  }
  await pyodide.runPythonAsync(
    "import sys\nsys.path.append('/home/pyodide')\nimport web_evaluator"
  );
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
    const result = await pyodide.runPythonAsync(`web_evaluator.${fn}(*_args)`);
    postMessage({ type: 'result', id, result });
  } catch (err) {
    postMessage({ type: 'error', id, error: String(err) });
  }
};
