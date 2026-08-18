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
    group.addItem(item);
    structureS3D.props.set(row.ref, item);
  }
  return group;
}

function attachEventIoAnchors(entity, eventIo) {
  if (!eventIo) return null;
  const host = ensureS3DEntity(entity);
  const inLocal = eventIo.inCenter.map((value, index) => value - entity.position[index]);
  const outLocal = eventIo.outCenter.map((value, index) => value - entity.position[index]);
  const incoming = new S3D.Anchor({ name: 'event_in', position: inLocal });
  const outgoing = new S3D.Anchor({ name: 'event_out', position: outLocal });
  host.setAnchor(incoming);
  host.setAnchor(outgoing);
  return { incoming, outgoing };
}

function buildStructureS3DObjects(layouts) {
  resetStructureS3DScene();
  for (const entity of assertWorkspace().entities) {
    const local = layouts.entities.get(entity.id);
    if (!local) continue;
    const host = ensureS3DEntity(entity);
    const events = makeEventGroup(entity, local.eventLayout);
    const props = makePropsGroup(entity, local.propsLayout);
    const eventIo = attachEventIoAnchors(entity, local.eventIo);
    host.metadata.events = events;
    host.metadata.props = props;
    host.metadata.eventIo = eventIo;
  }
  return structureS3D;
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

window.StructureS3D = Object.freeze({
  state: structureS3D,
  renderer: structureS3DRenderer,
  reset: resetStructureS3DScene,
  buildObjects: buildStructureS3DObjects,
  buildLink: buildStructureS3DLink,
});
