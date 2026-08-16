// Canonical Event -> Effect -> target -> Event impact projection.
// Projection instances are view-only and remain attached to their canonical owner Entities.
// Only Entity labels are fixed-size camera billboards. Data/Effect panels are true Entity-child world planes.

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

function propertyPanelSettings() {
  ws.settings ??= {};
  ws.settings.view_defaults ??= {};
  const view = ws.settings.view_defaults;
  view.property_panel_direction ??= 0;
  view.property_panel_size ??= 1;
  view.property_panel_collapsed ??= {};
  view.show_all_props ??= false;
  return view;
}

function propertyPanelCollapsed(ownerId) {
  const settings = propertyPanelSettings();
  if (settings.show_all_props) return false;
  return Boolean(settings.property_panel_collapsed?.[ownerId]);
}

function setPropertyPanelCollapsed(ownerId, collapsed) {
  const settings = propertyPanelSettings();
  settings.property_panel_collapsed ??= {};
  if (collapsed) settings.property_panel_collapsed[ownerId] = true;
  else delete settings.property_panel_collapsed[ownerId];
}

function ensurePropertyPanelControls() {
  const controls = document.querySelector('#viewControls');
  if (!controls) return;

  const directionInput = document.querySelector('#propertyPanelDirection');
  const directionLabel = directionInput?.closest('label')?.querySelector('span');
  if (directionLabel) directionLabel.textContent = 'PROPS ANGLE';

  if (!document.querySelector('#propertyPanelSize')) {
    const sizeControl = document.createElement('label');
    sizeControl.className = 'node-size-control property-size-control';
    sizeControl.innerHTML = `
      <span>PROPS SIZE</span>
      <input id="propertyPanelSize" type="range" min="0.25" max="2.50" step="0.05" value="1">
      <output id="propertyPanelSizeValue">1.00×</output>
    `;
    const directionControl = directionInput?.closest('label');
    directionControl?.after(sizeControl);
  }

  if (!document.querySelector('#showAllProps')) {
    const button = document.createElement('button');
    button.id = 'showAllProps';
    button.type = 'button';
    button.className = 'show-all-props-control';
    button.textContent = 'SHOW ALL PROPS';
    button.title = 'Temporarily expand every node Property panel. Disable to restore node-specific collapsed states.';
    document.querySelector('#propertyPanelSize')?.closest('label')?.after(button);
  }

  const direction = document.querySelector('#propertyPanelDirection');
  if (direction && !direction.dataset.propertyPanelBound) {
    direction.dataset.propertyPanelBound = '1';
    direction.addEventListener('input', event => {
      propertyPanelSettings().property_panel_direction = Number(event.target.value);
      syncPropertyPanelControls();
    });
  }

  const size = document.querySelector('#propertyPanelSize');
  if (size && !size.dataset.propertyPanelBound) {
    size.dataset.propertyPanelBound = '1';
    size.addEventListener('input', event => {
      propertyPanelSettings().property_panel_size = Number(event.target.value);
      syncPropertyPanelControls();
    });
  }

  const showAll = document.querySelector('#showAllProps');
  if (showAll && !showAll.dataset.propertyPanelBound) {
    showAll.dataset.propertyPanelBound = '1';
    showAll.addEventListener('click', () => {
      const settings = propertyPanelSettings();
      settings.show_all_props = !settings.show_all_props;
      syncPropertyPanelControls();
    });
  }
}

function syncPropertyPanelControls() {
  const settings = propertyPanelSettings();
  const direction = document.querySelector('#propertyPanelDirection');
  const directionOutput = document.querySelector('#propertyPanelDirectionValue');
  const size = document.querySelector('#propertyPanelSize');
  const sizeOutput = document.querySelector('#propertyPanelSizeValue');
  const showAll = document.querySelector('#showAllProps');

  if (direction) direction.value = String(Number(settings.property_panel_direction || 0));
  if (directionOutput) directionOutput.textContent = `${Math.round(Number(settings.property_panel_direction || 0))}°`;
  if (size) size.value = String(Number(settings.property_panel_size || 1));
  if (sizeOutput) sizeOutput.textContent = `${Number(settings.property_panel_size || 1).toFixed(2)}×`;
  if (showAll) {
    showAll.classList.toggle('active', Boolean(settings.show_all_props));
    showAll.setAttribute('aria-pressed', settings.show_all_props ? 'true' : 'false');
  }
}

