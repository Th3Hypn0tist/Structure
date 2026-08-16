// Entity authoring only. Scene representation lives in the 3D projection
// layer; this module must not create DOM representations of canonical scene
// objects.

const entityEditor = { entityId: null };

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
  if (existing) { existing.value.type_ref = value; return; }
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
