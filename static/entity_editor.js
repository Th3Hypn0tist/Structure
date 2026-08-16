// Entity authoring and owner-relative representation.
// Canonical data is never defaulted or migrated here. Optional fields are only
// created as a direct result of an explicit edit.

const entityEditor = {
  entityId: null,
  labelElements: new Map(),
  eventElements: new Map(),
  eventGeometry: new Map(),
};

function humanizeCanonicalName(value) {
  return String(value)
    .split('_')
    .filter(Boolean)
    .map(part => {
      const upper = part.toUpperCase();
      if (['ID', 'DB', 'API', 'HTTP', 'REST', 'OSC', 'URL', 'URI', 'SQL'].includes(upper)) return upper;
      return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
    })
    .join(' ');
}

function propertyDisplayName(property, owner = null) {
  const explicit = property.name ?? property.value?.properties?.name;
  if (typeof explicit === 'string' && explicit.trim()) return explicit.trim();
  let ref = String(property.id);
  const ownerPrefix = owner ? `${owner.id}_` : '';
  if (ownerPrefix && ref.startsWith(ownerPrefix)) ref = ref.slice(ownerPrefix.length);
  for (const prefix of ['EVENT_', 'EFFECT_', 'DATA_', 'FUNCTION_', 'TYPE_', 'MOUNT_']) {
    if (ref.startsWith(prefix)) { ref = ref.slice(prefix.length); break; }
  }
  return humanizeCanonicalName(ref);
}

function applyWorldPlaneTransform(element, centerWorld, worldPerCssPixel) {
  const vp = viewProjection();
  const density = devicePixelRatio || 1;
  const center = project(centerWorld, vp);
  const xPoint = project(V.add(centerWorld, [worldPerCssPixel, 0, 0]), vp);
  const yPoint = project(V.add(centerWorld, [0, -worldPerCssPixel, 0]), vp);
  if (!center || !xPoint || !yPoint) return false;
  const cx = center[0] / density;
  const cy = center[1] / density;
  const a = xPoint[0] / density - cx;
  const b = xPoint[1] / density - cy;
  const c = yPoint[0] / density - cx;
  const d = yPoint[1] / density - cy;
  const width = element.offsetWidth;
  const height = element.offsetHeight;
  if (!width || !height || Math.abs(a * d - b * c) < .00001) return false;
  const e = cx - a * width / 2 - c * height / 2;
  const f = cy - b * width / 2 - d * height / 2;
  element.style.left = '0px';
  element.style.top = '0px';
  element.style.transformOrigin = '0 0';
  element.style.transform = `matrix(${a}, ${b}, ${c}, ${d}, ${e}, ${f})`;
  return true;
}

function worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, localX, localY) {
  return [
    centerWorld[0] + (localX - width / 2) * worldPerCssPixel,
    centerWorld[1] - (localY - height / 2) * worldPerCssPixel,
    centerWorld[2],
  ];
}
function projectWorldToCss(world) {
  const screen = project(world, viewProjection());
  if (!screen) return null;
  const density = devicePixelRatio || 1;
  return { x: screen[0] / density, y: screen[1] / density };
}
function worldPlaneProjectedAnchors(element, centerWorld, worldPerCssPixel, localY = null) {
  const width = element.offsetWidth;
  const height = element.offsetHeight;
  if (!width || !height) return null;
  const y = localY ?? height / 2;
  const worldPoints = {
    left: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, 0, y),
    right: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, width, y),
    top: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, width / 2, 0),
    bottom: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, width / 2, height),
    center: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, width / 2, y),
  };
  const result = {};
  for (const [name, world] of Object.entries(worldPoints)) {
    const screen = projectWorldToCss(world);
    if (!screen) return null;
    result[name] = { ...screen, world };
  }
  return result;
}

function selectedEntityForEditor() {
  if (selected.size !== 1) return null;
  return assertWorkspace().entities.find(item => selected.has(item.id)) ?? null;
}
function infoPanelSettings() { return requiredObject(viewSettings(), 'entity_info_collapsed', 'settings.view_defaults'); }
function infoSectionCollapsed(entityId, section) { return entityId ? Boolean(infoPanelSettings()[entityId]?.[section]) : false; }
function setInfoSectionCollapsed(entityId, section, collapsed) {
  if (!entityId) return;
  const states = infoPanelSettings();
  if (!states[entityId]) states[entityId] = {};
  if (collapsed) states[entityId][section] = true;
  else delete states[entityId][section];
  if (!Object.keys(states[entityId]).length) delete states[entityId];
}
function syncInfoSections() {
  const entity = selectedEntityForEditor();
  for (const section of document.querySelectorAll('.entity-info-section[data-info-section]')) {
    const key = section.dataset.infoSection;
    const collapsed = infoSectionCollapsed(entity?.id ?? null, key);
    section.classList.toggle('collapsed', collapsed);
    section.querySelector('.entity-info-heading')?.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  }
}

