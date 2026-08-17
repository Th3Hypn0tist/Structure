// Scene projection: every represented object in the view is a world-space 3D
// instance. DOM is not used for Entity, Event, Property or causal-route
// representation.
//
// Locked Entity-local layout:
//   Dependency OUT above
//   Event list left of Entity
//   Props list directly below Entity
//   Event IN left of Props, Event OUT right of Props, same Y as Props center
//   Dependency IN below Props
//
// Link animation contract:
//   - canonical links define causality; animation never invents a route
//   - event routes retain slow baseline direction flow at all times
//   - firing an Event creates a transient trace in currentEvents[]
//   - source Entity/Event activates in that trace's color
//   - the same link receives a growing travel segment + small head point
//   - Effects/targets activate only when the canonical trace reaches them
//   - downstream Events continue the same canonical trace
//   - concurrent traces use distinct stable colors
//   - completed traces hold briefly, fade, disappear; baseline links remain

const CAUSAL_LINK_TYPES = new Set([
  'event_read', 'event_input', 'event_output', 'event_effect',
  'event_cause', 'event_condition', 'effect_target',
]);
const EVENT_TRACE_COLORS = Object.freeze([
  [.98, .34, .20],
  [.20, .66, 1.00],
  [.80, .38, 1.00],
  [.18, .88, .58],
  [1.00, .70, .18],
  [.22, .88, .92],
]);

const causalProjection = {
  rootEventRef: null,
  maxDepth: 8,
  graph: null,
  playbackStartedAt: 0,
  eventHitTargets: [],
  propertyHitTargets: [],
  routePhases: new Map(),
  currentEvents: [],
  nextTraceId: 1,
};
window.StructureSceneProjection = Object.freeze({
  state: causalProjection,
  reset: () => clearCausalProjection(),
});
window.StructureCausalProjection = Object.freeze({
  state: causalProjection,
  surface: { style: { display: '' } },
});

function playbackApi() {
  const api = window.StructurePlayback;
  if (!api) throw new Error('StructurePlayback runtime contract missing');
  return api;
}
function propertyPanelSettings() { return viewSettings(); }
function propertyPanelCollapsed(ownerId) {
  return propertyPanelSettings().show_all_props ? false : Boolean(propertyPanelSettings().property_panel_collapsed[ownerId]);
}
function setPropertyPanelCollapsed(ownerId, collapsed) {
  const states = propertyPanelSettings().property_panel_collapsed;
  if (collapsed) states[ownerId] = true;
  else delete states[ownerId];
}
function bindPropertyPanelControls() {
  $('#propertyPanelSize').addEventListener('input', event => {
    propertyPanelSettings().property_panel_size = Number(event.target.value);
    syncPropertyPanelControls();
  });
  $('#showAllProps').addEventListener('click', () => {
    propertyPanelSettings().show_all_props = !propertyPanelSettings().show_all_props;
    syncPropertyPanelControls();
  });
}
function syncPropertyPanelControls() {
  if (!ws) return;
  const settings = propertyPanelSettings();
  $('#propertyPanelSize').value = String(settings.property_panel_size);
  $('#propertyPanelSizeValue').textContent = `${Number(settings.property_panel_size).toFixed(2)}×`;
  $('#showAllProps').classList.toggle('active', settings.show_all_props);
  $('#showAllProps').setAttribute('aria-pressed', settings.show_all_props ? 'true' : 'false');
}

