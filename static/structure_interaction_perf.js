// High-density interaction path for Structure.
// Keep rendering GPU-resident while avoiding dense-scene full scans on passive
// hover, Entity selection and Event Rule summaries. Canonical semantics stay
// unchanged; this module only replaces lookup strategy.
(() => {
  if (typeof pickEntity !== 'function' || typeof entityScreenBounds !== 'function') {
    throw new Error('Structure interaction primitives must load before structure_interaction_perf');
  }

  const legacyPickEntity = pickEntity;
  const legacyMouseMove = window.onmousemove;
  const stats = {
    picks: 0,
    broadPhaseEntities: 0,
    exactCandidates: 0,
    hoverPicks: 0,
    hoverEventsCoalesced: 0,
    entitySceneTargetScansSkipped: 0,
    eventRuleLinkIndexBuilds: 0,
  };

  function densePickEntity(clientX, clientY) {
    if (!ws) return null;
    const density = devicePixelRatio || 1;
    const x = clientX * density;
    const y = clientY * density;
    const vp = viewProjection();
    const visible = visibleEntityIds();
    const workspace = assertWorkspace();
    const camera = workspace.camera;
    const forward = viewForward();
    const half = nodeHalfSize();
    const broadWorldRadius = Math.sqrt(3) * half;
    const projectionScale = canvas.height / (2 * Math.tan(camera.fov * Math.PI / 360));
    const padding = 5 * density;
    const candidates = [];

    stats.picks += 1;
    stats.broadPhaseEntities = 0;
    stats.exactCandidates = 0;

    // Cheap center/radius broad phase: one projection per visible Entity instead
    // of projecting all eight cube corners. Exact legacy bounds are evaluated
    // only for the small set under the pointer.
    for (const entity of workspace.entities) {
      if (!visible.has(entity.id)) continue;
      stats.broadPhaseEntities += 1;

      const dx = entity.position[0] - camera.position[0];
      const dy = entity.position[1] - camera.position[1];
      const dz = entity.position[2] - camera.position[2];
      const depth = dx * forward[0] + dy * forward[1] + dz * forward[2];
      if (depth <= 1e-6) continue;

      const projected = project(entity.position, vp);
      if (!projected) continue;
      const radius = broadWorldRadius * projectionScale / depth + padding;
      if (Math.abs(projected[0] - x) <= radius && Math.abs(projected[1] - y) <= radius) {
        candidates.push(entity);
      }
    }

    stats.exactCandidates = candidates.length;
    let winner = null;
    let best = Infinity;
    for (const entity of candidates) {
      const bounds = entityScreenBounds(entity, vp);
      if (!bounds) continue;
      if (
        x >= bounds.minX - 4 * density &&
        x <= bounds.maxX + 4 * density &&
        y >= bounds.minY - 4 * density &&
        y <= bounds.maxY + 4 * density &&
        bounds.depth < best
      ) {
        winner = entity;
        best = bounds.depth;
      }
    }
    return winner;
  }

  // Dense scenes use the accelerated picker. Keep the legacy implementation as
  // an explicit fallback for small scenes and for diagnostics.
  pickEntity = function pickEntityAccelerated(clientX, clientY) {
    if (!ws || assertWorkspace().entities.length < 500) return legacyPickEntity(clientX, clientY);
    return densePickEntity(clientX, clientY);
  };

  let pendingHover = null;
  let hoverRaf = 0;

  function flushHoverPick() {
    hoverRaf = 0;
    const point = pendingHover;
    pendingHover = null;
    if (!point || !ws) return;
    hovered = pickEntity(point.clientX, point.clientY)?.id ?? null;
    stats.hoverPicks += 1;
  }

  // Pointer devices can emit mousemove much faster than the display refresh.
  // Passive hover therefore resolves at most once per animation frame using the
  // latest pointer position. Orbit/pan/drag/box-selection retain their original
  // immediate handlers.
  window.onmousemove = event => {
    if (
      ws &&
      event.target === canvas &&
      !orbit &&
      !boxSelection &&
      !pan &&
      !(dragAxis && selected.size)
    ) {
      if (pendingHover) stats.hoverEventsCoalesced += 1;
      pendingHover = { clientX: event.clientX, clientY: event.clientY };
      if (!hoverRaf) hoverRaf = requestAnimationFrame(flushHoverPick);
      return;
    }
    pendingHover = null;
    if (event.target !== canvas) hovered = null;
    return legacyMouseMove?.(event);
  };

  // app.js selects Entities on mousedown. causal_projection.js also listens for
  // the following canvas click to resolve Event/Props world-space targets. On a
  // dense scene that legacy target resolver can scan tens of thousands of rows.
  // If the click is still inside the Entity selected by mousedown, Entity wins
  // and the Event/Props scan is provably unnecessary.
  function selectedEntityUnderPointer(clientX, clientY) {
    if (!ws || selected.size !== 1 || !activeEntityId) return false;
    const entity = assertWorkspace().entities.find(item => item.id === activeEntityId);
    if (!entity) return false;
    const density = devicePixelRatio || 1;
    const bounds = entityScreenBounds(entity, viewProjection());
    if (!bounds) return false;
    const x = clientX * density;
    const y = clientY * density;
    return x >= bounds.minX && x <= bounds.maxX && y >= bounds.minY && y <= bounds.maxY;
  }

  canvas.addEventListener('click', event => {
    if (event.button !== 0 || !selectedEntityUnderPointer(event.clientX, event.clientY)) return;
    stats.entitySceneTargetScansSkipped += 1;
    event.stopImmediatePropagation();
  }, true);

  // Event Rule summaries used to rebuild and rescan the complete canonical link
  // collection separately for every Ruleset. Reuse Structure's frame-local
  // linkProperties() collection and build endpoint indexes once for that source.
  if (typeof eventRuleLinks === 'function' && typeof eventRuleSubjectLinks === 'function' && typeof linkProperties === 'function') {
    let cachedSource = null;
    let cachedRows = null;
    let parentIndex = null;
    let childIndex = null;

    function ensureEventRuleLinkIndexes() {
      const source = linkProperties();
      if (source === cachedSource && cachedRows && parentIndex && childIndex) return;
      cachedSource = source;
      cachedRows = source.map(({ owner, property }) => ({ owner, property, value: property.value }));
      parentIndex = new Map();
      childIndex = new Map();
      for (const entry of cachedRows) {
        const rulesetRef = entry.property.ruleset_ref;
        const parentKey = `${rulesetRef}\u0000${entry.value.parent_ref}`;
        const childKey = `${rulesetRef}\u0000${entry.value.child_ref}`;
        if (!parentIndex.has(parentKey)) parentIndex.set(parentKey, []);
        if (!childIndex.has(childKey)) childIndex.set(childKey, []);
        parentIndex.get(parentKey).push(entry);
        childIndex.get(childKey).push(entry);
      }
      stats.eventRuleLinkIndexBuilds += 1;
    }

    eventRuleLinks = function eventRuleLinksIndexed() {
      ensureEventRuleLinkIndexes();
      return cachedRows;
    };

    eventRuleSubjectLinks = function eventRuleSubjectLinksIndexed(ruleset, role, subjectRef) {
      ensureEventRuleLinkIndexes();
      const endpoint = eventRuleEndpointField(ruleset, role);
      const key = `${ruleset.id}\u0000${subjectRef}`;
      return (endpoint === 'parent_ref' ? parentIndex : childIndex).get(key) ?? [];
    };
  }

  window.StructureInteractionPerf = Object.freeze({
    stats: () => ({ ...stats }),
    legacyPickEntity,
    densePickEntity,
    selectedEntityUnderPointer,
  });
})();