for (const button of document.querySelectorAll('[data-info-section-toggle]')) {
  button.addEventListener('click', event => {
    event.preventDefault();
    const entity = selectedEntityForEditor();
    const section = button.closest('.entity-info-section');
    const collapsed = !section.classList.contains('collapsed');
    section.classList.toggle('collapsed', collapsed);
    button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    if (entity) setInfoSectionCollapsed(entity.id, button.dataset.infoSectionToggle, collapsed);
  });
}

function entityTypeProperty(entity) {
  const matches = entity.properties.filter(property => property.property_type_ref === 'type');
  if (matches.length > 1) throw new Error(`Entity ${entity.id} has multiple Type Properties`);
  return matches[0] ?? null;
}
function setEntityType(entity, typeRef) {
  const existing = entityTypeProperty(entity);
  const value = typeRef.trim();
  if (!value) {
    if (existing) entity.properties = entity.properties.filter(property => property.id !== existing.id);
    return;
  }
  if (existing) {
    existing.value.type_ref = value;
    return;
  }
  entity.properties.push({
    id: nextId('TYPE'),
    property_type_ref: 'type',
    ruleset_ref: 'RULESET_TYPE',
    status: 'unlocked',
    value: { type_ref: value, properties: {} },
  });
}

function machineContractStatus(entity) {
  const contract = entity.contract;
  if (!contract) return 'not generated — no human contract';
  if (!contract.human) return 'not generated — human contract is empty';
  const machine = contract.machine;
  if (!machine) return `needs generation from human revision ${contract.human_revision}`;
  if (machine.status === 'synchronized' && machine.generated_from_human_revision === contract.human_revision) return `synchronized with human revision ${contract.human_revision}`;
  return `needs generation from human revision ${contract.human_revision}`;
}
function contractForExplicitEdit(entity) {
  if (!entity.contract) {
    entity.contract = {
      human: '',
      human_revision: 0,
      machine: { status: 'not_generated', generated_from_human_revision: null, data: null },
    };
  }
  return entity.contract;
}
function invalidateMachineContract(entity) {
  const contract = contractForExplicitEdit(entity);
  contract.human_revision += 1;
  contract.machine = { status: 'needs_generation', generated_from_human_revision: null, data: null };
}

function renderEntityEditor() {
  const entity = selectedEntityForEditor();
  const editor = $('#entityEditorFields');
  const empty = $('#entityEditorEmpty');
  if (!entity) {
    entityEditor.entityId = null;
    editor.hidden = true;
    empty.hidden = false;
    empty.textContent = selected.size > 1 ? `${selected.size} Entities selected` : 'Select one Entity to edit';
    syncInfoSections();
    return;
  }
  empty.hidden = true;
  editor.hidden = false;
  entityEditor.entityId = entity.id;
  $('#entityId').textContent = entity.id;
  $('#entityName').value = entity.name;
  $('#entityType').value = entityTypeProperty(entity)?.value.type_ref ?? '';
  $('#entityDescription').value = entity.description ?? '';
  $('#entityHumanContract').value = entity.contract?.human ?? '';
  $('#machineContractStatus').textContent = machineContractStatus(entity);
  syncInfoSections();
}

$('#entityName').addEventListener('change', event => {
  const entity = selectedEntityForEditor();
  if (!entity) return;
  const name = event.target.value.trim();
  if (!name) { event.target.value = entity.name; status('Entity name is required'); return; }
  entity.name = name;
});
$('#entityType').addEventListener('change', event => {
  const entity = selectedEntityForEditor();
  if (!entity) return;
  setEntityType(entity, event.target.value);
  renderEntityEditor();
  status(event.target.value.trim() ? `type declared: ${event.target.value.trim()}` : 'type unresolved');
});
$('#entityDescription').addEventListener('input', event => {
  const entity = selectedEntityForEditor();
  if (!entity) return;
  entity.description = event.target.value;
});
$('#entityHumanContract').addEventListener('input', event => {
  const entity = selectedEntityForEditor();
  if (!entity) return;
  const contract = contractForExplicitEdit(entity);
  contract.human = event.target.value;
  invalidateMachineContract(entity);
  $('#machineContractStatus').textContent = machineContractStatus(entity);
});