function canonicalLinks() {
  return assertWorkspace().entities.flatMap(owner => owner.properties
    .filter(property => property.property_type_ref === 'link')
    .map(property => ({ owner, property, value: property.value })));
}
function causalOutgoing(ref, index) {
  const current = index.get(ref);
  if (!current) throw new Error(`causal ref unresolved: ${ref}`);
  const type = current.kind === 'entity' ? 'entity' : current.propertyType;
  const allowed = type === 'event'
    ? new Set(['event_effect', 'event_output'])
    : type === 'effect'
      ? new Set(['effect_target'])
      : new Set(['event_condition', 'event_input', 'event_read', 'event_cause']);
  return canonicalLinks().filter(({ value }) => value.parent_ref === ref && allowed.has(value.link_type_ref));
}
function buildCausalGraph(rootRef, maxDepth = 8) {
  const index = canonicalIndex();
  const root = index.get(rootRef);
  if (!root || root.propertyType !== 'event') throw new Error(`causal root must be Event: ${rootRef}`);
  const nodes = new Map([[rootRef, { ref: rootRef, depth: 0 }]]);
  const edges = [];
  const seenEdges = new Set();
  const queue = [{ ref: rootRef, depth: 0, path: new Set([rootRef]) }];
  while (queue.length) {
    const current = queue.shift();
    if (current.depth >= maxDepth) continue;
    for (const { property, value } of causalOutgoing(current.ref, index)) {
      const targetRef = value.child_ref;
      if (!index.has(targetRef)) throw new Error(`causal target unresolved: ${targetRef}`);
      const edgeKey = `${property.id}:${current.ref}:${targetRef}`;
      if (seenEdges.has(edgeKey)) continue;
      seenEdges.add(edgeKey);
      const cycle = current.path.has(targetRef);
      const nextDepth = current.depth + 1;
      edges.push({ id: property.id, from: current.ref, to: targetRef, linkType: value.link_type_ref, depth: nextDepth, cycle });
      const existing = nodes.get(targetRef);
      if (!existing || nextDepth < existing.depth) nodes.set(targetRef, { ref: targetRef, depth: nextDepth });
      if (!cycle) {
        const path = new Set(current.path);
        path.add(targetRef);
        queue.push({ ref: targetRef, depth: nextDepth, path });
      }
    }
  }
  return { rootRef, index, nodes: [...nodes.values()], edges };
}
function displayName(item) {
  return item.kind === 'entity' ? item.owner.name : propertyDisplayName(item.object, item.owner);
}

function propertyGroups(index) {
  const groups = new Map();
  for (const item of index.values()) {
    if (item.kind !== 'property' || ['link', 'event'].includes(item.propertyType)) continue;
    if (!groups.has(item.owner.id)) groups.set(item.owner.id, []);
    groups.get(item.owner.id).push({ ref: item.ref, item });
  }
  const order = { effect: 0, data: 1, function: 2, type: 3, mount: 4 };
  for (const items of groups.values()) {
    items.sort((a, b) => {
      const delta = (order[a.item.propertyType] ?? 100) - (order[b.item.propertyType] ?? 100);
      return delta || displayName(a.item).localeCompare(displayName(b.item));
    });
  }
  return groups;
}

const SCENE_COLORS = Object.freeze({
  event: [.42, .25, .09],
  propsFrame: [.36, .42, .52],
  effect: [.48, .16, .13],
  data: [.08, .29, .43],
  function: [.30, .20, .42],
  type: [.28, .32, .38],
  mount: [.16, .34, .24],
  generic: [.24, .28, .34],
  outline: [.50, .58, .70],
  causal: [.30, .12, .10],
  causalFlow: [.66, .24, .18],
});

function eventListLayout(entity) {
  const size = nodeMasterSize();
  const half = nodeHalfSize();
  const gap = .20 * size;
  const width = 1.52 * size;
  const rowHeight = .28 * size;
  const rowGap = .07 * size;
  const depth = .085 * size;
  const events = entity.properties.filter(property => property.property_type_ref === 'event');
  const totalHeight = events.length ? events.length * rowHeight + Math.max(0, events.length - 1) * rowGap : 0;
  const top = entity.position[1] + totalHeight / 2;
  const rightEdge = entity.position[0] - half - gap;
  const rows = events.map((property, index) => ({
    ref: property.id,
    property,
    center: [rightEdge - width / 2, top - rowHeight / 2 - index * (rowHeight + rowGap), entity.position[2]],
    halfScale: [width / 2, rowHeight / 2, depth],
    width,
    height: rowHeight,
  }));
  return { entity, rows, rightEdge };
}

