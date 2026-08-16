// Canonical Event -> Effect -> target -> downstream Event projection.
// Event semantics stay in Properties and Rulesets; this module only resolves
// and renders the canonical causal chain.

const causalProjection = {
  rootEventRef: null,
  maxDepth: 8,
  panelElements: new Map(),
  graph: null,
  playbackStartedAt: 0,
};

const causalSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
causalSvg.id = 'causalLines';
causalSvg.setAttribute('aria-hidden', 'true');
causalSvg.innerHTML = `
  <defs>
    <marker id="causalArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L8,4 L0,8 z"></path>
    </marker>
  </defs>
`;
document.body.appendChild(causalSvg);
const causalNodes = document.createElement('div');
causalNodes.id = 'causalNodes';
document.body.appendChild(causalNodes);

function propertyPanelSettings() { return viewSettings(); }
function propertyPanelCollapsed(ownerId) {
  if (propertyPanelSettings().show_all_props) return false;
  return Boolean(propertyPanelSettings().property_panel_collapsed[ownerId]);
}
function setPropertyPanelCollapsed(ownerId, collapsed) {
  const states = propertyPanelSettings().property_panel_collapsed;
  if (collapsed) states[ownerId] = true;
  else delete states[ownerId];
}
function ensurePropertyPanelControls() {
  const directionLabel = $('#propertyPanelDirection').closest('label').querySelector('span');
  directionLabel.textContent = 'PROPS ANGLE';
  if (!document.querySelector('#propertyPanelSize')) {
    const sizeControl = document.createElement('label');
    sizeControl.className = 'node-size-control property-size-control';
    sizeControl.innerHTML = '<span>PROPS SIZE</span><input id="propertyPanelSize" type="range" min="0.25" max="2.50" step="0.05" value="1"><output id="propertyPanelSizeValue">1.00×</output>';
    $('#propertyPanelDirection').closest('label').after(sizeControl);
  }
  if (!document.querySelector('#showAllProps')) {
    const button = document.createElement('button');
    button.id = 'showAllProps';
    button.type = 'button';
    button.className = 'show-all-props-control';
    button.textContent = 'SHOW ALL PROPS';
    button.title = 'Expand every Property panel. Disable to restore per-node collapse states.';
    $('#propertyPanelSize').closest('label').after(button);
  }
  $('#propertyPanelDirection').addEventListener('input', event => {
    propertyPanelSettings().property_panel_direction = Number(event.target.value);
    syncPropertyPanelControls();
  });
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
  $('#propertyPanelDirection').value = String(settings.property_panel_direction);
  $('#propertyPanelDirectionValue').textContent = `${Math.round(settings.property_panel_direction)}°`;
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
  const queue = [{ ref: rootRef, depth: 0, path: new Set([rootRef]) }];
  const seenEdges = new Set();
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
        const nextPath = new Set(current.path);
        nextPath.add(targetRef);
        queue.push({ ref: targetRef, depth: nextDepth, path: nextPath });
      }
    }
  }
  return { rootRef, index, nodes: [...nodes.values()], edges };
}
function displayName(item) {
  if (item.kind === 'entity') return item.owner.name;
  return propertyDisplayName(item.object, item.owner);
}
function nodeClass(item) { return item.kind === 'entity' ? 'entity' : item.propertyType; }
function propertyGroups(index) {
  const groups = new Map();
  for (const item of index.values()) {
    if (item.kind !== 'property' || !['data', 'effect'].includes(item.propertyType)) continue;
    if (!groups.has(item.owner.id)) groups.set(item.owner.id, []);
    groups.get(item.owner.id).push({ ref: item.ref, item });
  }
  for (const items of groups.values()) {
    items.sort((a, b) => {
      const order = { effect: 0, data: 1 };
      const delta = order[a.item.propertyType] - order[b.item.propertyType];
      return delta || displayName(a.item).localeCompare(displayName(b.item));
    });
  }
  return groups;
}
function ensurePropertyPanel(owner, items) {
  let panel = causalProjection.panelElements.get(owner.id);
  if (!panel) {
    panel = document.createElement('div');
    panel.className = 'property-panel';
    panel.dataset.ownerEntityId = owner.id;
    const header = document.createElement('div');
    header.className = 'property-panel-header';
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'property-panel-toggle';
    toggle.textContent = 'PROPS';
    toggle.addEventListener('click', event => {
      event.stopPropagation();
      if (propertyPanelSettings().show_all_props) return;
      setPropertyPanelCollapsed(owner.id, !propertyPanelCollapsed(owner.id));
    });
    header.appendChild(toggle);
    panel.appendChild(header);
    causalNodes.appendChild(panel);
    causalProjection.panelElements.set(owner.id, panel);
  }
  const collapsed = propertyPanelCollapsed(owner.id);
  panel.classList.toggle('collapsed', collapsed);
  panel.classList.toggle('expanded', !collapsed);
  const toggle = panel.querySelector('.property-panel-toggle');
  toggle.disabled = propertyPanelSettings().show_all_props;
  toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');

  const wanted = new Set(items.map(({ ref }) => ref));
  for (const row of [...panel.querySelectorAll('.property-row')]) if (!wanted.has(row.dataset.ref)) row.remove();
  for (const { ref, item } of items) {
    let row = panel.querySelector(`.property-row[data-ref="${CSS.escape(ref)}"]`);
    if (!row) {
      row = document.createElement('button');
      row.type = 'button';
      row.className = 'property-row';
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
      panel.appendChild(row);
    }
    row.className = `property-row ${nodeClass(item)}`;
    row.innerHTML = `<span class="property-type">${nodeClass(item).toUpperCase()}</span><strong>${displayName(item)}</strong>`;
    row.title = `${nodeClass(item).toUpperCase()}: ${displayName(item)}`;
  }
  return panel;
}