function ensureNodeLabel(entity) {
  let label = entityEditor.labelElements.get(entity.id);
  if (!label) {
    label = document.createElement('div');
    label.className = 'node-label';
    label.dataset.entityId = entity.id;
    $('#nodeLabels').appendChild(label);
    entityEditor.labelElements.set(entity.id, label);
  }
  return label;
}
function ensureEventButton(entity, property) {
  let button = entityEditor.eventElements.get(property.id);
  if (!button) {
    button = document.createElement('button');
    button.type = 'button';
    button.className = 'event-button';
    button.dataset.entityId = entity.id;
    button.dataset.eventId = property.id;
    button.addEventListener('click', event => {
      event.stopPropagation();
      const item = canonicalIndex().get(button.dataset.eventId);
      if (!item || item.propertyType !== 'event') throw new Error(`Event unresolved: ${button.dataset.eventId}`);
      status(`Event ${propertyDisplayName(item.object, item.owner)} @ ${item.owner.name}`);
      button.classList.remove('pulse');
      void button.offsetWidth;
      button.classList.add('pulse');
    });
    document.body.appendChild(button);
    entityEditor.eventElements.set(property.id, button);
  }
  return button;
}

function renderNodeOverlays() {
  if (!ws) { requestAnimationFrame(renderNodeOverlays); return; }
  const livingEntities = new Set(assertWorkspace().entities.map(entity => entity.id));
  const livingEvents = new Set(assertWorkspace().entities.flatMap(entity => entity.properties.filter(property => property.property_type_ref === 'event').map(property => property.id)));
  for (const [id, label] of entityEditor.labelElements) {
    if (!livingEntities.has(id)) { label.remove(); entityEditor.labelElements.delete(id); }
  }
  for (const [id, button] of entityEditor.eventElements) {
    if (!livingEvents.has(id)) { button.remove(); entityEditor.eventElements.delete(id); entityEditor.eventGeometry.delete(id); }
  }

  const visible = visibleEntityIds();
  const vp = viewProjection();
  const density = devicePixelRatio || 1;
  const size = nodeMasterSize();
  const half = nodeHalfSize();
  for (const entity of assertWorkspace().entities) {
    const label = ensureNodeLabel(entity);
    if (!visible.has(entity.id)) label.hidden = true;
    else {
      const screen = project([entity.position[0], entity.position[1] + .72 * size, entity.position[2]], vp);
      if (!screen) label.hidden = true;
      else {
        label.hidden = false;
        label.textContent = entity.name;
        label.style.left = `${screen[0] / density}px`;
        label.style.top = `${screen[1] / density}px`;
        label.classList.toggle('selected', selected.has(entity.id));
      }
    }

    const events = entity.properties.filter(property => property.property_type_ref === 'event');
    const eventSpacing = .34 * size;
    const eventStart = -(events.length - 1) * eventSpacing / 2;
    const worldPerCssPixel = size / 42;
    events.forEach((property, index) => {
      const button = ensureEventButton(entity, property);
      if (!visible.has(entity.id)) {
        button.hidden = true;
        entityEditor.eventGeometry.delete(property.id);
        return;
      }
      button.textContent = propertyDisplayName(property, entity);
      button.hidden = false;
      const anchorWorld = [entity.position[0] - half, entity.position[1] + eventStart + index * eventSpacing, entity.position[2]];
      const widthWorld = button.offsetWidth * worldPerCssPixel;
      const centerWorld = [anchorWorld[0] - widthWorld / 2, anchorWorld[1], anchorWorld[2]];
      if (!applyWorldPlaneTransform(button, centerWorld, worldPerCssPixel)) {
        button.hidden = true;
        entityEditor.eventGeometry.delete(property.id);
        return;
      }
      entityEditor.eventGeometry.set(property.id, { centerWorld, worldPerCssPixel, parentAnchorWorld: anchorWorld, parentAnchor: 'right-edge-to-entity-left-edge' });
    });
  }
  requestAnimationFrame(renderNodeOverlays);
}

requestAnimationFrame(renderNodeOverlays);
