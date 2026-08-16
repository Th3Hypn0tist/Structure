// Generic link projection owns visual attachment and direction flow only.
// Canonical Link Properties remain unchanged.
//
// Direction material is a procedural equivalent of a 100 px transparent strip
// containing one white pixel. Generic links tile a scaled copy of that mask;
// Event routes use one white sample stretched over the whole route and run it
// once from 0 -> 100 when the Event propagates.

const LINK_FLOW_MASK_PIXELS = 100;
const LINK_FLOW_REPEAT_SCALE = 0.26;
const LINK_FLOW_MIN_PULSE_PX = 1.2;

const linkProjection = {
  ports: new Map(),
};

const linkFlowSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
linkFlowSvg.id = 'linkFlowLines';
linkFlowSvg.setAttribute('aria-hidden', 'true');
Object.assign(linkFlowSvg.style, {
  position: 'fixed',
  inset: '0',
  pointerEvents: 'none',
  zIndex: '9',
  overflow: 'visible',
});
document.body.appendChild(linkFlowSvg);

function linkProjectionColor(property, variant = 'flow') {
  const ruleset = rulesetMap().get(property.ruleset_ref);
  const colorSpace = colorSpaceMap().get(ruleset?.color_space_ref);
  const rgb = colorSpace?.colors?.[variant] || colorSpace?.colors?.base || [.72, .78, .86];

  // The mask sample itself is white. A subtractive material only needs the
  // complementary channel values; 1 - (1 - rgb) resolves the requested tint.
  const tinted = rgb.slice(0, 3).map(value => {
    const clamped = Math.max(0, Math.min(1, Number(value)));
    const subtract = 1 - clamped;
    return 1 - subtract;
  });
  return `rgb(${tinted.map(value => Math.round(value * 255)).join(',')})`;
}

function linkProjectionTypeColor(linkType) {
  const ruleset = (ws.rulesets || []).find(item => item.property_type_ref === 'link' && item.link_type_ref === linkType);
  const colorSpace = colorSpaceMap().get(ruleset?.color_space_ref);
  const rgb = colorSpace?.colors?.flow || colorSpace?.colors?.base || [.72, .78, .86];
  return `rgb(${rgb.slice(0, 3).map(value => Math.round(Math.max(0, Math.min(1, Number(value))) * 255)).join(',')})`;
}

function linkProjectionTypeOrder(types) {
  const order = new Map();
  let index = 0;
  for (const ruleset of ws.rulesets || []) {
    if (ruleset.property_type_ref !== 'link' || !ruleset.link_type_ref || order.has(ruleset.link_type_ref)) continue;
    order.set(ruleset.link_type_ref, index++);
  }
  return [...types].sort((left, right) =>
    (order.get(left) ?? 10000) - (order.get(right) ?? 10000) || left.localeCompare(right));
}

function linkProjectionPanelBottomY(entity) {
  let bottom = entity.position[1] - nodeHalfSize();
  if (typeof causalProjection === 'undefined' || typeof propertyPanelGeometry !== 'function' || typeof propertyPanelLocalWorld !== 'function') {
    return bottom;
  }

  const panel = causalProjection.panelElements?.get(entity.id);
  if (!panel || panel.hidden || !panel.offsetWidth || !panel.offsetHeight) return bottom;

  const geometry = propertyPanelGeometry(entity);
  const corners = [
    propertyPanelLocalWorld(geometry, 0, 0),
    propertyPanelLocalWorld(geometry, panel.offsetWidth, 0),
    propertyPanelLocalWorld(geometry, 0, panel.offsetHeight),
    propertyPanelLocalWorld(geometry, panel.offsetWidth, panel.offsetHeight),
  ];
  return Math.min(bottom, ...corners.map(point => point[1]));
}

