// Structure high-density benchmark.
// This intentionally uses the normal Structure workspace, Entity/Property/Link,
// projection, camera and causal Event mechanisms. No benchmark renderer exists.
(() => {
  if (!globalThis.S3D?.Benchmark) throw new Error('S3D benchmark metrics must load before Structure benchmark');
  if (!window.StructureRenderPipeline) throw new Error('Structure render pipeline must load before Structure benchmark');

  const BENCH = {
    active: false,
    building: false,
    buildGeneration: 0,
    buildProgress: { phase: 'idle', completed: 0, total: 0, percent: 0 },
    nodeCount: 1000,
    original: null,
    metrics: new S3D.Benchmark.FrameMetrics(300),
    lastDrawCalls: 0,
    lastUploads: 0,
    lastRenderMs: 0,
    frameStartedAt: 0,
    buildMs: 0,
    canonicalLinkCount: 0,
    triggerEventRef: 'EVENT_BENCH_TRIGGER',
    previousMaxDepth: null,
    hiddenCanvases: new Map(),
  };

  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function pad(index) { return String(index + 1).padStart(5, '0'); }
  function property(id, propertyType, rulesetRef, value) {
    return { id, property_type_ref: propertyType, ruleset_ref: rulesetRef, status: 'unlocked', value };
  }
  function typeProperty(id, typeRef) {
    return property(id, 'type', 'RULESET_TYPE', { type_ref: typeRef, properties: {} });
  }
  function dataProperty(id, index) {
    return property(id, 'data', 'RULESET_DATA', {
      data_type_ref: 'benchmark_value',
      properties: { index, role: 'benchmark_payload' },
    });
  }
  function eventProperty(id, index) {
    return property(id, 'event', 'RULESET_EVENT', {
      event_type_ref: 'benchmark_trigger',
      properties: { index },
    });
  }
  function effectProperty(id, index) {
    return property(id, 'effect', 'RULESET_EFFECT', {
      effect_type_ref: 'benchmark_activate',
      properties: { index },
    });
  }
  function linkProperty(id, rulesetRef, linkTypeRef, parentRef, childRef, properties = {}) {
    return property(id, 'link', rulesetRef, {
      link_type_ref: linkTypeRef,
      parent_ref: parentRef,
      child_ref: childRef,
      properties,
    });
  }
  function entity(id, name, position, properties) {
    return { id, name, status: 'unlocked', position, properties };
  }

  function benchmarkNode(index, position) {
    const suffix = pad(index);
    const entityId = `BENCH_NODE_${suffix}`;
    const eventId = `EVENT_BENCH_${suffix}`;
    const effectId = `EFFECT_BENCH_${suffix}`;
    const props = [
      typeProperty(`TYPE_BENCH_${suffix}`, 'benchmark_node'),
      dataProperty(`DATA_BENCH_${suffix}`, index),
      eventProperty(eventId, index),
      effectProperty(effectId, index),
      linkProperty(`LINK_BENCH_EVENT_EFFECT_${suffix}`, 'RULESET_LINK_EVENT_EFFECT', 'event_effect', eventId, effectId),
      linkProperty(`LINK_BENCH_EFFECT_TARGET_${suffix}`, 'RULESET_LINK_EFFECT_TARGET', 'effect_target', effectId, entityId),
    ];
    return { entity: entity(entityId, `Node ${suffix}`, position, props), entityId, eventId, effectId };
  }

  function deterministicParent(layerIndex, childIndex, parentCount, salt = 0) {
    if (!parentCount) throw new Error('benchmark causal layer requires a parent');
    const mixed = Math.imul(childIndex + 1 + salt, 1103515245) + Math.imul(layerIndex + 17, 12345);
    return Math.abs(mixed | 0) % parentCount;
  }

  function progress(phase, completed, total, percent, callback) {
    BENCH.buildProgress = {
      phase,
      completed: Number(completed) || 0,
      total: Number(total) || 0,
      percent: Math.max(0, Math.min(100, Number(percent) || 0)),
    };
    callback?.({ ...BENCH.buildProgress });
  }

  function yieldToBrowser() {
    return new Promise(resolve => requestAnimationFrame(() => resolve()));
  }

  function assertBuildCurrent(generation) {
    if (generation !== BENCH.buildGeneration) throw new Error('benchmark build cancelled');
  }

  async function buildWorkspace(count, callback = null, generation = BENCH.buildGeneration) {
    if (!ws) throw new Error('Structure workspace must be loaded before benchmark');
    const started = performance.now();
    const workspace = clone(ws);
    const positions = S3D.Benchmark.nodePositions(count);
    const side = Math.ceil(Math.cbrt(Math.max(1, count)));
    const nodes = [];
    const layers = Array.from({ length: side }, () => []);
    const entityChunk = 500;
    let minX = Infinity;

    progress('Entities + Props + Events + Effects', 0, count, 0, callback);
    await yieldToBrowser();

    for (let index = 0; index < count; index++) {
      const offset = index * 3;
      const item = benchmarkNode(index, [positions[offset], positions[offset + 1], positions[offset + 2]]);
      nodes.push(item);
      layers[index % side].push(item);
      minX = Math.min(minX, item.entity.position[0]);

      const completed = index + 1;
      if (completed % entityChunk === 0 || completed === count) {
        progress('Entities + Props + Events + Effects', completed, count, (completed / count) * 55, callback);
        await yieldToBrowser();
        assertBuildCurrent(generation);
      }
    }

    const triggerId = 'BENCH_TRIGGER';
    const triggerEffectRef = 'EFFECT_BENCH_TRIGGER';
    const trigger = entity(triggerId, 'TRIGGER', [minX - 5.0, 0, 0], [
      typeProperty('TYPE_BENCH_TRIGGER', 'benchmark_trigger'),
      dataProperty('DATA_BENCH_TRIGGER', -1),
      eventProperty(BENCH.triggerEventRef, -1),
      effectProperty(triggerEffectRef, -1),
      linkProperty('LINK_BENCH_TRIGGER_EVENT_EFFECT', 'RULESET_LINK_EVENT_EFFECT', 'event_effect', BENCH.triggerEventRef, triggerEffectRef),
      linkProperty('LINK_BENCH_TRIGGER_EFFECT_TARGET', 'RULESET_LINK_EFFECT_TARGET', 'effect_target', triggerEffectRef, triggerId),
    ]);

    let linkCount = 2 + count * 2;
    let linkedChildren = 0;
    const linkWorkTotal = Math.max(1, count);
    const linkChunk = 500;
    const firstLayer = layers.find(layer => layer.length) ?? [];

    progress('Canonical Links', 0, linkWorkTotal, 55, callback);
    for (let index = 0; index < firstLayer.length; index++) {
      const child = firstLayer[index];
      trigger.properties.push(linkProperty(
        `LINK_BENCH_TRIGGER_CAUSE_${pad(index)}`,
        'RULESET_LINK_EVENT_CAUSE',
        'event_cause',
        triggerId,
        child.eventId,
        { benchmark_layer: 0 },
      ));
      linkCount += 1;
      linkedChildren += 1;
    }

    for (let layerIndex = 1; layerIndex < layers.length; layerIndex++) {
      const previous = layers[layerIndex - 1];
      const current = layers[layerIndex];
      if (!previous.length || !current.length) continue;
      for (let childIndex = 0; childIndex < current.length; childIndex++) {
        const child = current[childIndex];
        const parentIndex = deterministicParent(layerIndex, childIndex, previous.length);
        const parent = previous[parentIndex];
        parent.entity.properties.push(linkProperty(
          `LINK_BENCH_CAUSE_${layerIndex}_${pad(childIndex)}`,
          'RULESET_LINK_EVENT_CAUSE',
          'event_cause',
          parent.entityId,
          child.eventId,
          { benchmark_layer: layerIndex },
        ));
        parent.entity.properties.push(linkProperty(
          `LINK_BENCH_DEP_${layerIndex}_${pad(childIndex)}`,
          'RULESET_LINK_DEPENDENCY',
          'dependency',
          child.entityId,
          parent.entityId,
          { benchmark_layer: layerIndex },
        ));
        linkCount += 2;

        if (previous.length > 1 && childIndex % 3 === 0) {
          const extraIndex = deterministicParent(layerIndex, childIndex, previous.length, 97);
          if (extraIndex !== parentIndex) {
            const extra = previous[extraIndex];
            extra.entity.properties.push(linkProperty(
              `LINK_BENCH_CAUSE_EXTRA_${layerIndex}_${pad(childIndex)}`,
              'RULESET_LINK_EVENT_CAUSE',
              'event_cause',
              extra.entityId,
              child.eventId,
              { benchmark_layer: layerIndex, branch: 'extra' },
            ));
            linkCount += 1;
          }
        }

        linkedChildren += 1;
        if (linkedChildren % linkChunk === 0 || linkedChildren >= count) {
          const ratio = Math.min(1, linkedChildren / linkWorkTotal);
          progress('Canonical Links', Math.min(linkedChildren, linkWorkTotal), linkWorkTotal, 55 + ratio * 40, callback);
          await yieldToBrowser();
          assertBuildCurrent(generation);
        }
      }
    }

    progress('Finalize workspace', count, count, 96, callback);
    await yieldToBrowser();
    assertBuildCurrent(generation);

    workspace.entities = [trigger, ...nodes.map(item => item.entity)];
    workspace.settings.view_defaults.ruleset_ref = 'ALL';
    workspace.settings.view_defaults.hidden_link_types = {};
    workspace.settings.view_defaults.event_routes_visible = true;
    workspace.settings.view_defaults.show_all_props = true;
    workspace.settings.view_defaults.property_panel_collapsed = {};
    workspace.settings.view_defaults.node_master_size = .70;
    workspace.settings.view_defaults.property_panel_size = .60;
    workspace.settings.camera_defaults.far_clip = Math.max(1000, side * 12);
    Object.assign(workspace.settings.event_playback, {
      event_activation_duration: .025,
      effect_travel_duration: .040,
      target_effect_duration: .020,
      next_event_delay: .005,
      branch_delay: 0,
      completion_hold: .180,
      fade_out_duration: .140,
      playback_speed: 1,
      active_link_speed: 2,
    });

    BENCH.buildMs = performance.now() - started;
    BENCH.canonicalLinkCount = linkCount;
    progress('Ready', count, count, 100, callback);
    return { workspace, side };
  }

  function suspendOtherCanvases() {
    BENCH.hiddenCanvases.clear();
    const scene = document.querySelector('#scene');
    for (const canvas of document.querySelectorAll('canvas')) {
      if (canvas === scene) continue;
      BENCH.hiddenCanvases.set(canvas, canvas.hidden);
      canvas.hidden = true;
    }
  }
  function restoreOtherCanvases() {
    for (const [canvas, hidden] of BENCH.hiddenCanvases) canvas.hidden = hidden;
    BENCH.hiddenCanvases.clear();
  }

  function resetRuntime() {
    selected.clear();
    activeEntityId = null;
    lookAtEntityId = null;
    hovered = null;
    linkSource = null;
    linkTarget = null;
    if (typeof clearCausalProjection === 'function') clearCausalProjection();
    if (window.StructureSceneProjection?.reset) window.StructureSceneProjection.reset();
  }

  function syncUi(label) {
    syncCatalog();
    syncSettings();
    renderProjectionControls();
    syncEventRouteVisibility();
    inspect();
    updateButtons();
    status(label);
  }

  async function activate(count = BENCH.nodeCount, progressCallback = null) {
    if (BENCH.active) deactivate();
    if (!Number.isInteger(count) || count < 100 || count > 20000) throw new Error('Structure benchmark node count must be 100..20000');
    BENCH.nodeCount = count;
    const generation = ++BENCH.buildGeneration;
    BENCH.building = true;
    BENCH.original = {
      workspace: ws,
      selected: [...selected],
      activeEntityId,
      lookAtEntityId,
      hovered,
      maxDepth: typeof causalProjection !== 'undefined' ? causalProjection.maxDepth : null,
    };

    try {
      const built = await buildWorkspace(count, progressCallback, generation);
      assertBuildCurrent(generation);
      BENCH.active = true;
      BENCH.metrics = new S3D.Benchmark.FrameMetrics(300);
      BENCH.previousMaxDepth = BENCH.original.maxDepth;
      ws = built.workspace;
      resetRuntime();
      if (typeof causalProjection !== 'undefined') causalProjection.maxDepth = built.side * 3 + 8;
      suspendOtherCanvases();
      syncUi(`benchmark ${count.toLocaleString()} Structure nodes · click TRIGGER Event`);
      fitWorkspaceToView();
      window.StructureRenderBatch?.invalidate?.('benchmark_workspace_built');
      return built.workspace;
    } finally {
      if (generation === BENCH.buildGeneration) BENCH.building = false;
    }
  }

  function deactivate() {
    if (BENCH.building) {
      BENCH.buildGeneration += 1;
      BENCH.building = false;
      BENCH.buildProgress = { phase: 'cancelled', completed: 0, total: 0, percent: 0 };
    }
    if (!BENCH.active) {
      BENCH.original = null;
      return;
    }
    resetRuntime();
    restoreOtherCanvases();
    const previous = BENCH.original;
    ws = previous.workspace;
    selected.clear();
    for (const id of previous.selected) selected.add(id);
    activeEntityId = previous.activeEntityId;
    lookAtEntityId = previous.lookAtEntityId;
    hovered = previous.hovered;
    if (typeof causalProjection !== 'undefined' && previous.maxDepth !== null) causalProjection.maxDepth = previous.maxDepth;
    BENCH.active = false;
    BENCH.original = null;
    window.StructureRenderBatch?.invalidate?.('benchmark_stopped');
    syncUi('benchmark stopped · workspace restored');
  }

  function setNodeCount(count) {
    const normalized = Math.max(100, Math.min(20000, Math.round(Number(count) / 100) * 100));
    BENCH.nodeCount = normalized;
    return normalized;
  }

  function fire() {
    if (!BENCH.active || BENCH.building) throw new Error('Structure benchmark is not ready');
    triggerCausalProjection(BENCH.triggerEventRef);
  }

  function patchGlCounters() {
    const proto = globalThis.WebGL2RenderingContext?.prototype;
    if (!proto || proto.__structureBenchmarkCounters) return;
    Object.defineProperty(proto, '__structureBenchmarkCounters', { value: true });
    for (const name of ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced']) {
      const base = proto[name];
      if (typeof base !== 'function') continue;
      proto[name] = function benchmarkCountedDraw(...args) {
        if (BENCH.active) BENCH.lastDrawCalls += 1;
        return base.apply(this, args);
      };
    }
    for (const name of ['bufferData', 'bufferSubData']) {
      const base = proto[name];
      if (typeof base !== 'function') continue;
      proto[name] = function benchmarkCountedUpload(...args) {
        if (BENCH.active) BENCH.lastUploads += 1;
        return base.apply(this, args);
      };
    }
  }

  function installRenderMetrics() {
    if (globalThis.__structureBenchmarkRenderMetricsInstalled) return;
    patchGlCounters();
    window.StructureRenderPipeline.addBeforeFrame('benchmark-metrics-start', () => {
      if (!BENCH.active) return;
      BENCH.lastDrawCalls = 0;
      BENCH.lastUploads = 0;
      BENCH.frameStartedAt = performance.now();
    }, -1000);
    window.StructureRenderPipeline.addAfterFrame('benchmark-metrics-end', () => {
      if (!BENCH.active || !BENCH.frameStartedAt) return;
      const ended = performance.now();
      BENCH.lastRenderMs = ended - BENCH.frameStartedAt;
      BENCH.metrics.push(ended);
      BENCH.frameStartedAt = 0;
    }, 1000);
    globalThis.__structureBenchmarkRenderMetricsInstalled = true;
  }

  function metricsSnapshot() {
    const frame = BENCH.metrics.snapshot();
    return {
      ...frame,
      render_ms: BENCH.lastRenderMs,
      draw_calls: BENCH.lastDrawCalls,
      uploads: BENCH.lastUploads,
      build_ms: BENCH.buildMs,
      building: BENCH.building,
      build_progress: { ...BENCH.buildProgress },
      entities: BENCH.active ? assertWorkspace().entities.length : 0,
      nodes: BENCH.nodeCount,
      links: BENCH.canonicalLinkCount,
      traces: typeof causalProjection !== 'undefined' ? causalProjection.currentEvents.length : 0,
    };
  }

  installRenderMetrics();
  window.StructureBenchmark = Object.freeze({
    state: BENCH,
    activate,
    deactivate,
    setNodeCount,
    fire,
    metricsSnapshot,
  });
})();
