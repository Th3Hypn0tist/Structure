// Link representation: one typed OUT port above each Entity and one typed IN
// port below its full Property box, per Link type. Canonical Link multiplicity
// is preserved; visual attachment is shared by type and direction.

const LINK_FLOW_MASK_PIXELS = 100;
const LINK_FLOW_REPEAT_SCALE = 0.26;
const LINK_EVENT_BOOST_MS = 480;
const NODE_EVENT_FLASH_MS = 360;
const linkProjection = {
  ports: new Map(),
  flowPhases: new Map(),
  boostUntil: new Map(),
  causalRunKey: null,
  causalTouchedLinks: new Set(),
  flashes: new Map(),
};

const linkFlowSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
linkFlowSvg.id = 'linkFlowLines';
linkFlowSvg.setAttribute('aria-hidden', 'true');
Object.assign(linkFlowSvg.style, { position: 'fixed', inset: '0', pointerEvents: 'none', zIndex: '9', overflow: 'visible' });
document.body.appendChild(linkFlowSvg);

const linkEventFlashLayer = document.createElement('div');
linkEventFlashLayer.setAttribute('aria-hidden', 'true');
Object.assign(linkEventFlashLayer.style, { position: 'fixed', inset: '0', pointerEvents: 'none', zIndex: '8' });
document.body.appendChild(linkEventFlashLayer);

function causalRuntime() {
  const runtime = window.StructureCausalProjection;
  if (!runtime || !runtime.state || !runtime.surface) throw new Error('StructureCausalProjection runtime contract missing');
  return runtime;
}

function linkProjectionRgb(property, variant) {
  const ruleset = rulesetMap().get(property.ruleset_ref);
  if (!ruleset) throw new Error(`Ruleset unresolved: ${property.ruleset_ref}`);
  const colorSpace = colorSpaceMap().get(ruleset.color_space_ref);
  if (!colorSpace) throw new Error(`ColorSpace unresolved: ${ruleset.color_space_ref}`);
  const rgb = colorSpace.colors[variant];
  if (!Array.isArray(rgb) || rgb.length !== 3) throw new Error(`ColorSpace ${colorSpace.id}.${variant} must be [r,g,b]`);
  return rgb.map(value => Number(value));
}
function rgbCss(rgb) { return `rgb(${rgb.map(value => Math.round(value * 255)).join(',')})`; }
function linkProjectionColor(property, variant) {
  const target = linkProjectionRgb(property, variant);
  const subtract = target.map(value => 1 - value);
  const tintedWhite = subtract.map(value => 1 - value);
  return rgbCss(tintedWhite);
}
function brightenedLinkColor(property) {
  return rgbCss(linkProjectionRgb(property, 'flow').map(value => value + (1 - value) * .58));
}
function linkTypeColor(linkType) {
  const matches = assertWorkspace().rulesets.filter(ruleset => ruleset.property_type_ref === 'link' && ruleset.link_type_ref === linkType);
  if (matches.length !== 1) throw new Error(`Link type ${linkType} must resolve to exactly one Ruleset, found ${matches.length}`);
  const colorSpace = colorSpaceMap().get(matches[0].color_space_ref);
  if (!colorSpace) throw new Error(`ColorSpace unresolved: ${matches[0].color_space_ref}`);
  return rgbCss(colorSpace.colors.flow);
}
function linkTypeOrder(types) {
  const order = new Map();
  let index = 0;
  for (const ruleset of assertWorkspace().rulesets) {
    if (ruleset.property_type_ref !== 'link') continue;
    if (!order.has(ruleset.link_type_ref)) order.set(ruleset.link_type_ref, index++);
  }
  return [...types].sort((left, right) => {
    if (!order.has(left) || !order.has(right)) throw new Error(`Link type order unresolved: ${left}, ${right}`);
    return order.get(left) - order.get(right);
  });
}