function typedLinkSlots() {
  const links = activeLinkProperties();
  const byEntity = new Map();
  const ensure = entityId => {
    if (!byEntity.has(entityId)) byEntity.set(entityId, { out: new Set(), in: new Set() });
    return byEntity.get(entityId);
  };

  for (const { property } of links) {
    const value = property.value || {};
    const linkType = value.link_type_ref || 'relation';
    const child = entityForCanonicalRef(value.child_ref);
    const parent = entityForCanonicalRef(value.parent_ref);
    if (!child || !parent) continue;
    ensure(child.id).out.add(linkType);
    ensure(parent.id).in.add(linkType);
  }

  const size = nodeMasterSize();
  const spacing = Math.max(.12, Number(ws.settings.link_visualization.anchor_spacing || .28)) * size;
  const gap = Math.max(.12, Number(ws.settings.link_visualization.anchor_offset || .58) * .32) * size;
  const ports = new Map();

  const placeRow = (entity, direction, types, y) => {
    const ordered = linkProjectionTypeOrder(types);
    const startX = entity.position[0] - (ordered.length - 1) * spacing / 2;
    ordered.forEach((linkType, index) => {
      ports.set(`${entity.id}\u0000${direction}\u0000${linkType}`, [
        startX + index * spacing,
        y,
        entity.position[2],
      ]);
    });
  };

  for (const entity of ws.entities || []) {
    const groups = byEntity.get(entity.id);
    if (!groups) continue;

    // OUT is always a horizontal type row above the node.
    placeRow(entity, 'out', groups.out, entity.position[1] + nodeHalfSize() + gap);

    // IN is always a horizontal type row below the complete Property box.
    // This follows the box's actual world extent, so collapse/expand does not
    // move the row back onto the node.
    placeRow(entity, 'in', groups.in, linkProjectionPanelBottomY(entity) - gap);
  }

  const slots = new Map();
  for (const { property } of links) {
    const value = property.value || {};
    const linkType = value.link_type_ref || 'relation';
    const child = entityForCanonicalRef(value.child_ref);
    const parent = entityForCanonicalRef(value.parent_ref);
    if (!child || !parent) continue;
    const out = ports.get(`${child.id}\u0000out\u0000${linkType}`);
    const incoming = ports.get(`${parent.id}\u0000in\u0000${linkType}`);
    if (out) slots.set(`${property.id}:out`, out);
    if (incoming) slots.set(`${property.id}:in`, incoming);
  }

  linkProjection.ports = ports;
  return slots;
}

// Direct replacement: one projection authority for generic Link attachment.
// No canonical data, Link multiplicity or semantic endpoint is rewritten.
linkSlots = typedLinkSlots;

function linkProjectionCssPoint(world) {
  const screen = project(world, viewProjection());
  if (!screen) return null;
  const density = devicePixelRatio || 1;
  return { x: screen[0] / density, y: screen[1] / density };
}

function linkProjectionSvgElement(name) {
  return document.createElementNS('http://www.w3.org/2000/svg', name);
}