function canonicalIndex() {
  const index = new Map();
  for (const entity of ws.entities) {
    index.set(entity.id, { ref: entity.id, kind: 'entity', entity, owner: entity, object: entity });
    for (const property of entity.properties || []) {
      index.set(property.id, {
        ref: property.id,
        kind: 'property',
        propertyType: property.property_type_ref,
        entity,
        owner: entity,
        object: property,
      });
    }
  }
  return index;
}

function canonicalLinks() {
  return ws.entities.flatMap(owner => (owner.properties || [])
    .filter(property => property.property_type_ref === 'link')
    .map(property => ({ owner, property, value: property.value || {} })));
}

function causalOutgoing(ref, index) {
  const current = index.get(ref);
  if (!current) return [];
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
  if (!root || root.propertyType !== 'event') return null;

  const nodes = new Map([[rootRef, { ref: rootRef, depth: 0 }]]);
  const edges = [];
  const queue = [{ ref: rootRef, depth: 0, path: new Set([rootRef]) }];
  const seenEdges = new Set();

  while (queue.length) {
    const current = queue.shift();
    if (current.depth >= maxDepth) continue;
    for (const { property, value } of causalOutgoing(current.ref, index)) {
      const targetRef = value.child_ref;
      if (!index.has(targetRef)) continue;
      const edgeKey = `${property.id}:${current.ref}:${targetRef}`;
      if (seenEdges.has(edgeKey)) continue;
      seenEdges.add(edgeKey);
      const cycle = current.path.has(targetRef);
      const nextDepth = current.depth + 1;
      edges.push({ id: property.id, from: current.ref, to: targetRef, linkType: value.link_type_ref, depth: nextDepth, cycle });
      const existing = nodes.get(targetRef);
      if (!existing || nextDepth < existing.depth) nodes.set(targetRef, { ref: targetRef, depth: nextDepth });
      if (cycle) continue;
      const nextPath = new Set(current.path);
      nextPath.add(targetRef);
      queue.push({ ref: targetRef, depth: nextDepth, path: nextPath });
    }
  }

  return { rootRef, index, nodes: [...nodes.values()], edges };
}

function displayName(item) {
  if (!item) return 'Missing';
  if (item.kind === 'entity') return item.entity.name || item.entity.id;
  return propertyDisplayName(item.object, item.owner);
}

function nodeClass(item) {
  if (!item) return 'missing';
  if (item.kind === 'entity') return 'entity';
  return item.propertyType || 'property';
}

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
      const typeOrder = (order[a.item.propertyType] ?? 9) - (order[b.item.propertyType] ?? 9);
      return typeOrder || displayName(a.item).localeCompare(displayName(b.item));
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
    toggle.title = 'Collapse or expand this node Property panel';
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
  if (toggle) {
    toggle.disabled = Boolean(propertyPanelSettings().show_all_props);
    toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    toggle.title = propertyPanelSettings().show_all_props
      ? 'SHOW ALL PROPS is active; disable it to restore node-specific Property panel states'
      : 'Collapse or expand this node Property panel';
  }

  const wanted = new Set(items.map(({ ref }) => ref));
  for (const row of [...panel.querySelectorAll('.property-row')]) {
    if (!wanted.has(row.dataset.ref)) row.remove();
  }

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
        if (!fresh) return;
        if (fresh.owner) {
          selected = new Set([fresh.owner.id]);
          setActiveEntity(fresh.owner.id);
          inspect();
          updateButtons();
        }
        status(`${fresh.propertyType || fresh.kind}: ${displayName(fresh)}`);
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
  causalSvg.querySelectorAll('.causal-edge').forEach(path => path.remove());
}

function triggerCausalProjection(eventRef) {
  document.querySelectorAll('.property-row.reached').forEach(row => row.classList.remove('reached'));
  document.querySelectorAll('.event-button.causal-reached').forEach(button => button.classList.remove('causal-reached'));
  const graph = buildCausalGraph(eventRef, causalProjection.maxDepth);
  if (!graph) { status(`Event ${eventRef} has no resolvable causal root`); return; }
  causalProjection.rootEventRef = eventRef;
  causalProjection.graph = graph;
  causalProjection.playbackStartedAt = performance.now();
  const eventItem = graph.index.get(eventRef);
  status(`fired: ${displayName(eventItem)}`);
}

function projectedPoint(world) {
  const screen = project(world, viewProjection());
  if (!screen) return null;
  const density = devicePixelRatio || 1;
  return { x: screen[0] / density, y: screen[1] / density, world };
}

