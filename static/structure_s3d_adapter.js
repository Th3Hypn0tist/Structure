// Structure -> S3D projection adapter.
// This is the semantic boundary: Structure resolves canonical CW meaning,
// while S3D receives only generic objects, anchors, links and presentation metadata.

const structureS3D = {
  scene: new S3D.Scene(),
  entities: new Map(),
  events: new Map(),
  props: new Map(),
  links: new Map(),
};

const structureS3DRenderer = new S3D.Renderer({
  box: (position, scale, color, outline = false) => drawBox(position, scale, color, outline),
  line: (start, end, color) => drawLine(start, end, color),
  point: (position, scale, color) => drawBox(position, scale, color),
});

function resetStructureS3DScene() {
  structureS3D.scene.clear();
  structureS3D.entities.clear();
  structureS3D.events.clear();
  structureS3D.props.clear();
  structureS3D.links.clear();
}

function ensureS3DEntity(entity) {
  let object = structureS3D.entities.get(entity.id);
  if (!object) {
    object = new S3D.SceneObject({ id: `entity:${entity.id}`, position: entity.position, metadata: { sourceRef: entity.id } });
    structureS3D.entities.set(entity.id, object);
    structureS3D.scene.add(object);
  }
  object.position = [...entity.position];
  return object;
}

function makeEventGroup(entity, layout) {
  const host = ensureS3DEntity(entity);
  const group = new S3D.Events({ id: `events:${entity.id}`, attachTo: host, metadata: { sourceRef: entity.id } });
  for (const row of layout.rows) {
    const item = new S3D.EventItem({
      id: `event:${row.ref}`,
      label: propertyDisplayName(row.property, entity),
      color: SCENE_COLORS.event,
      metadata: { sourceRef: row.ref },
    });
    item.position = row.center.map((value, index) => value - entity.position[index]);
    item.scale = [...row.halfScale];
    item.layoutWidth = row.width;
    item.layoutHeight = row.height;
    group.addItem(item);
    structureS3D.events.set(row.ref, item);
  }
  return group;
}

function makePropsGroup(entity, layout) {
  if (!layout) return null;
  const host = ensureS3DEntity(entity);
  const group = new S3D.Props({
    id: `props:${entity.id}`,
    attachTo: host,
    collapsed: layout.collapsed,
    metadata: { sourceRef: entity.id },
  });
  group.position = layout.center.map((value, index) => value - entity.position[index]);
  group.scale = [...layout.frameScale];
  for (const row of layout.rows) {
    const item = new S3D.PropsItem({
      id: `prop:${row.ref}`,
      label: `${row.item.propertyType.toUpperCase()} · ${displayName(row.item)}`,
      color: SCENE_COLORS[row.item.propertyType] ?? SCENE_COLORS.generic,
      metadata: { sourceRef: row.ref, propertyType: row.item.propertyType },
    });
    item.position = row.center.map((value, index) => value - entity.position[index]);
    item.scale = [...row.halfScale];
    item.layoutWidth = row.width;
    item.layoutHeight = row.height;
    group.addItem(item);
    structureS3D.props.set(row.ref, item);
  }
  return group;
}

function attachEventIoAnchors(entity, eventIo) {
  if (!eventIo) return null;
  const host = ensureS3DEntity(entity);
  const incoming = host.addAnchor(new S3D.Anchor({
    name: 'event_in',
    position: eventIo.inCenter.map((value, index) => value - entity.position[index]),
  }));
  const outgoing = host.addAnchor(new S3D.Anchor({
    name: 'event_out',
    position: eventIo.outCenter.map((value, index) => value - entity.position[index]),
  }));
  return { incoming, outgoing, halfScale: [...eventIo.halfScale] };
}

function buildStructureS3DObjects(layouts) {
  resetStructureS3DScene();
  for (const entity of assertWorkspace().entities) {
    const local = layouts.entities.get(entity.id);
    if (!local) continue;
    const host = ensureS3DEntity(entity);
    host.metadata.events = makeEventGroup(entity, local.eventLayout);
    host.metadata.props = makePropsGroup(entity, local.propsLayout);
    host.metadata.eventIo = attachEventIoAnchors(entity, local.eventIo);
  }
  return structureS3D;
}

