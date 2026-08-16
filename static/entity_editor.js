// Entity authoring overlays. Only Entity labels are fixed-size camera billboards.
// Event/Data/Effect projection instances are owner-relative world-space UI.

const entityEditor = {
  entityId: null,
  labelElements: new Map(),
  eventElements: new Map(),
  eventGeometry: new Map(),
};

function ensureAuthoringFields(entity) {
  entity.name ??= entity.id;
  entity.description ??= '';
  entity.contract ??= {};
  entity.contract.human ??= '';
  entity.contract.human_revision ??= 0;
  entity.contract.machine ??= {
    status: entity.contract.human ? 'needs_generation' : 'not_generated',
    generated_from_human_revision: null,
    data: null,
  };
  entity.contract.machine.status ??= entity.contract.human ? 'needs_generation' : 'not_generated';
  entity.contract.machine.generated_from_human_revision ??= null;
  if (!Object.hasOwn(entity.contract.machine, 'data')) entity.contract.machine.data = null;
  return entity;
}

function humanizeCanonicalName(value) {
  return String(value || '')
    .split('_')
    .filter(Boolean)
    .map(part => {
      const upper = part.toUpperCase();
      if (['ID', 'DB', 'API', 'HTTP', 'REST', 'OSC', 'URL', 'URI', 'SQL'].includes(upper)) return upper;
      return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
    })
    .join(' ');
}

// One presentation-name resolver for Property instances. It does not create semantic authority.
function propertyDisplayName(property, owner = null) {
  const explicit = property?.name || property?.value?.properties?.name;
  if (typeof explicit === 'string' && explicit.trim()) return explicit.trim();

  let ref = String(property?.id || '');
  const ownerPrefix = owner?.id ? `${owner.id}_` : '';
  if (ownerPrefix && ref.startsWith(ownerPrefix)) ref = ref.slice(ownerPrefix.length);

  for (const prefix of ['EVENT_', 'EFFECT_', 'DATA_', 'FUNCTION_']) {
    if (ref.startsWith(prefix)) {
      ref = ref.slice(prefix.length);
      break;
    }
  }

  if (/^\d+$/.test(ref)) {
    const semanticRef = property?.value?.event_type_ref || property?.value?.effect_type_ref || property?.value?.function_type_ref;
    if (semanticRef) ref = semanticRef;
  }

  return humanizeCanonicalName(ref || property?.id || property?.property_type_ref || 'Property');
}

// Apply an actual world-plane transform to a DOM overlay. The plane is fixed to world XY,
// so camera orbit changes its apparent angle/foreshortening instead of billboarding it.
// `worldPerCssPixel` controls physical size in the scene.
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

  const determinant = a * d - b * c;
  if (Math.abs(determinant) < 0.00001 || !width || !height) return false;

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

// World-derived projected edge anchors. These are intentionally not DOM bounding-box anchors:
// the attachment points remain on the fixed Entity-child plane when the camera orbits.
function worldPlaneProjectedAnchors(element, centerWorld, worldPerCssPixel, localY = null) {
  const width = element.offsetWidth;
  const height = element.offsetHeight;
  if (!width || !height) return null;
  const y = localY ?? height / 2;
  const points = {
    left: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, 0, y),
    right: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, width, y),
    top: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, width / 2, 0),
    bottom: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, width / 2, height),
    center: worldPlaneLocalToWorld(centerWorld, worldPerCssPixel, width, height, width / 2, y),
  };
  const projected = {};
  for (const [name, world] of Object.entries(points)) {
    const screen = projectWorldToCss(world);
    if (!screen) return null;
    projected[name] = { ...screen, world };
  }
  return projected;
}

function selectedEntityForEditor() {
  if (selected.size !== 1) return null;
  const id = [...selected][0];
  const entity = ws.entities.find(item => item.id === id) || null;
  return entity ? ensureAuthoringFields(entity) : null;
}

function infoPanelSettings() {
  ws.settings ??= {};
  ws.settings.view_defaults ??= {};
  ws.settings.view_defaults.entity_info_collapsed ??= {};
  return ws.settings.view_defaults.entity_info_collapsed;
}

function infoSectionCollapsed(entityId, section) {
  if (!entityId) return false;
  return Boolean(infoPanelSettings()[entityId]?.[section]);
}

function setInfoSectionCollapsed(entityId, section, collapsed) {
  if (!entityId) return;
  const states = infoPanelSettings();
  states[entityId] ??= {};
  if (collapsed) states[entityId][section] = true;
  else delete states[entityId][section];
  if (!Object.keys(states[entityId]).length) delete states[entityId];
}

function syncInfoSections() {
  const entity = selectedEntityForEditor();
  const entityId = entity?.id || null;
  for (const section of document.querySelectorAll('.entity-info-section[data-info-section]')) {
    const key = section.dataset.infoSection;
    const collapsed = infoSectionCollapsed(entityId, key);
    section.classList.toggle('collapsed', collapsed);
    const button = section.querySelector('.entity-info-heading');
    if (button) button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  }
}

