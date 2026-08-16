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

function projectionVisibilitySettings() {
  ws.settings ??= {};
  ws.settings.view_defaults ??= {};
  const view = ws.settings.view_defaults;
  view.hidden_link_types ??= {};
  view.event_routes_visible ??= true;
  return view;
}

function isLinkTypeVisible(linkType) {
  return !projectionVisibilitySettings().hidden_link_types?.[linkType];
}

function setLinkTypeVisible(linkType, visible) {
  const hidden = projectionVisibilitySettings().hidden_link_types;
  if (visible) delete hidden[linkType];
  else hidden[linkType] = true;
}

function projectedGenericLinkProperties() {
  const grouped = new Map();
  for (const item of linkProperties()) {
    const property = item.property;
    const value = property.value || {};
    const linkType = value.link_type_ref || 'relation';
    if (GENERIC_EXCLUDED_LINK_TYPES.has(linkType)) continue;
    if (!isLinkTypeVisible(linkType)) continue;
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

// Causal Ruleset views keep Entities visible; their connections belong exclusively to the
// curved causal projection, never to the generic WebGL link renderer.
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

function genericLinkTypes() {
  const types = new Map();
  for (const ruleset of ws.rulesets || []) {
    if (ruleset.property_type_ref !== 'link') continue;
    const linkType = ruleset.link_type_ref;
    if (!linkType || GENERIC_EXCLUDED_LINK_TYPES.has(linkType) || types.has(linkType)) continue;
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
  if (swatch) marker.style.background = swatch;
  const text = document.createElement('span');
  text.textContent = label;
  input.addEventListener('change', () => onChange(input.checked));
  row.append(input, marker, text);
  return row;
}

function cssColor(rgb) {
  if (!Array.isArray(rgb) || rgb.length < 3) return '#77879b';
  return `rgb(${rgb.slice(0, 3).map(value => Math.round(Math.max(0, Math.min(1, value)) * 255)).join(',')})`;
}

function renderProjectionControls() {
  const root = document.querySelector('#projectionControls');
  if (!root) return;
  const settings = projectionVisibilitySettings();
  const rulesets = rulesetMap();
  const colorSpaces = colorSpaceMap();

  root.replaceChildren();
  const heading = document.createElement('div');
  heading.className = 'projection-controls-heading';
  heading.textContent = 'VISIBILITY';
  root.appendChild(heading);

  for (const [linkType, ruleset] of genericLinkTypes()) {
    const color = cssColor(colorSpaces.get(ruleset.color_space_ref)?.colors?.flow || colorSpaces.get(ruleset.color_space_ref)?.colors?.base);
    root.appendChild(projectionToggle(
      ruleset.name || humanizeCanonicalName(linkType),
      isLinkTypeVisible(linkType),
      color,
      visible => setLinkTypeVisible(linkType, visible),
    ));
  }

  const causalColor = cssColor(colorSpaces.get(rulesets.get('RULESET_LINK_EVENT_EFFECT')?.color_space_ref)?.colors?.flow || [1, .48, .30]);
  root.appendChild(projectionToggle(
    'Event routes',
    Boolean(settings.event_routes_visible),
    causalColor,
    visible => {
      settings.event_routes_visible = visible;
      syncEventRouteVisibility();
    },
  ));
}

function syncEventRouteVisibility() {
  const visible = Boolean(projectionVisibilitySettings().event_routes_visible);
  if (typeof causalSvg !== 'undefined') causalSvg.style.display = visible ? '' : 'none';
}

ensureResetEventsControl();
renderProjectionControls();
syncEventRouteVisibility();