function clearCausalProjection() {
  causalProjection.rootEventRef = null;
  causalProjection.graph = null;
  causalProjection.playbackStartedAt = 0;
  document.querySelectorAll('.property-row.reached').forEach(row => row.classList.remove('reached'));
  document.querySelectorAll('.event-button.causal-reached').forEach(button => button.classList.remove('causal-reached'));
  causalSvg.querySelectorAll('.causal-edge,.causal-flow-pulse').forEach(path => path.remove());
}
function triggerCausalProjection(eventRef) {
  document.querySelectorAll('.property-row.reached').forEach(row => row.classList.remove('reached'));
  document.querySelectorAll('.event-button.causal-reached').forEach(button => button.classList.remove('causal-reached'));
  const graph = buildCausalGraph(eventRef, causalProjection.maxDepth);
  causalProjection.rootEventRef = eventRef;
  causalProjection.graph = graph;
  causalProjection.playbackStartedAt = performance.now();
  status(`fired: ${displayName(graph.index.get(eventRef))}`);
}
function projectedPoint(world) {
  const screen = project(world, viewProjection());
  if (!screen) return null;
  const density = devicePixelRatio || 1;
  return { x: screen[0] / density, y: screen[1] / density, world };
}
function propertyPanelBasis() {
  const angle = propertyPanelSettings().property_panel_direction * Math.PI / 180;
  return { x: [Math.cos(angle), Math.sin(angle), 0], down: [Math.sin(angle), -Math.cos(angle), 0] };
}
function propertyPanelGeometry(owner) {
  const half = nodeHalfSize();
  return {
    anchorWorld: [owner.position[0] - half, owner.position[1] - half, owner.position[2]],
    worldPerCssPixel: nodeMasterSize() / 44 * propertyPanelSettings().property_panel_size,
    basis: propertyPanelBasis(),
  };
}
function propertyPanelLocalWorld(geometry, localX, localY) {
  return V.add(geometry.anchorWorld, V.add(V.mul(geometry.basis.x, localX * geometry.worldPerCssPixel), V.mul(geometry.basis.down, localY * geometry.worldPerCssPixel)));
}
function applyPropertyPanelTransform(panel, geometry) {
  const density = devicePixelRatio || 1;
  const origin = project(geometry.anchorWorld, viewProjection());
  const xPoint = project(propertyPanelLocalWorld(geometry, 1, 0), viewProjection());
  const yPoint = project(propertyPanelLocalWorld(geometry, 0, 1), viewProjection());
  if (!origin || !xPoint || !yPoint || !panel.offsetWidth || !panel.offsetHeight) return false;
  const ox = origin[0] / density;
  const oy = origin[1] / density;
  const a = xPoint[0] / density - ox;
  const b = xPoint[1] / density - oy;
  const c = yPoint[0] / density - ox;
  const d = yPoint[1] / density - oy;
  if (Math.abs(a * d - b * c) < .00001) return false;
  panel.style.left = '0px';
  panel.style.top = '0px';
  panel.style.transformOrigin = '0 0';
  panel.style.transform = `matrix(${a}, ${b}, ${c}, ${d}, ${ox}, ${oy})`;
  return true;
}
function propertyRowAnchors(panel, row, geometry) {
  const y = row.offsetTop + row.offsetHeight / 2;
  const left = projectedPoint(propertyPanelLocalWorld(geometry, 0, y));
  const right = projectedPoint(propertyPanelLocalWorld(geometry, panel.offsetWidth, y));
  const center = projectedPoint(propertyPanelLocalWorld(geometry, panel.offsetWidth / 2, y));
  return left && right && center ? { left, right, center } : null;
}
function propertyPanelAnchors(panel, geometry) {
  const y = panel.offsetHeight / 2;
  const left = projectedPoint(propertyPanelLocalWorld(geometry, 0, y));
  const right = projectedPoint(propertyPanelLocalWorld(geometry, panel.offsetWidth, y));
  const center = projectedPoint(propertyPanelLocalWorld(geometry, panel.offsetWidth / 2, y));
  return left && right && center ? { left, right, center } : null;
}
function eventButtonAnchors(ref) {
  const button = document.querySelector(`.event-button[data-event-id="${CSS.escape(ref)}"]`);
  const geometry = entityEditor.eventGeometry.get(ref);
  if (!button || button.hidden || !geometry) return null;
  return worldPlaneProjectedAnchors(button, geometry.centerWorld, geometry.worldPerCssPixel);
}