function renderGenericFlowMaterial(time) {
  linkFlowSvg.setAttribute('width', String(innerWidth));
  linkFlowSvg.setAttribute('height', String(innerHeight));
  linkFlowSvg.setAttribute('viewBox', `0 0 ${innerWidth} ${innerHeight}`);
  linkFlowSvg.replaceChildren();

  const slots = typedLinkSlots();
  const period = Math.max(8, LINK_FLOW_MASK_PIXELS * LINK_FLOW_REPEAT_SCALE);
  const pulse = Math.max(LINK_FLOW_MIN_PULSE_PX, period / LINK_FLOW_MASK_PIXELS);
  const gap = Math.max(1, period - pulse);
  const cyclesPerSecond = Math.max(.01, Number(ws.settings.link_visualization.base_flow_speed || .15));
  const offset = -((time * .001 * cyclesPerSecond * period) % period);

  for (const { property } of activeLinkProperties()) {
    const startWorld = slots.get(`${property.id}:out`);
    const endWorld = slots.get(`${property.id}:in`);
    if (!startWorld || !endWorld) continue;
    const start = linkProjectionCssPoint(startWorld);
    const end = linkProjectionCssPoint(endWorld);
    if (!start || !end) continue;

    const path = linkProjectionSvgElement('path');
    path.setAttribute('d', `M ${start.x} ${start.y} L ${end.x} ${end.y}`);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', linkProjectionColor(property, 'flow'));
    path.setAttribute('stroke-width', '1.6');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-dasharray', `${pulse} ${gap}`);
    path.setAttribute('stroke-dashoffset', String(offset));
    path.setAttribute('opacity', '.88');
    path.dataset.linkId = property.id;
    linkFlowSvg.appendChild(path);
  }

  // A single visible port per Link type and per direction. Every canonical Link
  // of that type shares this exact attachment point on the Entity instance.
  for (const [key, world] of linkProjection.ports) {
    const [entityId, direction, linkType] = key.split('\u0000');
    const point = linkProjectionCssPoint(world);
    if (!point) continue;
    const circle = linkProjectionSvgElement('circle');
    circle.setAttribute('cx', String(point.x));
    circle.setAttribute('cy', String(point.y));
    circle.setAttribute('r', direction === 'out' ? '3.0' : '3.3');
    circle.setAttribute('stroke', linkProjectionTypeColor(linkType));
    circle.setAttribute('stroke-width', '1.4');
    circle.setAttribute('fill', direction === 'out' ? linkProjectionTypeColor(linkType) : '#090b10');
    circle.setAttribute('opacity', '.95');
    circle.dataset.entityId = entityId;
    circle.dataset.direction = direction;
    circle.dataset.linkType = linkType;
    linkFlowSvg.appendChild(circle);
  }
}

function causalFlowColor() {
  const ruleset = rulesetMap().get('RULESET_LINK_EVENT_EFFECT');
  const colorSpace = colorSpaceMap().get(ruleset?.color_space_ref);
  const rgb = colorSpace?.colors?.flow || [1, .48, .30];
  return `rgb(${rgb.slice(0, 3).map(value => Math.round(Math.max(0, Math.min(1, Number(value))) * 255)).join(',')})`;
}

function renderEventFlowMaterial(time) {
  if (typeof causalSvg === 'undefined' || typeof causalProjection === 'undefined') return;
  causalSvg.querySelectorAll('.causal-flow-pulse').forEach(node => node.remove());
  const graph = causalProjection.graph;
  if (!graph || !causalProjection.playbackStartedAt) return;

  const elapsed = time - causalProjection.playbackStartedAt;
  const stepMs = Math.max(120, Number(ws.settings.event_playback.effect_travel_duration || 1.2) * 350);
  const edgeById = new Map(graph.edges.map(edge => [edge.id, edge]));

  for (const path of causalSvg.querySelectorAll('.causal-edge')) {
    const ids = String(path.dataset.linkId || '').split(',').filter(Boolean);
    const edges = ids.map(id => edgeById.get(id)).filter(Boolean);
    if (!edges.length) continue;

    let progress = null;
    for (const edge of edges) {
      const activeAt = Math.max(0, edge.depth - 1) * stepMs;
      const local = (elapsed - activeAt) / stepMs;
      if (local >= 0 && local <= 1 && (progress === null || local > progress)) progress = local;
    }
    if (progress === null) continue;

    try {
      const length = path.getTotalLength();
      if (!(length > 0)) continue;
      const point = path.getPointAtLength(length * Math.max(0, Math.min(1, progress)));
      const circle = linkProjectionSvgElement('circle');
      circle.classList.add('causal-flow-pulse');
      circle.setAttribute('cx', String(point.x));
      circle.setAttribute('cy', String(point.y));
      circle.setAttribute('r', '2.4');
      circle.setAttribute('fill', causalFlowColor());
      circle.setAttribute('stroke', '#ffffff');
      circle.setAttribute('stroke-width', '.55');
      circle.setAttribute('opacity', '1');
      causalSvg.appendChild(circle);
    } catch (error) {
      window.reportStructureError?.(error, { type: 'event_flow_material' });
    }
  }
}

function renderLinkProjection(time) {
  renderGenericFlowMaterial(time);
  renderEventFlowMaterial(time);
  requestAnimationFrame(renderLinkProjection);
}

requestAnimationFrame(renderLinkProjection);
