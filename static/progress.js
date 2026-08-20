// Reusable Structure task/progress overlay.
// Runtime/view chrome only: never part of canonical CW semantics.
(() => {
  let root = null;
  let title = null;
  let detail = null;
  let bar = null;
  let percent = null;
  let active = false;
  let hideTimer = 0;

  function ensureUi() {
    if (root) return root;
    root = document.createElement('div');
    root.id = 'structureProgress';
    root.hidden = true;
    root.setAttribute('role', 'status');
    root.setAttribute('aria-live', 'polite');
    Object.assign(root.style, {
      position: 'fixed',
      left: '50%',
      top: '50%',
      transform: 'translate(-50%, -50%)',
      zIndex: '20000',
      width: 'min(460px, calc(100vw - 40px))',
      padding: '14px 16px',
      border: '1px solid rgba(100, 140, 190, .58)',
      borderRadius: '8px',
      background: 'rgba(7, 10, 16, .94)',
      boxShadow: '0 16px 50px rgba(0,0,0,.48)',
      color: '#e8f1ff',
      font: '13px/1.35 system-ui, sans-serif',
      pointerEvents: 'none',
    });

    title = document.createElement('div');
    Object.assign(title.style, { fontWeight: '700', marginBottom: '7px' });

    detail = document.createElement('div');
    Object.assign(detail.style, { opacity: '.78', marginBottom: '9px', minHeight: '1.35em' });

    const row = document.createElement('div');
    Object.assign(row.style, { display: 'grid', gridTemplateColumns: '1fr auto', gap: '10px', alignItems: 'center' });

    bar = document.createElement('progress');
    bar.max = 1;
    Object.assign(bar.style, { width: '100%', height: '12px' });

    percent = document.createElement('span');
    Object.assign(percent.style, { minWidth: '3.6em', textAlign: 'right', fontVariantNumeric: 'tabular-nums' });

    row.append(bar, percent);
    root.append(title, detail, row);
    document.body.appendChild(root);
    return root;
  }

  function clamp(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return null;
    return Math.max(0, Math.min(1, number));
  }

  function begin(label = 'Working…', options = {}) {
    ensureUi();
    clearTimeout(hideTimer);
    hideTimer = 0;
    active = true;
    root.hidden = false;
    title.textContent = String(label);
    detail.textContent = String(options.detail ?? '');
    if (options.indeterminate || options.value === undefined) {
      bar.removeAttribute('value');
      percent.textContent = '';
    } else {
      const value = clamp(options.value) ?? 0;
      bar.value = value;
      percent.textContent = `${Math.round(value * 100)}%`;
    }
    return snapshot();
  }

  function update(value, message = null) {
    ensureUi();
    if (!active) begin('Working…', { value: 0 });
    const normalized = clamp(value);
    if (normalized === null) {
      bar.removeAttribute('value');
      percent.textContent = '';
    } else {
      bar.value = normalized;
      percent.textContent = `${Math.round(normalized * 100)}%`;
    }
    if (message !== null) detail.textContent = String(message);
    return snapshot();
  }

  function indeterminate(message = null) {
    ensureUi();
    if (!active) begin('Working…', { indeterminate: true });
    bar.removeAttribute('value');
    percent.textContent = '';
    if (message !== null) detail.textContent = String(message);
    return snapshot();
  }

  function finish(message = 'Ready', delayMs = 260) {
    ensureUi();
    active = false;
    bar.value = 1;
    percent.textContent = '100%';
    if (message) detail.textContent = String(message);
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      root.hidden = true;
      hideTimer = 0;
    }, Math.max(0, Number(delayMs) || 0));
  }

  function fail(error) {
    ensureUi();
    active = false;
    bar.removeAttribute('value');
    percent.textContent = '';
    title.textContent = 'Operation failed';
    detail.textContent = error instanceof Error ? error.message : String(error);
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => { root.hidden = true; hideTimer = 0; }, 2200);
  }

  function paint() {
    return new Promise(resolve => requestAnimationFrame(() => resolve()));
  }

  function snapshot() {
    return Object.freeze({
      active,
      title: title?.textContent ?? '',
      detail: detail?.textContent ?? '',
      value: bar?.hasAttribute('value') ? Number(bar.value) : null,
    });
  }

  window.StructureProgress = Object.freeze({
    begin,
    update,
    indeterminate,
    finish,
    fail,
    paint,
    snapshot,
  });
})();