// Multiple canonical Effect Target contracts between the same source and target
// Entity remain distinct facts, but the projection uses one panel-to-panel route.
function projectedCausalRoutes(graph) {
  const routes = [];
  const groups = new Map();
  for (const edge of graph.edges) {
    if (edge.linkType !== 'effect_target') { routes.push({ edges: [edge], edge }); continue; }
    const source = graph.index.get(edge.from);
    const target = graph.index.get(edge.to);
    if (!source || !target) throw new Error(`causal route endpoint unresolved: ${edge.id}`);
    if (source.owner.id === target.owner.id) { routes.push({ edges: [edge], edge }); continue; }
    const key = `${source.owner.id}\u0000${target.owner.id}`;
    if (!groups.has(key)) groups.set(key, { sourceOwnerId: source.owner.id, targetOwnerId: target.owner.id, edges: [] });
    groups.get(key).edges.push(edge);
  }
  for (const group of groups.values()) {
    const representative = group.edges[0];
    routes.push({
      ...group,
      edges: group.edges,
      edge: { ...representative, id: group.edges.map(item => item.id).join(','), depth: Math.min(...group.edges.map(item => item.depth)), cycle: group.edges.some(item => item.cycle) },
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

function renderCausalProjection() {
  if (!ws) { requestAnimationFrame(renderCausalProjection); return; }
  const graph = causalProjection.rootEventRef ? buildCausalGraph(causalProjection.rootEventRef, causalProjection.maxDepth) : null;
  causalProjection.graph = graph;
  const index = graph ? graph.index : canonicalIndex();
  const groups = propertyGroups(index);
  const graphDepth = new Map(graph ? graph.nodes.map(node => [node.ref, node.depth]) : []);
  const positions = new Map();
  const panelPositions = new Map();
  const visibleOwners = new Set();
  const elapsed = graph ? performance.now() - causalProjection.playbackStartedAt : 0;
  const stepMs = Math.max(120, eventSettings().effect_travel_duration * 350);
  causalSvg.setAttribute('width', String(innerWidth));
  causalSvg.setAttribute('height', String(innerHeight));
  causalSvg.setAttribute('viewBox', `0 0 ${innerWidth} ${innerHeight}`);
  causalSvg.querySelectorAll('.causal-edge').forEach(path => path.remove());

  for (const [ownerId, items] of groups) {
    const owner = items[0].item.owner;
    visibleOwners.add(ownerId);
    const panel = ensurePropertyPanel(owner, items);
    const geometry = propertyPanelGeometry(owner);
    panel.hidden = false;
    if (!applyPropertyPanelTransform(panel, geometry)) { panel.hidden = true; continue; }
    const panelAnchors = propertyPanelAnchors(panel, geometry);
    if (panelAnchors) panelPositions.set(ownerId, panelAnchors);
    for (const { ref } of items) {
      const row = panel.querySelector(`.property-row[data-ref="${CSS.escape(ref)}"]`);
      const depth = graphDepth.get(ref);
      row.classList.toggle('reached', depth !== undefined && elapsed >= depth * stepMs);
      const anchors = propertyRowAnchors(panel, row, geometry);
      if (anchors) positions.set(ref, anchors);
    }
  }
  for (const [ownerId, element] of causalProjection.panelElements) if (!visibleOwners.has(ownerId)) element.hidden = true;
  if (!graph) { requestAnimationFrame(renderCausalProjection); return; }

  const rootAnchors = eventButtonAnchors(graph.rootRef);
  if (rootAnchors) positions.set(graph.rootRef, rootAnchors);
  for (const node of graph.nodes) {
    if (node.ref === graph.rootRef) continue;
    const item = graph.index.get(node.ref);
    if (item.propertyType !== 'event') continue;
    const anchors = eventButtonAnchors(node.ref);
    if (anchors) positions.set(node.ref, anchors);
    const button = document.querySelector(`.event-button[data-event-id="${CSS.escape(node.ref)}"]`);
    if (button) button.classList.toggle('causal-reached', elapsed >= node.depth * stepMs);
  }

  const svgNS = 'http://www.w3.org/2000/svg';
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
    const path = document.createElementNS(svgNS, 'path');
    const state = causalPlaybackState(route.edges, elapsed, stepMs);
    path.setAttribute('class', `causal-edge ${edge.linkType}${route.panelRoute ? ' aggregated' : ''}${edge.cycle ? ' cycle' : ''}${state.active ? ' active' : ''}${state.reached ? ' reached' : ''}`);
    path.setAttribute('d', `M ${x1} ${y1} C ${x1 + direction * bend} ${y1}, ${x2 - direction * bend} ${y2}, ${x2} ${y2}`);
    path.setAttribute('marker-end', 'url(#causalArrow)');
    path.dataset.linkId = edge.id;
    path.style.strokeWidth = `${Math.max(.7, Math.min(5, worldPixelsAt(graph.index.get(route.edges[0].from).owner.position) / 24))}px`;
    causalSvg.appendChild(path);
  }
  requestAnimationFrame(renderCausalProjection);
}

document.addEventListener('click', event => {
  const button = event.target.closest?.('.event-button');
  if (button?.dataset.eventId) triggerCausalProjection(button.dataset.eventId);
}, true);
window.addEventListener('keydown', event => { if (event.key === 'Escape' && causalProjection.rootEventRef) clearCausalProjection(); });
window.addEventListener('load', () => {
  ensurePropertyPanelControls();
  syncPropertyPanelControls();
  syncEventRouteVisibility();
});
requestAnimationFrame(renderCausalProjection);
