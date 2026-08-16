// Entity authoring overlays. Labels are fixed-size billboards; Event controls are node-relative.

const entityEditor = {
  entityId: null,
  labelElements: new Map(),
  eventElements: new Map(),
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

function selectedEntityForEditor() {
  if (selected.size !== 1) return null;
  const id = [...selected][0];
  const entity = ws.entities.find(item => item.id === id) || null;
  return entity ? ensureAuthoringFields(entity) : null;
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
      status(`Event ${currentEvent.value?.event_type_ref || currentEvent.id} @ ${currentEntity.name || currentEntity.id}`);
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
    }
  }

  const visible = visibleEntityIds();
  const vp = viewProjection();
  const density = devicePixelRatio || 1;
  const size = nodeMasterSize();

  for (const entity of ws.entities) {
    ensureAuthoringFields(entity);
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

    const events = (entity.properties || []).filter(property => property.property_type_ref === 'event');
    const eventSpacing = .34 * size;
    const eventStart = -(events.length - 1) * eventSpacing / 2;
    const pxPerWorld = worldPixelsAt(entity.position);
    const eventScale = Math.max(.18, Math.min(4, pxPerWorld * size / 42));

    events.forEach((property, index) => {
      const button = ensureEventButton(entity, property);
      if (!visible.has(entity.id)) {
        button.hidden = true;
        return;
      }
      const world = [
        entity.position[0] - .72 * size,
        entity.position[1] + eventStart + index * eventSpacing,
        entity.position[2],
      ];
      const screen = project(world, vp);
      if (!screen) {
        button.hidden = true;
        return;
      }
      button.hidden = false;
      button.textContent = property.value?.event_type_ref || property.id;
      button.style.left = `${screen[0] / density}px`;
      button.style.top = `${screen[1] / density}px`;
      button.style.setProperty('--event-world-scale', String(eventScale));
    });
  }
  requestAnimationFrame(renderNodeOverlays);
}

for (const entity of ws.entities) ensureAuthoringFields(entity);
renderEntityEditor();
requestAnimationFrame(renderNodeOverlays);
