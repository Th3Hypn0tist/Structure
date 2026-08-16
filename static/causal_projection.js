// Canonical Event -> Effect -> target -> Event impact projection.
// Projection instances are view-only and remain attached to their canonical owner Entities.
// Only Entity labels are fixed-size camera billboards. Data/Effect panels are owner-relative world-space UI.

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
  view.property_panel_direction ??= -90;
  view.property_panel_distance ??= 1.35;
  return view;
}

function syncPropertyPanelDirectionControl() {
  const input = document.querySelector('#propertyPanelDirection');
  const output = document.querySelector('#propertyPanelDirectionValue');
  if (!input || !output) return;
  const value = Number(propertyPanelSettings().property_panel_direction ?? -90);
  input.value = String(value);
  output.textContent = `${Math.round(value)}°`;
}

const propertyDirectionInput = document.querySelector('#propertyPanelDirection');
if (propertyDirectionInput) {
  propertyDirectionInput.addEventListener('input', event => {
    const value = Number(event.target.value);
    propertyPanelSettings().property_panel_direction = value;
    const output = document.querySelector('#propertyPanelDirectionValue');
    if (output) output.textContent = `${Math.round(value)}°`;
  });
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
    causalNodes.appendChild(panel);
    causalProjection.panelElements.set(owner.id, panel);
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

function eventButtonRect(ref) {
  const button = document.querySelector(`.event-button[data-event-id="${CSS.escape(ref)}"]`);
  if (!button || button.hidden) return null;
  const rect = button.getBoundingClientRect();
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
}

function propertyPanelWorldPoint(owner) {
  const settings = propertyPanelSettings();
  const angle = Number(settings.property_panel_direction ?? -90) * Math.PI / 180;
  const distance = Number(settings.property_panel_distance ?? 1.35) * nodeMasterSize();
  return [
    owner.position[0] + Math.cos(angle) * distance,
    owner.position[1] + Math.sin(angle) * distance,
    owner.position[2],
  ];
}

function rectPoint(rect) {
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
}

function renderCausalProjection() {
  const graph = causalProjection.rootEventRef ? buildCausalGraph(causalProjection.rootEventRef, causalProjection.maxDepth) : null;
  causalProjection.graph = graph;
  const index = graph?.index || canonicalIndex();
  const groups = propertyGroups(index);
  const graphDepth = new Map((graph?.nodes || []).map(node => [node.ref, node.depth]));
  const positions = new Map();
  const visibleOwners = new Set();
  const density = devicePixelRatio || 1;
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
    const world = propertyPanelWorldPoint(owner);
    const screen = project(world, viewProjection());
    const panel = ensurePropertyPanel(owner, items);
    if (!screen) { panel.hidden = true; continue; }

    const scale = Math.max(.08, worldPixelsAt(world) / 44) * nodeMasterSize();
    panel.hidden = false;
    panel.style.left = `${screen[0] / density}px`;
    panel.style.top = `${screen[1] / density}px`;
    panel.style.setProperty('--property-world-scale', String(scale));

    for (const { ref } of items) {
      const row = panel.querySelector(`.property-row[data-ref="${CSS.escape(ref)}"]`);
      if (!row) continue;
      const depth = graphDepth.get(ref);
      row.classList.toggle('reached', depth !== undefined && elapsed >= depth * stepMs);
      positions.set(ref, rectPoint(row.getBoundingClientRect()));
    }
  }

  for (const [ownerId, element] of causalProjection.panelElements) {
    if (!visibleOwners.has(ownerId)) element.hidden = true;
  }

  if (!graph) {
    requestAnimationFrame(renderCausalProjection);
    return;
  }

  const rootRect = eventButtonRect(graph.rootRef);
  if (rootRect) positions.set(graph.rootRef, rootRect);

  for (const node of graph.nodes) {
    if (node.ref === graph.rootRef) continue;
    const item = graph.index.get(node.ref);
    if (!item || item.propertyType !== 'event') continue;
    const rect = eventButtonRect(node.ref);
    if (rect) positions.set(node.ref, rect);
    const eventButton = document.querySelector(`.event-button[data-event-id="${CSS.escape(node.ref)}"]`);
    if (eventButton) eventButton.classList.toggle('causal-reached', elapsed >= node.depth * stepMs);
  }

  const svgNS = 'http://www.w3.org/2000/svg';
  for (const edge of graph.edges) {
    const from = positions.get(edge.from);
    const to = positions.get(edge.to);
    if (!from || !to) continue;
    const x1 = from.right ?? from.x;
    const y1 = from.y;
    const x2 = to.left ?? to.x;
    const y2 = to.y;
    const bend = Math.max(24, Math.abs(x2 - x1) * .35);
    const direction = x2 >= x1 ? 1 : -1;
    const path = document.createElementNS(svgNS, 'path');
    const activeAt = Math.max(0, edge.depth - 1) * stepMs;
    const reached = elapsed >= activeAt + stepMs * .75;
    const active = elapsed >= activeAt && elapsed < activeAt + stepMs * .9;
    path.setAttribute('class', `causal-edge ${edge.linkType}${edge.cycle ? ' cycle' : ''}${active ? ' active' : ''}${reached ? ' reached' : ''}`);
    path.setAttribute('d', `M ${x1} ${y1} C ${x1 + direction * bend} ${y1}, ${x2 - direction * bend} ${y2}, ${x2} ${y2}`);
    path.setAttribute('marker-end', 'url(#causalArrow)');
    path.dataset.linkId = edge.id;
    const sourceItem = graph.index.get(edge.from);
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
  syncPropertyPanelDirectionControl();
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
syncPropertyPanelDirectionControl();
requestAnimationFrame(renderCausalProjection);
loadStartingScene().catch(error => {
  window.reportStructureError?.(error, { type: 'starting_scene_error' });
  status(`starter scene error: ${error.message}`);
});