function propertyBoxBottom(entity) {
  let bottom = entity.position[1] - nodeHalfSize();
  const panel = causalRuntime().state.panelElements.get(entity.id);
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

function linkSlots() {
  const links = activeLinkProperties();
  const byEntity = new Map();
  const groups = entityId => {
    if (!byEntity.has(entityId)) byEntity.set(entityId, { out: new Set(), in: new Set() });
    return byEntity.get(entityId);
  };
  for (const { property } of links) {
    const linkType = property.value.link_type_ref;
    const source = entityForCanonicalRef(property.value.child_ref);
    const target = entityForCanonicalRef(property.value.parent_ref);
    if (!source || !target) throw new Error(`visual endpoint unresolved for ${property.id}`);
    groups(source.id).out.add(linkType);
    groups(target.id).in.add(linkType);
  }
  const spacing = linkSettings().anchor_spacing * nodeMasterSize();
  const gap = linkSettings().anchor_offset * nodeMasterSize();
  if (spacing <= 0 || gap <= 0) throw new Error('Link anchor spacing and offset must be positive');
  const ports = new Map();
  const placeRow = (entity, direction, types, y) => {
    const ordered = linkTypeOrder(types);
    const firstX = entity.position[0] - (ordered.length - 1) * spacing / 2;
    ordered.forEach((linkType, index) => ports.set(`${entity.id}\u0000${direction}\u0000${linkType}`, [firstX + index * spacing, y, entity.position[2]]));
  };
  for (const entity of assertWorkspace().entities) {
    const typed = byEntity.get(entity.id);
    if (!typed) continue;
    placeRow(entity, 'out', typed.out, entity.position[1] + nodeHalfSize() + gap);
    placeRow(entity, 'in', typed.in, propertyBoxBottom(entity) - gap);
  }
  const slots = new Map();
  for (const { property } of links) {
    const linkType = property.value.link_type_ref;
    const source = entityForCanonicalRef(property.value.child_ref);
    const target = entityForCanonicalRef(property.value.parent_ref);
    const out = ports.get(`${source.id}\u0000out\u0000${linkType}`);
    const incoming = ports.get(`${target.id}\u0000in\u0000${linkType}`);
    if (!out || !incoming) throw new Error(`typed Link ports unresolved for ${property.id}`);
    slots.set(`${property.id}:out`, out);
    slots.set(`${property.id}:in`, incoming);
  }
  linkProjection.ports = ports;
  return slots;
}

function cssPoint(world) {
  const screen = project(world, viewProjection());
  if (!screen) return null;
  const density = devicePixelRatio || 1;
  return { x: screen[0] / density, y: screen[1] / density };
}
function svgElement(name) { return document.createElementNS('http://www.w3.org/2000/svg', name); }
function flowDashOffset(property, time, period) {
  let state = linkProjection.flowPhases.get(property.id);
  if (!state) {
    state = { phase: 0, time };
    linkProjection.flowPhases.set(property.id, state);
  }
  const dt = Math.max(0, Math.min(.05, (time - state.time) / 1000));
  const active = time < (linkProjection.boostUntil.get(property.id) ?? 0);
  const speed = active ? eventSettings().active_link_speed : linkSettings().base_flow_speed;
  if (!Number.isFinite(speed) || speed < 0) throw new Error('Link flow speed must be a non-negative number');
  state.phase = (state.phase + dt * speed * period) % period;
  state.time = time;
  return -state.phase;
}
function activateGenericLinkFromEvent(property, time) {
  const target = entityForCanonicalRef(property.value.parent_ref);
  if (!target) throw new Error(`Generic Link target unresolved during Event playback: ${property.id}`);
  linkProjection.boostUntil.set(property.id, time + LINK_EVENT_BOOST_MS);
  linkProjection.flashes.set(target.id, { startedAt: time, color: brightenedLinkColor(property) });
}
function syncGenericLinksFromCausalPlayback(time) {
  const state = causalRuntime().state;
  if (!ws || !state.graph || !state.playbackStartedAt) {
    linkProjection.causalRunKey = null;
    linkProjection.causalTouchedLinks.clear();
    return;
  }
  const runKey = `${state.rootEventRef}\u0000${state.playbackStartedAt}`;
  if (linkProjection.causalRunKey !== runKey) {
    linkProjection.causalRunKey = runKey;
    linkProjection.causalTouchedLinks.clear();
  }
  const elapsed = time - state.playbackStartedAt;
  const stepMs = Math.max(120, eventSettings().effect_travel_duration * 350);
  const reachedOwners = new Set();
  for (const node of state.graph.nodes) {
    if (elapsed < node.depth * stepMs) continue;
    const item = state.graph.index.get(node.ref);
    if (!item) throw new Error(`Causal node unresolved during generic Link feedback: ${node.ref}`);
    reachedOwners.add(item.owner.id);
  }
  for (const { property } of activeLinkProperties()) {
    if (linkProjection.causalTouchedLinks.has(property.id)) continue;
    const source = entityForCanonicalRef(property.value.child_ref);
    if (!source) throw new Error(`Generic Link source unresolved during Event playback: ${property.id}`);
    if (!reachedOwners.has(source.id)) continue;
    linkProjection.causalTouchedLinks.add(property.id);
    activateGenericLinkFromEvent(property, time);
  }
}
function renderNodeEventFlashes(time) {
  linkEventFlashLayer.replaceChildren();
  const density = devicePixelRatio || 1;
  for (const [entityId, flash] of [...linkProjection.flashes]) {
    const progress = (time - flash.startedAt) / NODE_EVENT_FLASH_MS;
    if (progress < 0 || progress >= 1) { linkProjection.flashes.delete(entityId); continue; }
    const entity = assertWorkspace().entities.find(item => item.id === entityId);
    if (!entity) throw new Error(`Event flash Entity unresolved: ${entityId}`);
    const bounds = entityScreenBounds(entity, viewProjection());
    if (!bounds) continue;
    const pulse = Math.sin(Math.PI * progress);
    const marker = document.createElement('div');
    Object.assign(marker.style, {
      position: 'fixed',
      left: `${bounds.minX / density}px`,
      top: `${bounds.minY / density}px`,
      width: `${Math.max(1, (bounds.maxX - bounds.minX) / density)}px`,
      height: `${Math.max(1, (bounds.maxY - bounds.minY) / density)}px`,
      pointerEvents: 'none',
      background: flash.color,
      border: `1px solid ${flash.color}`,
      borderRadius: '3px',
      boxShadow: `0 0 18px ${flash.color}`,
      mixBlendMode: 'screen',
      opacity: String(.68 * pulse),
    });
    linkEventFlashLayer.appendChild(marker);
  }
}

function renderGenericLinks(time) {
  linkFlowSvg.setAttribute('width', String(innerWidth));
  linkFlowSvg.setAttribute('height', String(innerHeight));
  linkFlowSvg.setAttribute('viewBox', `0 0 ${innerWidth} ${innerHeight}`);
  linkFlowSvg.replaceChildren();
  if (!ws) return;
  const slots = linkSlots();
  const period = LINK_FLOW_MASK_PIXELS * LINK_FLOW_REPEAT_SCALE;
  const whitePixel = Math.max(1, period / LINK_FLOW_MASK_PIXELS);
  const transparentPixels = period - whitePixel;
  const width = linkSettings().flow_width;
  if (width <= 0) throw new Error('settings.link_visualization.flow_width must be positive');
  for (const { property } of activeLinkProperties()) {
    const start = cssPoint(slots.get(`${property.id}:out`));
    const end = cssPoint(slots.get(`${property.id}:in`));
    if (!start || !end) continue;
    const base = svgElement('path');
    base.setAttribute('d', `M ${start.x} ${start.y} L ${end.x} ${end.y}`);
    base.setAttribute('fill', 'none');
    base.setAttribute('stroke', linkProjectionColor(property, 'base'));
    base.setAttribute('stroke-width', String(Math.max(1, width * 8)));
    base.setAttribute('opacity', '.55');
    linkFlowSvg.appendChild(base);
    const flow = svgElement('path');
    flow.setAttribute('d', `M ${start.x} ${start.y} L ${end.x} ${end.y}`);
    flow.setAttribute('fill', 'none');
    flow.setAttribute('stroke', linkProjectionColor(property, 'flow'));
    flow.setAttribute('stroke-width', String(Math.max(1.2, width * 9)));
    flow.setAttribute('stroke-linecap', 'round');
    flow.setAttribute('stroke-dasharray', `${whitePixel} ${transparentPixels}`);
    flow.setAttribute('stroke-dashoffset', String(flowDashOffset(property, time, period)));
    flow.setAttribute('opacity', '.95');
    flow.dataset.linkId = property.id;
    linkFlowSvg.appendChild(flow);
  }
  for (const [key, world] of linkProjection.ports) {
    const [entityId, direction, linkType] = key.split('\u0000');
    const point = cssPoint(world);
    if (!point) continue;
    const circle = svgElement('circle');
    circle.setAttribute('cx', String(point.x));
    circle.setAttribute('cy', String(point.y));
    circle.setAttribute('r', '3.2');
    circle.setAttribute('stroke', linkTypeColor(linkType));
    circle.setAttribute('stroke-width', '1.4');
    circle.setAttribute('fill', direction === 'out' ? linkTypeColor(linkType) : '#090b10');
    circle.dataset.entityId = entityId;
    circle.dataset.direction = direction;
    circle.dataset.linkType = linkType;
    linkFlowSvg.appendChild(circle);
  }
}

function causalFlowColor() {
  const ruleset = rulesetMap().get('RULESET_LINK_EVENT_EFFECT');
  if (!ruleset) throw new Error('RULESET_LINK_EVENT_EFFECT missing');
  const colorSpace = colorSpaceMap().get(ruleset.color_space_ref);
  if (!colorSpace) throw new Error(`ColorSpace unresolved: ${ruleset.color_space_ref}`);
  return rgbCss(colorSpace.colors.flow);
}
function renderEventFlow(time) {
  const runtime = causalRuntime();
  const surface = runtime.surface;
  const state = runtime.state;
  surface.querySelectorAll('.causal-flow-pulse').forEach(node => node.remove());
  if (!ws || !state.graph || !state.playbackStartedAt) return;
  const elapsed = time - state.playbackStartedAt;
  const stepMs = Math.max(120, eventSettings().effect_travel_duration * 350);
  const edgeById = new Map(state.graph.edges.map(edge => [edge.id, edge]));
  for (const path of surface.querySelectorAll('.causal-edge')) {
    const ids = String(path.dataset.linkId).split(',');
    const edges = ids.map(id => edgeById.get(id)).filter(Boolean);
    if (!edges.length) throw new Error(`causal visual has no canonical edge: ${path.dataset.linkId}`);
    let progress = null;
    for (const edge of edges) {
      const activeAt = Math.max(0, edge.depth - 1) * stepMs;
      const local = (elapsed - activeAt) / stepMs;
      if (local >= 0 && local <= 1 && (progress === null || local > progress)) progress = local;
    }
    if (progress === null) continue;
    const length = path.getTotalLength();
    if (length <= 0) throw new Error(`causal path has zero length: ${path.dataset.linkId}`);
    const point = path.getPointAtLength(length * progress);
    const pulse = svgElement('circle');
    pulse.classList.add('causal-flow-pulse');
    pulse.setAttribute('cx', String(point.x));
    pulse.setAttribute('cy', String(point.y));
    pulse.setAttribute('r', '2.5');
    pulse.setAttribute('fill', causalFlowColor());
    pulse.setAttribute('stroke', '#ffffff');
    pulse.setAttribute('stroke-width', '.6');
    surface.appendChild(pulse);
  }
}

function renderLinkProjection(time) {
  syncGenericLinksFromCausalPlayback(time);
  renderGenericLinks(time);
  renderEventFlow(time);
  renderNodeEventFlashes(time);
  requestAnimationFrame(renderLinkProjection);
}
requestAnimationFrame(renderLinkProjection);
