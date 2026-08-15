// Canonical Event -> Effect -> target -> Event impact projection.
// This is presentation only: traversal follows explicit canonical Link Properties.

const CAUSAL_LINK_TYPES = new Set([
  'event_effect',
  'effect_target',
  'event_condition',
  'event_input',
  'event_read',
  'event_cause',
  'event_output',
]);

const causalProjection = {
  rootEventRef: null,
  maxDepth: 8,
  nodeElements: new Map(),
  graph: null,
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

function canonicalIndex() {
  const index = new Map();
  for (const entity of ws.entities) {
    index.set(entity.id, {
      ref: entity.id,
      kind: 'entity',
      entity,
      owner: entity,
      object: entity,
    });
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
  return ws.entities.flatMap(owner =>
    (owner.properties || [])
      .filter(property => property.property_type_ref === 'link')
      .map(property => ({ owner, property, value: property.value || {} }))
  );
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

  return canonicalLinks().filter(({ value }) =>
    value.parent_ref === ref && allowed.has(value.link_type_ref)
  );
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
      edges.push({
        id: property.id,
        from: current.ref,
        to: targetRef,
        linkType: value.link_type_ref,
        cycle,
      });

      const nextDepth = current.depth + 1;
      const existing = nodes.get(targetRef);
      if (!existing || nextDepth < existing.depth) nodes.set(targetRef, { ref: targetRef, depth: nextDepth });
      if (cycle) continue;

      const nextPath = new Set(current.path);
      nextPath.add(targetRef);
      queue.push({ ref: targetRef, depth: nextDepth, path: nextPath });
    }
  }

  const result = { rootRef, index, nodes: [...nodes.values()], edges };
  causalProjection.graph = result;
  return result;
}

function displayName(item) {
  if (!item) return 'missing';
  if (item.kind === 'entity') return item.entity.name || item.entity.id;

  const property = item.object;
  const value = property.value || {};
  if (property.property_type_ref === 'event') return value.event_type_ref || property.id;
  if (property.property_type_ref === 'effect') return value.effect_type_ref || property.id;
  if (property.property_type_ref === 'function') return value.function_type_ref || property.id;
  return property.id;
}

function ownerName(item) {
  return item?.owner?.name || item?.owner?.id || '';
}

function nodeClass(item) {
  if (!item) return 'missing';
  if (item.kind === 'entity') return 'entity';
  return item.propertyType || 'property';
}

function ensureCausalNode(ref, item) {
  let element = causalProjection.nodeElements.get(ref);
  if (!element) {
    element = document.createElement('button');
    element.type = 'button';
    element.className = 'causal-node';
    element.dataset.ref = ref;
    element.onclick = event => {
      event.stopPropagation();
      const fresh = canonicalIndex().get(ref);
      if (!fresh) return;

      if (fresh.propertyType === 'event') {
        openCausalProjection(ref);
        return;
      }

      if (fresh.owner) {
        selected = new Set([fresh.owner.id]);
        setActiveEntity(fresh.owner.id);
        inspect();
        updateButtons();
      }
      status(`${fresh.propertyType || fresh.kind}: ${ref}`);
    };
    causalNodes.appendChild(element);
    causalProjection.nodeElements.set(ref, element);
  }

  element.className = `causal-node ${nodeClass(item)}`;
  element.innerHTML = `<strong>${displayName(item)}</strong><small>${nodeClass(item).toUpperCase()} · ${ownerName(item)}</small>`;
  return element;
}

function clearCausalProjection() {
  causalProjection.rootEventRef = null;
  causalProjection.graph = null;
  for (const element of causalProjection.nodeElements.values()) element.hidden = true;
  causalSvg.querySelectorAll('.causal-edge').forEach(path => path.remove());
}

function openCausalProjection(eventRef) {
  if (causalProjection.rootEventRef === eventRef) {
    clearCausalProjection();
    status('causal projection closed');
    return;
  }

  causalProjection.rootEventRef = eventRef;
  buildCausalGraph(eventRef, causalProjection.maxDepth);
  status(`impact: ${eventRef}`);
}

function rootEventButton() {
  if (!causalProjection.rootEventRef) return null;
  return document.querySelector(`.event-button[data-event-id="${CSS.escape(causalProjection.rootEventRef)}"]`);
}

