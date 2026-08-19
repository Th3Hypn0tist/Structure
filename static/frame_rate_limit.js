// Structure render-loop frame-rate cap.
// This is local view/runtime policy only: it never changes CW/canonical semantics.
(() => {
  const STORAGE_KEY = 'structure.frame_rate_limit';
  const DEFAULT_FPS = 25;
  const OPTIONS = Object.freeze([15, 25, 30, 60, 120, 0]); // 0 = display / uncapped rAF

  function normalize(value) {
    const numeric = Number(value);
    return OPTIONS.includes(numeric) ? numeric : DEFAULT_FPS;
  }

  function loadLimit() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored === null ? DEFAULT_FPS : normalize(stored);
    } catch (_) {
      return DEFAULT_FPS;
    }
  }

  let frameRateLimit = loadLimit();
  let lastRenderedAt = 0;
  let skippedFrames = 0;
  let renderedFrames = 0;

  function saveLimit(value) {
    frameRateLimit = normalize(value);
    lastRenderedAt = 0;
    try { localStorage.setItem(STORAGE_KEY, String(frameRateLimit)); } catch (_) {}
    syncControl();
    return frameRateLimit;
  }

  function installControl() {
    const settings = document.querySelector('#settings');
    if (!settings || document.querySelector('#frameRateLimit')) return;

    const separator = document.createElement('hr');
    const heading = document.createElement('h3');
    heading.textContent = 'Rendering';
    const label = document.createElement('label');
    label.textContent = 'FPS limit ';
    const select = document.createElement('select');
    select.id = 'frameRateLimit';

    for (const value of OPTIONS) {
      const option = document.createElement('option');
      option.value = String(value);
      option.textContent = value === 0 ? 'Display' : String(value);
      select.appendChild(option);
    }
    select.addEventListener('change', () => saveLimit(select.value));
    label.appendChild(select);
    settings.append(separator, heading, label);
    syncControl();
  }

  function syncControl() {
    const select = document.querySelector('#frameRateLimit');
    if (select) select.value = String(frameRateLimit);
  }

  function installRenderCap() {
    if (typeof render !== 'function') throw new Error('Structure render loop unavailable for frame-rate cap');
    if (render.__structureFrameRateLimited) return;

    const renderBeforeFrameRateLimit = render;
    const capped = function renderWithFrameRateLimit(timestamp = performance.now()) {
      const limit = frameRateLimit;
      if (limit === 0) {
        lastRenderedAt = timestamp;
        renderedFrames += 1;
        return renderBeforeFrameRateLimit();
      }

      const interval = 1000 / limit;
      if (!lastRenderedAt) {
        lastRenderedAt = timestamp;
        renderedFrames += 1;
        return renderBeforeFrameRateLimit();
      }

      const elapsed = timestamp - lastRenderedAt;
      if (elapsed + 0.25 >= interval) {
        // Preserve the target cadence instead of resetting to the display tick;
        // this avoids a 25 FPS cap collapsing to 20 FPS on a 60 Hz display.
        const intervals = Math.max(1, Math.floor((elapsed + 0.25) / interval));
        lastRenderedAt += intervals * interval;
        renderedFrames += 1;
        return renderBeforeFrameRateLimit();
      }

      skippedFrames += 1;
      requestAnimationFrame(render);
    };
    capped.__structureFrameRateLimited = true;
    capped.__uncappedRender = renderBeforeFrameRateLimit;
    render = capped;
  }

  function installWhenRendererReady() {
    const tryInstall = () => {
      if (!window.StructureRenderBatch) {
        setTimeout(tryInstall, 10);
        return;
      }
      installRenderCap();
      installControl();
    };
    tryInstall();
  }

  window.StructureFrameRateLimit = Object.freeze({
    defaultFps: DEFAULT_FPS,
    options: OPTIONS,
    get: () => frameRateLimit,
    set: saveLimit,
    stats: () => ({ limit: frameRateLimit, renderedFrames, skippedFrames }),
    installControl,
  });

  if (document.readyState === 'complete') installWhenRendererReady();
  else window.addEventListener('load', installWhenRendererReady, { once: true });
})();