function propertyPanelBasis() {
  const angle = Number(propertyPanelSettings().property_panel_direction || 0) * Math.PI / 180;
  return {
    x: [Math.cos(angle), Math.sin(angle), 0],
    down: [Math.sin(angle), -Math.cos(angle), 0],
  };
}

function propertyPanelGeometry(owner) {
  const half = nodeHalfSize();
  const settings = propertyPanelSettings();
  return {
    // Exact parent attachment: Property panel top-left == Entity bottom-left in world XY.
    anchorWorld: [owner.position[0] - half, owner.position[1] - half, owner.position[2]],
    worldPerCssPixel: nodeMasterSize() / 44 * Number(settings.property_panel_size || 1),
    basis: propertyPanelBasis(),
  };
}

function propertyPanelLocalWorld(geometry, localX, localY) {
  return V.add(
    geometry.anchorWorld,
    V.add(
      V.mul(geometry.basis.x, localX * geometry.worldPerCssPixel),
      V.mul(geometry.basis.down, localY * geometry.worldPerCssPixel),
    ),
  );
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
  const determinant = a * d - b * c;
  if (Math.abs(determinant) < 0.00001) return false;

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
  if (!left || !right || !center) return null;
  return { left, right, center };
}

function propertyPanelAnchors(panel, geometry) {
  const y = panel.offsetHeight / 2;
  const left = projectedPoint(propertyPanelLocalWorld(geometry, 0, y));
  const right = projectedPoint(propertyPanelLocalWorld(geometry, panel.offsetWidth, y));
  const center = projectedPoint(propertyPanelLocalWorld(geometry, panel.offsetWidth / 2, y));
  if (!left || !right || !center) return null;
  return { left, right, center };
}

function eventButtonAnchors(ref) {
  const button = document.querySelector(`.event-button[data-event-id="${CSS.escape(ref)}"]`);
  const geometry = entityEditor.eventGeometry.get(ref);
  if (!button || button.hidden || !geometry) return null;
  return worldPlaneProjectedAnchors(button, geometry.centerWorld, geometry.worldPerCssPixel);
}

