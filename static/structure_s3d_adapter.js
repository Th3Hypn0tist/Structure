// Structure -> S3D projection adapter.
// This is the semantic boundary: Structure resolves canonical CW meaning,
// while S3D receives only generic objects, anchors, links and presentation metadata.
//
// Scene objects are persistent. Rendering may reconcile presentation state, but
// it must not destroy/recreate the S3D object graph every animation frame.

const structureS3D = {
  scene: new S3D.Scene(),
  entities: new Map(),
  eventGroups: new Map(),
  propGroups: new Map(),
  events: new Map(),
  props: new Map(),
  links: new Map(),
  routePulses: new Map(),
  lifecycle: {
    reconciles: 0,
    entitiesCreated: 0,
    eventGroupsCreated: 0,
    propGroupsCreated: 0,
    eventsCreated: 0,
    propsCreated: 0,
    anchorsCreated: 0,
    linksCreated: 0,
    pulsesCreated: 0,
  },
};

const structureS3DRenderer = new S3D.Renderer({
  box: (position, scale, color, outline = false) => drawBox(position, scale, color, outline),
  line: (start, end, color) => drawLine(start, end, color),
  point: (position, scale, color) => drawBox(position, scale, color),
});

function assignVec3(object, field, value) {
  const current = object[field];
  if (Array.isArray(current) && current.length === 3) {
    current[0] = Number(value[0]);
    current[1] = Number(value[1]);
    current[2] = Number(value[2]);
  } else {
    object[field] = [Number(value[0]), Number(value[1]), Number(value[2])];
  }
  return object[field];
}

function removeChildObject(object) {
  if (object?.parent?.remove) object.parent.remove(object);
}

function resetStructureS3DScene() {
  structureS3D.scene.clear();
  structureS3D.entities.clear();
  structureS3D.eventGroups.clear();
  structureS3D.propGroups.clear();
  structureS3D.events.clear();
  structureS3D.props.clear();
  structureS3D.links.clear();
  structureS3D.routePulses.clear();
}

function ensureS3DEntity(entity) {
  let object = structureS3D.entities.get(entity.id);
  if (!object) {
    object = new S3D.SceneObject({ id: `entity:${entity.id}`, position: entity.position, metadata: { sourceRef: entity.id } });
    structureS3D.entities.set(entity.id, object);
    structureS3D.scene.add(object);
    structureS3D.lifecycle.entitiesCreated += 1;
  }
  assignVec3(object, 'position', entity.position);
  object.metadata.sourceRef = entity.id;
  return object;
}

function ensureEventGroup(entity) {
  const host = ensureS3DEntity(entity);
  let group = structureS3D.eventGroups.get(entity.id);
  if (!group) {
    group = new S3D.Events({ id: `events:${entity.id}`, attachTo: host, metadata: { sourceRef: entity.id } });
    structureS3D.eventGroups.set(entity.id, group);
    structureS3D.lifecycle.eventGroupsCreated += 1;
  }
  group.attachTo = host;
  group.metadata.sourceRef = entity.id;
  return group;
}

function syncEventGroup(entity, layout, seenEvents) {
  const group = ensureEventGroup(entity);
  for (const row of layout.rows) {
    seenEvents.add(row.ref);
    let item = structureS3D.events.get(row.ref);
    if (!item) {
      item = new S3D.EventItem({
        id: `event:${row.ref}`,
        label: propertyDisplayName(row.property, entity),
        color: SCENE_COLORS.event,
        metadata: { sourceRef: row.ref },
      });
      group.addItem(item);
      structureS3D.events.set(row.ref, item);
      structureS3D.lifecycle.eventsCreated += 1;
    } else if (item.parent !== group) {
      group.addItem(item);
    }
    item.label = propertyDisplayName(row.property, entity);
    item.metadata.sourceRef = row.ref;
    assignVec3(item, 'position', row.center.map((value, index) => value - entity.position[index]));
    assignVec3(item, 'scale', row.halfScale);
    item.layoutWidth = row.width;
    item.layoutHeight = row.height;
  }
  return group;
}

function ensurePropsGroup(entity, layout) {
  const host = ensureS3DEntity(entity);
  let group = structureS3D.propGroups.get(entity.id);
  if (!group) {
    group = new S3D.Props({
      id: `props:${entity.id}`,
      attachTo: host,
      collapsed: layout.collapsed,
      metadata: { sourceRef: entity.id },
    });
    structureS3D.propGroups.set(entity.id, group);
    structureS3D.lifecycle.propGroupsCreated += 1;
  }
  group.attachTo = host;
  group.collapsed = layout.collapsed;
  group.metadata.sourceRef = entity.id;
  assignVec3(group, 'position', layout.center.map((value, index) => value - entity.position[index]));
  assignVec3(group, 'scale', layout.frameScale);
  return group;
}

