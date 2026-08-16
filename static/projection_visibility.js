// Generic projection policy. This module owns active Link selection and Entity
// visibility directly; it never replaces functions defined by another module.

const GENERIC_EXCLUDED_LINK_TYPES = new Set([
  'event_read',
  'event_input',
  'event_output',
  'event_effect',
  'event_cause',
  'event_condition',
  'effect_target',
]);

function projectionVisibilitySettings() { return viewSettings(); }
function isLinkTypeVisible(linkType) { return !projectionVisibilitySettings().hidden_link_types[linkType]; }
function setLinkTypeVisible(linkType, visible) {
  const hidden = projectionVisibilitySettings().hidden_link_types;
  if (visible) delete hidden[linkType];
  else hidden[linkType] = true;
}

function activeLinkProperties() {
  const grouped = new Map();
  const selectedRuleset = projectionVisibilitySettings().ruleset_ref;
  for (const item of linkProperties()) {
    const property = item.property;
    const linkType = property.value.link_type_ref;
    if (GENERIC_EXCLUDED_LINK_TYPES.has(linkType)) continue;
    if (!isLinkTypeVisible(linkType)) continue;
    if (selectedRuleset !== 'ALL' && property.ruleset_ref !== selectedRuleset) continue;
    const parentEntity = entityForCanonicalRef(property.value.parent_ref);
    const childEntity = entityForCanonicalRef(property.value.child_ref);
    if (!parentEntity || !childEntity) throw new Error(`Link ${property.id} has unresolved visual endpoint`);
    const key = `${parentEntity.id}\u0000${childEntity.id}\u0000${linkType}`;
    if (!grouped.has(key)) grouped.set(key, item);
  }
  return [...grouped.values()];
}

function visibleEntityIds() {
  const selectedRuleset = projectionVisibilitySettings().ruleset_ref;
  if (selectedRuleset === 'ALL') return new Set(assertWorkspace().entities.map(entity => entity.id));
  const ruleset = rulesetMap().get(selectedRuleset);
  if (!ruleset) throw new Error(`selected Ruleset does not resolve: ${selectedRuleset}`);
  if (GENERIC_EXCLUDED_LINK_TYPES.has(ruleset.link_type_ref)) return new Set(assertWorkspace().entities.map(entity => entity.id));
  const ids = new Set();
  for (const { property } of activeLinkProperties()) {
    ids.add(entityForCanonicalRef(property.value.parent_ref).id);
    ids.add(entityForCanonicalRef(property.value.child_ref).id);
  }
  return ids;
}

function resetEventProjection() {
  clearCausalProjection();
  document.querySelectorAll('.event-button.pulse').forEach(button => button.classList.remove('pulse'));
  status('events reset');
}
function bindResetEventsControl() {
  $('#resetEvents').addEventListener('click', resetEventProjection);
}

function genericLinkTypes() {
  const types = new Map();
  for (const ruleset of assertWorkspace().rulesets) {
    if (ruleset.property_type_ref !== 'link') continue;
    const linkType = ruleset.link_type_ref;
    if (GENERIC_EXCLUDED_LINK_TYPES.has(linkType) || types.has(linkType)) continue;
    types.set(linkType, ruleset);
  }
  return [...types.entries()];
}
function projectionToggle(label, checked, swatch, onChange) {
  const row = document.createElement('label');
  row.className = 'projection-toggle';
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = checked;
  const marker = document.createElement('span');
  marker.className = 'projection-toggle-marker';
  marker.style.background = swatch;
  const text = document.createElement('span');
  text.textContent = label;
  input.addEventListener('change', () => onChange(input.checked));
  row.append(input, marker, text);
  return row;
}
function cssColor(rgb) {
  if (!Array.isArray(rgb) || rgb.length !== 3) throw new Error('color must be [r,g,b]');
  return `rgb(${rgb.map(value => Math.round(value * 255)).join(',')})`;
}

function renderProjectionControls() {
  if (!ws) return;
  const root = $('#projectionControls');
  const settings = projectionVisibilitySettings();
  const rulesets = rulesetMap();
  const colorSpaces = colorSpaceMap();
  root.replaceChildren();
  const heading = document.createElement('div');
  heading.className = 'projection-controls-heading';
  heading.textContent = 'VISIBILITY';
  root.appendChild(heading);
  for (const [linkType, ruleset] of genericLinkTypes()) {
    const colorSpace = colorSpaces.get(ruleset.color_space_ref);
    if (!colorSpace) throw new Error(`ColorSpace unresolved: ${ruleset.color_space_ref}`);
    root.appendChild(projectionToggle(
      ruleset.name,
      isLinkTypeVisible(linkType),
      cssColor(colorSpace.colors.flow),
      visible => setLinkTypeVisible(linkType, visible),
    ));
  }
  const causalRuleset = rulesets.get('RULESET_LINK_EVENT_EFFECT');
  if (!causalRuleset) throw new Error('RULESET_LINK_EVENT_EFFECT missing');
  const causalSpace = colorSpaces.get(causalRuleset.color_space_ref);
  if (!causalSpace) throw new Error(`ColorSpace unresolved: ${causalRuleset.color_space_ref}`);
  root.appendChild(projectionToggle(
    'Event routes',
    settings.event_routes_visible,
    cssColor(causalSpace.colors.flow),
    visible => {
      settings.event_routes_visible = visible;
      syncEventRouteVisibility();
    },
  ));
}
function syncEventRouteVisibility() {
  if (!ws) return;
  const svg = document.querySelector('#causalLines');
  if (!svg) throw new Error('required causal projection surface missing: #causalLines');
  svg.style.display = projectionVisibilitySettings().event_routes_visible ? '' : 'none';
}

window.addEventListener('load', bindResetEventsControl);
