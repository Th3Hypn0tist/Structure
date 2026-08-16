// Generic Link projection. All represented Link geometry, ports and event
// feedback live in world-space WebGL. DOM/SVG is not used for scene content.

const LINK_EVENT_BOOST_MS = 480;
const NODE_EVENT_FLASH_MS = 360;
const linkProjection = {
  ports: new Map(),
  flowPhases: new Map(),
  boostUntil: new Map(),
  causalRunKey: null,
  causalTouchedLinks: new Set(),
  genericReachedAt: new Map(),
  flashes: new Map(),
};

function causalRuntime() {
  const runtime = window.StructureCausalProjection;
  if (!runtime || !runtime.state) throw new Error('StructureCausalProjection runtime contract missing');
  return runtime;
}

function linkProjectionRgb(property, variant) {
  const ruleset = rulesetMap().get(property.ruleset_ref);
  if (!ruleset) throw new Error(`Ruleset unresolved: ${property.ruleset_ref}`);
  const colorSpace = colorSpaceMap().get(ruleset.color_space_ref);
  if (!colorSpace) throw new Error(`ColorSpace unresolved: ${ruleset.color_space_ref}`);
  const rgb = colorSpace.colors[variant];
  if (!Array.isArray(rgb) || rgb.length !== 3) throw new Error(`ColorSpace ${colorSpace.id}.${variant} must be [r,g,b]`);
  return rgb.map(Number);
}
function linkTypeRgb(linkType, variant = 'flow') {
  const matches = assertWorkspace().rulesets.filter(ruleset => ruleset.property_type_ref === 'link' && ruleset.link_type_ref === linkType);
  if (matches.length !== 1) throw new Error(`Link type ${linkType} must resolve to exactly one Ruleset, found ${matches.length}`);
  const colorSpace = colorSpaceMap().get(matches[0].color_space_ref);
  if (!colorSpace) throw new Error(`ColorSpace unresolved: ${matches[0].color_space_ref}`);
  const rgb = colorSpace.colors[variant];
  if (!Array.isArray(rgb) || rgb.length !== 3) throw new Error(`ColorSpace ${colorSpace.id}.${variant} must be [r,g,b]`);
  return rgb.map(Number);
}
function brightenedLinkRgb(property) {
  return linkProjectionRgb(property, 'flow').map(value => value + (1 - value) * .58);
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
  const items = propertyGroups(canonicalIndex()).get(entity.id) ?? [];
  if (!items.length) return bottom;
  const layout = propsListLayout(entity, items);
  return Math.min(bottom, layout.center[1] - layout.height / 2);
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
    ordered.forEach((linkType, index) => {
      ports.set(`${entity.id}\u0000${direction}\u0000${linkType}`, [firstX + index * spacing, y, entity.position[2]]);
    });
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

function flowProgress(property, time) {
  let state = linkProjection.flowPhases.get(property.id);
  if (!state) {
    state = { phase: 0, time };
    linkProjection.flowPhases.set(property.id, state);
  }
  const dt = Math.max(0, Math.min(.05, (time - state.time) / 1000));
  const active = time < (linkProjection.boostUntil.get(property.id) ?? 0);
  const speed = active ? eventSettings().active_link_speed : linkSettings().base_flow_speed;
  if (!Number.isFinite(speed) || speed < 0) throw new Error('Link flow speed must be a non-negative number');
  state.phase = (state.phase + dt * speed) % 1;
  state.time = time;
  return state.phase;
}

function activateGenericLinkFromEvent(property, sourceReachedAt) {
  const target = entityForCanonicalRef(property.value.parent_ref);
  if (!target) throw new Error(`Generic Link target unresolved during Event playback: ${property.id}`);
  const arrivalAt = sourceReachedAt + LINK_EVENT_BOOST_MS;
  linkProjection.boostUntil.set(property.id, arrivalAt);
  linkProjection.flashes.set(target.id, { startedAt: arrivalAt, color: brightenedLinkRgb(property) });
  return { target, arrivalAt };
}
function resetGenericEventFeedback() {
  linkProjection.causalRunKey = null;
  linkProjection.causalTouchedLinks.clear();
  linkProjection.genericReachedAt.clear();
  linkProjection.boostUntil.clear();
  linkProjection.flashes.clear();
}
function registerGenericReach(entityId, reachedAt) {
  const current = linkProjection.genericReachedAt.get(entityId);
  if (current === undefined || reachedAt < current) {
    linkProjection.genericReachedAt.set(entityId, reachedAt);
    return true;
  }
  return false;
}
function syncGenericLinksFromCausalPlayback(time) {
  const state = causalRuntime().state;
  if (!ws || !state.graph || !state.playbackStartedAt) {
    resetGenericEventFeedback();
    return;
  }
  const runKey = `${state.rootEventRef}\u0000${state.playbackStartedAt}`;
  if (linkProjection.causalRunKey !== runKey) {
    resetGenericEventFeedback();
    linkProjection.causalRunKey = runKey;
  }
  const stepMs = Math.max(120, eventSettings().effect_travel_duration * 350);
  for (const node of state.graph.nodes) {
    const reachedAt = state.playbackStartedAt + node.depth * stepMs;
    if (time < reachedAt) continue;
    const item = state.graph.index.get(node.ref);
    if (!item) throw new Error(`Causal node unresolved during generic Link feedback: ${node.ref}`);
    registerGenericReach(item.owner.id, reachedAt);
  }
  let propagated = true;
  while (propagated) {
    propagated = false;
    for (const { property } of activeLinkProperties()) {
      if (linkProjection.causalTouchedLinks.has(property.id)) continue;
      const source = entityForCanonicalRef(property.value.child_ref);
      if (!source) throw new Error(`Generic Link source unresolved during Event playback: ${property.id}`);
      const sourceReachedAt = linkProjection.genericReachedAt.get(source.id);
      if (sourceReachedAt === undefined || time < sourceReachedAt) continue;
      linkProjection.causalTouchedLinks.add(property.id);
      const { target, arrivalAt } = activateGenericLinkFromEvent(property, sourceReachedAt);
      registerGenericReach(target.id, arrivalAt);
      propagated = true;
    }
  }
}

function drawNodeEventFlashes3D(time) {
  for (const [entityId, flash] of [...linkProjection.flashes]) {
    const progress = (time - flash.startedAt) / NODE_EVENT_FLASH_MS;
    if (progress < 0) continue;
    if (progress >= 1) {
      linkProjection.flashes.delete(entityId);
      continue;
    }
    const entity = assertWorkspace().entities.find(item => item.id === entityId);
    if (!entity) throw new Error(`Event flash Entity unresolved: ${entityId}`);
    const pulse = Math.sin(Math.PI * progress);
    const half = nodeHalfSize() + (.025 + .035 * pulse) * nodeMasterSize();
    const color = flash.color.map(value => Math.min(1, value * (.65 + .35 * pulse)));
    drawBox(entity.position, [half, half, half], color, true);
  }
}

function drawGenericLinks3D(time) {
  if (!ws) return;
  const slots = linkSlots();
  const width = linkSettings().flow_width;
  if (!Number.isFinite(width) || width <= 0) throw new Error('settings.link_visualization.flow_width must be positive');
  const pulseRadius = Math.max(.025, width * .14) * nodeMasterSize();

  for (const { property } of activeLinkProperties()) {
    const start = slots.get(`${property.id}:out`);
    const end = slots.get(`${property.id}:in`);
    if (!start || !end) continue;
    const baseColor = linkProjectionRgb(property, 'base');
    const flowColor = linkProjectionRgb(property, 'flow');
    drawLine(start, end, baseColor);
    const progress = flowProgress(property, time);
    const pulse = V.add(start, V.mul(V.sub(end, start), progress));
    drawBox(pulse, [pulseRadius, pulseRadius, pulseRadius], flowColor);
  }

  const portRadius = .055 * nodeMasterSize();
  for (const [key, world] of linkProjection.ports) {
    const [, direction, linkType] = key.split('\u0000');
    const color = linkTypeRgb(linkType);
    drawBox(world, [portRadius, portRadius, portRadius], color, direction === 'in');
  }
}

function drawLinkProjection3D(time) {
  syncGenericLinksFromCausalPlayback(time);
  drawGenericLinks3D(time);
  drawNodeEventFlashes3D(time);
}

const renderSceneBeforeLinks = render;
render = function renderSceneWith3dLinks() {
  renderSceneBeforeLinks();
  if (ws) drawLinkProjection3D(performance.now());
};
