// Transient Event playback clock and controls.
// Playback timing is view/runtime configuration only. It never changes canonical
// Entity/Property/Link semantics.

const PLAYBACK_DEFAULTS = Object.freeze({
  event_activation_duration: 0.30,
  effect_travel_duration: 1.20,
  target_effect_duration: 0.30,
  next_event_delay: 0.20,
  branch_delay: 0.10,
  completion_hold: 0.50,
  fade_out_duration: 0.35,
  playback_speed: 1.00,
});

const playbackRuntime = {
  startedAt: 0,
  paused: false,
  pausedAt: 0,
  pausedAccumulatedMs: 0,
  manualAdvanceMs: 0,
  boundaryProvider: null,
};

function playbackNumber(field) {
  if (!ws) return PLAYBACK_DEFAULTS[field];
  const settings = eventSettings();
  const raw = settings[field];
  const value = raw === undefined ? PLAYBACK_DEFAULTS[field] : Number(raw);
  if (!Number.isFinite(value)) throw new Error(`settings.event_playback.${field} must be numeric`);
  if (field === 'playback_speed') {
    if (value <= 0) throw new Error('settings.event_playback.playback_speed must be positive');
  } else if (value < 0) {
    throw new Error(`settings.event_playback.${field} must be non-negative`);
  }
  return value;
}
function playbackTimingMs() {
  return {
    activation: playbackNumber('event_activation_duration') * 1000,
    travel: playbackNumber('effect_travel_duration') * 1000,
    target: playbackNumber('target_effect_duration') * 1000,
    next: playbackNumber('next_event_delay') * 1000,
    branch: playbackNumber('branch_delay') * 1000,
    hold: playbackNumber('completion_hold') * 1000,
    fade: playbackNumber('fade_out_duration') * 1000,
  };
}
function playbackElapsed(now = performance.now()) {
  if (!playbackRuntime.startedAt) return 0;
  const effectiveNow = playbackRuntime.paused ? playbackRuntime.pausedAt : now;
  const wallElapsed = Math.max(0, effectiveNow - playbackRuntime.startedAt - playbackRuntime.pausedAccumulatedMs);
  return wallElapsed * playbackNumber('playback_speed') + playbackRuntime.manualAdvanceMs;
}
function startPlayback(now = performance.now()) {
  playbackRuntime.startedAt = now;
  playbackRuntime.paused = false;
  playbackRuntime.pausedAt = 0;
  playbackRuntime.pausedAccumulatedMs = 0;
  playbackRuntime.manualAdvanceMs = 0;
  syncPlaybackButtons();
}
function resetPlayback() {
  playbackRuntime.startedAt = 0;
  playbackRuntime.paused = false;
  playbackRuntime.pausedAt = 0;
  playbackRuntime.pausedAccumulatedMs = 0;
  playbackRuntime.manualAdvanceMs = 0;
  syncPlaybackButtons();
}
function setPlaybackPaused(paused, now = performance.now()) {
  if (!playbackRuntime.startedAt || playbackRuntime.paused === paused) return;
  if (paused) {
    playbackRuntime.paused = true;
    playbackRuntime.pausedAt = now;
  } else {
    playbackRuntime.pausedAccumulatedMs += Math.max(0, now - playbackRuntime.pausedAt);
    playbackRuntime.paused = false;
    playbackRuntime.pausedAt = 0;
  }
  syncPlaybackButtons();
}
function togglePlaybackPause() { setPlaybackPaused(!playbackRuntime.paused); }
function normalizePlaybackBoundaries(values) {
  return [...new Set((values ?? []).filter(value => Number.isFinite(value) && value >= 0).map(value => Math.round(value * 1000) / 1000))].sort((a, b) => a - b);
}
function stepPlayback() {
  if (!playbackRuntime.startedAt) return;
  if (!playbackRuntime.paused) setPlaybackPaused(true);
  const current = playbackElapsed();
  const boundaries = normalizePlaybackBoundaries(playbackRuntime.boundaryProvider?.() ?? []);
  const next = boundaries.find(value => value > current + 0.5);
  if (next === undefined) return;
  playbackRuntime.manualAdvanceMs += next - current;
  syncPlaybackButtons();
}
function setPlaybackBoundaryProvider(provider) {
  if (provider !== null && typeof provider !== 'function') throw new Error('playback boundary provider must be a function or null');
  playbackRuntime.boundaryProvider = provider;
}

