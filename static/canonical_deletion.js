// Canonical deletion authoring. Destructive edits are preflighted against
// surviving canonical references before any mutation is applied.

function deletionLinkRecords() {
  return assertWorkspace().entities.flatMap(owner => owner.properties
    .filter(property => property.property_type_ref === 'link')
    .map(property => ({ owner, property })));
}

function deletionPropertyRecord(ref, expectedType = null) {
  const item = canonicalIndex().get(ref);
  if (!item || item.kind !== 'property') return null;
  if (expectedType && item.propertyType !== expectedType) return null;
  return { owner: item.owner, property: item.object };
}

function deletionLinkClosure(seedRefs) {
  const deletedRefs = new Set(seedRefs);
  const linkIds = new Set();
  let changed = true;
  while (changed) {
    changed = false;
    for (const { property } of deletionLinkRecords()) {
      if (linkIds.has(property.id) || deletedRefs.has(property.id)) continue;
      const value = property.value;
      if (deletedRefs.has(value.parent_ref) || deletedRefs.has(value.child_ref)) {
        linkIds.add(property.id);
        deletedRefs.add(property.id);
        changed = true;
      }
    }
  }
  return { deletedRefs, linkIds };
}

function deletionBlockers(deletedRefs, removedEntityIds = new Set(), removedPropertyIds = new Set(), removedLinkIds = new Set()) {
  const blockers = [];
  for (const entity of assertWorkspace().entities) {
    if (removedEntityIds.has(entity.id)) continue;
    if (entity.coordinate_space_ref && deletedRefs.has(entity.coordinate_space_ref)) {
      blockers.push(`${entity.id}.coordinate_space_ref -> ${entity.coordinate_space_ref}`);
    }
    for (const property of entity.properties) {
      if (removedPropertyIds.has(property.id) || removedLinkIds.has(property.id)) continue;
      if (property.property_type_ref === 'function') {
        for (const field of ['input_refs', 'output_refs']) {
          const refs = property.value[field];
          if (!Array.isArray(refs)) continue;
          for (const ref of refs) if (deletedRefs.has(ref)) blockers.push(`${property.id}.${field} -> ${ref}`);
        }
      }
      if (property.property_type_ref === 'link') {
        for (const field of ['parent_ref', 'child_ref']) {
          const ref = property.value[field];
          if (deletedRefs.has(ref)) blockers.push(`${property.id}.${field} -> ${ref}`);
        }
      }
    }
  }
  return [...new Set(blockers)].sort();
}

function deletionBlocked(label, blockers) {
  if (!blockers.length) return false;
  status(`cannot delete ${label}; referenced by ${blockers.join(', ')}`);
  return true;
}

function removeCanonicalLinks(linkIds) {
  if (!linkIds.size) return 0;
  let removed = 0;
  for (const entity of assertWorkspace().entities) {
    const before = entity.properties.length;
    entity.properties = entity.properties.filter(property => !linkIds.has(property.id));
    removed += before - entity.properties.length;
  }
  return removed;
}

function resetDeletionRuntimeProjection() {
  const reset = document.querySelector('#resetEvents');
  if (reset) reset.click();
}

function deleteCanonicalLink(linkRef) {
  const record = deletionPropertyRecord(linkRef, 'link');
  if (!record) throw new Error(`Link unresolved: ${linkRef}`);
  const deletedRefs = new Set([linkRef]);
  const removedPropertyIds = new Set([linkRef]);
  const blockers = deletionBlockers(deletedRefs, new Set(), removedPropertyIds, new Set());
  if (deletionBlocked(linkRef, blockers)) return false;
  record.owner.properties = record.owner.properties.filter(property => property.id !== linkRef);
  resetDeletionRuntimeProjection();
  inspect();
  status(`deleted Link ${linkRef}`);
  return true;
}

function deleteCanonicalEvent(eventRef) {
  const record = deletionPropertyRecord(eventRef, 'event');
  if (!record) throw new Error(`Event unresolved: ${eventRef}`);
  const removedPropertyIds = new Set([eventRef]);
  const { deletedRefs, linkIds } = deletionLinkClosure(removedPropertyIds);
  const blockers = deletionBlockers(deletedRefs, new Set(), removedPropertyIds, linkIds);
  if (deletionBlocked(eventRef, blockers)) return false;
  record.owner.properties = record.owner.properties.filter(property => property.id !== eventRef);
  const removedLinks = removeCanonicalLinks(linkIds);
  if (typeof eventRuleEditor !== 'undefined' && eventRuleEditor.eventRef === eventRef) {
    eventRuleEditor.eventRef = null;
    const modal = document.querySelector('#eventRuleEditor');
    if (modal) modal.hidden = true;
  }
  resetDeletionRuntimeProjection();
  inspect();
  status(`deleted Event ${eventRef}${removedLinks ? ` + ${removedLinks} incident Links` : ''}`);
  return true;
}

