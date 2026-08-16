// Scene projection: every represented object in the view is a world-space 3D
// instance. DOM is not used for Entity, Event, Property or causal-route
// representation.

const causalProjection = {
  rootEventRef: null,
  maxDepth: 8,
  graph: null,
  playbackStartedAt: 0,
  eventHitTargets: [],
  propertyHitTargets: [],
};
window.StructureSceneProjection = Object.freeze({
  state: causalProjection,
  reset: () => clearCausalProjection(),
});
window.StructureCausalProjection = Object.freeze({
  state: causalProjection,
  surface: { style: { display: '' } },
});

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
  propsFrame: [.36, .42, .52],
  effect: [.48, .16, .13],
  data: [.08, .29, .43],
  function: [.30, .20, .42],
  type: [.28, .32, .38],
  mount: [.16, .34, .24],
  generic: [.24, .28, .34],
  reached: [.92, .32, .24],
  outline: [.50, .58, .70],
  causal: [.72, .28, .22],
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
    center: [
      rightEdge - width / 2,
      top - rowHeight / 2 - index * (rowHeight + rowGap),
      entity.position[2],
    ],
    halfScale: [width / 2, rowHeight / 2, depth],
    width,
    height: rowHeight,
  }));
  return { entity, rows, rightEdge };
}

function propsListLayout(entity, items) {
  const master = nodeMasterSize();
  const scale = propertyPanelSettings().property_panel_size;
  const half = nodeHalfSize();
  const gap = .20 * master;
  const depth = .075 * master * scale;
  const collapsed = propertyPanelCollapsed(entity.id);
  if (collapsed) {
    const size = .28 * master * scale;
    const leftEdge = entity.position[0] + half + gap;
    const center = [leftEdge + size / 2, entity.position[1], entity.position[2]];
    return { entity, collapsed, center, frameScale: [size / 2, size / 2, depth], rows: [], width: size, height: size };
  }
  const width = 1.62 * master * scale;
  const rowHeight = .25 * master * scale;
  const rowGap = .055 * master * scale;
  const rowsHeight = items.length ? items.length * rowHeight + Math.max(0, items.length - 1) * rowGap : rowHeight;
  const padding = .10 * master * scale;
  const height = rowsHeight + padding * 2;
  const leftEdge = entity.position[0] + half + gap;
  const center = [leftEdge + width / 2, entity.position[1], entity.position[2]];
  const top = center[1] + height / 2 - padding;
  const rows = items.map(({ ref, item }, index) => ({
    ref,
    item,
    center: [center[0], top - rowHeight / 2 - index * (rowHeight + rowGap), center[2]],
    halfScale: [width * .47, rowHeight * .42, depth * 1.35],
    width: width * .94,
    height: rowHeight * .84,
  }));
  return { entity, collapsed, center, frameScale: [width / 2, height / 2, depth], rows, width, height };
}

function refWorldPosition(ref, layouts, index) {
  const item = index.get(ref);
  if (!item) return null;
  if (item.kind === 'entity') return item.owner.position;
  const event = layouts.events.get(ref);
  if (event) return event.center;
  const prop = layouts.properties.get(ref);
  if (prop) return prop.center;
  return item.owner.position;
}

function clearCausalProjection() {
  causalProjection.rootEventRef = null;
  causalProjection.graph = null;
  causalProjection.playbackStartedAt = 0;
}
function triggerCausalProjection(eventRef) {
  const graph = buildCausalGraph(eventRef, causalProjection.maxDepth);
  causalProjection.rootEventRef = eventRef;
  causalProjection.graph = graph;
  causalProjection.playbackStartedAt = performance.now();
  status(`fired: ${displayName(graph.index.get(eventRef))}`);
}
function causalPlaybackState(edge, elapsed, stepMs) {
  const activeAt = Math.max(0, edge.depth - 1) * stepMs;
  return {
    active: elapsed >= activeAt && elapsed < activeAt + stepMs * .9,
    reached: elapsed >= activeAt + stepMs * .75,
  };
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
    entities.set(entity.id, { eventLayout, propsLayout });
    for (const row of eventLayout.rows) events.set(row.ref, row);
    for (const row of propsLayout.rows) properties.set(row.ref, row);
  }
  return { entities, events, properties };
}