function installPlaybackControls() {
  const right = document.querySelector('#rightControls');
  if (!right || document.querySelector('#playbackPause')) return;
  const group = document.createElement('details');
  group.className = 'right-control-group';
  group.open = true;
  const summary = document.createElement('summary');
  summary.textContent = 'PLAYBACK';
  const body = document.createElement('div');
  body.className = 'right-control-body';
  const pause = document.createElement('button');
  pause.id = 'playbackPause';
  pause.type = 'button';
  pause.textContent = 'PAUSE';
  const step = document.createElement('button');
  step.id = 'playbackStep';
  step.type = 'button';
  step.textContent = 'STEP';
  body.append(pause, step);
  group.append(summary, body);
  const reset = document.querySelector('#resetEvents');
  right.insertBefore(group, reset ?? null);
  pause.addEventListener('click', togglePlaybackPause);
  step.addEventListener('click', stepPlayback);
}
function syncPlaybackButtons() {
  const pause = document.querySelector('#playbackPause');
  const step = document.querySelector('#playbackStep');
  if (!pause || !step) return;
  pause.textContent = playbackRuntime.paused ? 'RESUME' : 'PAUSE';
  pause.disabled = !playbackRuntime.startedAt;
  step.disabled = !playbackRuntime.startedAt;
  pause.classList.toggle('active', playbackRuntime.paused);
}

function installPlaybackTimingControls() {
  const settingsPanel = document.querySelector('#settings');
  if (!settingsPanel || document.querySelector('#eventActivationDuration')) return;
  const fields = [
    ['event_activation_duration', 'eventActivationDuration', 'Event activation (s)'],
    ['target_effect_duration', 'targetEffectDuration', 'Target effect (s)'],
    ['next_event_delay', 'nextEventDelay', 'Next Event delay (s)'],
    ['branch_delay', 'branchDelay', 'Branch delay (s)'],
    ['completion_hold', 'completionHold', 'Completion hold (s)'],
    ['fade_out_duration', 'fadeOutDuration', 'Fade out (s)'],
    ['playback_speed', 'playbackSpeed', 'Playback speed'],
  ];
  for (const [field, id, label] of fields) {
    const wrapper = document.createElement('label');
    wrapper.textContent = `${label} `;
    const input = document.createElement('input');
    input.id = id;
    input.type = 'number';
    input.min = field === 'playback_speed' ? '0.05' : '0';
    input.step = '0.05';
    input.value = String(PLAYBACK_DEFAULTS[field]);
    input.addEventListener('change', () => {
      if (!ws) return;
      const value = Number(input.value);
      if (!Number.isFinite(value) || (field === 'playback_speed' ? value <= 0 : value < 0)) {
        input.value = String(playbackNumber(field));
        return;
      }
      eventSettings()[field] = value;
    });
    wrapper.appendChild(input);
    settingsPanel.appendChild(wrapper);
  }
  const existingActive = document.querySelector('#activeLinkSpeed');
  if (existingActive) existingActive.closest('label').firstChild.textContent = 'Active flow speed ';
}
function syncPlaybackTimingControls() {
  if (!ws) return;
  const fields = {
    eventActivationDuration: 'event_activation_duration',
    targetEffectDuration: 'target_effect_duration',
    nextEventDelay: 'next_event_delay',
    branchDelay: 'branch_delay',
    completionHold: 'completion_hold',
    fadeOutDuration: 'fade_out_duration',
    playbackSpeed: 'playback_speed',
  };
  for (const [id, field] of Object.entries(fields)) {
    const input = document.querySelector(`#${id}`);
    if (input) input.value = String(playbackNumber(field));
  }
}

window.StructurePlayback = Object.freeze({
  state: playbackRuntime,
  defaults: PLAYBACK_DEFAULTS,
  elapsed: playbackElapsed,
  timingMs: playbackTimingMs,
  start: startPlayback,
  reset: resetPlayback,
  pause: setPlaybackPaused,
  togglePause: togglePlaybackPause,
  step: stepPlayback,
  setBoundaryProvider: setPlaybackBoundaryProvider,
  syncControls: syncPlaybackTimingControls,
});

// Extend the existing canonical settings sync rather than creating a second
// workspace/settings lifecycle.
const syncSettingsBeforePlayback = syncSettings;
syncSettings = function syncSettingsWithPlayback() {
  syncSettingsBeforePlayback();
  syncPlaybackTimingControls();
  syncPlaybackButtons();
};

window.addEventListener('load', () => {
  installPlaybackControls();
  installPlaybackTimingControls();
  syncPlaybackTimingControls();
  syncPlaybackButtons();
});
