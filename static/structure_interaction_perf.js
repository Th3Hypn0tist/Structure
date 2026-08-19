// High-density interaction path for Structure.
// Keep rendering GPU-resident while avoiding the legacy O(N * 8 projections)
// hover path on dense scenes. Structure semantics stay unchanged: this module
// only accelerates candidate picking and throttles passive hover work.
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

  window.StructureInteractionPerf = Object.freeze({
    stats: () => ({ ...stats }),
    legacyPickEntity,
    densePickEntity,
  });
})();