function propsListLayout(entity, items) {
  if (!items.length) return null;
  const master = nodeMasterSize();
  const scale = propertyPanelSettings().property_panel_size;
  const half = nodeHalfSize();
  const gap = .20 * master;
  const depth = .075 * master * scale;
  const topEdge = entity.position[1] - half - gap;
  const width = 1.62 * master * scale;
  const rowHeight = .25 * master * scale;
  const rowGap = .055 * master * scale;
  const padding = .10 * master * scale;
  const rowsHeight = items.length * rowHeight + Math.max(0, items.length - 1) * rowGap;
  const expandedHeight = rowsHeight + padding * 2;
  const attachmentCenter = [entity.position[0], topEdge - expandedHeight / 2, entity.position[2]];
  const collapsed = propertyPanelCollapsed(entity.id);

  if (collapsed) {
    const buttonSize = .24 * master * scale;
    const center = [entity.position[0] + half - buttonSize / 2, topEdge - buttonSize / 2, entity.position[2]];
    return {
      entity, collapsed, center,
      frameScale: [buttonSize / 2, buttonSize / 2, depth],
      rows: [], width: buttonSize, height: buttonSize, toggleCenter: center,
      attachmentCenter, attachmentWidth: width, attachmentHeight: expandedHeight,
    };
  }

  const center = attachmentCenter;
  const top = topEdge - padding;
  const rows = items.map(({ ref, item }, index) => ({
    ref, item,
    center: [center[0], top - rowHeight / 2 - index * (rowHeight + rowGap), center[2]],
    halfScale: [width * .47, rowHeight * .42, depth * 1.35],
    width: width * .94,
    height: rowHeight * .84,
  }));
  const toggleSize = .18 * master * scale;
  const toggleCenter = [center[0] + width / 2 - padding - toggleSize / 2, topEdge - padding - toggleSize / 2, center[2] + depth + .012];
  return {
    entity, collapsed, center,
    frameScale: [width / 2, expandedHeight / 2, depth],
    rows, width, height: expandedHeight, toggleCenter, toggleSize,
    attachmentCenter, attachmentWidth: width, attachmentHeight: expandedHeight,
  };
}

function eventIoLayout(entity, eventLayout, propsLayout) {
  if (!eventLayout.rows.length) return null;
  const master = nodeMasterSize();
  const gap = .20 * master;
  const nodeHalf = nodeHalfSize();
  const pointHalf = nodeHalf * .10;
  const propsCenter = propsLayout?.attachmentCenter ?? [entity.position[0], entity.position[1] - nodeHalf - gap - nodeHalf, entity.position[2]];
  const propsWidth = propsLayout?.attachmentWidth ?? master;
  const leftEdge = propsCenter[0] - propsWidth / 2;
  const rightEdge = propsCenter[0] + propsWidth / 2;
  return {
    inCenter: [leftEdge - gap - pointHalf, propsCenter[1], entity.position[2]],
    outCenter: [rightEdge + gap + pointHalf, propsCenter[1], entity.position[2]],
    halfScale: [pointHalf, pointHalf, pointHalf],
  };
}

