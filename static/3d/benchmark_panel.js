// Structure Settings integration for the S3D WebGL2 density benchmark.
// Benchmark stays hidden until explicitly enabled and uses an isolated overlay canvas.
(() => {
  if (!globalThis.S3D?.WebGLBenchmark) throw new Error('S3D WebGL benchmark must load before benchmark panel');

  const state = {
    benchmark: null,
    enabled: false,
    nodes: 1000,
    suspendedCanvases: new Map(),
    suspendedOverlays: new Map(),
    renderGateInstalled: false,
  };

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

  function installRenderGate() {
    if (state.renderGateInstalled) return;
    if (typeof globalThis.render !== 'function') throw new Error('Structure render loop unavailable for benchmark gate');
    const structureRender = globalThis.render;
    globalThis.render = function renderWithBenchmarkGate() {
      if (state.enabled) {
        requestAnimationFrame(globalThis.render);
        return;
      }
      structureRender();
    };
    state.renderGateInstalled = true;
  }

  function suspendStructureScene(benchmarkCanvas) {
    state.suspendedCanvases.clear();
    for (const canvas of document.querySelectorAll('canvas')) {
      if (canvas === benchmarkCanvas) continue;
      state.suspendedCanvases.set(canvas, canvas.hidden);
      canvas.hidden = true;
    }

    state.suspendedOverlays.clear();
    for (const selector of ['#nodeLabels', '#gizmoLabels']) {
      const element = document.querySelector(selector);
      if (!element) continue;
      state.suspendedOverlays.set(element, element.hidden);
      element.hidden = true;
    }
  }

  function restoreStructureScene() {
    for (const [canvas, wasHidden] of state.suspendedCanvases) canvas.hidden = wasHidden;
    state.suspendedCanvases.clear();
    for (const [element, wasHidden] of state.suspendedOverlays) element.hidden = wasHidden;
    state.suspendedOverlays.clear();
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
    const canvas = document.querySelector('#s3dBenchmarkCanvas');
    const metrics = document.querySelector('#s3dBenchmarkMetrics');
    const toggle = document.querySelector('#s3dBenchmarkEnabled');
    if (!canvas || !metrics || !toggle) return;

    const next = Boolean(enabled);
    if (next === state.enabled) return;
    state.enabled = next;
    toggle.checked = state.enabled;

    if (state.enabled) {
      suspendStructureScene(canvas);
      canvas.hidden = false;
      metrics.hidden = false;
      if (!state.benchmark) state.benchmark = new S3D.WebGLBenchmark(canvas, metrics);
      state.benchmark.loadPreset(currentPreset());
      state.benchmark.start();
    } else {
      state.benchmark?.stop();
      canvas.hidden = true;
      metrics.hidden = true;
      restoreStructureScene();
    }
  }

  function install() {
    if (document.querySelector('#s3dBenchmarkSettings')) return;
    const settings = document.querySelector('#settings');
    const scene = document.querySelector('#scene');
    if (!settings || !scene) throw new Error('S3D benchmark requires Structure settings and scene canvas');
    installRenderGate();

    const canvas = create('canvas', { id: 's3dBenchmarkCanvas', 'aria-label': 'S3D benchmark canvas' });
    canvas.hidden = true;
    Object.assign(canvas.style, {
      position: 'fixed', inset: '0', width: '100%', height: '100%', zIndex: '1', pointerEvents: 'auto', touchAction: 'none',
    });
    document.body.insertBefore(canvas, document.body.firstChild);

    const metrics = create('pre', { id: 's3dBenchmarkMetrics', 'aria-live': 'polite' }, 'benchmark stopped');
    metrics.hidden = true;
    Object.assign(metrics.style, {
      position: 'fixed',
      right: '16px',
      bottom: '16px',
      zIndex: '12000',
      margin: '0',
      padding: '10px 12px',
      minWidth: '250px',
      maxWidth: 'calc(100vw - 32px)',
      whiteSpace: 'pre',
      pointerEvents: 'none',
      background: 'rgba(5, 8, 13, .88)',
      border: '1px solid rgba(90, 125, 170, .55)',
      borderRadius: '6px',
      color: '#dbe9ff',
      font: '12px/1.35 ui-monospace, SFMono-Regular, Consolas, monospace',
      boxShadow: '0 8px 28px rgba(0,0,0,.35)',
    });
    document.body.appendChild(metrics);

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

    const note = create('small', { className: 'muted' }, 'Continuous WebGL2 benchmark. LMB pan · RMB orbit · wheel zoom. Node count 100–20,000.');

    enable.addEventListener('change', () => setEnabled(enable.checked));
    nodes.addEventListener('input', () => setNodes(nodes.value));

    body.append(enableLabel, nodeLabel, note);
    details.append(summary, body);
    settings.append(document.createElement('hr'), details);
  }

  window.S3DBenchmarkSettings = Object.freeze({ state, setEnabled, setNodes });
  if (document.readyState === 'loading') window.addEventListener('load', install);
  else install();
})();
