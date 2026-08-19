// Explicit Structure render pipeline.
// Rendering stages register here; no module is allowed to replace global render().
(() => {
  const beforeFrame = new Map();
  const passes = new Map();
  let coreRenderer = null;
  let backend = null;
  let backendName = 'direct';
  let running = false;
  let rafId = 0;
  let frame = 0;
  let fpsLimit = 25;
  let lastRenderedAt = 0;
  let renderedFrames = 0;
  let skippedFrames = 0;

  function ordered(map) {
    return [...map.values()].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
  }

  function register(map, name, fn, order = 0) {
    if (typeof name !== 'string' || !name) throw new Error('render pipeline stage requires non-empty name');
    if (typeof fn !== 'function') throw new Error(`render pipeline stage ${name} requires function`);
    map.set(name, { name, fn, order: Number(order) || 0 });
    return () => map.delete(name);
  }

  function setCoreRenderer(fn) {
    if (typeof fn !== 'function') throw new Error('render pipeline core renderer requires function');
    coreRenderer = fn;
  }

  function setBackend(name, fn) {
    if (typeof name !== 'string' || !name) throw new Error('render backend requires non-empty name');
    if (typeof fn !== 'function') throw new Error(`render backend ${name} requires function`);
    backendName = name;
    backend = fn;
  }

  function clearBackend(name = null) {
    if (name && name !== backendName) return false;
    backendName = 'direct';
    backend = null;
    return true;
  }

  function setFpsLimit(value) {
    const numeric = Number(value);
    if (![0, 15, 25, 30, 60, 120].includes(numeric)) throw new Error(`unsupported FPS limit: ${value}`);
    fpsLimit = numeric;
    lastRenderedAt = 0;
    return fpsLimit;
  }

  function renderContent(context) {
    if (!coreRenderer) throw new Error('Structure render pipeline core renderer is not registered');
    const result = coreRenderer(context);
    for (const stage of ordered(passes)) stage.fn(context);
    return result;
  }

  function renderNow(timestamp = performance.now()) {
    const context = {
      timestamp,
      frame: ++frame,
      renderContent,
      backend: backendName,
    };
    for (const stage of ordered(beforeFrame)) stage.fn(context);
    if (backend) return backend(context);
    return renderContent(context);
  }

  function frameDue(timestamp) {
    if (fpsLimit === 0) return true;
    const interval = 1000 / fpsLimit;
    if (!lastRenderedAt) {
      lastRenderedAt = timestamp;
      return true;
    }
    const elapsed = timestamp - lastRenderedAt;
    if (elapsed + 0.25 < interval) return false;
    const intervals = Math.max(1, Math.floor((elapsed + 0.25) / interval));
    lastRenderedAt += intervals * interval;
    return true;
  }

  function loop(timestamp) {
    if (!running) return;
    if (frameDue(timestamp)) {
      renderedFrames += 1;
      try {
        renderNow(timestamp);
      } catch (error) {
        window.reportStructureError?.(error, { type: 'render_pipeline' });
        running = false;
        rafId = 0;
        throw error;
      }
    } else {
      skippedFrames += 1;
    }
    if (running) rafId = requestAnimationFrame(loop);
  }

  function start() {
    if (running) return;
    running = true;
    rafId = requestAnimationFrame(loop);
  }

  function stop() {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
  }

  window.StructureRenderPipeline = Object.freeze({
    setCoreRenderer,
    addBeforeFrame: (name, fn, order = 0) => register(beforeFrame, name, fn, order),
    addPass: (name, fn, order = 0) => register(passes, name, fn, order),
    removeBeforeFrame: name => beforeFrame.delete(name),
    removePass: name => passes.delete(name),
    setBackend,
    clearBackend,
    setFpsLimit,
    getFpsLimit: () => fpsLimit,
    renderNow,
    start,
    stop,
    isRunning: () => running,
    stats: () => ({ frame, fpsLimit, renderedFrames, skippedFrames, backend: backendName, passes: ordered(passes).map(item => item.name) }),
  });
})();