function setS3DAnchor(object, name, worldPosition) {
  object.anchors.delete(name);
  return object.addAnchor(new S3D.Anchor({
    name,
    position: worldPosition.map((value, index) => value - object.worldPosition()[index]),
  }));
}

function buildStructureS3DLink(id, sourceObject, sourceAnchorName, targetObject, targetAnchorName, options = {}) {
  const from = sourceObject.anchor(sourceAnchorName);
  const to = targetObject.anchor(targetAnchorName);
  if (!from || !to) throw new Error(`S3D Link anchors unresolved: ${id}`);
  const link = new S3D.Link({ id: `link:${id}`, from, to, ...options, metadata: { ...(options.metadata ?? {}), sourceRef: id } });
  structureS3D.links.set(id, link);
  structureS3D.scene.add(link);
  return link;
}

const buildSceneLayoutsBeforeS3D = buildSceneLayouts;
buildSceneLayouts = function buildSceneLayoutsWithS3D(index) {
  const layouts = buildSceneLayoutsBeforeS3D(index);
  buildStructureS3DObjects(layouts);
  return layouts;
};

// Render Event/Props rows through their actual S3D instances while Structure
// retains the semantic activation, labels and hit-target policy.
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
    for (const route of allEventRoutes(layouts)) {
      const sourceObject = structureS3D.entities.get(route.sourceOwner.id);
      const targetObject = structureS3D.entities.get(route.targetOwner.id);
      const start = sourceObject?.anchor('event_out')?.worldPosition() ?? route.start;
      const end = targetObject?.anchor('event_in')?.worldPosition() ?? route.end;
      const projectedRoute = { ...route, start, end };
      drawLine(start, end, SCENE_COLORS.causal);
      const progress = eventRouteFlowProgress(route.key, now);
      new S3D.Pulse({ id: `event-route:${route.key}`, from: start, to: end, progress, color: SCENE_COLORS.causalFlow, scale: [pulseRadius*.65,pulseRadius*.65,pulseRadius*.65] }).draw(structureS3DRenderer, { now });
      for (const trace of causalProjection.currentEvents) {
        const edges = traceRouteEdges(trace).get(route.key);
        if (edges?.length) drawTransientTraceRoute(projectedRoute, trace, edges, globalElapsed, pulseRadius);
      }
    }
  }
};

const linkSlotsBeforeS3D = linkSlots;
linkSlots = function linkSlotsWithS3D() {
  const slots = linkSlotsBeforeS3D();
  for (const { property } of activeLinkProperties()) {
    const sourceEntity = entityForCanonicalRef(property.value.child_ref);
    const targetEntity = entityForCanonicalRef(property.value.parent_ref);
    const sourceObject = sourceEntity ? structureS3D.entities.get(sourceEntity.id) : null;
    const targetObject = targetEntity ? structureS3D.entities.get(targetEntity.id) : null;
    if (!sourceObject || !targetObject) throw new Error(`S3D Link endpoint object unresolved: ${property.id}`);
    const outName = `link:${property.id}:out`;
    const inName = `link:${property.id}:in`;
    setS3DAnchor(sourceObject, outName, slots.get(`${property.id}:out`));
    setS3DAnchor(targetObject, inName, slots.get(`${property.id}:in`));
    buildStructureS3DLink(property.id, sourceObject, outName, targetObject, inName, {
      color: linkProjectionRgb(property, 'base'),
      flowColor: linkProjectionRgb(property, 'flow'),
      speed: requiredNumber(linkSettings(), 'base_flow_speed', 'settings.link_visualization'),
    });
  }
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
    link.color = mixedLinkRgb(property, amount);
    link.flowColor = amount > 0 ? brightenedLinkRgb(property) : linkProjectionRgb(property, 'flow');
    link.phase = flowProgress(property, time);
    link.pulseScale = [pulseRadius, pulseRadius, pulseRadius];
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
});