function causalEdgeSchedules(graph) {
  const timing = playbackApi().timingMs();
  const siblings = new Map();
  for (const edge of graph.edges) {
    if (!siblings.has(edge.from)) siblings.set(edge.from, []);
    siblings.get(edge.from).push(edge);
  }
  for (const edges of siblings.values()) edges.sort((a, b) => a.id.localeCompare(b.id));
  const schedules = new Map();
  for (const edge of graph.edges) {
    const branchIndex = siblings.get(edge.from).findIndex(item => item.id === edge.id);
    const generationStart = timing.activation + Math.max(0, edge.depth - 1) * (timing.travel + timing.target + timing.next);
    const start = generationStart + branchIndex * timing.branch;
    const arrival = start + timing.travel;
    const effectEnd = arrival + timing.target;
    const nextAt = effectEnd + timing.next;
    schedules.set(edge.id, { start, arrival, effectEnd, nextAt });
  }
  return schedules;
}
function causalPlaybackBoundariesForTrace(trace) {
  const timing = playbackApi().timingMs();
  const values = [trace.startedAt, trace.startedAt + timing.activation];
  let end = timing.activation;
  for (const schedule of trace.schedules.values()) {
    values.push(
      trace.startedAt + schedule.start,
      trace.startedAt + schedule.arrival,
      trace.startedAt + schedule.effectEnd,
      trace.startedAt + schedule.nextAt,
    );
    end = Math.max(end, schedule.nextAt);
  }
  values.push(trace.startedAt + end + timing.hold, trace.startedAt + end + timing.hold + timing.fade);
  return values;
}
function causalNodeReachedTimes(graph, schedules) {
  const reached = new Map([[graph.rootRef, 0]]);
  for (const edge of graph.edges) {
    const arrival = schedules.get(edge.id)?.arrival ?? 0;
    const current = reached.get(edge.to);
    if (current === undefined || arrival < current) reached.set(edge.to, arrival);
  }
  return reached;
}
function traceEndTimes(trace) {
  const timing = playbackApi().timingMs();
  let contentEnd = timing.activation;
  for (const schedule of trace.schedules.values()) contentEnd = Math.max(contentEnd, schedule.nextAt);
  return {
    contentEnd,
    holdEnd: contentEnd + timing.hold,
    fadeEnd: contentEnd + timing.hold + timing.fade,
  };
}
function traceAlpha(trace, elapsed) {
  const local = elapsed - trace.startedAt;
  const ends = traceEndTimes(trace);
  if (local < 0 || local >= ends.fadeEnd) return 0;
  if (local <= ends.holdEnd) return 1;
  const fade = ends.fadeEnd - ends.holdEnd;
  return fade > 0 ? 1 - (local - ends.holdEnd) / fade : 0;
}
function causalPlaybackState(schedule, localElapsed) {
  if (!schedule) return { active: false, reached: false, targetActive: false, progress: 0 };
  const active = localElapsed >= schedule.start && localElapsed < schedule.arrival;
  const reached = localElapsed >= schedule.arrival;
  const targetActive = localElapsed >= schedule.arrival && localElapsed < schedule.effectEnd;
  const progress = localElapsed <= schedule.start ? 0 : localElapsed >= schedule.arrival ? 1 : (localElapsed - schedule.start) / Math.max(1, schedule.arrival - schedule.start);
  return { active, reached, targetActive, progress: Math.max(0, Math.min(1, progress)) };
}

function syncPlaybackBoundaryProvider() {
  playbackApi().setBoundaryProvider(() => causalProjection.currentEvents.flatMap(causalPlaybackBoundariesForTrace));
}
function clearCausalProjection() {
  causalProjection.rootEventRef = null;
  causalProjection.graph = null;
  causalProjection.playbackStartedAt = 0;
  causalProjection.currentEvents = [];
  causalProjection.routePhases.clear();
  playbackApi().setBoundaryProvider(null);
  playbackApi().reset();
}
function triggerCausalProjection(eventRef) {
  const graph = buildCausalGraph(eventRef, causalProjection.maxDepth);
  if (!playbackApi().state.startedAt) playbackApi().start(performance.now());
  const startedAt = playbackApi().elapsed();
  const traceId = causalProjection.nextTraceId++;
  const trace = {
    id: traceId,
    rootEventRef: eventRef,
    graph,
    schedules: causalEdgeSchedules(graph),
    reachedAt: null,
    startedAt,
    color: EVENT_TRACE_COLORS[(traceId - 1) % EVENT_TRACE_COLORS.length],
  };
  trace.reachedAt = causalNodeReachedTimes(graph, trace.schedules);
  causalProjection.currentEvents.push(trace);
  causalProjection.rootEventRef = eventRef;
  causalProjection.graph = graph;
  causalProjection.playbackStartedAt = performance.now();
  syncPlaybackBoundaryProvider();
  status(`fired: ${displayName(graph.index.get(eventRef))}`);
}
function pruneCompletedTraces(elapsed) {
  causalProjection.currentEvents = causalProjection.currentEvents.filter(trace => elapsed - trace.startedAt < traceEndTimes(trace).fadeEnd);
  const latest = causalProjection.currentEvents.at(-1) ?? null;
  causalProjection.rootEventRef = latest?.rootEventRef ?? null;
  causalProjection.graph = latest?.graph ?? null;
  if (!latest && playbackApi().state.startedAt) {
    playbackApi().setBoundaryProvider(null);
    playbackApi().reset();
  } else if (latest) {
    syncPlaybackBoundaryProvider();
  }
}

