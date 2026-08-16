// Abstraction Library and canonical semantic export.
// Publish and Export CW share exactly the same semantic source boundary:
// Entities + Rulesets + ColorSpaces. Camera and view/runtime state are excluded.

const ABSTRACTION_VERSION = '1.0.0';

function canonicalSemanticPayload() {
  const source = assertWorkspace();
  return {
    entities: structuredClone(source.entities),
    rulesets: structuredClone(source.rulesets),
    color_spaces: structuredClone(source.color_spaces),
  };
}

function cwExportDocument() {
  const source = assertWorkspace();
  return {
    version: source.version,
    ...canonicalSemanticPayload(),
  };
}

function cwExportFilename() {
  const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
  return `Structure_CW_${timestamp}.json`;
}

function downloadJson(filename, value) {
  const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

function exportCurrentCw() {
  const documentValue = cwExportDocument();
  const filename = cwExportFilename();
  downloadJson(filename, documentValue);
  status(`exported CW · ${documentValue.entities.length} entities · ${filename}`);
}

function openPublishAbstraction() {
  $('#abstractionId').value = '';
  $('#abstractionName').value = '';
  $('#publishAbstractionPopup').hidden = false;
  $('#abstractionId').focus();
}
function closePublishAbstraction() { $('#publishAbstractionPopup').hidden = true; }

async function publishCurrentAbstraction() {
  const id = $('#abstractionId').value.trim();
  const name = $('#abstractionName').value.trim();
  if (!id || !name) { status('Abstraction ID and name are required'); return; }
  const abstraction = {
    version: ABSTRACTION_VERSION,
    id,
    name,
    ...canonicalSemanticPayload(),
  };
  await fetchJson('/api/abstractions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(abstraction),
  });
  closePublishAbstraction();
  status(`published Abstraction ${id}`);
}

async function openMountAbstraction() {
  const abstractions = (await fetchJson('/api/abstractions')).abstractions;
  const list = $('#mountAbstractionList');
  list.replaceChildren();
  if (!abstractions.length) {
    list.textContent = 'No published Abstractions';
  } else {
    for (const abstraction of abstractions) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'abstraction-list-item';
      button.dataset.abstractionRef = abstraction.id;
      button.dataset.abstractionName = abstraction.name;
      button.innerHTML = `<strong>${abstraction.name}</strong><code>${abstraction.id}</code><small>${abstraction.version}</small>`;
      list.appendChild(button);
    }
  }
  $('#mountAbstractionPopup').hidden = false;
}
function closeMountAbstraction() { $('#mountAbstractionPopup').hidden = true; }

function mountPublishedAbstraction(abstractionRef, abstractionName) {
  if (!abstractionRef || !abstractionName) throw new Error('Mount requires Abstraction reference and name');
  const position = V.add(assertWorkspace().camera.position, V.mul(viewForward(), 5));
  if (viewSettings().snap_to_grid) {
    for (let axis = 0; axis < 3; axis++) position[axis] = Math.round(position[axis] / gridSize()) * gridSize();
  }
  const entityId = nextId('ENTITY');
  const mountId = nextId('MOUNT');
  assertWorkspace().entities.push({
    id: entityId,
    name: abstractionName,
    status: 'unlocked',
    position,
    properties: [{
      id: mountId,
      property_type_ref: 'mount',
      ruleset_ref: 'RULESET_MOUNT',
      status: 'unlocked',
      value: { abstraction_ref: abstractionRef, properties: {} },
    }],
  });
  selected = new Set([entityId]);
  setActiveEntity(entityId);
  closeMountAbstraction();
  inspect();
  updateButtons();
  status(`mounted Abstraction ${abstractionRef}`);
}

window.addEventListener('load', () => {
  $('#exportCw').onclick = () => {
    try { exportCurrentCw(); }
    catch (error) { reportUiError(error); }
  };
  $('#confirmPublishAbstraction').onclick = () => publishCurrentAbstraction().catch(reportUiError);
  $('#cancelPublishAbstraction').onclick = closePublishAbstraction;
  $('#cancelMountAbstraction').onclick = closeMountAbstraction;
  $('#mountAbstractionList').addEventListener('click', event => {
    const button = event.target.closest('.abstraction-list-item');
    if (!button) return;
    mountPublishedAbstraction(button.dataset.abstractionRef, button.dataset.abstractionName);
  });
});
