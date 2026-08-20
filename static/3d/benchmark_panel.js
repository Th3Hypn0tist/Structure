// Settings integration for the real Structure high-density benchmark.
(() => {
  if (!globalThis.StructureBenchmark) throw new Error('Structure benchmark must load before benchmark panel');

  const state = { enabled: false, nodes: 1000, metricsFrame: 0, previousFpsLimit: null };

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
      `resident reason ${residency.reason ?? 'n/a'}`,
      `workspace build ${metric.build_ms.toFixed(1)} ms`,
      `benchmark cap Display`,
      `JS heap       ${memory}`,
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

  function enableBenchmarkCapacityMode() {
    if (!globalThis.StructureFrameRateLimit) throw new Error('Structure benchmark requires frame-rate settings');
    if (state.previousFpsLimit === null) state.previousFpsLimit = StructureFrameRateLimit.get();
    StructureFrameRateLimit.set(0);
  }

  function restoreUserFrameRateLimit() {
    if (state.previousFpsLimit === null) return;
    StructureFrameRateLimit.set(state.previousFpsLimit);
    state.previousFpsLimit = null;
  }

  function showBuildProgress(info) {
    const wrap = document.querySelector('#benchmarkBuildProgress');
    const bar = document.querySelector('#benchmarkBuildBar');
    const text = document.querySelector('#benchmarkBuildText');
    if (!wrap || !bar || !text) return;
    wrap.hidden = false;
    bar.value = info.percent;
    text.textContent = `${info.phase} · ${Math.round(info.percent)}%`;
  }

  function hideBuildProgress() {
    const wrap = document.querySelector('#benchmarkBuildProgress');
    if (wrap) wrap.hidden = true;
  }

  async function setEnabled(enabled) {
    const toggle = document.querySelector('#s3dBenchmarkEnabled');
    const metrics = document.querySelector('#structureBenchmarkMetrics');
    const nodes = document.querySelector('#s3dBenchmarkNodes');
    const fire = document.querySelector('#structureBenchmarkFire');
    if (!toggle || !metrics || !nodes || !fire) return;

    const next = Boolean(enabled);
    if (!next) {
      state.enabled = false;
      toggle.checked = false;
      toggle.disabled = false;
      nodes.disabled = false;
      fire.disabled = true;
      cancelAnimationFrame(state.metricsFrame);
      state.metricsFrame = 0;
      StructureBenchmark.deactivate();
      restoreUserFrameRateLimit();
      hideBuildProgress();
      metrics.hidden = true;
      return;
    }

    if (state.enabled || StructureBenchmark.state.building) return;
    toggle.checked = true;
    toggle.disabled = true;
    nodes.disabled = true;
    fire.disabled = true;
    metrics.hidden = true;
    showBuildProgress({ phase: 'Preparing benchmark', percent: 0 });

    try {
      await StructureBenchmark.activate(state.nodes, showBuildProgress);
      enableBenchmarkCapacityMode();
      state.enabled = true;
      metrics.hidden = false;
      hideBuildProgress();
      fire.disabled = false;
      cancelAnimationFrame(state.metricsFrame);
      updateMetrics();
    } catch (error) {
      state.enabled = false;
      toggle.checked = false;
      hideBuildProgress();
      restoreUserFrameRateLimit();
      window.reportStructureError?.(error, { type: 'benchmark_build' });
      throw error;
    } finally {
      toggle.disabled = false;
      nodes.disabled = false;
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
      minWidth: '285px', background: 'rgba(5, 8, 13, .88)', border: '1px solid rgba(90, 125, 170, .55)',
      borderRadius: '6px', color: '#dbe9ff', font: '12px/1.35 ui-monospace, SFMono-Regular, Consolas, monospace',
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
    const nodes = create('input', { id: 's3dBenchmarkNodes', type: 'range', min: '100', max: '20000', step: '100', value: String(state.nodes) });
    const nodeCount = create('output', { id: 's3dBenchmarkNodeCount' }, state.nodes.toLocaleString());
    nodeLabel.append(nodes, document.createTextNode(' '), nodeCount);

    const progressWrap = create('div', { id: 'benchmarkBuildProgress' });
    progressWrap.hidden = true;
    const progressBar = create('progress', { id: 'benchmarkBuildBar', max: '100', value: '0' });
    progressBar.style.width = '100%';
    const progressText = create('small', { id: 'benchmarkBuildText', className: 'muted' }, 'Preparing benchmark');
    progressWrap.append(progressBar, progressText);

    const fire = create('button', { id: 'structureBenchmarkFire', type: 'button' }, 'FIRE TRIGGER EVENT');
    fire.disabled = true;
    const note = create('small', { className: 'muted' }, 'Benchmark workspace is generated in chunks so large tests do not block the tab. Rendering starts only after the workspace is complete.');

    enable.addEventListener('change', () => setEnabled(enable.checked).catch(error => window.reportStructureError?.(error, { type: 'benchmark_toggle' })));
    nodes.addEventListener('change', () => setNodes(nodes.value));
    fire.addEventListener('click', () => StructureBenchmark.fire());

    body.append(enableLabel, nodeLabel, progressWrap, fire, note);
    details.append(summary, body);
    settings.append(document.createElement('hr'), details);
  }

  window.S3DBenchmarkSettings = Object.freeze({ state, setEnabled, setNodes });
  if (document.readyState === 'loading') window.addEventListener('load', install);
  else install();
})();