function deleteSelectedEntitiesCanonical() {
  const removedEntityIds = new Set(selected);
  if (!removedEntityIds.size) return false;
  const removedPropertyIds = new Set();
  const rootRefs = new Set(removedEntityIds);
  for (const entity of assertWorkspace().entities) {
    if (!removedEntityIds.has(entity.id)) continue;
    for (const property of entity.properties) {
      removedPropertyIds.add(property.id);
      rootRefs.add(property.id);
    }
  }
  const { deletedRefs, linkIds } = deletionLinkClosure(rootRefs);
  const blockers = deletionBlockers(deletedRefs, removedEntityIds, removedPropertyIds, linkIds);
  if (deletionBlocked(`${removedEntityIds.size} selected Entities`, blockers)) return false;
  if (lookAtEntityId && removedEntityIds.has(lookAtEntityId)) detachLookAtReference();
  assertWorkspace().entities = assertWorkspace().entities.filter(entity => !removedEntityIds.has(entity.id));
  const removedLinks = removeCanonicalLinks(linkIds);
  selected.clear();
  activeEntityId = null;
  resetDeletionRuntimeProjection();
  inspect();
  updateButtons();
  status(`deleted ${removedEntityIds.size} Entities${removedLinks ? ` + ${removedLinks} incident Links` : ''}`);
  return true;
}

deleteSelectedEntities = deleteSelectedEntitiesCanonical;

function ensureCanonicalDeletionStyles() {
  if (document.querySelector('#canonicalDeletionStyles')) return;
  const style = document.createElement('style');
  style.id = 'canonicalDeletionStyles';
  style.textContent = `
    #selection .link-row.canonical-delete-ready{grid-template-columns:14px minmax(0,1fr) 24px;align-items:center}
    .canonical-link-delete,.canonical-event-delete{width:24px;height:24px;padding:0;border-radius:50%;background:#241416;border-color:#60302f;color:#e47a6d;font-weight:900}
    .canonical-event-list-entry{display:grid;grid-template-columns:minmax(0,1fr) 26px;gap:5px;align-items:center;margin:4px 0}
    .canonical-event-list-entry .event-rule-list-button{margin:0}
  `;
  document.head.appendChild(style);
}

function enhanceLinkDeleteControls() {
  if (selected.size !== 1) return;
  const entity = assertWorkspace().entities.find(item => selected.has(item.id));
  if (!entity) return;
  const entries = linkProperties().filter(({ property }) =>
    entityForCanonicalRef(property.value.parent_ref)?.id === entity.id ||
    entityForCanonicalRef(property.value.child_ref)?.id === entity.id);
  const rows = [...document.querySelectorAll('#selection .link-row')];
  entries.forEach((entry, index) => {
    const row = rows[index];
    if (!row || row.querySelector('[data-canonical-link-delete]')) return;
    row.classList.add('canonical-delete-ready');
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'canonical-link-delete';
    remove.dataset.canonicalLinkDelete = entry.property.id;
    remove.title = `Delete ${entry.property.id}`;
    remove.textContent = '×';
    remove.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      deleteCanonicalLink(entry.property.id);
    });
    row.appendChild(remove);
  });
}

function enhanceEventDeleteControls() {
  for (const open of [...document.querySelectorAll('[data-event-rule-open]')]) {
    if (open.closest('.canonical-event-list-entry')) continue;
    const wrapper = document.createElement('div');
    wrapper.className = 'canonical-event-list-entry';
    open.parentNode.insertBefore(wrapper, open);
    wrapper.appendChild(open);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'canonical-event-delete';
    remove.dataset.canonicalEventDelete = open.dataset.eventRuleOpen;
    remove.title = `Delete ${open.dataset.eventRuleOpen}`;
    remove.textContent = '×';
    remove.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      deleteCanonicalEvent(open.dataset.eventRuleOpen);
    });
    wrapper.appendChild(remove);
  }
}

const canonicalDeletionInspectBase = inspect;
inspect = function inspectWithCanonicalDeletion() {
  canonicalDeletionInspectBase();
  enhanceLinkDeleteControls();
};

const canonicalDeletionEventRenderBase = renderEventRuleSection;
renderEventRuleSection = function renderEventRuleSectionWithCanonicalDeletion() {
  canonicalDeletionEventRenderBase();
  enhanceEventDeleteControls();
};

ensureCanonicalDeletionStyles();

window.StructureCanonicalDeletion = {
  deletionLinkClosure,
  deletionBlockers,
  deleteCanonicalLink,
  deleteCanonicalEvent,
  deleteSelectedEntitiesCanonical,
};