function projectedCausalRoutes(graph) {
  const routes = [];
  const effectTargetGroups = new Map();

  for (const edge of graph.edges) {
    if (edge.linkType !== 'effect_target') {
      routes.push({ edges: [edge], edge });
      continue;
    }

    const source = graph.index.get(edge.from);
    const target = graph.index.get(edge.to);
    const sourceOwnerId = source?.owner?.id;
    const targetOwnerId = target?.owner?.id;

    if (!sourceOwnerId || !targetOwnerId || sourceOwnerId === targetOwnerId) {
      routes.push({ edges: [edge], edge });
      continue;
    }

    const key = `${sourceOwnerId}\u0000${targetOwnerId}`;
    if (!effectTargetGroups.has(key)) {
      effectTargetGroups.set(key, {
        sourceOwnerId,
        targetOwnerId,
        edges: [],
      });
    }
    effectTargetGroups.get(key).edges.push(edge);
  }

  for (const group of effectTargetGroups.values()) {
    const edge = group.edges[0];
    routes.push({
      ...group,
      edge: {
        ...edge,
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

function renderCausalProjection() {
  const graph = causalProjection.rootEventRef ? buildCausalGraph(causalProjection.rootEventRef, causalProjection.maxDepth) : null;
  causalProjection.graph = graph;
  const index = graph?.index || canonicalIndex();
  const groups = propertyGroups(index);
  const graphDepth = new Map((graph?.nodes || []).map(node => [node.ref, node.depth]));
  const positions = new Map();
  const panelPositions = new Map();
  const visibleOwners = new Set();
  const elapsed = graph ? performance.now() - causalProjection.playbackStartedAt : 0;
  const stepMs = Math.max(120, Number(ws.settings.event_playback.effect_travel_duration || 1.2) * 350);

  causalSvg.setAttribute('width', String(innerWidth));
  causalSvg.setAttribute('height', String(innerHeight));
  causalSvg.setAttribute('viewBox', `0 0 ${innerWidth} ${innerHeight}`);
  causalSvg.querySelectorAll('.causal-edge').forEach(path => path.remove());

  for (const [ownerId, items] of groups) {
    const owner = items[0]?.item?.owner;
    if (!owner) continue;
    visibleOwners.add(ownerId);
    const panel = ensurePropertyPanel(owner, items);
    const geometry = propertyPanelGeometry(owner);
    panel.hidden = false;

    if (!applyPropertyPanelTransform(panel, geometry)) {
      panel.hidden = true;
      continue;
    }

    const panelAnchors = propertyPanelAnchors(panel, geometry);
    if (panelAnchors) panelPositions.set(ownerId, panelAnchors);

    for (const { ref } of items) {
      const row = panel.querySelector(`.property-row[data-ref="${CSS.escape(ref)}"]`);
      if (!row) continue;
      const depth = graphDepth.get(ref);
      row.classList.toggle('reached', depth !== undefined && elapsed >= depth * stepMs);
      const anchors = propertyRowAnchors(panel, row, geometry);
      if (anchors) positions.set(ref, anchors);
    }
  }

  for (const [ownerId, element] of causalProjection.panelElements) {
    if (!visibleOwners.has(ownerId)) element.hidden = true;
  }

  if (!graph) {
    requestAnimationFrame(renderCausalProjection);
    return;
  }

  const rootAnchors = eventButtonAnchors(graph.rootRef);
  if (rootAnchors) positions.set(graph.rootRef, rootAnchors);

  for (const node of graph.nodes) {
    if (node.ref === graph.rootRef) continue;
    const item = graph.index.get(node.ref);
    if (!item || item.propertyType !== 'event') continue;
    const anchors = eventButtonAnchors(node.ref);
    if (anchors) positions.set(node.ref, anchors);
    const eventButton = document.querySelector(`.event-button[data-event-id="${CSS.escape(node.ref)}"]`);
    if (eventButton) eventButton.classList.toggle('causal-reached', elapsed >= node.depth * stepMs);
  }

  const svgNS = 'http://www.w3.org/2000/svg';
  for (const route of projectedCausalRoutes(graph)) {
    const edge = route.edge;
    const from = route.panelRoute ? panelPositions.get(route.sourceOwnerId) : positions.get(edge.from);
    const to = route.panelRoute ? panelPositions.get(route.targetOwnerId) : positions.get(edge.to);
    if (!from || !to) continue;
    const start = from.right || from.center;
    const end = to.left || to.center;
    if (!start || !end) continue;
    const x1 = start.x;
    const y1 = start.y;
    const x2 = end.x;
    const y2 = end.y;
    const bend = Math.max(24, Math.abs(x2 - x1) * .35);
    const direction = x2 >= x1 ? 1 : -1;
    const path = document.createElementNS(svgNS, 'path');
    const { active, reached } = causalPlaybackState(route.edges, elapsed, stepMs);
    path.setAttribute('class', `causal-edge ${edge.linkType}${route.panelRoute ? ' aggregated' : ''}${edge.cycle ? ' cycle' : ''}${active ? ' active' : ''}${reached ? ' reached' : ''}`);
    path.setAttribute('d', `M ${x1} ${y1} C ${x1 + direction * bend} ${y1}, ${x2 - direction * bend} ${y2}, ${x2} ${y2}`);
    path.setAttribute('marker-end', 'url(#causalArrow)');
    path.dataset.linkId = edge.id;
    if (route.panelRoute) path.dataset.linkCount = String(route.edges.length);
    const sourceItem = graph.index.get(route.edges[0].from);
    const sourceWorld = sourceItem?.owner?.position || [0, 0, 0];
    path.style.strokeWidth = `${Math.max(.7, Math.min(5, worldPixelsAt(sourceWorld) / 24))}px`;
    causalSvg.appendChild(path);
  }

  requestAnimationFrame(renderCausalProjection);
}

async function loadStartingScene() {
  const response = await fetch('/api/starting-scene');
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error);
  ws = payload.workspace;
  ensureWorkspace();
  propertyPanelSettings();
  syncCatalog();
  syncSettings();
  ensurePropertyPanelControls();
  syncPropertyPanelControls();
  selected.clear();
  activeEntityId = null;
  lookAtEntityId = null;
  clearLink();
  clearCausalProjection();
  inspect();
  updateButtons();
  status('starter scene: click NEW ORDER to fire');
}

document.addEventListener('click', event => {
  const button = event.target.closest?.('.event-button');
  if (!button) return;
  const eventRef = button.dataset.eventId;
  if (eventRef) triggerCausalProjection(eventRef);
}, true);

window.addEventListener('keydown', event => {
  if (event.key === 'Escape' && causalProjection.rootEventRef) clearCausalProjection();
});

propertyPanelSettings();
ensurePropertyPanelControls();
syncPropertyPanelControls();
requestAnimationFrame(renderCausalProjection);
loadStartingScene().catch(error => {
  window.reportStructureError?.(error, { type: 'starting_scene_error' });
  status(`starter scene error: ${error.message}`);
});