function buildSceneLayouts(index) {
  const visible = visibleEntityIds();
  const groups = propertyGroups(index);
  const events = new Map();
  const properties = new Map();
  const entities = new Map();
  for (const entity of assertWorkspace().entities) {
    if (!visible.has(entity.id)) continue;
    const eventLayout = eventListLayout(entity);
    const propsItems = groups.get(entity.id) ?? [];
    const propsLayout = propsListLayout(entity, propsItems);
    const eventIo = eventIoLayout(entity, eventLayout, propsLayout);
    entities.set(entity.id, { eventLayout, propsLayout, eventIo });
    for (const row of eventLayout.rows) events.set(row.ref, row);
    if (propsLayout) for (const row of propsLayout.rows) properties.set(row.ref, row);
  }
  return { entities, events, properties };
}

function ownerForRef(ref, index) { return index.get(ref)?.owner ?? null; }
function eventRouteKey(sourceOwner, targetOwner) { return `${sourceOwner.id}\u0000${targetOwner.id}`; }
function allEventRoutes(layouts) {
  const grouped = new Map();
  const index = canonicalIndex();
  for (const { property, value } of canonicalLinks()) {
    if (!CAUSAL_LINK_TYPES.has(value.link_type_ref)) continue;
    const sourceOwner = ownerForRef(value.parent_ref, index);
    const targetOwner = ownerForRef(value.child_ref, index);
    if (!sourceOwner || !targetOwner || sourceOwner.id === targetOwner.id) continue;
    const key = eventRouteKey(sourceOwner, targetOwner);
    if (!grouped.has(key)) grouped.set(key, { key, sourceOwner, targetOwner, properties: [] });
    grouped.get(key).properties.push(property);
  }
  return [...grouped.values()].map(route => {
    const sourceLayout = layouts.entities.get(route.sourceOwner.id);
    const targetLayout = layouts.entities.get(route.targetOwner.id);
    return {
      ...route,
      start: sourceLayout?.eventIo?.outCenter ?? route.sourceOwner.position,
      end: targetLayout?.eventIo?.inCenter ?? route.targetOwner.position,
    };
  });
}
function traceRouteEdges(trace) {
  const grouped = new Map();
  for (const edge of trace.graph.edges) {
    const sourceOwner = ownerForRef(edge.from, trace.graph.index);
    const targetOwner = ownerForRef(edge.to, trace.graph.index);
    if (!sourceOwner || !targetOwner || sourceOwner.id === targetOwner.id) continue;
    const key = eventRouteKey(sourceOwner, targetOwner);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(edge);
  }
  return grouped;
}
function eventRouteFlowProgress(routeKey, now) {
  let state = causalProjection.routePhases.get(routeKey);
  if (!state) {
    state = { phase: 0, time: now };
    causalProjection.routePhases.set(routeKey, state);
  }
  const dt = Math.max(0, Math.min(.05, (now - state.time) / 1000));
  const speed = requiredNumber(linkSettings(), 'base_flow_speed', 'settings.link_visualization');
  if (speed < 0) throw new Error('Event baseline link flow speed must be non-negative');
  state.phase = (state.phase + dt * speed) % 1;
  state.time = now;
  return state.phase;
}
function fadedColor(color, alpha, floor = .08) {
  const amount = floor + (1 - floor) * Math.max(0, Math.min(1, alpha));
  return color.map(value => value * amount);
}
function drawTransientTraceRoute(route, trace, edges, globalElapsed, pulseRadius) {
  const localElapsed = globalElapsed - trace.startedAt;
  const alpha = traceAlpha(trace, globalElapsed);
  if (alpha <= 0) return;
  let furthest = 0;
  let touched = false;
  for (const edge of edges) {
    const state = causalPlaybackState(trace.schedules.get(edge.id), localElapsed);
    if (state.progress > 0) touched = true;
    furthest = Math.max(furthest, state.progress);
  }
  if (!touched) return;
  const endpoint = V.add(route.start, V.mul(V.sub(route.end, route.start), furthest));
  const color = fadedColor(trace.color, alpha, .18);
  drawLine(route.start, endpoint, color);
  if (furthest > 0 && furthest < 1) drawBox(endpoint, [pulseRadius, pulseRadius, pulseRadius], color);
}
function activeTraceForRef(ref, globalElapsed) {
  for (let index = causalProjection.currentEvents.length - 1; index >= 0; index--) {
    const trace = causalProjection.currentEvents[index];
    const local = globalElapsed - trace.startedAt;
    const reached = trace.reachedAt.get(ref);
    if (reached === undefined || local < reached) continue;
    const alpha = traceAlpha(trace, globalElapsed);
    if (alpha > 0) return { trace, alpha, local, reached };
  }
  return null;
}