for (const button of document.querySelectorAll('[data-info-section-toggle]')) {
  button.addEventListener('click', event => {
    event.preventDefault();
    const sectionKey = button.dataset.infoSectionToggle;
    const section = button.closest('.entity-info-section');
    const entity = selectedEntityForEditor();
    const collapsed = !section.classList.contains('collapsed');
    section.classList.toggle('collapsed', collapsed);
    button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    if (entity) setInfoSectionCollapsed(entity.id, sectionKey, collapsed);
  });
}

function machineContractStatus(entity) {
  const machine = entity.contract.machine;
  if (machine.status === 'synchronized' && machine.generated_from_human_revision === entity.contract.human_revision) {
    return `synchronized with human revision ${entity.contract.human_revision}`;
  }
  if (!entity.contract.human.trim()) return 'not generated — human contract is empty';
  return `needs generation from human revision ${entity.contract.human_revision}`;
}

function invalidateMachineContract(entity) {
  const contract = ensureAuthoringFields(entity).contract;
  contract.human_revision += 1;
  contract.machine.status = 'needs_generation';
  contract.machine.generated_from_human_revision = null;
  contract.machine.data = null;
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
  $('#entityDescription').value = entity.description;
  $('#entityHumanContract').value = entity.contract.human;
  $('#machineContractStatus').textContent = machineContractStatus(entity);
  syncInfoSections();
}

const baseInspect = inspect;
inspect = function () {
  baseInspect();
  renderEntityEditor();
};

$('#entityName').addEventListener('input', event => {
  const entity = selectedEntityForEditor();
  if (!entity) return;
  entity.name = event.target.value;
});

$('#entityDescription').addEventListener('input', event => {
  const entity = selectedEntityForEditor();
  if (!entity) return;
  entity.description = event.target.value;
});

$('#entityHumanContract').addEventListener('input', event => {
  const entity = selectedEntityForEditor();
  if (!entity) return;
  entity.contract.human = event.target.value;
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
      const currentEntity = ws.entities.find(item => item.id === button.dataset.entityId);
      const currentEvent = currentEntity?.properties?.find(item => item.id === button.dataset.eventId);
      if (!currentEntity || !currentEvent) return;
      status(`Event ${propertyDisplayName(currentEvent, currentEntity)} @ ${currentEntity.name || currentEntity.id}`);
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
  const livingEntities = new Set(ws.entities.map(entity => entity.id));
  const livingEvents = new Set(ws.entities.flatMap(entity => (entity.properties || [])
    .filter(property => property.property_type_ref === 'event')
    .map(property => property.id)));

  for (const [id, label] of entityEditor.labelElements) {
    if (!livingEntities.has(id)) {
      label.remove();
      entityEditor.labelElements.delete(id);
    }
  }
  for (const [id, button] of entityEditor.eventElements) {
    if (!livingEvents.has(id)) {
      button.remove();
      entityEditor.eventElements.delete(id);
      entityEditor.eventGeometry.delete(id);
    }
  }

  const visible = visibleEntityIds();
  const vp = viewProjection();
  const density = devicePixelRatio || 1;
  const size = nodeMasterSize();
  const half = nodeHalfSize();

  for (const entity of ws.entities) {
    ensureAuthoringFields(entity);

    // Entity label is the only fixed-size camera-facing label.
    const label = ensureNodeLabel(entity);
    if (!visible.has(entity.id)) {
      label.hidden = true;
    } else {
      const labelWorld = [entity.position[0], entity.position[1] + .72 * size, entity.position[2]];
      const screen = project(labelWorld, vp);
      if (!screen) {
        label.hidden = true;
      } else {
        label.hidden = false;
        label.textContent = entity.name || entity.id;
        label.style.left = `${screen[0] / density}px`;
        label.style.top = `${screen[1] / density}px`;
        label.classList.toggle('selected', selected.has(entity.id));
      }
    }

    // Event controls are true Entity-child world planes. Each Event's RIGHT EDGE is
    // attached directly to the Entity's LEFT EDGE. No camera-facing attachment math.
    const events = (entity.properties || []).filter(property => property.property_type_ref === 'event');
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

      const anchorWorld = [
        entity.position[0] - half,
        entity.position[1] + eventStart + index * eventSpacing,
        entity.position[2],
      ];
      const widthWorld = button.offsetWidth * worldPerCssPixel;
      const centerWorld = [anchorWorld[0] - widthWorld / 2, anchorWorld[1], anchorWorld[2]];

      if (!applyWorldPlaneTransform(button, centerWorld, worldPerCssPixel)) {
        button.hidden = true;
        entityEditor.eventGeometry.delete(property.id);
        return;
      }

      entityEditor.eventGeometry.set(property.id, {
        centerWorld,
        worldPerCssPixel,
        parentAnchorWorld: anchorWorld,
        parentAnchor: 'right-edge-to-entity-left-edge',
      });
    });
  }
  requestAnimationFrame(renderNodeOverlays);
}

for (const entity of ws.entities) ensureAuthoringFields(entity);
renderEntityEditor();
requestAnimationFrame(renderNodeOverlays);
