// View-only projection policy. Canonical links remain untouched.
// Generic scene links are aggregated by Entity pair + link type; causal links render only as Event routes.

const GENERIC_EXCLUDED_LINK_TYPES = new Set([
  'event_read',
  'event_input',
  'event_output',
  'event_effect',
  'event_cause',
  'event_condition',
  'effect_target',
]);

function projectedGenericLinkProperties() {
  const grouped = new Map();
  for (const item of linkProperties()) {
    const property = item.property;
    const value = property.value || {};
    const linkType = value.link_type_ref || 'relation';
    if (GENERIC_EXCLUDED_LINK_TYPES.has(linkType)) continue;
    if (ws.view.ruleset_ref !== 'ALL' && property.ruleset_ref !== ws.view.ruleset_ref) continue;

    const parentEntity = entityForCanonicalRef(value.parent_ref);
    const childEntity = entityForCanonicalRef(value.child_ref);
    if (!parentEntity || !childEntity) continue;

    const key = `${parentEntity.id}\u0000${childEntity.id}\u0000${linkType}`;
    if (!grouped.has(key)) grouped.set(key, item);
  }
  return [...grouped.values()];
}

// One projected line per Entity pair + link type. Multiple canonical links of the same type
// remain available semantically but do not create duplicate scene geometry.
activeLinkProperties = projectedGenericLinkProperties;

// Causal Ruleset views still keep the Entity field visible; their connections are rendered by
// causal_projection.js instead of the generic WebGL link renderer.
visibleEntityIds = function visibleEntityIds() {
  if (ws.view.ruleset_ref === 'ALL') return new Set(ws.entities.map(entity => entity.id));
  const selectedRuleset = rulesetMap().get(ws.view.ruleset_ref);
  if (GENERIC_EXCLUDED_LINK_TYPES.has(selectedRuleset?.link_type_ref)) {
    return new Set(ws.entities.map(entity => entity.id));
  }

  const ids = new Set();
  for (const { property } of activeLinkProperties()) {
    const parent = entityForCanonicalRef(property.value.parent_ref);
    const child = entityForCanonicalRef(property.value.child_ref);
    if (parent) ids.add(parent.id);
    if (child) ids.add(child.id);
  }
  return ids;
};

function resetEventProjection() {
  clearCausalProjection();
  document.querySelectorAll('.event-button.pulse').forEach(button => button.classList.remove('pulse'));
  status('events reset');
}

function ensureResetEventsControl() {
  const showAll = document.querySelector('#showAllProps');
  if (!showAll || document.querySelector('#resetEvents')) return;
  const button = document.createElement('button');
  button.id = 'resetEvents';
  button.type = 'button';
  button.className = 'show-all-props-control reset-events-control';
  button.textContent = 'RESET EVENTS';
  button.title = 'Clear active Event route, Event highlights and reached Property state';
  button.addEventListener('click', resetEventProjection);
  showAll.after(button);
}

ensureResetEventsControl();