function syncPropsGroup(entity, layout, seenProps) {
  if (!layout) return null;
  const group = ensurePropsGroup(entity, layout);
  for (const row of layout.rows) {
    seenProps.add(row.ref);
    let item = structureS3D.props.get(row.ref);
    if (!item) {
      item = new S3D.PropsItem({
        id: `prop:${row.ref}`,
        label: `${row.item.propertyType.toUpperCase()} · ${displayName(row.item)}`,
        color: SCENE_COLORS[row.item.propertyType] ?? SCENE_COLORS.generic,
        metadata: { sourceRef: row.ref, propertyType: row.item.propertyType },
      });
      group.addItem(item);
      structureS3D.props.set(row.ref, item);
      structureS3D.lifecycle.propsCreated += 1;
    } else if (item.parent !== group) {
      group.addItem(item);
    }
    item.label = `${row.item.propertyType.toUpperCase()} · ${displayName(row.item)}`;
    item.metadata.sourceRef = row.ref;
    item.metadata.propertyType = row.item.propertyType;
    assignVec3(item, 'position', row.center.map((value, index) => value - entity.position[index]));
    assignVec3(item, 'scale', row.halfScale);
    item.layoutWidth = row.width;
    item.layoutHeight = row.height;
  }
  return group;
}

function ensureS3DAnchor(object, name, worldPosition, metadata = {}) {
  let anchor = object.anchor(name);
  if (!anchor) {
    anchor = object.addAnchor(new S3D.Anchor({ name, metadata }));
    structureS3D.lifecycle.anchorsCreated += 1;
  }
  const base = object.worldPosition();
  assignVec3(anchor, 'position', worldPosition.map((value, index) => value - base[index]));
  anchor.metadata = { ...anchor.metadata, ...metadata };
  return anchor;
}

function syncEventIoAnchors(entity, eventIo) {
  const host = ensureS3DEntity(entity);
  if (!eventIo) {
    host.anchors.delete('event_in');
    host.anchors.delete('event_out');
    return null;
  }
  const incoming = ensureS3DAnchor(host, 'event_in', eventIo.inCenter, { role: 'event_in' });
  const outgoing = ensureS3DAnchor(host, 'event_out', eventIo.outCenter, { role: 'event_out' });
  const current = host.metadata.eventIo ?? { incoming, outgoing, halfScale: [0, 0, 0] };
  current.incoming = incoming;
  current.outgoing = outgoing;
  assignVec3(current, 'halfScale', eventIo.halfScale);
  return current;
}

function prunePersistentObjects(seenEntities, seenEventGroups, seenPropGroups, seenEvents, seenProps) {
  for (const [ref, item] of [...structureS3D.events]) {
    if (seenEvents.has(ref)) continue;
    removeChildObject(item);
    structureS3D.events.delete(ref);
  }
  for (const [ref, item] of [...structureS3D.props]) {
    if (seenProps.has(ref)) continue;
    removeChildObject(item);
    structureS3D.props.delete(ref);
  }
  for (const [entityId] of [...structureS3D.eventGroups]) {
    if (!seenEventGroups.has(entityId)) structureS3D.eventGroups.delete(entityId);
  }
  for (const [entityId] of [...structureS3D.propGroups]) {
    if (!seenPropGroups.has(entityId)) structureS3D.propGroups.delete(entityId);
  }
  for (const [entityId, object] of [...structureS3D.entities]) {
    if (seenEntities.has(entityId)) continue;
    structureS3D.scene.remove(object);
    structureS3D.entities.delete(entityId);
  }
}

function buildStructureS3DObjects(layouts) {
  structureS3D.lifecycle.reconciles += 1;
  const seenEntities = new Set();
  const seenEventGroups = new Set();
  const seenPropGroups = new Set();
  const seenEvents = new Set();
  const seenProps = new Set();

  for (const entity of assertWorkspace().entities) {
    const local = layouts.entities.get(entity.id);
    if (!local) continue;
    seenEntities.add(entity.id);
    const host = ensureS3DEntity(entity);
    seenEventGroups.add(entity.id);
    host.metadata.events = syncEventGroup(entity, local.eventLayout, seenEvents);
    if (local.propsLayout) {
      seenPropGroups.add(entity.id);
      host.metadata.props = syncPropsGroup(entity, local.propsLayout, seenProps);
    } else {
      host.metadata.props = null;
    }
    host.metadata.eventIo = syncEventIoAnchors(entity, local.eventIo);
  }

  prunePersistentObjects(seenEntities, seenEventGroups, seenPropGroups, seenEvents, seenProps);
  return structureS3D;
}