function drawSceneProjection3D() {
  if (!ws) return;
  const graph = causalProjection.rootEventRef ? buildCausalGraph(causalProjection.rootEventRef, causalProjection.maxDepth) : null;
  causalProjection.graph = graph;
  const index = graph ? graph.index : canonicalIndex();
  const layouts = buildSceneLayouts(index);
  const elapsed = graph ? performance.now() - causalProjection.playbackStartedAt : 0;
  const stepMs = Math.max(120, eventSettings().effect_travel_duration * 350);
  const graphDepth = new Map(graph ? graph.nodes.map(node => [node.ref, node.depth]) : []);

  causalProjection.eventHitTargets = [];
  causalProjection.propertyHitTargets = [];

  for (const entity of assertWorkspace().entities) {
    const local = layouts.entities.get(entity.id);
    if (!local) continue;

    // Entity label is a real world-space text plane above the Entity.
    const labelCenter = [entity.position[0], entity.position[1] + nodeHalfSize() + .28 * nodeMasterSize(), entity.position[2] + .012];
    drawSceneText3D(entity.name, labelCenter, 1.75 * nodeMasterSize(), .32 * nodeMasterSize(), selected.has(entity.id) ? [.62,.82,1] : [.94,.97,1]);

    // EventList: list right edge is attached to Entity left edge with local gap.
    for (const row of local.eventLayout.rows) {
      const depth = graphDepth.get(row.ref);
      const reached = depth !== undefined && elapsed >= depth * stepMs;
      const active = graph?.rootRef === row.ref || reached;
      const color = active ? SCENE_COLORS.eventActive : SCENE_COLORS.event;
      drawBox(row.center, row.halfScale, color);
      drawBox(row.center, [row.halfScale[0]+.008,row.halfScale[1]+.008,row.halfScale[2]+.008], active ? [.98,.66,.28] : SCENE_COLORS.outline, true);
      drawSceneText3D(propertyDisplayName(row.property, entity), [row.center[0],row.center[1],row.center[2]+row.halfScale[2]+.012], row.width*.88, row.height*.68, [.98,.92,.82]);
      causalProjection.eventHitTargets.push({ ref: row.ref, center: row.center, halfWidth: row.halfScale[0], halfHeight: row.halfScale[1] });
    }

    // PropsList: one 3D child of Entity, rows are children of that list.
    const props = local.propsLayout;
    drawBox(props.center, props.frameScale, SCENE_COLORS.propsFrame, true);
    if (props.collapsed) {
      drawSceneText3D('+', [props.center[0],props.center[1],props.center[2]+props.frameScale[2]+.012], props.width*.6, props.height*.6, [.82,.88,.95]);
      causalProjection.propertyHitTargets.push({ kind: 'toggle', ownerId: entity.id, center: props.center, halfWidth: props.frameScale[0], halfHeight: props.frameScale[1] });
    } else {
      for (const row of props.rows) {
        const depth = graphDepth.get(row.ref);
        const reached = depth !== undefined && elapsed >= depth * stepMs;
        const base = SCENE_COLORS[row.item.propertyType] ?? SCENE_COLORS.generic;
        const color = reached ? SCENE_COLORS.reached : base;
        drawBox(row.center, row.halfScale, color);
        drawBox(row.center, [row.halfScale[0]+.008,row.halfScale[1]+.008,row.halfScale[2]+.008], reached ? [.98,.58,.48] : SCENE_COLORS.outline, true);
        drawSceneText3D(`${row.item.propertyType.toUpperCase()} · ${displayName(row.item)}`, [row.center[0],row.center[1],row.center[2]+row.halfScale[2]+.012], row.width*.90, row.height*.68, [.92,.95,.99]);
        causalProjection.propertyHitTargets.push({ kind: 'property', ref: row.ref, center: row.center, halfWidth: row.halfScale[0], halfHeight: row.halfScale[1] });
      }
      const toggleCenter = [props.center[0]+props.width/2-.12*nodeMasterSize(), props.center[1]+props.height/2-.12*nodeMasterSize(), props.center[2]+props.frameScale[2]+.012];
      drawSceneText3D('−', toggleCenter, .20*nodeMasterSize(), .20*nodeMasterSize(), [.78,.84,.92]);
      causalProjection.propertyHitTargets.push({ kind: 'toggle', ownerId: entity.id, center: toggleCenter, halfWidth: .14*nodeMasterSize(), halfHeight: .14*nodeMasterSize() });
    }
  }

  // Causal routes are 3D world-space lines as well; no SVG/DOM scene path.
  if (graph && viewSettings().event_routes_visible) {
    for (const edge of graph.edges) {
      const from = refWorldPosition(edge.from, layouts, graph.index);
      const to = refWorldPosition(edge.to, layouts, graph.index);
      if (!from || !to) continue;
      const state = causalPlaybackState(edge, elapsed, stepMs);
      const color = state.active ? SCENE_COLORS.causalActive : SCENE_COLORS.causal;
      drawLine(from, to, color);
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
