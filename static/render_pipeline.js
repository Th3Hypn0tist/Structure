// Explicit Structure render pipeline.
// The app owns one core render function. Projection/cache/backend/metrics modules
// register stages here; they never replace global render() themselves.
(() => {
  if (typeof render !== 'function') throw new Error('Structure core render must exist before render_pipeline');

  const coreRenderer = render;
  const beforeFrame = new Map();
  const passes = new Map();
  const afterFrame = new Map();
  let backend = null;
  let backendName = 'direct';
  let frame = 0;
  let fpsLimit = 25;
  let lastRenderedAt = 0;
  let renderedFrames = 0;
  let skippedFrames = 0;
  let running = false;
  let rafId = 0;

  function ordered(map) {
    return [...map.values()].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
  }

  function register(map, name, fn, order = 0) {
    if (typeof name !== 'string' || !name) throw new Error('render pipeline stage requires non-empty name');
    if (typeof fn !== 'function') throw new Error(`render pipeline stage ${name} requires function`);
    map.set(name, { name, fn, order: Number(order) || 0 });
    return () => map.delete(name);
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
    const result = coreRenderer();
    for (const stage of ordered(passes)) stage.fn(context);
    return result;
  }

  function renderFrame(timestamp = performance.now()) {
    const context = {
      timestamp,
      frame: ++frame,
      renderContent,
      backend: backendName,
      result: undefined,
      error: null,
    };
    for (const stage of ordered(beforeFrame)) stage.fn(context);
    try {
      context.result = backend ? backend(context) : renderContent(context);
      return context.result;
    } catch (error) {
      context.error = error;
      throw error;
    } finally {
      for (const stage of ordered(afterFrame)) stage.fn(context);
    }
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

  function scheduleNext() {
    if (!running || rafId) return;
    rafId = requestAnimationFrame(render);
  }

  function renderDispatcher(timestamp = performance.now()) {
    rafId = 0;
    if (!running) running = true;
    try {
      if (!frameDue(timestamp)) {
        skippedFrames += 1;
        return;
      }
      renderedFrames += 1;
      return renderFrame(timestamp);
    } catch (error) {
      window.reportStructureError?.(error, { type: 'render_pipeline' });
      running = false;
      throw error;
    } finally {
      scheduleNext();
    }
  }

  function start() {
    if (running) return;
    running = true;
    scheduleNext();
  }

  function stop() {
    running = false;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
  }

  function startWhenWorkspaceReady() {
    if (running) return;
    if (typeof ws !== 'undefined' && ws) {
      start();
      return;
    }
    requestAnimationFrame(startWhenWorkspaceReady);
  }

  // This is the only global render assignment in the architecture. All modules
  // below this boundary register stages/backends instead of wrapping render().
  render = renderDispatcher;

  window.StructureRenderPipeline = Object.freeze({
    addBeforeFrame: (name, fn, order = 0) => register(beforeFrame, name, fn, order),
    addPass: (name, fn, order = 0) => register(passes, name, fn, order),
    addAfterFrame: (name, fn, order = 0) => register(afterFrame, name, fn, order),
    removeBeforeFrame: name => beforeFrame.delete(name),
    removePass: name => passes.delete(name),
    removeAfterFrame: name => afterFrame.delete(name),
    setBackend,
    clearBackend,
    setFpsLimit,
    getFpsLimit: () => fpsLimit,
    renderFrame,
    start,
    stop,
    isRunning: () => running,
    coreRenderer: () => coreRenderer,
    stats: () => ({
      frame,
      fpsLimit,
      renderedFrames,
      skippedFrames,
      backend: backendName,
      passes: ordered(passes).map(item => item.name),
      running,
    }),
  });

  window.addEventListener('load', startWhenWorkspaceReady, { once: true });
})();