function setS3DAnchor(object, name, worldPosition, metadata = {}) {
  return ensureS3DAnchor(object, name, worldPosition, metadata);
}

function buildStructureS3DLink(id, sourceObject, sourceAnchorName, targetObject, targetAnchorName, options = {}) {
  const from = sourceObject.anchor(sourceAnchorName);
  const to = targetObject.anchor(targetAnchorName);
  if (!from || !to) throw new Error(`S3D Link anchors unresolved: ${id}`);
  let link = structureS3D.links.get(id);
  if (!link) {
    link = new S3D.Link({ id: `link:${id}`, from, to, ...options, metadata: { ...(options.metadata ?? {}), sourceRef: id } });
    structureS3D.links.set(id, link);
    structureS3D.scene.add(link);
    structureS3D.lifecycle.linksCreated += 1;
  }
  link.from = from;
  link.to = to;
  if (options.color) assignVec3(link, 'color', options.color);
  if (options.flowColor) assignVec3(link, 'flowColor', options.flowColor);
  if (options.pulseScale) assignVec3(link, 'pulseScale', options.pulseScale);
  if (options.speed !== undefined) link.speed = Number(options.speed);
  if (options.flow !== undefined) link.flow = Boolean(options.flow);
  link.metadata = { ...link.metadata, ...(options.metadata ?? {}), sourceRef: id };
  return link;
}

function pruneStructureS3DLinks(seenLinks) {
  for (const [id, link] of [...structureS3D.links]) {
    if (seenLinks.has(id)) continue;
    structureS3D.scene.remove(link);
    structureS3D.links.delete(id);
  }
  for (const object of structureS3D.entities.values()) {
    for (const [name, anchor] of [...object.anchors]) {
      const sourceLinkRef = anchor.metadata?.sourceLinkRef;
      if (sourceLinkRef && !seenLinks.has(sourceLinkRef)) object.anchors.delete(name);
    }
  }
}

function ensureRoutePulse(routeKey, start, end, progress, color, scale) {
  let pulse = structureS3D.routePulses.get(routeKey);
  if (!pulse) {
    pulse = new S3D.Pulse({ id: `event-route:${routeKey}`, from: start, to: end, progress, color, scale });
    structureS3D.routePulses.set(routeKey, pulse);
    structureS3D.lifecycle.pulsesCreated += 1;
  }
  assignVec3(pulse, 'from', start);
  assignVec3(pulse, 'to', end);
  assignVec3(pulse, 'color', color);
  assignVec3(pulse, 'scale', scale);
  pulse.progress = Number(progress);
  return pulse;
}

const buildSceneLayoutsBeforeS3D = buildSceneLayouts;
buildSceneLayouts = function buildSceneLayoutsWithS3D(index) {
  const layouts = buildSceneLayoutsBeforeS3D(index);
  buildStructureS3DObjects(layouts);
  return layouts;
};

