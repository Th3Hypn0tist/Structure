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
// Event links obey the shared animation contract: the same projected link is
// always present with slow direction-only baseline flow. Event playback speeds
// up and brightens that same link transiently, then it fades back to baseline.

const CAUSAL_LINK_TYPES = new Set([
  'event_read', 'event_input', 'event_output', 'event_effect',
  'event_cause', 'event_condition', 'effect_target',
]);

const causalProjection = {
  rootEventRef: null,
  maxDepth: 8,
  graph: null,
  playbackStartedAt: 0,
  eventHitTargets: [],
  propertyHitTargets: [],
  routePhases: new Map(),
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
  eventActive: [.92, .42, .10],
  eventIo: [.42, .25, .09],
  eventIoActive: [.92, .42, .10],
  propsFrame: [.36, .42, .52],
  effect: [.48, .16, .13],
  data: [.08, .29, .43],
  function: [.30, .20, .42],
  type: [.28, .32, .38],
  mount: [.16, .34, .24],
  generic: [.24, .28, .34],
  reached: [.92, .32, .24],
  outline: [.50, .58, .70],
  causal: [.48, .18, .14],
  causalFlow: [.78, .30, .22],
  causalActive: [.98, .44, .30],
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
  const half = nodeHalfSize();
  const propsCenter = propsLayout?.attachmentCenter ?? [entity.position[0], entity.position[1] - nodeHalfSize() - gap - half, entity.position[2]];
  const propsWidth = propsLayout?.attachmentWidth ?? master;
  const leftEdge = propsCenter[0] - propsWidth / 2;
  const rightEdge = propsCenter[0] + propsWidth / 2;
  return {
    inCenter: [leftEdge - gap - half, propsCenter[1], entity.position[2]],
    outCenter: [rightEdge + gap + half, propsCenter[1], entity.position[2]],
    halfScale: [half, half, half],
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
function causalPlaybackBoundaries(graph) {
  if (!graph) return [];
  const timing = playbackApi().timingMs();
  const schedules = causalEdgeSchedules(graph);
  const values = [0, timing.activation];
  let end = timing.activation;
  for (const schedule of schedules.values()) {
    values.push(schedule.start, schedule.arrival, schedule.effectEnd, schedule.nextAt);
    end = Math.max(end, schedule.nextAt);
  }
  values.push(end + timing.hold, end + timing.hold + timing.fade);
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
function causalPlaybackState(schedule, elapsed) {
  if (!schedule) return { active: false, reached: false, targetActive: false, fade: 0 };
  const timing = playbackApi().timingMs();
  const active = elapsed >= schedule.start && elapsed < schedule.arrival;
  const reached = elapsed >= schedule.arrival;
  const targetActive = elapsed >= schedule.arrival && elapsed < schedule.effectEnd;
  let fade = 0;
  if (elapsed >= schedule.effectEnd && elapsed < schedule.effectEnd + timing.fade && timing.fade > 0) {
    fade = 1 - (elapsed - schedule.effectEnd) / timing.fade;
  }
  return { active, reached, targetActive, fade };
}

function clearCausalProjection() {
  causalProjection.rootEventRef = null;
  causalProjection.graph = null;
  causalProjection.playbackStartedAt = 0;
  playbackApi().setBoundaryProvider(null);
  playbackApi().reset();
}
function triggerCausalProjection(eventRef) {
  const graph = buildCausalGraph(eventRef, causalProjection.maxDepth);
  causalProjection.rootEventRef = eventRef;
  causalProjection.graph = graph;
  causalProjection.playbackStartedAt = performance.now();
  playbackApi().start(causalProjection.playbackStartedAt);
  playbackApi().setBoundaryProvider(() => causalPlaybackBoundaries(causalProjection.graph));
  status(`fired: ${displayName(graph.index.get(eventRef))}`);
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

function ownerForRef(ref, index) {
  return index.get(ref)?.owner ?? null;
}
function allEventRoutes(layouts) {
  const grouped = new Map();
  const index = canonicalIndex();
  for (const { property, value } of canonicalLinks()) {
    if (!CAUSAL_LINK_TYPES.has(value.link_type_ref)) continue;
    const sourceOwner = ownerForRef(value.parent_ref, index);
    const targetOwner = ownerForRef(value.child_ref, index);
    if (!sourceOwner || !targetOwner || sourceOwner.id === targetOwner.id) continue;
    const key = `${sourceOwner.id}\u0000${targetOwner.id}`;
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
function activeRouteStates(graph, schedules, elapsed) {
  const states = new Map();
  if (!graph) return states;
  for (const edge of graph.edges) {
    const sourceOwner = ownerForRef(edge.from, graph.index);
    const targetOwner = ownerForRef(edge.to, graph.index);
    if (!sourceOwner || !targetOwner || sourceOwner.id === targetOwner.id) continue;
    const key = `${sourceOwner.id}\u0000${targetOwner.id}`;
    const state = causalPlaybackState(schedules.get(edge.id), elapsed);
    const current = states.get(key) ?? { active: false, reached: false, targetActive: false, fade: 0 };
    current.active ||= state.active;
    current.reached ||= state.reached;
    current.targetActive ||= state.targetActive;
    current.fade = Math.max(current.fade, state.fade);
    states.set(key, current);
  }
  return states;
}
function eventRouteFlowProgress(routeKey, now, active) {
  let state = causalProjection.routePhases.get(routeKey);
  if (!state) {
    state = { phase: 0, time: now };
    causalProjection.routePhases.set(routeKey, state);
  }
  const dt = Math.max(0, Math.min(.05, (now - state.time) / 1000));
  const speed = active ? requiredNumber(eventSettings(), 'active_link_speed', 'settings.event_playback') : requiredNumber(linkSettings(), 'base_flow_speed', 'settings.link_visualization');
  if (speed < 0) throw new Error('Event link flow speed must be non-negative');
  state.phase = (state.phase + dt * speed) % 1;
  state.time = now;
  return state.phase;
}
function mixColor(base, active, amount) {
  const t = Math.max(0, Math.min(1, amount));
  return base.map((value, index) => value + (active[index] - value) * t);
}

function drawSceneProjection3D() {
  if (!ws) return;
  const graph = causalProjection.rootEventRef ? buildCausalGraph(causalProjection.rootEventRef, causalProjection.maxDepth) : null;
  causalProjection.graph = graph;
  const index = graph ? graph.index : canonicalIndex();
  const layouts = buildSceneLayouts(index);
  const elapsed = graph ? playbackApi().elapsed() : 0;
  const schedules = graph ? causalEdgeSchedules(graph) : new Map();
  const reachedAt = graph ? causalNodeReachedTimes(graph, schedules) : new Map();
  const timing = playbackApi().timingMs();
  const routeStates = activeRouteStates(graph, schedules, elapsed);

  causalProjection.eventHitTargets = [];
  causalProjection.propertyHitTargets = [];

  for (const entity of assertWorkspace().entities) {
    const local = layouts.entities.get(entity.id);
    if (!local) continue;

    const labelCenter = [entity.position[0], entity.position[1] + nodeHalfSize() + .28 * nodeMasterSize(), entity.position[2] + .012];
    drawSceneText3D(entity.name, labelCenter, 1.75 * nodeMasterSize(), .32 * nodeMasterSize(), selected.has(entity.id) ? [.62,.82,1] : [.94,.97,1]);

    for (const row of local.eventLayout.rows) {
      const reached = reachedAt.has(row.ref) && elapsed >= reachedAt.get(row.ref);
      const rootActive = graph?.rootRef === row.ref && elapsed < timing.activation;
      const color = rootActive || reached ? SCENE_COLORS.eventActive : SCENE_COLORS.event;
      drawBox(row.center, row.halfScale, color);
      drawBox(row.center, [row.halfScale[0]+.008,row.halfScale[1]+.008,row.halfScale[2]+.008], rootActive || reached ? [.98,.66,.28] : SCENE_COLORS.outline, true);
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
          const reached = reachedAt.has(row.ref) && elapsed >= reachedAt.get(row.ref);
          const base = SCENE_COLORS[row.item.propertyType] ?? SCENE_COLORS.generic;
          drawBox(row.center, row.halfScale, reached ? SCENE_COLORS.reached : base);
          drawBox(row.center, [row.halfScale[0]+.008,row.halfScale[1]+.008,row.halfScale[2]+.008], reached ? [.98,.58,.48] : SCENE_COLORS.outline, true);
          drawSceneText3D(`${row.item.propertyType.toUpperCase()} · ${displayName(row.item)}`, [row.center[0],row.center[1],row.center[2]+row.halfScale[2]+.012], row.width*.90, row.height*.68, [.92,.95,.99]);
          causalProjection.propertyHitTargets.push({ kind: 'property', ref: row.ref, center: row.center, halfWidth: row.halfScale[0], halfHeight: row.halfScale[1] });
        }
        const toggleHalf = props.toggleSize / 2;
        drawBox(props.toggleCenter, [toggleHalf, toggleHalf, props.frameScale[2]*1.45], [.18,.22,.29]);
        drawSceneText3D('×', [props.toggleCenter[0],props.toggleCenter[1],props.toggleCenter[2]+props.frameScale[2]*1.5], props.toggleSize*.72, props.toggleSize*.72, [.88,.92,.98]);
        causalProjection.propertyHitTargets.push({ kind: 'toggle', ownerId: entity.id, center: props.toggleCenter, halfWidth: toggleHalf, halfHeight: toggleHalf });
      }
    }

    if (local.eventIo) {
      const hasActiveRoute = [...routeStates.entries()].some(([key, state]) => state.active && key.startsWith(`${entity.id}\u0000`) || state.active && key.endsWith(`\u0000${entity.id}`));
      const ioColor = hasActiveRoute ? SCENE_COLORS.eventIoActive : SCENE_COLORS.eventIo;
      drawBox(local.eventIo.inCenter, local.eventIo.halfScale, ioColor, true);
      drawBox(local.eventIo.outCenter, local.eventIo.halfScale, ioColor);
      const textY = local.eventIo.inCenter[1] + local.eventIo.halfScale[1] + .24 * nodeMasterSize();
      drawSceneText3D('Event in', [local.eventIo.inCenter[0], textY, local.eventIo.inCenter[2]+.012], 1.20*nodeMasterSize(), .28*nodeMasterSize(), [.96,.91,.84]);
      drawSceneText3D('Event out', [local.eventIo.outCenter[0], textY, local.eventIo.outCenter[2]+.012], 1.20*nodeMasterSize(), .28*nodeMasterSize(), [.96,.91,.84]);
    }
  }

  if (viewSettings().event_routes_visible) {
    const now = performance.now();
    const pulseRadius = Math.max(.025, linkSettings().flow_width * .14) * nodeMasterSize();
    for (const route of allEventRoutes(layouts)) {
      const state = routeStates.get(route.key) ?? { active: false, fade: 0 };
      const intensity = state.active ? 1 : state.fade;
      const lineColor = mixColor(SCENE_COLORS.causal, SCENE_COLORS.causalActive, intensity);
      const flowColor = mixColor(SCENE_COLORS.causalFlow, SCENE_COLORS.causalActive, intensity);
      drawLine(route.start, route.end, lineColor);
      const progress = eventRouteFlowProgress(route.key, now, state.active);
      const pulse = V.add(route.start, V.mul(V.sub(route.end, route.start), progress));
      drawBox(pulse, [pulseRadius, pulseRadius, pulseRadius], flowColor);
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
  if (event.key === 'Escape' && causalProjection.rootEventRef) clearCausalProjection();
});
window.addEventListener('load', () => {
  bindPropertyPanelControls();
  syncPropertyPanelControls();
});
