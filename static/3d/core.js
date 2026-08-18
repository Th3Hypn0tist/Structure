// Structure-independent 3D authoring foundation.
// This layer owns runtime scene mechanics only. It must not know CW/workspace semantics.
(() => {
  if (globalThis.S3D) throw new Error('S3D already initialized');

  const S3D = { version: '0.1.0' };

  class Scene {
    constructor() {
      this.objects = new Map();
      this.layers = [];
    }
    add(object) {
      if (!object || typeof object.id !== 'string' || !object.id) throw new Error('Scene object requires a non-empty id');
      if (this.objects.has(object.id)) throw new Error(`Scene object already exists: ${object.id}`);
      this.objects.set(object.id, object);
      object.scene = this;
      return object;
    }
    remove(ref) {
      const id = typeof ref === 'string' ? ref : ref?.id;
      if (!id) throw new Error('Scene.remove requires an object or id');
      const object = this.objects.get(id);
      if (!object) return null;
      this.objects.delete(id);
      if (object.scene === this) object.scene = null;
      return object;
    }
    get(id) { return this.objects.get(id) ?? null; }
    clear() {
      for (const object of this.objects.values()) if (object.scene === this) object.scene = null;
      this.objects.clear();
    }
    addLayer(layer) {
      if (typeof layer !== 'function') throw new Error('Scene layer must be a function');
      this.layers.push(layer);
      return () => { this.layers = this.layers.filter(item => item !== layer); };
    }
    update(deltaSeconds, now = performance.now()) {
      for (const object of this.objects.values()) object.update?.(deltaSeconds, now);
    }
    draw(renderer, context = {}) {
      for (const object of this.objects.values()) if (object.visible !== false) object.draw?.(renderer, context);
      for (const layer of this.layers) layer(renderer, context);
    }
  }

  class Selection {
    constructor() { this.refs = new Set(); }
    get size() { return this.refs.size; }
    has(ref) { return this.refs.has(typeof ref === 'string' ? ref : ref?.id); }
    set(refs) {
      this.refs = new Set((refs ?? []).map(ref => typeof ref === 'string' ? ref : ref?.id).filter(Boolean));
      return this;
    }
    add(ref) {
      const id = typeof ref === 'string' ? ref : ref?.id;
      if (!id) throw new Error('Selection.add requires an object or id');
      this.refs.add(id);
      return this;
    }
    delete(ref) { return this.refs.delete(typeof ref === 'string' ? ref : ref?.id); }
    toggle(refs) {
      const values = Array.isArray(refs) ? refs : [refs];
      for (const ref of values) {
        const id = typeof ref === 'string' ? ref : ref?.id;
        if (!id) throw new Error('Selection.toggle requires objects or ids');
        if (this.refs.has(id)) this.refs.delete(id); else this.refs.add(id);
      }
      return this;
    }
    clear() { this.refs.clear(); }
    values() { return [...this.refs]; }
  }

  function normalizeBoundaries(values) {
    return [...new Set((values ?? [])
      .filter(value => Number.isFinite(value) && value >= 0)
      .map(value => Math.round(value * 1000) / 1000))]
      .sort((a, b) => a - b);
  }

  class Playback {
    constructor({ speed = () => 1 } = {}) {
      if (typeof speed !== 'function') throw new Error('Playback speed provider must be a function');
      this.speed = speed;
      this.state = {
        startedAt: 0,
        paused: false,
        pausedAt: 0,
        pausedAccumulatedMs: 0,
        manualAdvanceMs: 0,
        boundaryProvider: null,
      };
    }
    playbackSpeed() {
      const value = Number(this.speed());
      if (!Number.isFinite(value) || value <= 0) throw new Error('Playback speed must be positive');
      return value;
    }
    start(now = performance.now()) {
      Object.assign(this.state, { startedAt: now, paused: false, pausedAt: 0, pausedAccumulatedMs: 0, manualAdvanceMs: 0 });
      return this;
    }
    reset() {
      Object.assign(this.state, { startedAt: 0, paused: false, pausedAt: 0, pausedAccumulatedMs: 0, manualAdvanceMs: 0 });
      return this;
    }
    elapsed(now = performance.now()) {
      if (!this.state.startedAt) return 0;
      const effectiveNow = this.state.paused ? this.state.pausedAt : now;
      const wallElapsed = Math.max(0, effectiveNow - this.state.startedAt - this.state.pausedAccumulatedMs);
      return wallElapsed * this.playbackSpeed() + this.state.manualAdvanceMs;
    }
    pause(paused, now = performance.now()) {
      if (!this.state.startedAt || this.state.paused === paused) return this;
      if (paused) {
        this.state.paused = true;
        this.state.pausedAt = now;
      } else {
        this.state.pausedAccumulatedMs += Math.max(0, now - this.state.pausedAt);
        this.state.paused = false;
        this.state.pausedAt = 0;
      }
      return this;
    }
    togglePause(now = performance.now()) { return this.pause(!this.state.paused, now); }
    setBoundaryProvider(provider) {
      if (provider !== null && typeof provider !== 'function') throw new Error('Playback boundary provider must be a function or null');
      this.state.boundaryProvider = provider;
      return this;
    }
    boundaries() { return normalizeBoundaries(this.state.boundaryProvider?.() ?? []); }
    step(now = performance.now(), epsilon = 0.5) {
      if (!this.state.startedAt) return null;
      if (!this.state.paused) this.pause(true, now);
      const current = this.elapsed(now);
      const next = this.boundaries().find(value => value > current + epsilon);
      if (next === undefined) return null;
      this.state.manualAdvanceMs += next - current;
      return next;
    }
  }

  S3D.Scene = Scene;
  S3D.Selection = Selection;
  S3D.Playback = Playback;
  S3D.normalizePlaybackBoundaries = normalizeBoundaries;
  globalThis.S3D = S3D;
})();
