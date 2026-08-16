// Canonical Event -> Effect -> target -> downstream Event projection.
// Events keep their dedicated world-space UI. Ordinary Properties are rendered
// as real WebGL child geometry of their owning Entity; DOM is only used for
// lightweight readable labels and interaction.

const causalProjection = {
  rootEventRef: null,
  maxDepth: 8,
  propertyOverlays: new Map(),
  graph: null,
  playbackStartedAt: 0,
};

const causalSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
causalSvg.id = 'causalLines';
causalSvg.setAttribute('aria-hidden', 'true');
causalSvg.innerHTML = '<defs><marker id="causalArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 z"></path></marker></defs>';
document.body.appendChild(causalSvg);

const causalNodes = document.createElement('div');
causalNodes.id = 'causalNodes';
document.body.appendChild(causalNodes);
window.StructureCausalProjection = Object.freeze({ state: causalProjection, surface: causalSvg });

function propertyPanelSettings() { return viewSettings(); }
function propertyPanelCollapsed(ownerId) { return propertyPanelSettings().show_all_props ? false : Boolean(propertyPanelSettings().property_panel_collapsed[ownerId]); }
function setPropertyPanelCollapsed(ownerId, collapsed) {
  const states = propertyPanelSettings().property_panel_collapsed;
  if (collapsed) states[ownerId] = true;
  else delete states[ownerId];
}
function bindPropertyPanelControls() {
  const legacyDirection = document.querySelector('.property-direction-control');
  if (legacyDirection) legacyDirection.hidden = true;
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
function displayName(item) { return item.kind === 'entity' ? item.owner.name : propertyDisplayName(item.object, item.owner); }
function nodeClass(item) { return item.kind === 'entity' ? 'entity' : item.propertyType; }

function propertyGroups(index) {
  const groups = new Map();
  for (const item of index.values()) {
    // Link and Event have dedicated projections. Every other Property belongs
    // to exactly one PropsVisual child hierarchy under its owning Entity.
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

const PROPERTY_COLORS = Object.freeze({
  effect: [.48, .16, .13],
  data: [.08, .29, .43],
  function: [.30, .20, .42],
  type: [.28, .32, .38],
  mount: [.16, .34, .24],
});
const PROPERTY_REACHED_COLOR = [.92, .32, .24];
const PROPS_FRAME_COLOR = [.34, .40, .50];

function propertyVisualLayout(owner, items) {
  const master = nodeMasterSize();
  const scale = propertyPanelSettings().property_panel_size;
  const width = 1.62 * master * scale;
  const rowHeight = .25 * master * scale;
  const rowGap = .055 * master * scale;
  const headerHeight = .22 * master * scale;
  const depth = .075 * master * scale;
  const entityHalf = nodeHalfSize();
  const entityGap = .22 * master;
  const collapsed = propertyPanelCollapsed(owner.id);

  if (collapsed) {
    const collapsedSize = .26 * master * scale;
    const center = [
      owner.position[0] + entityHalf + entityGap + collapsedSize / 2,
      owner.position[1],
      owner.position[2],
    ];
    return {
      owner,
      collapsed,
      width: collapsedSize,
      height: collapsedSize,
      depth,
      center,
      frameScale: [collapsedSize / 2, collapsedSize / 2, depth],
      rows: [],
      toggleWorld: center,
    };
  }

  const rowsHeight = items.length ? items.length * rowHeight + Math.max(0, items.length - 1) * rowGap : rowHeight;
  const height = headerHeight + rowsHeight + .12 * master * scale;
  const center = [
    owner.position[0] + entityHalf + entityGap + width / 2,
    owner.position[1],
    owner.position[2],
  ];
  const top = center[1] + height / 2;
  const rows = items.map(({ ref, item }, index) => ({
    ref,
    item,
    center: [
      center[0],
      top - headerHeight - rowHeight / 2 - index * (rowHeight + rowGap),
      center[2],
    ],
    halfScale: [width * .47, rowHeight * .42, depth * 1.35],
    width: width * .94,
    height: rowHeight * .84,
  }));
  return {
    owner,
    collapsed,
    width,
    height,
    depth,
    center,
    frameScale: [width / 2, height / 2, depth],
    rows,
    toggleWorld: [center[0], top - headerHeight / 2, center[2]],
  };
}

function projectedPoint(world) {
  const screen = project(world, viewProjection());
  if (!screen) return null;
  const density = devicePixelRatio || 1;
  return { x: screen[0] / density, y: screen[1] / density, world };
}
function worldBoxAnchors(center, halfWidth) {
  const left = projectedPoint([center[0] - halfWidth, center[1], center[2]]);
  const right = projectedPoint([center[0] + halfWidth, center[1], center[2]]);
  const middle = projectedPoint(center);
  return left && right && middle ? { left, right, center: middle } : null;
}
function propertyLayoutAnchors(layout) { return worldBoxAnchors(layout.center, layout.width / 2); }
function propertyRowLayoutAnchors(row) { return worldBoxAnchors(row.center, row.width / 2); }

function ensurePropertyOverlay(owner) {
  let overlay = causalProjection.propertyOverlays.get(owner.id);
  if (overlay) return overlay;

  const root = document.createElement('div');
  root.className = 'property-overlay-group';
  root.dataset.ownerEntityId = owner.id;

  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'property-overlay-toggle';
  toggle.textContent = 'PROPS';
  toggle.addEventListener('click', event => {
    event.stopPropagation();
    if (propertyPanelSettings().show_all_props) return;
    setPropertyPanelCollapsed(owner.id, !propertyPanelCollapsed(owner.id));
  });
  root.appendChild(toggle);
  causalNodes.appendChild(root);

  overlay = { root, toggle, rows: new Map() };
  causalProjection.propertyOverlays.set(owner.id, overlay);
  return overlay;
}
function ensurePropertyOverlayRow(overlay, ref) {
  let row = overlay.rows.get(ref);
  if (row) return row;
  row = document.createElement('button');
  row.type = 'button';
  row.className = 'property-overlay-label';
  row.dataset.ref = ref;
  row.addEventListener('click', event => {
    event.stopPropagation();
    const fresh = canonicalIndex().get(row.dataset.ref);
    if (!fresh) throw new Error(`Property unresolved: ${row.dataset.ref}`);
    selected = new Set([fresh.owner.id]);
    setActiveEntity(fresh.owner.id);
    inspect();
    updateButtons();
    status(`${fresh.propertyType}: ${displayName(fresh)}`);
  });
  overlay.root.appendChild(row);
  overlay.rows.set(ref, row);
  return row;
}
function placeOverlayElement(element, world, visible = true) {
  const point = visible ? projectedPoint(world) : null;
  if (!point) {
    element.hidden = true;
    return;
  }
  element.hidden = false;
  element.style.left = `${point.x}px`;
  element.style.top = `${point.y}px`;
}
function updatePropertyOverlay(owner, items, layout) {
  const overlay = ensurePropertyOverlay(owner);
  overlay.toggle.textContent = layout.collapsed ? '+' : 'PROPS';
  overlay.toggle.setAttribute('aria-expanded', layout.collapsed ? 'false' : 'true');
  overlay.toggle.disabled = propertyPanelSettings().show_all_props;
  placeOverlayElement(overlay.toggle, layout.toggleWorld);

  const wanted = new Set(items.map(item => item.ref));
  for (const [ref, element] of [...overlay.rows]) {
    if (wanted.has(ref)) continue;
    element.remove();
    overlay.rows.delete(ref);
  }

  for (const rowLayout of layout.rows) {
    const element = ensurePropertyOverlayRow(overlay, rowLayout.ref);
    element.className = `property-overlay-label ${nodeClass(rowLayout.item)}`;
    element.textContent = `${nodeClass(rowLayout.item).toUpperCase()} · ${displayName(rowLayout.item)}`;
    placeOverlayElement(element, rowLayout.center, true);
  }
  if (layout.collapsed) {
    for (const element of overlay.rows.values()) element.hidden = true;
  }
}
function removeStalePropertyOverlays(livingOwnerIds) {
  for (const [ownerId, overlay] of [...causalProjection.propertyOverlays]) {
    if (livingOwnerIds.has(ownerId)) continue;
    overlay.root.remove();
    causalProjection.propertyOverlays.delete(ownerId);
  }
}

function clearCausalProjection() {
  causalProjection.rootEventRef = null;
  causalProjection.graph = null;
  causalProjection.playbackStartedAt = 0;
  document.querySelectorAll('.property-overlay-label.reached').forEach(row => row.classList.remove('reached'));
  document.querySelectorAll('.event-button.causal-reached').forEach(button => button.classList.remove('causal-reached'));
  causalSvg.querySelectorAll('.causal-edge,.causal-flow-pulse').forEach(path => path.remove());
}
function triggerCausalProjection(eventRef) {
  document.querySelectorAll('.property-overlay-label.reached').forEach(row => row.classList.remove('reached'));
  document.querySelectorAll('.event-button.causal-reached').forEach(button => button.classList.remove('causal-reached'));
  const graph = buildCausalGraph(eventRef, causalProjection.maxDepth);
  causalProjection.rootEventRef = eventRef;
  causalProjection.graph = graph;
  causalProjection.playbackStartedAt = performance.now();
  status(`fired: ${displayName(graph.index.get(eventRef))}`);
}
function eventButtonAnchors(ref) {
  const button = document.querySelector(`.event-button[data-event-id="${CSS.escape(ref)}"]`);
  const geometry = entityEditor.eventGeometry.get(ref);
  return button && !button.hidden && geometry
    ? worldPlaneProjectedAnchors(button, geometry.centerWorld, geometry.worldPerCssPixel)
    : null;
}

function projectedCausalRoutes(graph) {
  const routes = [];
  const groups = new Map();
  for (const edge of graph.edges) {
    if (edge.linkType !== 'effect_target') {
      routes.push({ edges: [edge], edge });
      continue;
    }
    const source = graph.index.get(edge.from);
    const target = graph.index.get(edge.to);
    if (!source || !target) throw new Error(`causal route endpoint unresolved: ${edge.id}`);
    if (source.owner.id === target.owner.id) {
      routes.push({ edges: [edge], edge });
      continue;
    }
    const key = `${source.owner.id}\u0000${target.owner.id}`;
    if (!groups.has(key)) groups.set(key, { sourceOwnerId: source.owner.id, targetOwnerId: target.owner.id, edges: [] });
    groups.get(key).edges.push(edge);
  }
  for (const group of groups.values()) {
    const representative = group.edges[0];
    routes.push({
      ...group,
      edge: {
        ...representative,
        id: group.edges.map(item => item.id).join(','),
        depth: Math.min(...group.edges.map(item => item.depth)),
        cycle: group.edges.some(item => item.cycle),
      },
      panelRoute: true,
    });
  }
  return routes;
}
function causalPlaybackState(edges, elapsed, stepMs) {
  let active = false;
  let reached = false;
  for (const edge of edges) {
    const activeAt = Math.max(0, edge.depth - 1) * stepMs;
    if (elapsed >= activeAt && elapsed < activeAt + stepMs * .9) active = true;
    if (elapsed >= activeAt + stepMs * .75) reached = true;
  }
  return { active, reached };
}

function currentPropertyProjectionState() {
  const graph = causalProjection.rootEventRef ? buildCausalGraph(causalProjection.rootEventRef, causalProjection.maxDepth) : null;
  causalProjection.graph = graph;
  const index = graph ? graph.index : canonicalIndex();
  const groups = propertyGroups(index);
  const graphDepth = new Map(graph ? graph.nodes.map(node => [node.ref, node.depth]) : []);
  const elapsed = graph ? performance.now() - causalProjection.playbackStartedAt : 0;
  const stepMs = Math.max(120, eventSettings().effect_travel_duration * 350);
  return { graph, index, groups, graphDepth, elapsed, stepMs };
}

function drawPropertyProjection3D() {
  if (!ws) return;
  const { groups, graphDepth, elapsed, stepMs } = currentPropertyProjectionState();
  const visible = visibleEntityIds();
  for (const [ownerId, items] of groups) {
    if (!visible.has(ownerId)) continue;
    const owner = items[0].item.owner;
    const layout = propertyVisualLayout(owner, items);
    drawBox(layout.center, layout.frameScale, PROPS_FRAME_COLOR, true);
    if (layout.collapsed) continue;
    for (const row of layout.rows) {
      const depth = graphDepth.get(row.ref);
      const reached = depth !== undefined && elapsed >= depth * stepMs;
      const color = reached ? PROPERTY_REACHED_COLOR : (PROPERTY_COLORS[row.item.propertyType] ?? [.24, .28, .34]);
      drawBox(row.center, row.halfScale, color);
      drawBox(row.center, [row.halfScale[0] + .008, row.halfScale[1] + .008, row.halfScale[2] + .008], reached ? [.98, .58, .48] : [.46, .54, .66], true);
    }
  }
}

function renderCausalProjection() {
  if (!ws) {
    requestAnimationFrame(renderCausalProjection);
    return;
  }

  const { graph, groups, graphDepth, elapsed, stepMs } = currentPropertyProjectionState();
  const positions = new Map();
  const panelPositions = new Map();
  const livingOwners = new Set();
  const visible = visibleEntityIds();

  causalSvg.setAttribute('width', String(innerWidth));
  causalSvg.setAttribute('height', String(innerHeight));
  causalSvg.setAttribute('viewBox', `0 0 ${innerWidth} ${innerHeight}`);
  causalSvg.querySelectorAll('.causal-edge').forEach(path => path.remove());

  for (const [ownerId, items] of groups) {
    const owner = items[0].item.owner;
    livingOwners.add(ownerId);
    const layout = propertyVisualLayout(owner, items);
    const isVisible = visible.has(ownerId);
    updatePropertyOverlay(owner, items, layout);
    const overlay = causalProjection.propertyOverlays.get(ownerId);
    if (overlay) overlay.root.hidden = !isVisible;
    if (!isVisible) continue;

    const panelAnchors = propertyLayoutAnchors(layout);
    if (panelAnchors) panelPositions.set(ownerId, panelAnchors);
    for (const row of layout.rows) {
      const anchors = propertyRowLayoutAnchors(row);
      if (anchors) positions.set(row.ref, anchors);
      const overlayRow = overlay?.rows.get(row.ref);
      const depth = graphDepth.get(row.ref);
      if (overlayRow) overlayRow.classList.toggle('reached', depth !== undefined && elapsed >= depth * stepMs);
    }
  }
  removeStalePropertyOverlays(livingOwners);

  if (!graph) {
    requestAnimationFrame(renderCausalProjection);
    return;
  }

  const rootAnchors = eventButtonAnchors(graph.rootRef);
  if (rootAnchors) positions.set(graph.rootRef, rootAnchors);
  for (const node of graph.nodes) {
    if (node.ref === graph.rootRef) continue;
    const item = graph.index.get(node.ref);
    if (!item) throw new Error(`causal node unresolved: ${node.ref}`);
    if (item.propertyType !== 'event') continue;
    const anchors = eventButtonAnchors(node.ref);
    if (anchors) positions.set(node.ref, anchors);
    const button = document.querySelector(`.event-button[data-event-id="${CSS.escape(node.ref)}"]`);
    if (button) button.classList.toggle('causal-reached', elapsed >= node.depth * stepMs);
  }

  for (const route of projectedCausalRoutes(graph)) {
    const edge = route.edge;
    const from = route.panelRoute ? panelPositions.get(route.sourceOwnerId) : positions.get(edge.from);
    const to = route.panelRoute ? panelPositions.get(route.targetOwnerId) : positions.get(edge.to);
    if (!from || !to) continue;
    const start = from.right;
    const end = to.left;
    const x1 = start.x, y1 = start.y, x2 = end.x, y2 = end.y;
    const bend = Math.max(24, Math.abs(x2 - x1) * .35);
    const direction = x2 >= x1 ? 1 : -1;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const state = causalPlaybackState(route.edges, elapsed, stepMs);
    path.setAttribute('class', `causal-edge ${edge.linkType}${route.panelRoute ? ' aggregated' : ''}${edge.cycle ? ' cycle' : ''}${state.active ? ' active' : ''}${state.reached ? ' reached' : ''}`);
    path.setAttribute('d', `M ${x1} ${y1} C ${x1 + direction * bend} ${y1}, ${x2 - direction * bend} ${y2}, ${x2} ${y2}`);
    path.setAttribute('marker-end', 'url(#causalArrow)');
    path.dataset.linkId = edge.id;
    const source = graph.index.get(route.edges[0].from);
    if (!source) throw new Error(`causal source unresolved: ${route.edges[0].from}`);
    path.style.strokeWidth = `${Math.max(.7, Math.min(5, worldPixelsAt(source.owner.position) / 24))}px`;
    causalSvg.appendChild(path);
  }

  requestAnimationFrame(renderCausalProjection);
}

// app.js owns the canonical WebGL scene render. Extend that render with the
// projection geometry instead of maintaining a second canvas/render authority.
const renderSceneWithoutPropertyProjection = render;
render = function renderSceneWithPropertyProjection() {
  renderSceneWithoutPropertyProjection();
  if (ws) drawPropertyProjection3D();
};

document.addEventListener('click', event => {
  const button = event.target.closest?.('.event-button');
  if (button?.dataset.eventId) triggerCausalProjection(button.dataset.eventId);
}, true);
window.addEventListener('keydown', event => {
  if (event.key === 'Escape' && causalProjection.rootEventRef) clearCausalProjection();
});
window.addEventListener('load', () => {
  bindPropertyPanelControls();
  syncPropertyPanelControls();
  syncEventRouteVisibility();
});
requestAnimationFrame(renderCausalProjection);
