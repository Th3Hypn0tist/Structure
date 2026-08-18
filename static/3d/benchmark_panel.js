// Structure Settings integration for the S3D WebGL2 density benchmark.
// Benchmark stays hidden until explicitly enabled and uses an isolated overlay canvas.
(() => {
  if (!globalThis.S3D?.WebGLBenchmark) throw new Error('S3D WebGL benchmark must load before benchmark panel');

  const state = { benchmark: null, enabled: false, nodes: 1000 };

  function create(tag, attrs = {}, text = '') {
    const element = document.createElement(tag);
    for (const [name, value] of Object.entries(attrs)) {
      if (name === 'className') element.className = value;
      else element.setAttribute(name, value);
    }
    if (text) element.textContent = text;
    return element;
  }

  function currentPreset() {
    return { id: `nodes-${state.nodes}`, nodes: state.nodes, links: 0 };
  }

  function setNodes(raw) {
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    state.nodes = Math.max(100, Math.min(20000, Math.round(value / 100) * 100));
    const slider = document.querySelector('#s3dBenchmarkNodes');
    const output = document.querySelector('#s3dBenchmarkNodeCount');
    if (slider) slider.value = String(state.nodes);
    if (output) output.textContent = state.nodes.toLocaleString();
    if (state.enabled && state.benchmark) state.benchmark.loadPreset(currentPreset());
  }

  function setEnabled(enabled) {
    state.enabled = Boolean(enabled);
    const canvas = document.querySelector('#s3dBenchmarkCanvas');
    const toggle = document.querySelector('#s3dBenchmarkEnabled');
    if (!canvas || !toggle) return;
    canvas.hidden = !state.enabled;
    toggle.checked = state.enabled;
    if (state.enabled) {
      const metrics = document.querySelector('#s3dBenchmarkMetrics');
      if (!state.benchmark) state.benchmark = new S3D.WebGLBenchmark(canvas, metrics);
      state.benchmark.loadPreset(currentPreset());
      state.benchmark.start();
    } else {
      state.benchmark?.stop();
    }
  }

  function install() {
    if (document.querySelector('#s3dBenchmarkSettings')) return;
    const settings = document.querySelector('#settings');
    const scene = document.querySelector('#scene');
    if (!settings || !scene) throw new Error('S3D benchmark requires Structure settings and scene canvas');

    const canvas = create('canvas', { id: 's3dBenchmarkCanvas', 'aria-label': 'S3D benchmark canvas' });
    canvas.hidden = true;
    Object.assign(canvas.style, {
      position: 'fixed', inset: '0', width: '100%', height: '100%', zIndex: '1', pointerEvents: 'none',
    });
    document.body.insertBefore(canvas, document.body.firstChild);

    const details = create('details', { id: 's3dBenchmarkSettings' });
    const summary = create('summary', {}, 'S3D Benchmark');
    const body = create('div', { className: 'benchmark-settings-body' });

    const enableLabel = create('label');
    const enable = create('input', { id: 's3dBenchmarkEnabled', type: 'checkbox' });
    enableLabel.append(enable, document.createTextNode(' Run benchmark'));

    const nodeLabel = create('label');
    nodeLabel.append(document.createTextNode('Nodes '));
    const nodes = create('input', { id: 's3dBenchmarkNodes', type: 'range', min: '100', max: '20000', step: '100', value: String(state.nodes) });
    const nodeCount = create('output', { id: 's3dBenchmarkNodeCount' }, state.nodes.toLocaleString());
    nodeLabel.append(nodes, document.createTextNode(' '), nodeCount);

    const note = create('small', { className: 'muted' }, 'Continuous WebGL2 orbit benchmark. Node count 100–20,000.');
    const metrics = create('pre', { id: 's3dBenchmarkMetrics' }, 'benchmark stopped');

    enable.addEventListener('change', () => setEnabled(enable.checked));
    nodes.addEventListener('input', () => setNodes(nodes.value));

    body.append(enableLabel, nodeLabel, note, metrics);
    details.append(summary, body);
    settings.append(document.createElement('hr'), details);
  }

  window.S3DBenchmarkSettings = Object.freeze({ state, setEnabled, setNodes });
  window.addEventListener('load', install);
})();