// Render Event/Props rows through their actual persistent S3D instances while
// Structure retains semantic activation, labels and hit-target policy.
drawSceneProjection3D = function drawSceneProjectionViaS3D() {
  if (!ws) return;
  const globalElapsed = playbackApi().state.startedAt ? playbackApi().elapsed() : 0;
  if (causalProjection.currentEvents.length) pruneCompletedTraces(globalElapsed);
  const index = canonicalIndex();
  const layouts = buildSceneLayouts(index);
  causalProjection.eventHitTargets = [];
  causalProjection.propertyHitTargets = [];

  for (const entity of assertWorkspace().entities) {
    const local = layouts.entities.get(entity.id);
    if (!local) continue;
    const entityActive = activeTraceForRef(entity.id, globalElapsed);
    const rootTrace = causalProjection.currentEvents.find(trace => {
      const localElapsed = globalElapsed - trace.startedAt;
      const root = trace.graph.index.get(trace.rootEventRef);
      return root?.owner.id === entity.id && localElapsed >= 0 && localElapsed < playbackApi().timingMs().activation;
    });
    const entityTrace = entityActive ?? (rootTrace ? { trace: rootTrace, alpha: traceAlpha(rootTrace, globalElapsed) } : null);
    if (entityTrace) {
      const overlayHalf = nodeHalfSize() + .018 * nodeMasterSize();
      drawBox(entity.position, [overlayHalf, overlayHalf, overlayHalf], fadedColor(entityTrace.trace.color, entityTrace.alpha, .28), true);
    }

    const labelCenter = [entity.position[0], entity.position[1] + nodeHalfSize() + .28 * nodeMasterSize(), entity.position[2] + .012];
    drawSceneText3D(entity.name, labelCenter, 1.75 * nodeMasterSize(), .32 * nodeMasterSize(), selected.has(entity.id) ? [.62,.82,1] : [.94,.97,1]);

    for (const row of local.eventLayout.rows) {
      const object = structureS3D.events.get(row.ref);
      if (!object) throw new Error(`S3D Event instance unresolved: ${row.ref}`);
      const active = activeTraceForRef(row.ref, globalElapsed);
      object.color = active ? fadedColor(active.trace.color, active.alpha, .24) : SCENE_COLORS.event;
      object.draw(structureS3DRenderer, { now: performance.now() });
      const center = object.worldPosition();
      drawBox(center, object.scale.map(value => value + .008), active ? object.color : SCENE_COLORS.outline, true);
      drawSceneText3D(object.label, [center[0], center[1], center[2] + object.scale[2] + .012], row.width * .88, row.height * .68, [.98,.92,.82]);
      causalProjection.eventHitTargets.push({ ref: row.ref, center, halfWidth: object.scale[0], halfHeight: object.scale[1] });
    }

    const props = local.propsLayout;
    const propsObject = structureS3D.entities.get(entity.id)?.metadata.props;
    if (props && propsObject) {
      if (props.collapsed) {
        drawBox(props.center, props.frameScale, SCENE_COLORS.propsFrame, true);
        drawSceneText3D('+', [props.center[0],props.center[1],props.center[2]+props.frameScale[2]+.012], props.width*.62, props.height*.62, [.82,.88,.95]);
        causalProjection.propertyHitTargets.push({ kind: 'toggle', ownerId: entity.id, center: props.center, halfWidth: props.frameScale[0], halfHeight: props.frameScale[1] });
      } else {
        drawBox(props.center, props.frameScale, SCENE_COLORS.propsFrame, true);
        for (const row of props.rows) {
          const object = structureS3D.props.get(row.ref);
          if (!object) throw new Error(`S3D PropsItem instance unresolved: ${row.ref}`);
          const active = activeTraceForRef(row.ref, globalElapsed);
          object.color = active ? fadedColor(active.trace.color, active.alpha, .22) : (SCENE_COLORS[row.item.propertyType] ?? SCENE_COLORS.generic);
          object.draw(structureS3DRenderer, { now: performance.now() });
          const center = object.worldPosition();
          drawBox(center, object.scale.map(value => value + .008), active ? object.color : SCENE_COLORS.outline, true);
          drawSceneText3D(object.label, [center[0], center[1], center[2] + object.scale[2] + .012], row.width*.90, row.height*.68, [.92,.95,.99]);
          causalProjection.propertyHitTargets.push({ kind: 'property', ref: row.ref, center, halfWidth: object.scale[0], halfHeight: object.scale[1] });
        }
        const toggleHalf = props.toggleSize / 2;
        drawBox(props.toggleCenter, [toggleHalf, toggleHalf, props.frameScale[2]*1.45], [.18,.22,.29]);
        drawSceneText3D('×', [props.toggleCenter[0],props.toggleCenter[1],props.toggleCenter[2]+props.frameScale[2]*1.5], props.toggleSize*.72, props.toggleSize*.72, [.88,.92,.98]);
        causalProjection.propertyHitTargets.push({ kind: 'toggle', ownerId: entity.id, center: props.toggleCenter, halfWidth: toggleHalf, halfHeight: toggleHalf });
      }
    }

    const io = structureS3D.entities.get(entity.id)?.metadata.eventIo;
    if (io) {
      drawBox(io.incoming.worldPosition(), io.halfScale, SCENE_COLORS.causalFlow, true);
      drawBox(io.outgoing.worldPosition(), io.halfScale, SCENE_COLORS.causalFlow);
    }
  }

  if (viewSettings().event_routes_visible) {
    const now = performance.now();
    const pulseRadius = Math.max(.018, linkSettings().flow_width * .10) * nodeMasterSize();
    const seenRoutePulses = new Set();
    for (const route of allEventRoutes(layouts)) {
      const sourceObject = structureS3D.entities.get(route.sourceOwner.id);
      const targetObject = structureS3D.entities.get(route.targetOwner.id);
      const start = sourceObject?.anchor('event_out')?.worldPosition() ?? route.start;
      const end = targetObject?.anchor('event_in')?.worldPosition() ?? route.end;
      const projectedRoute = { ...route, start, end };
      drawLine(start, end, SCENE_COLORS.causal);
      const progress = eventRouteFlowProgress(route.key, now);
      const pulse = ensureRoutePulse(route.key, start, end, progress, SCENE_COLORS.causalFlow, [pulseRadius*.65,pulseRadius*.65,pulseRadius*.65]);
      pulse.draw(structureS3DRenderer, { now });
      seenRoutePulses.add(route.key);
      for (const trace of causalProjection.currentEvents) {
        const edges = traceRouteEdges(trace).get(route.key);
        if (edges?.length) drawTransientTraceRoute(projectedRoute, trace, edges, globalElapsed, pulseRadius);
      }
    }
    for (const key of [...structureS3D.routePulses.keys()]) if (!seenRoutePulses.has(key)) structureS3D.routePulses.delete(key);
  } else {
    structureS3D.routePulses.clear();
  }
};