function drawSceneProjection3D() {
  if (!ws) return;
  const globalElapsed = playbackApi().state.startedAt ? playbackApi().elapsed() : 0;
  if (causalProjection.currentEvents.length) pruneCompletedTraces(globalElapsed);
  const index = canonicalIndex();
  const layouts = buildSceneLayouts(index);

  causalProjection.eventHitTargets = [];
  causalProjection.propertyHitTargets = [];

  for (const entity of assertWorkspace().entities) {
    const local = layouts.entities.get(entity.id);
    if (!local) continue;

    const entityTrace = causalProjection.currentEvents.find(trace => {
      const localElapsed = globalElapsed - trace.startedAt;
      const root = trace.graph.index.get(trace.rootEventRef);
      return root?.owner.id === entity.id && localElapsed >= 0 && localElapsed < playbackApi().timingMs().activation;
    });
    if (entityTrace) {
      const overlayHalf = nodeHalfSize() + .018 * nodeMasterSize();
      drawBox(entity.position, [overlayHalf, overlayHalf, overlayHalf], fadedColor(entityTrace.color, traceAlpha(entityTrace, globalElapsed), .28), true);
    }

    const labelCenter = [entity.position[0], entity.position[1] + nodeHalfSize() + .28 * nodeMasterSize(), entity.position[2] + .012];
    drawSceneText3D(entity.name, labelCenter, 1.75 * nodeMasterSize(), .32 * nodeMasterSize(), selected.has(entity.id) ? [.62,.82,1] : [.94,.97,1]);

    for (const row of local.eventLayout.rows) {
      const active = activeTraceForRef(row.ref, globalElapsed);
      const color = active ? fadedColor(active.trace.color, active.alpha, .24) : SCENE_COLORS.event;
      drawBox(row.center, row.halfScale, color);
      drawBox(row.center, [row.halfScale[0]+.008,row.halfScale[1]+.008,row.halfScale[2]+.008], active ? color : SCENE_COLORS.outline, true);
      drawSceneText3D(propertyDisplayName(row.property, entity), [row.center[0],row.center[1],row.center[2]+row.halfScale[2]+.012], row.width*.88, row.height*.68, [.98,.92,.82]);
      causalProjection.eventHitTargets.push({ ref: row.ref, center: row.center, halfWidth: row.halfScale[0], halfHeight: row.halfScale[1] });
    }

    const props = local.propsLayout;
    if (props) {
      if (props.collapsed) {
        drawBox(props.center, props.frameScale, SCENE_COLORS.propsFrame, true);
        drawSceneText3D('+', [props.center[0],props.center[1],props.center[2]+props.frameScale[2]+.012], props.width*.62, props.height*.62, [.82,.88,.95]);
        causalProjection.propertyHitTargets.push({ kind: 'toggle', ownerId: entity.id, center: props.center, halfWidth: props.frameScale[0], halfHeight: props.frameScale[1] });
      } else {
        drawBox(props.center, props.frameScale, SCENE_COLORS.propsFrame, true);
        for (const row of props.rows) {
          const active = activeTraceForRef(row.ref, globalElapsed);
          const base = SCENE_COLORS[row.item.propertyType] ?? SCENE_COLORS.generic;
          const color = active ? fadedColor(active.trace.color, active.alpha, .22) : base;
          drawBox(row.center, row.halfScale, color);
          drawBox(row.center, [row.halfScale[0]+.008,row.halfScale[1]+.008,row.halfScale[2]+.008], active ? color : SCENE_COLORS.outline, true);
          drawSceneText3D(`${row.item.propertyType.toUpperCase()} · ${displayName(row.item)}`, [row.center[0],row.center[1],row.center[2]+row.halfScale[2]+.012], row.width*.90, row.height*.68, [.92,.95,.99]);
          causalProjection.propertyHitTargets.push({ kind: 'property', ref: row.ref, center: row.center, halfWidth: row.halfScale[0], halfHeight: row.halfScale[1] });
        }
        const toggleHalf = props.toggleSize / 2;
        drawBox(props.toggleCenter, [toggleHalf, toggleHalf, props.frameScale[2]*1.45], [.18,.22,.29]);
        drawSceneText3D('×', [props.toggleCenter[0],props.toggleCenter[1],props.toggleCenter[2]+props.frameScale[2]*1.5], props.toggleSize*.72, props.toggleSize*.72, [.88,.92,.98]);
        causalProjection.propertyHitTargets.push({ kind: 'toggle', ownerId: entity.id, center: props.toggleCenter, halfWidth: toggleHalf, halfHeight: toggleHalf });
      }
    }

    // Shared Event I/O are intentionally only visible points: 10% of the old
    // node-sized markers and no text labels.
    if (local.eventIo) {
      drawBox(local.eventIo.inCenter, local.eventIo.halfScale, SCENE_COLORS.causalFlow, true);
      drawBox(local.eventIo.outCenter, local.eventIo.halfScale, SCENE_COLORS.causalFlow);
    }
  }

  if (viewSettings().event_routes_visible) {
    const now = performance.now();
    const pulseRadius = Math.max(.018, linkSettings().flow_width * .10) * nodeMasterSize();
    for (const route of allEventRoutes(layouts)) {
      // Baseline link is always present and always shows canonical direction.
      drawLine(route.start, route.end, SCENE_COLORS.causal);
      const progress = eventRouteFlowProgress(route.key, now);
      const baselinePulse = V.add(route.start, V.mul(V.sub(route.end, route.start), progress));
      drawBox(baselinePulse, [pulseRadius*.65, pulseRadius*.65, pulseRadius*.65], SCENE_COLORS.causalFlow);

      // Each current Event overlays only its own canonical trace on that same
      // route. No semantic or visual route is invented by the animation.
      for (const trace of causalProjection.currentEvents) {
        const edges = traceRouteEdges(trace).get(route.key);
        if (edges?.length) drawTransientTraceRoute(route, trace, edges, globalElapsed, pulseRadius);
      }
    }
  }
}

