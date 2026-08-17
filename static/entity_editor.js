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
function bindInfoSectionToggle(button) {
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
for (const button of document.querySelectorAll('[data-info-section-toggle]')) bindInfoSectionToggle(button);

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

function propertyRulesetForAuthoring(propertyTypeRef) {
  const matches = assertWorkspace().rulesets.filter(ruleset => ruleset.property_type_ref === propertyTypeRef);
  if (matches.length !== 1) throw new Error(`CW authoring requires exactly one ${propertyTypeRef} Ruleset, found ${matches.length}`);
  return matches[0];
}
function canonicalReferencesTo(ref) {
  const references = [];
  for (const owner of assertWorkspace().entities) {
    for (const property of owner.properties) {
      if (property.id === ref) continue;
      if (property.property_type_ref === 'link') {
        if (property.value.parent_ref === ref || property.value.child_ref === ref) references.push(property.id);
      }
      if (property.property_type_ref === 'function') {
        for (const field of ['input_refs', 'output_refs']) {
          if (Array.isArray(property.value[field]) && property.value[field].includes(ref)) references.push(`${property.id}.${field}`);
        }
      }
    }
  }
  return references;
}
function deleteCanonicalProperty(entity, propertyId) {
  const property = entity.properties.find(item => item.id === propertyId);
  if (!property) throw new Error(`Property unresolved: ${propertyId}`);
  const references = canonicalReferencesTo(propertyId);
  if (references.length) {
    status(`cannot delete ${propertyId}; referenced by ${references.join(', ')}`);
    return false;
  }
  entity.properties = entity.properties.filter(item => item.id !== propertyId);
  status(`deleted ${propertyId}`);
  renderEntityEditor();
  return true;
}
function normalizeCanonicalRefList(text, propertyId, field) {
  const refs = [...new Set(String(text).split(',').map(item => item.trim()).filter(Boolean))];
  const index = canonicalIndex();
  const unresolved = refs.filter(ref => !index.has(ref));
  if (unresolved.length) throw new Error(`${propertyId}.${field} unresolved canonical refs: ${unresolved.join(', ')}`);
  return refs;
}

function createDataProperty(entity, name, dataTypeRef) {
  const type = dataTypeRef.trim();
  if (!type) { status('Data type is required'); return null; }
  const ruleset = propertyRulesetForAuthoring('data');
  const property = {
    id: nextId('DATA'),
    property_type_ref: 'data',
    ruleset_ref: ruleset.id,
    status: 'unlocked',
    value: { data_type_ref: type, properties: {} },
  };
  const explicitName = name.trim();
  if (explicitName) property.name = explicitName;
  entity.properties.push(property);
  status(`created Data ${explicitName || property.id}`);
  renderEntityEditor();
  return property;
}
function createFunctionProperty(entity, name, functionTypeRef) {
  const type = functionTypeRef.trim();
  if (!type) { status('Function type is required'); return null; }
  const ruleset = propertyRulesetForAuthoring('function');
  const property = {
    id: nextId('FUNCTION'),
    property_type_ref: 'function',
    ruleset_ref: ruleset.id,
    status: 'unlocked',
    value: { function_type_ref: type, properties: {} },
  };
  const explicitName = name.trim();
  if (explicitName) property.name = explicitName;
  entity.properties.push(property);
  status(`created Function ${explicitName || property.id}`);
  renderEntityEditor();
  return property;
}

function createAuthoringInput(labelText, value, onChange, placeholder = '') {
  const label = document.createElement('label');
  label.textContent = labelText;
  const input = document.createElement('input');
  input.type = 'text';
  input.value = value ?? '';
  input.placeholder = placeholder;
  input.addEventListener('change', onChange);
  label.appendChild(input);
  return { label, input };
}
function renderAuthoredPropertyRow(entity, property) {
  const row = document.createElement('div');
  row.className = 'cw-property-authoring-row';
  row.dataset.propertyId = property.id;

  const heading = document.createElement('div');
  heading.className = 'cw-property-authoring-heading';
  const strong = document.createElement('strong');
  strong.textContent = propertyDisplayName(property, entity);
  const code = document.createElement('code');
  code.textContent = property.id;
  const remove = document.createElement('button');
  remove.type = 'button';
  remove.textContent = '×';
  remove.title = `Delete ${property.id}`;
  remove.addEventListener('click', () => deleteCanonicalProperty(entity, property.id));
  heading.append(strong, code, remove);
  row.appendChild(heading);

  const name = createAuthoringInput('Name', property.name ?? '', event => {
    const value = event.target.value.trim();
    if (value) property.name = value; else delete property.name;
    renderEntityEditor();
  });
  row.appendChild(name.label);

  if (property.property_type_ref === 'data') {
    const type = createAuthoringInput('Data type', property.value.data_type_ref, event => {
      const value = event.target.value.trim();
      if (!value) { event.target.value = property.value.data_type_ref; status('Data type is required'); return; }
      property.value.data_type_ref = value;
      renderEntityEditor();
    });
    row.appendChild(type.label);
  } else if (property.property_type_ref === 'function') {
    const type = createAuthoringInput('Function type', property.value.function_type_ref, event => {
      const value = event.target.value.trim();
      if (!value) { event.target.value = property.value.function_type_ref; status('Function type is required'); return; }
      property.value.function_type_ref = value;
      renderEntityEditor();
    });
    row.appendChild(type.label);
    for (const [field, labelText] of [['input_refs', 'Inputs'], ['output_refs', 'Outputs']]) {
      const refs = createAuthoringInput(labelText, (property.value[field] ?? []).join(', '), event => {
        try {
          const values = normalizeCanonicalRefList(event.target.value, property.id, field);
          if (values.length) property.value[field] = values; else delete property.value[field];
          renderEntityEditor();
        } catch (error) {
          event.target.value = (property.value[field] ?? []).join(', ');
          status(error.message);
        }
      }, 'canonical refs, comma separated');
      row.appendChild(refs.label);
    }
  }
  return row;
}

function ensureCwPropertyAuthoringSection() {
  if (document.querySelector('#cwPropertyAuthoring')) return;
  const editor = document.querySelector('#entityEditorFields');
  if (!editor) throw new Error('entity editor fields missing');
  const section = document.createElement('section');
  section.id = 'cwPropertyAuthoring';
  section.className = 'entity-info-section';
  section.dataset.infoSection = 'properties';
  const heading = document.createElement('button');
  heading.className = 'entity-info-heading';
  heading.type = 'button';
  heading.dataset.infoSectionToggle = 'properties';
  heading.setAttribute('aria-expanded', 'true');
  heading.textContent = 'CW Properties';
  bindInfoSectionToggle(heading);
  const body = document.createElement('div');
  body.className = 'entity-info-body';
  body.innerHTML = `
    <div class="cw-property-create" data-cw-create="data">
      <strong>Data</strong>
      <input data-cw-name="data" type="text" placeholder="Name (optional)">
      <input data-cw-type="data" type="text" placeholder="Data type">
      <button type="button" data-cw-create-button="data">+ Data</button>
    </div>
    <div class="cw-property-create" data-cw-create="function">
      <strong>Function</strong>
      <input data-cw-name="function" type="text" placeholder="Name (optional)">
      <input data-cw-type="function" type="text" placeholder="Function type">
      <button type="button" data-cw-create-button="function">+ Function</button>
    </div>
    <div id="cwAuthoredProperties"></div>`;
  section.append(heading, body);
  const descriptionSection = editor.querySelector('[data-info-section="description"]');
  editor.insertBefore(section, descriptionSection ?? null);

  body.querySelector('[data-cw-create-button="data"]').addEventListener('click', () => {
    const entity = selectedEntityForEditor();
    if (!entity) { status('Select one Entity to add Data'); return; }
    const name = body.querySelector('[data-cw-name="data"]');
    const type = body.querySelector('[data-cw-type="data"]');
    if (createDataProperty(entity, name.value, type.value)) { name.value = ''; type.value = ''; }
  });
  body.querySelector('[data-cw-create-button="function"]').addEventListener('click', () => {
    const entity = selectedEntityForEditor();
    if (!entity) { status('Select one Entity to add Function'); return; }
    const name = body.querySelector('[data-cw-name="function"]');
    const type = body.querySelector('[data-cw-type="function"]');
    if (createFunctionProperty(entity, name.value, type.value)) { name.value = ''; type.value = ''; }
  });
}
function renderCwPropertyAuthoring(entity) {
  const root = document.querySelector('#cwAuthoredProperties');
  if (!root) return;
  root.replaceChildren();
  if (!entity) return;
  const properties = entity.properties.filter(property => ['data', 'function'].includes(property.property_type_ref));
  for (const property of properties) root.appendChild(renderAuthoredPropertyRow(entity, property));
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
    renderCwPropertyAuthoring(null);
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
  renderCwPropertyAuthoring(entity);
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

ensureCwPropertyAuthoringSection();
