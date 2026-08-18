// Settings integration for the real Structure high-density benchmark.
// The benchmark uses the normal Structure scene, canonical objects and Event path.
(() => {
  if (!globalThis.StructureBenchmark) throw new Error('Structure benchmark must load before benchmark panel');

  const state = { enabled: false, nodes: 1000, metricsFrame: 0 };

  function create(tag, attrs = {}, text = '') {
    const element = document.createElement(tag);
    for (const [name, value] of Object.entries(attrs)) {
      if (name === 'className') element.className = value;
      else element.setAttribute(name, value);
    }
    if (text) element.textContent = text;
    return element;
  }

  function metricsText() {
    const metric = StructureBenchmark.metricsSnapshot();
    const batch = globalThis.StructureRenderBatch?.stats?.() ?? {};
    const residency = globalThis.StructureRenderBatch?.residency?.() ?? {};
    const memory = performance.memory ? `${(performance.memory.usedJSHeapSize / 1048576).toFixed(1)} MB` : 'n/a';
    const uploadBytes = Number(batch.uploadBytes ?? 0);
    return [
      'STRUCTURE BENCHMARK',
      `nodes         ${metric.nodes.toLocaleString()}`,
      `entities      ${metric.entities.toLocaleString()}`,
      `canonical links ${metric.links.toLocaleString()}`,
      `active traces ${metric.traces}`,
      `fps           ${metric.fps.toFixed(1)}`,
      `avg frame     ${metric.avg_ms.toFixed(2)} ms`,
      `p95 frame     ${metric.p95_ms.toFixed(2)} ms`,
      `p99 frame     ${metric.p99_ms.toFixed(2)} ms`,
      `render CPU    ${metric.render_ms.toFixed(2)} ms`,
      `draw calls    ${batch.drawCalls ?? metric.draw_calls}`,
      `buffer uploads ${batch.uploads ?? metric.uploads}`,
      `upload bytes  ${uploadBytes.toLocaleString()}`,
      `GPU resident  ${batch.resident ? 'YES' : 'NO'}`,
      `resident compiles ${residency.residentCompiles ?? 0}`,
      `resident frames ${residency.residentFrames ?? 0}`,
      `workspace build ${metric.build_ms.toFixed(1)} ms`,
      `JS heap       ${memory}`,
      '',
      'Real Structure path:',
      'Entity + Props + Event + Effect + Links',
      'TRIGGER Event -> normal causal playback',
      '',
      'Target: camera-only = 0 uploads/frame.',
    ].join('\n');
  }

  function updateMetrics() {
    if (!state.enabled) return;
    const output = document.querySelector('#structureBenchmarkMetrics');
    if (output) output.textContent = metricsText();
    state.metricsFrame = requestAnimationFrame(updateMetrics);
  }

  function setNodes(raw) {
    const normalized = StructureBenchmark.setNodeCount(raw);
    state.nodes = normalized;
    const slider = document.querySelector('#s3dBenchmarkNodes');
    const output = document.querySelector('#s3dBenchmarkNodeCount');
    if (slider) slider.value = String(normalized);
    if (output) output.textContent = normalized.toLocaleString();
  }

  function setEnabled(enabled) {
    const toggle = document.querySelector('#s3dBenchmarkEnabled');
    const metrics = document.querySelector('#structureBenchmarkMetrics');
    if (!toggle || !metrics) return;
    const next = Boolean(enabled);
    if (next === state.enabled) return;
    state.enabled = next;
    toggle.checked = next;
    if (next) {
      StructureBenchmark.activate(state.nodes);
      metrics.hidden = false;
      cancelAnimationFrame(state.metricsFrame);
      updateMetrics();
    } else {
      cancelAnimationFrame(state.metricsFrame);
      state.metricsFrame = 0;
      StructureBenchmark.deactivate();
      metrics.hidden = true;
    }
  }

  function install() {
    if (document.querySelector('#s3dBenchmarkSettings')) return;
    const settings = document.querySelector('#settings');
    if (!settings) throw new Error('Structure benchmark requires Settings');

    const metrics = create('pre', { id: 'structureBenchmarkMetrics', 'aria-live': 'polite' }, 'benchmark stopped');
    metrics.hidden = true;
    Object.assign(metrics.style, {
      position: 'fixed', right: '16px', bottom: '16px', zIndex: '12000', margin: '0', padding: '10px 12px',
      minWidth: '285px', maxWidth: 'calc(100vw - 32px)', whiteSpace: 'pre', pointerEvents: 'none',
      background: 'rgba(5, 8, 13, .88)', border: '1px solid rgba(90, 125, 170, .55)', borderRadius: '6px',
      color: '#dbe9ff', font: '12px/1.35 ui-monospace, SFMono-Regular, Consolas, monospace',
      boxShadow: '0 8px 28px rgba(0,0,0,.35)',
    });
    document.body.appendChild(metrics);

    const details = create('details', { id: 's3dBenchmarkSettings' });
    const summary = create('summary', {}, 'S3D Benchmark');
    const body = create('div', { className: 'benchmark-settings-body' });

    const enableLabel = create('label');
    const enable = create('input', { id: 's3dBenchmarkEnabled', type: 'checkbox' });
    enableLabel.append(enable, document.createTextNode(' Run real Structure benchmark'));

    const nodeLabel = create('label');
    nodeLabel.append(document.createTextNode('Nodes '));
    const nodes = create('input', {
      id: 's3dBenchmarkNodes', type: 'range', min: '100', max: '20000', step: '100', value: String(state.nodes),
    });
    const nodeCount = create('output', { id: 's3dBenchmarkNodeCount' }, state.nodes.toLocaleString());
    nodeLabel.append(nodes, document.createTextNode(' '), nodeCount);

    const fire = create('button', { id: 'structureBenchmarkFire', type: 'button' }, 'FIRE TRIGGER EVENT');
    const note = create('small', { className: 'muted' },
      'Creates a temporary real Structure workspace. The TRIGGER Entity is left of the blue cube; its Event starts the normal causal chain. Original workspace is restored when stopped.');

    enable.addEventListener('change', () => setEnabled(enable.checked));
    nodes.addEventListener('change', () => setNodes(nodes.value));
    fire.addEventListener('click', () => StructureBenchmark.fire());

    body.append(enableLabel, nodeLabel, fire, note);
    details.append(summary, body);
    settings.append(document.createElement('hr'), details);
  }

  window.S3DBenchmarkSettings = Object.freeze({ state, setEnabled, setNodes });
  if (document.readyState === 'loading') window.addEventListener('load', install);
  else install();
})();