function hitSceneTarget(clientX, clientY, targets) {
  let winner = null;
  let best = Infinity;
  for (const target of targets) {
    const bounds = sceneWorldBoxScreenBounds(target.center, target.halfWidth, target.halfHeight);
    if (!bounds) continue;
    if (clientX < bounds.minX || clientX > bounds.maxX || clientY < bounds.minY || clientY > bounds.maxY) continue;
    if (bounds.depth < best) { best = bounds.depth; winner = target; }
  }
  return winner;
}

canvas.addEventListener('click', event => {
  if (!ws || event.button !== 0) return;
  const eventTarget = hitSceneTarget(event.clientX, event.clientY, causalProjection.eventHitTargets);
  if (eventTarget) {
    event.stopPropagation();
    triggerCausalProjection(eventTarget.ref);
    return;
  }
  const propertyTarget = hitSceneTarget(event.clientX, event.clientY, causalProjection.propertyHitTargets);
  if (!propertyTarget) return;
  event.stopPropagation();
  if (propertyTarget.kind === 'toggle') {
    if (!propertyPanelSettings().show_all_props) setPropertyPanelCollapsed(propertyTarget.ownerId, !propertyPanelCollapsed(propertyTarget.ownerId));
    return;
  }
  const fresh = canonicalIndex().get(propertyTarget.ref);
  if (!fresh) throw new Error(`Property unresolved: ${propertyTarget.ref}`);
  selected = new Set([fresh.owner.id]);
  setActiveEntity(fresh.owner.id);
  inspect();
  updateButtons();
  status(`${fresh.propertyType}: ${displayName(fresh)}`);
});

const renderSceneBase = render;
render = function renderSceneWith3dChildren() {
  renderSceneBase();
  if (ws) drawSceneProjection3D();
};

window.addEventListener('keydown', event => {
  if (event.key === 'Escape' && causalProjection.currentEvents.length) clearCausalProjection();
});
window.addEventListener('load', () => {
  bindPropertyPanelControls();
  syncPropertyPanelControls();
});