function renderCausalProjection() {
  const graph = causalProjection.rootEventRef
    ? buildCausalGraph(causalProjection.rootEventRef, causalProjection.maxDepth)
    : null;
  const rootButton = rootEventButton();

  causalSvg.setAttribute('width', String(innerWidth));
  causalSvg.setAttribute('height', String(innerHeight));
  causalSvg.setAttribute('viewBox', `0 0 ${innerWidth} ${innerHeight}`);
  causalSvg.querySelectorAll('.causal-edge').forEach(path => path.remove());

  if (!graph || !rootButton || rootButton.hidden) {
    for (const element of causalProjection.nodeElements.values()) element.hidden = true;
    requestAnimationFrame(renderCausalProjection);
    return;
  }

  const rootRect = rootButton.getBoundingClientRect();
  const rootPoint = {
    x: rootRect.right + 5,
    y: rootRect.top + rootRect.height / 2,
  };

  const layers = new Map();
  for (const node of graph.nodes) {
    if (node.depth === 0) continue;
    if (!layers.has(node.depth)) layers.set(node.depth, []);
    layers.get(node.depth).push(node.ref);
  }

  for (const refs of layers.values()) refs.sort();
  const positions = new Map([[graph.rootRef, rootPoint]]);
  const visibleRefs = new Set();
  const columnWidth = 148;
  const rowHeight = 50;

  for (const [depth, refs] of [...layers.entries()].sort((a, b) => a[0] - b[0])) {
    const startY = rootPoint.y - ((refs.length - 1) * rowHeight) / 2;
    refs.forEach((ref, index) => {
      const item = graph.index.get(ref);
      const element = ensureCausalNode(ref, item);
      visibleRefs.add(ref);
      element.hidden = false;
      element.style.left = `${rootPoint.x + depth * columnWidth}px`;
      element.style.top = `${startY + index * rowHeight}px`;

      const width = element.offsetWidth || 132;
      const height = element.offsetHeight || 36;
      positions.set(ref, {
        x: rootPoint.x + depth * columnWidth,
        y: startY + index * rowHeight,
        left: rootPoint.x + depth * columnWidth - width / 2,
        right: rootPoint.x + depth * columnWidth + width / 2,
        top: startY + index * rowHeight - height / 2,
        bottom: startY + index * rowHeight + height / 2,
      });
    });
  }

  for (const [ref, element] of causalProjection.nodeElements) {
    if (!visibleRefs.has(ref)) element.hidden = true;
  }

  const svgNS = 'http://www.w3.org/2000/svg';
  for (const edge of graph.edges) {
    const from = positions.get(edge.from);
    const to = positions.get(edge.to);
    if (!from || !to) continue;

    const x1 = edge.from === graph.rootRef ? from.x : from.right;
    const y1 = from.y;
    const x2 = to.left;
    const y2 = to.y;
    const bend = Math.max(28, (x2 - x1) * .45);
    const path = document.createElementNS(svgNS, 'path');
    path.setAttribute('class', `causal-edge ${edge.linkType}${edge.cycle ? ' cycle' : ''}`);
    path.setAttribute('d', `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`);
    path.setAttribute('marker-end', 'url(#causalArrow)');
    path.dataset.linkId = edge.id;
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
  syncCatalog();
  syncSettings();
  selected.clear();
  activeEntityId = null;
  clearLink();
  inspect();
  updateButtons();
  causalProjection.rootEventRef = 'EVENT_NEW_ORDER';
  buildCausalGraph(causalProjection.rootEventRef, causalProjection.maxDepth);
  status('starter scene: New Order');
}

// Capture phase is intentional: the Event button's own pulse handler stops bubbling.
document.addEventListener('click', event => {
  const button = event.target.closest?.('.event-button');
  if (!button) return;
  const eventRef = button.dataset.eventId;
  if (eventRef) openCausalProjection(eventRef);
}, true);

window.addEventListener('keydown', event => {
  if (event.key === 'Escape' && causalProjection.rootEventRef) clearCausalProjection();
});

requestAnimationFrame(renderCausalProjection);
loadStartingScene().catch(error => status(`starter scene error: ${error.message}`));
