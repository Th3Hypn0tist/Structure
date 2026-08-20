// Structure frame-rate setting.
// The render pipeline owns scheduling; this module only owns the Settings control
// and persisted local preference. It never wraps or replaces global render().
(() => {
  if (!window.StructureRenderPipeline) throw new Error('Structure render pipeline must load before frame-rate settings');

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

  function syncControl() {
    const select = document.querySelector('#frameRateLimit');
    if (select) select.value = String(frameRateLimit);
  }

  function saveLimit(value) {
    frameRateLimit = normalize(value);
    window.StructureRenderPipeline.setFpsLimit(frameRateLimit);
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

  window.StructureRenderPipeline.setFpsLimit(frameRateLimit);

  window.StructureFrameRateLimit = Object.freeze({
    defaultFps: DEFAULT_FPS,
    options: OPTIONS,
    get: () => frameRateLimit,
    set: saveLimit,
    stats: () => ({ limit: frameRateLimit, ...window.StructureRenderPipeline.stats() }),
    installControl,
  });

  if (document.readyState === 'loading') window.addEventListener('load', installControl, { once: true });
  else installControl();
})();