const linkSlotsBeforeS3D = linkSlots;
linkSlots = function linkSlotsWithS3D() {
  const slots = linkSlotsBeforeS3D();
  const seenLinks = new Set();
  for (const { property } of activeLinkProperties()) {
    const sourceEntity = entityForCanonicalRef(property.value.child_ref);
    const targetEntity = entityForCanonicalRef(property.value.parent_ref);
    const sourceObject = sourceEntity ? structureS3D.entities.get(sourceEntity.id) : null;
    const targetObject = targetEntity ? structureS3D.entities.get(targetEntity.id) : null;
    if (!sourceObject || !targetObject) throw new Error(`S3D Link endpoint object unresolved: ${property.id}`);
    const outName = `link:${property.id}:out`;
    const inName = `link:${property.id}:in`;
    setS3DAnchor(sourceObject, outName, slots.get(`${property.id}:out`), { sourceLinkRef: property.id, role: 'out' });
    setS3DAnchor(targetObject, inName, slots.get(`${property.id}:in`), { sourceLinkRef: property.id, role: 'in' });
    buildStructureS3DLink(property.id, sourceObject, outName, targetObject, inName, {
      color: linkProjectionRgb(property, 'base'),
      flowColor: linkProjectionRgb(property, 'flow'),
      speed: requiredNumber(linkSettings(), 'base_flow_speed', 'settings.link_visualization'),
    });
    seenLinks.add(property.id);
  }
  pruneStructureS3DLinks(seenLinks);
  return slots;
};

drawGenericLinks3D = function drawGenericLinksViaS3D(time) {
  if (!ws) return;
  linkSlots();
  const width = linkSettings().flow_width;
  if (!Number.isFinite(width) || width <= 0) throw new Error('settings.link_visualization.flow_width must be positive');
  const pulseRadius = Math.max(.025, width * .14) * nodeMasterSize();
  for (const { property } of activeLinkProperties()) {
    const link = structureS3D.links.get(property.id);
    if (!link) throw new Error(`S3D Link instance unresolved: ${property.id}`);
    const amount = activationAmount(property.id);
    assignVec3(link, 'color', mixedLinkRgb(property, amount));
    assignVec3(link, 'flowColor', amount > 0 ? brightenedLinkRgb(property) : linkProjectionRgb(property, 'flow'));
    link.phase = flowProgress(property, time);
    assignVec3(link, 'pulseScale', [pulseRadius, pulseRadius, pulseRadius]);
    link.draw(structureS3DRenderer, { now: time });
  }
  const portRadius = .055 * nodeMasterSize();
  for (const [key, world] of linkProjection.ports) {
    const [, direction, linkType] = key.split('\u0000');
    drawBox(world, [portRadius, portRadius, portRadius], linkTypeRgb(linkType), direction === 'in');
  }
};

window.StructureS3D = Object.freeze({
  state: structureS3D,
  renderer: structureS3DRenderer,
  reset: resetStructureS3DScene,
  buildObjects: buildStructureS3DObjects,
  buildLink: buildStructureS3DLink,
  lifecycle: () => ({ ...structureS3D.lifecycle }),
});
