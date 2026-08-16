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

activeLinkProperties = projectedGenericLinkProperties;

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

// Event Rule Editor ---------------------------------------------------------
// Ruleset semantic_roles are the editor schema. The editor never creates a
// parallel Event object: every edit writes the same canonical Properties that
// the server validates and the causal projection reads.
const eventRuleEditor = { eventRef: null };

function eventRuleEscape(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function eventRuleIndex() {
  const index = new Map();
  for (const entity of ws.entities || []) {
    index.set(entity.id, { ref: entity.id, kind: 'entity', type: 'entity', owner: entity, object: entity, label: entity.name || entity.id });
    for (const property of entity.properties || []) {
      index.set(property.id, {
        ref: property.id,
        kind: 'property',
        type: property.property_type_ref,
        owner: entity,
        object: property,
        label: propertyDisplayName(property, entity),
      });
    }
  }
  return index;
}

function eventRuleLinks() {
  return (ws.entities || []).flatMap(owner => (owner.properties || [])
    .filter(property => property.property_type_ref === 'link')
    .map(property => ({ owner, property, value: property.value || {} })));
}

function eventRuleRulesets(role) {
  return (ws.rulesets || []).filter(ruleset => {
    if (ruleset.property_type_ref !== 'link') return false;
    const roles = ruleset.semantic_roles || {};
    return roles.parent_ref === role || roles.child_ref === role;
  });
}

function eventRuleEndpointField(ruleset, role) {
  const roles = ruleset.semantic_roles || {};
  if (roles.parent_ref === role) return 'parent_ref';
  if (roles.child_ref === role) return 'child_ref';
  return null;
}

function eventRuleOtherField(field) {
  return field === 'parent_ref' ? 'child_ref' : 'parent_ref';
}

function eventRuleOtherRole(ruleset, role) {
  const endpoint = eventRuleEndpointField(ruleset, role);
  return endpoint ? ruleset.semantic_roles?.[eventRuleOtherField(endpoint)] : null;
}

function eventRuleSubjectLinks(ruleset, role, subjectRef) {
  const endpoint = eventRuleEndpointField(ruleset, role);
  if (!endpoint) return [];
  return eventRuleLinks().filter(({ property, value }) => property.ruleset_ref === ruleset.id && value[endpoint] === subjectRef);
}

function eventRulePropertyRecord(ref, type) {
  const item = eventRuleIndex().get(ref);
  if (!item || item.kind !== 'property' || item.type !== type) return null;
  return { owner: item.owner, property: item.object };
}

function eventRuleEventRulesets() {
  return eventRuleRulesets('event');
}

function eventRuleEffectLinkRulesets() {
  return eventRuleEventRulesets().filter(ruleset =>
    ruleset.semantic_roles?.parent_ref === 'event' && ruleset.semantic_roles?.child_ref === 'effect');
}

function eventRuleEffectTargetRulesets() {
  return eventRuleRulesets('effect').filter(ruleset =>
    ruleset.semantic_roles?.parent_ref !== 'event' && ruleset.semantic_roles?.child_ref !== 'event');
}

function eventRuleCandidates(ruleset, role, subjectRef) {
  const index = eventRuleIndex();
  const endpoint = eventRuleEndpointField(ruleset, role);
  const other = eventRuleOtherField(endpoint);
  const targetRole = eventRuleOtherRole(ruleset, role);
  const used = new Set(eventRuleSubjectLinks(ruleset, role, subjectRef).map(({ value }) => value[other]));
  let candidates = [...index.values()].filter(item =>
    item.ref !== subjectRef && !(item.kind === 'property' && item.type === 'link') && !used.has(item.ref));
  if (targetRole === 'event') candidates = candidates.filter(item => item.kind === 'property' && item.type === 'event');
  if (targetRole === 'effect') candidates = candidates.filter(item => item.kind === 'property' && item.type === 'effect');
  candidates.sort((left, right) =>
    (left.owner.name || left.owner.id).localeCompare(right.owner.name || right.owner.id) || left.label.localeCompare(right.label));
  return candidates;
}

function eventRuleTargetHtml(ref) {
  const item = eventRuleIndex().get(ref);
  if (!item) return `<code>${eventRuleEscape(ref)}</code>`;
  const prefix = item.kind === 'entity' ? '' : `${eventRuleEscape(item.owner.name || item.owner.id)} › `;
  const type = item.kind === 'entity' ? 'ENTITY' : String(item.type).toUpperCase();
  return `<span class="event-rule-target"><strong>${prefix}${eventRuleEscape(item.label)}</strong><small>${eventRuleEscape(type)}</small></span>`;
}

function eventRuleOptions(ruleset, role, subjectRef) {
  return ['<option value="">Select canonical target…</option>', ...eventRuleCandidates(ruleset, role, subjectRef).map(item => {
    const prefix = item.kind === 'entity' ? '' : `${item.owner.name || item.owner.id} › `;
    const type = item.kind === 'entity' ? 'ENTITY' : String(item.type).toUpperCase();
    return `<option value="${eventRuleEscape(item.ref)}">${eventRuleEscape(prefix + item.label)} [${eventRuleEscape(type)}]</option>`;
  })].join('');
}

function eventRuleRelationHtml(entry, ruleset, role) {
  const endpoint = eventRuleEndpointField(ruleset, role);
  const targetRef = entry.value[eventRuleOtherField(endpoint)];
  const parameters = eventRuleEscape(JSON.stringify(entry.value.properties || {}, null, 2));
  return `<div class="event-rule-relation">
    <div class="event-rule-relation-main">${eventRuleTargetHtml(targetRef)}<button class="event-rule-remove" data-event-rule-remove="${eventRuleEscape(entry.property.id)}">×</button></div>
    <details><summary>parameters</summary><textarea data-event-rule-parameters="${eventRuleEscape(entry.property.id)}">${parameters}</textarea><button data-event-rule-apply-parameters="${eventRuleEscape(entry.property.id)}">Apply</button></details>
  </div>`;
}

function eventRuleGroupHtml(ruleset, role, subjectRef) {
  const relations = eventRuleSubjectLinks(ruleset, role, subjectRef);
  return `<section class="event-rule-group">
    <header><span>${eventRuleEscape(ruleset.name || ruleset.id)}</span><b>${relations.length}</b></header>
    ${relations.length ? relations.map(entry => eventRuleRelationHtml(entry, ruleset, role)).join('') : '<div class="event-rule-empty">No contract yet</div>'}
    <div class="event-rule-add"><select data-event-rule-select="${eventRuleEscape(ruleset.id)}" data-role="${role}" data-subject="${eventRuleEscape(subjectRef)}">${eventRuleOptions(ruleset, role, subjectRef)}</select><button data-event-rule-add="${eventRuleEscape(ruleset.id)}" data-role="${role}" data-subject="${eventRuleEscape(subjectRef)}">+</button></div>
  </section>`;
}

function eventRuleSummary(eventRef) {
  const incoming = eventRuleEventRulesets().filter(ruleset => eventRuleEndpointField(ruleset, 'event') === 'child_ref')
    .reduce((count, ruleset) => count + eventRuleSubjectLinks(ruleset, 'event', eventRef).length, 0);
  const effects = eventRuleEffectLinkRulesets()
    .reduce((count, ruleset) => count + eventRuleSubjectLinks(ruleset, 'event', eventRef).length, 0);
  const outgoing = eventRuleEventRulesets().filter(ruleset =>
    eventRuleEndpointField(ruleset, 'event') === 'parent_ref' && eventRuleOtherRole(ruleset, 'event') !== 'effect')
    .reduce((count, ruleset) => count + eventRuleSubjectLinks(ruleset, 'event', eventRef).length, 0);
  return { incoming, effects, outgoing };
}

function eventRuleEffectHtml(entry, ruleset) {
  const eventField = eventRuleEndpointField(ruleset, 'event');
  const effectRef = entry.value[eventRuleOtherField(eventField)];
  const record = eventRulePropertyRecord(effectRef, 'effect');
  if (!record) return '';
  const property = record.property;
  return `<article class="event-rule-effect">
    <header><span><strong>${eventRuleEscape(propertyDisplayName(property, record.owner))}</strong><code>${eventRuleEscape(property.id)}</code></span><button class="event-rule-remove" data-event-rule-remove="${eventRuleEscape(entry.property.id)}">×</button></header>
    <div class="event-rule-effect-fields"><label>Name<input data-event-rule-effect-name="${eventRuleEscape(property.id)}" value="${eventRuleEscape(property.name || '')}"></label><label>Type<input data-event-rule-effect-type="${eventRuleEscape(property.id)}" value="${eventRuleEscape(property.value?.effect_type_ref || '')}"></label></div>
    <div class="event-rule-effect-targets">${eventRuleEffectTargetRulesets().map(targetRuleset => eventRuleGroupHtml(targetRuleset, 'effect', property.id)).join('') || '<div class="event-rule-empty">No Effect target Ruleset</div>'}</div>
  </article>`;
}

function eventRuleEffectComposer(eventRef) {
  const rulesets = eventRuleEffectLinkRulesets();
  if (!rulesets.length) return '<div class="event-rule-empty">No Event → Effect Ruleset</div>';
  const ruleset = rulesets[0];
  const existing = eventRuleCandidates(ruleset, 'event', eventRef).filter(item => item.kind === 'property' && item.type === 'effect');
  return `<div class="event-rule-composer">
    <small>Link existing Effect</small><div class="event-rule-add"><select id="eventRuleExistingEffect"><option value="">Select Effect…</option>${existing.map(item => `<option value="${eventRuleEscape(item.ref)}">${eventRuleEscape(item.owner.name || item.owner.id)} › ${eventRuleEscape(item.label)}</option>`).join('')}</select><button data-event-rule-link-effect="${eventRuleEscape(ruleset.id)}">+</button></div>
    <small>Create Effect</small><div class="event-rule-new-effect"><input id="eventRuleNewEffectName" placeholder="Name"><input id="eventRuleNewEffectType" placeholder="Effect type"><button data-event-rule-create-effect="${eventRuleEscape(ruleset.id)}">Create + link</button></div>
  </div>`;
}

function ensureEventRuleStyles() {
  if (document.querySelector('#eventRuleEditorStyles')) return;
  const style = document.createElement('style');
  style.id = 'eventRuleEditorStyles';
  style.textContent = `
    .event-rule-list-button{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 8px;width:100%;margin:4px 0;text-align:left;background:#0d1420;border-color:#263044}.event-rule-list-button span{display:grid;min-width:0}.event-rule-list-button strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.event-rule-list-button code,.event-rule-list-button small{color:#71839b;font-size:9px}.event-rule-list-button b{grid-column:2;grid-row:1/3;align-self:center;color:#ff7968;font-size:9px}
    #eventRuleEditor{position:fixed;inset:0;z-index:45;display:grid;place-items:center;padding:24px;background:#05070bdb;backdrop-filter:blur(7px)}#eventRuleEditor[hidden]{display:none}.event-rule-shell{display:grid;grid-template-rows:auto minmax(0,1fr);width:min(1180px,calc(100vw - 48px));height:min(800px,calc(100vh - 48px));overflow:hidden;background:#0c111a;border:1px solid #39465a;border-radius:12px;box-shadow:0 25px 80px #000c}.event-rule-head{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:14px;align-items:center;padding:13px 15px;border-bottom:1px solid #293548;background:#111925}.event-rule-head h2{margin:1px 0;font-size:18px}.event-rule-kicker{color:#ff7968;font-size:9px;font-weight:900;letter-spacing:.15em}.event-rule-counts,.event-rule-actions{display:flex;gap:6px}.event-rule-counts span{padding:3px 6px;border:1px solid #334157;border-radius:999px;color:#a8b9cb;font-size:9px;font-weight:900}.event-rule-flow{display:grid;grid-template-columns:.9fr 1.3fr .9fr;gap:9px;min-height:0;padding:9px;background:#080c12}.event-rule-column{min-width:0;overflow:auto;padding:9px;border:1px solid #222e3e;border-radius:8px;background:#0c121c}.event-rule-column.core{border-color:#4a302e;background:#100e13}.event-rule-title{display:flex;gap:8px;align-items:baseline;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #263244}.event-rule-title b{color:#ff7968;font-size:10px;letter-spacing:.12em}.event-rule-title span{color:#71839b;font-size:9px}
    .event-rule-group{margin-bottom:8px;padding:7px;border:1px solid #28364a;border-radius:6px;background:#0e1622}.event-rule-group>header{display:flex;justify-content:space-between;margin-bottom:5px;color:#a9b9cb;font-size:9px;font-weight:900;text-transform:uppercase}.event-rule-relation{margin:4px 0;border:1px solid #29364a;border-radius:5px;background:#090f18}.event-rule-relation-main{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px;align-items:center;padding:5px}.event-rule-target{display:grid;min-width:0}.event-rule-target strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.event-rule-target small{color:#66788f;font-size:8px;font-weight:900}.event-rule-remove{width:24px;height:24px;padding:0;border-radius:50%;background:#241416;border-color:#60302f;color:#e47a6d}.event-rule-relation details{border-top:1px solid #202b3a;padding:3px 5px 5px}.event-rule-relation summary{cursor:pointer;color:#6e8095;font-size:8px}.event-rule-relation textarea{box-sizing:border-box;width:100%;min-height:54px;margin:4px 0;padding:4px;background:#070c13;color:#dce6f0;border:1px solid #33425c;border-radius:4px;font:9px/1.3 monospace}.event-rule-add{display:grid;grid-template-columns:minmax(0,1fr) 30px;gap:5px;margin-top:5px}.event-rule-add select{min-width:0;width:100%;padding:4px;background:#09101a;color:#d4dfeb;border:1px solid #33425c}.event-rule-add button{padding:3px;font-size:15px}.event-rule-empty{padding:7px;border:1px dashed #2d394b;border-radius:5px;color:#687b91;font-size:9px;text-align:center}
    .event-rule-core{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:8px;border:1px solid #5a3531;border-radius:7px;background:#171014}.event-rule-core label,.event-rule-effect-fields label{display:grid;gap:3px;color:#8fa0b4;font-size:9px;font-weight:800;text-transform:uppercase}.event-rule-core input,.event-rule-effect-fields input,.event-rule-new-effect input{box-sizing:border-box;width:100%;padding:5px;background:#080d14;color:#eef3f8;border:1px solid #3a4658;border-radius:4px}.event-rule-core small{grid-column:1/3;color:#6f8094}.event-rule-effects-heading{display:flex;justify-content:space-between;margin:10px 1px 5px;color:#d46f62;font-size:9px;font-weight:900;letter-spacing:.1em}.event-rule-effect{margin-bottom:7px;padding:7px;border:1px solid #5b302d;border-radius:7px;background:#181012}.event-rule-effect>header{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px}.event-rule-effect>header span{display:grid}.event-rule-effect strong{color:#ffd9d2}.event-rule-effect code{color:#8a5d5a;font-size:8px}.event-rule-effect-fields{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:6px}.event-rule-effect-targets{margin-top:7px}.event-rule-composer{margin-top:8px;padding:7px;border:1px dashed #543430;border-radius:7px}.event-rule-composer>small{display:block;margin:5px 0 3px;color:#946d69;font-size:8px;font-weight:900;text-transform:uppercase}.event-rule-new-effect{display:grid;grid-template-columns:1fr 1fr auto;gap:5px}@media(max-width:900px){.event-rule-shell{width:calc(100vw - 20px);height:calc(100vh - 20px)}.event-rule-flow{grid-template-columns:1fr;overflow:auto}.event-rule-column{overflow:visible}.event-rule-counts{display:none}}
  `;
  document.head.appendChild(style);
}

function ensureEventRuleSection() {
  if (document.querySelector('#eventRuleSection')) return;
  const relations = document.querySelector('.entity-info-section[data-info-section="relations"]');
  if (!relations) return;
  const section = document.createElement('section');
  section.id = 'eventRuleSection';
  section.className = 'entity-info-section';
  section.dataset.infoSection = 'event-rules';
  section.innerHTML = '<button class="entity-info-heading" type="button" aria-expanded="true">Event Rules</button><div class="entity-info-body"><div id="eventRuleList"></div></div>';
  relations.before(section);
  const heading = section.querySelector('.entity-info-heading');
  heading.addEventListener('click', () => {
    const entity = selectedEntityForEditor();
    const collapsed = !section.classList.contains('collapsed');
    section.classList.toggle('collapsed', collapsed);
    heading.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    if (entity) setInfoSectionCollapsed(entity.id, 'event-rules', collapsed);
  });
}

function renderEventRuleSection() {
  ensureEventRuleSection();
  const section = document.querySelector('#eventRuleSection');
  const list = document.querySelector('#eventRuleList');
  if (!section || !list) return;
  const entity = selectedEntityForEditor();
  if (!entity) {
    list.innerHTML = '<div class="event-rule-empty">Select one Entity</div>';
    return;
  }
  const collapsed = infoSectionCollapsed(entity.id, 'event-rules');
  section.classList.toggle('collapsed', collapsed);
  section.querySelector('.entity-info-heading')?.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  const events = (entity.properties || []).filter(property => property.property_type_ref === 'event');
  list.innerHTML = events.length ? events.map(property => {
    const summary = eventRuleSummary(property.id);
    return `<button class="event-rule-list-button" data-event-rule-open="${eventRuleEscape(property.id)}"><span><strong>${eventRuleEscape(propertyDisplayName(property, entity))}</strong><code>${eventRuleEscape(property.id)}</code></span><small>${summary.incoming} in · ${summary.effects} effects · ${summary.outgoing} out</small><b>EDIT</b></button>`;
  }).join('') : '<div class="event-rule-empty">No Event Properties</div>';
}

function ensureEventRuleModal() {
  if (document.querySelector('#eventRuleEditor')) return;
  const modal = document.createElement('div');
  modal.id = 'eventRuleEditor';
  modal.hidden = true;
  document.body.appendChild(modal);
}

function renderEventRuleModal() {
  ensureEventRuleModal();
  const modal = document.querySelector('#eventRuleEditor');
  const record = eventRulePropertyRecord(eventRuleEditor.eventRef, 'event');
  if (!modal || !record) {
    closeEventRuleEditor();
    return;
  }
  const property = record.property;
  const summary = eventRuleSummary(property.id);
  const incomingRulesets = eventRuleEventRulesets().filter(ruleset => eventRuleEndpointField(ruleset, 'event') === 'child_ref');
  const outgoingRulesets = eventRuleEventRulesets().filter(ruleset =>
    eventRuleEndpointField(ruleset, 'event') === 'parent_ref' && eventRuleOtherRole(ruleset, 'event') !== 'effect');
  const effects = eventRuleEffectLinkRulesets().flatMap(ruleset =>
    eventRuleSubjectLinks(ruleset, 'event', property.id).map(entry => ({ ruleset, entry })));

  modal.innerHTML = `<div class="event-rule-shell">
    <header class="event-rule-head"><div><span class="event-rule-kicker">EVENT RULE EDITOR</span><h2>${eventRuleEscape(propertyDisplayName(property, record.owner))}</h2><code>${eventRuleEscape(property.id)}</code></div><div class="event-rule-counts"><span>${summary.incoming} IN</span><span>${summary.effects} EFFECTS</span><span>${summary.outgoing} OUT</span></div><div class="event-rule-actions"><button data-event-rule-fire="${eventRuleEscape(property.id)}">▶ Fire</button><button data-event-rule-close>Close</button></div></header>
    <div class="event-rule-flow">
      <section class="event-rule-column"><div class="event-rule-title"><b>IN</b><span>What may reach or qualify this Event</span></div>${incomingRulesets.map(ruleset => eventRuleGroupHtml(ruleset, 'event', property.id)).join('') || '<div class="event-rule-empty">No incoming Event Rulesets</div>'}</section>
      <section class="event-rule-column core"><div class="event-rule-title"><b>EVENT</b><span>Canonical Event Property</span></div><div class="event-rule-core"><label>Name<input data-event-rule-event-name value="${eventRuleEscape(property.name || '')}" placeholder="${eventRuleEscape(propertyDisplayName(property, record.owner))}"></label><label>Type<input data-event-rule-event-type value="${eventRuleEscape(property.value?.event_type_ref || '')}"></label><small>owner <code>${eventRuleEscape(record.owner.id)}</code></small></div><div class="event-rule-effects-heading"><span>EFFECTS</span><b>${effects.length}</b></div>${effects.length ? effects.map(({ entry, ruleset }) => eventRuleEffectHtml(entry, ruleset)).join('') : '<div class="event-rule-empty">No Effect contract yet</div>'}${eventRuleEffectComposer(property.id)}</section>
      <section class="event-rule-column"><div class="event-rule-title"><b>OUT</b><span>What this Event exposes directly</span></div>${outgoingRulesets.map(ruleset => eventRuleGroupHtml(ruleset, 'event', property.id)).join('') || '<div class="event-rule-empty">No direct outgoing Event Rulesets</div>'}</section>
    </div>
  </div>`;
  modal.hidden = false;
}

function openEventRuleEditor(eventRef) {
  if (!eventRulePropertyRecord(eventRef, 'event')) return;
  eventRuleEditor.eventRef = eventRef;
  renderEventRuleModal();
}

function closeEventRuleEditor() {
  eventRuleEditor.eventRef = null;
  const modal = document.querySelector('#eventRuleEditor');
  if (modal) {
    modal.hidden = true;
    modal.innerHTML = '';
  }
}

function refreshEventRuleEditor(message = '') {
  if (message) status(message);
  inspect();
  renderEventRuleSection();
  if (eventRuleEditor.eventRef) renderEventRuleModal();
}

function removeEventRuleLink(linkId) {
  for (const entity of ws.entities || []) {
    const count = (entity.properties || []).length;
    entity.properties = (entity.properties || []).filter(property => property.id !== linkId);
    if (entity.properties.length !== count) {
      refreshEventRuleEditor(`removed ${linkId}`);
      return;
    }
  }
}

function createEventRuleLink(rulesetId, role, subjectRef, targetRef) {
  const ruleset = rulesetMap().get(rulesetId);
  const subject = eventRuleIndex().get(subjectRef);
  if (!ruleset || !subject || !targetRef) return;
  const subjectField = eventRuleEndpointField(ruleset, role);
  if (!subjectField) return;
  const targetField = eventRuleOtherField(subjectField);
  const value = { link_type_ref: ruleset.link_type_ref, parent_ref: null, child_ref: null, properties: {} };
  value[subjectField] = subjectRef;
  value[targetField] = targetRef;
  const duplicate = eventRuleLinks().some(entry =>
    entry.property.ruleset_ref === ruleset.id && entry.value.parent_ref === value.parent_ref && entry.value.child_ref === value.child_ref);
  if (duplicate) {
    status(`${ruleset.name || ruleset.id}: contract already exists`);
    return;
  }
  subject.owner.properties ??= [];
  subject.owner.properties.push({
    id: nextId('LINK'),
    property_type_ref: 'link',
    ruleset_ref: ruleset.id,
    status: 'unlocked',
    value,
    metadata: { workspace_entity_ref: subject.owner.id },
  });
  refreshEventRuleEditor(`created ${ruleset.name || ruleset.id}`);
}

function applyEventRuleParameters(linkId, text) {
  const entry = eventRuleLinks().find(({ property }) => property.id === linkId);
  if (!entry) return;
  try {
    const parameters = text.trim() ? JSON.parse(text) : {};
    if (!parameters || Array.isArray(parameters) || typeof parameters !== 'object') throw new Error('JSON object required');
    entry.value.properties = parameters;
    refreshEventRuleEditor(`updated ${linkId}`);
  } catch (error) {
    window.reportStructureError?.(error, { type: 'event_rule_parameters', context: linkId });
    status(`invalid parameters: ${error.message}`);
  }
}

function createEventRuleEffect(rulesetId) {
  const event = eventRulePropertyRecord(eventRuleEditor.eventRef, 'event');
  const effectRuleset = (ws.rulesets || []).find(ruleset => ruleset.property_type_ref === 'effect');
  const linkRuleset = rulesetMap().get(rulesetId);
  const name = document.querySelector('#eventRuleNewEffectName')?.value.trim() || '';
  const type = document.querySelector('#eventRuleNewEffectType')?.value.trim() || '';
  if (!event || !effectRuleset || !linkRuleset || !type) {
    status('Effect type is required');
    return;
  }
  const effectId = nextId('EFFECT');
  const effect = {
    id: effectId,
    property_type_ref: 'effect',
    ruleset_ref: effectRuleset.id,
    status: 'unlocked',
    value: { effect_type_ref: type, properties: {} },
    metadata: { workspace_entity_ref: event.owner.id },
  };
  if (name) effect.name = name;
  event.owner.properties.push(effect);

  const eventField = eventRuleEndpointField(linkRuleset, 'event');
  const linkValue = { link_type_ref: linkRuleset.link_type_ref, parent_ref: null, child_ref: null, properties: {} };
  linkValue[eventField] = eventRuleEditor.eventRef;
  linkValue[eventRuleOtherField(eventField)] = effectId;
  event.owner.properties.push({
    id: nextId('LINK'), property_type_ref: 'link', ruleset_ref: linkRuleset.id, status: 'unlocked',
    value: linkValue, metadata: { workspace_entity_ref: event.owner.id },
  });
  refreshEventRuleEditor(`created Effect ${name || effectId}`);
}

function bindEventRuleEditor() {
  document.addEventListener('click', event => {
    const open = event.target.closest?.('[data-event-rule-open]');
    if (open) { openEventRuleEditor(open.dataset.eventRuleOpen); return; }
    if (event.target.closest?.('[data-event-rule-close]')) { closeEventRuleEditor(); return; }

    const remove = event.target.closest?.('[data-event-rule-remove]');
    if (remove) { removeEventRuleLink(remove.dataset.eventRuleRemove); return; }

    const add = event.target.closest?.('[data-event-rule-add]');
    if (add) {
      const selector = `select[data-event-rule-select="${CSS.escape(add.dataset.eventRuleAdd)}"][data-role="${CSS.escape(add.dataset.role)}"][data-subject="${CSS.escape(add.dataset.subject)}"]`;
      const targetRef = document.querySelector(selector)?.value || '';
      if (targetRef) createEventRuleLink(add.dataset.eventRuleAdd, add.dataset.role, add.dataset.subject, targetRef);
      return;
    }

    const apply = event.target.closest?.('[data-event-rule-apply-parameters]');
    if (apply) {
      const linkId = apply.dataset.eventRuleApplyParameters;
      const textarea = document.querySelector(`textarea[data-event-rule-parameters="${CSS.escape(linkId)}"]`);
      if (textarea) applyEventRuleParameters(linkId, textarea.value);
      return;
    }

    const linkEffect = event.target.closest?.('[data-event-rule-link-effect]');
    if (linkEffect) {
      const targetRef = document.querySelector('#eventRuleExistingEffect')?.value || '';
      if (targetRef) createEventRuleLink(linkEffect.dataset.eventRuleLinkEffect, 'event', eventRuleEditor.eventRef, targetRef);
      return;
    }

    const createEffect = event.target.closest?.('[data-event-rule-create-effect]');
    if (createEffect) { createEventRuleEffect(createEffect.dataset.eventRuleCreateEffect); return; }

    const fire = event.target.closest?.('[data-event-rule-fire]');
    if (fire) { triggerCausalProjection(fire.dataset.eventRuleFire); return; }

    const modal = document.querySelector('#eventRuleEditor');
    if (modal && event.target === modal) closeEventRuleEditor();
  });

  document.addEventListener('change', event => {
    const eventRecord = eventRulePropertyRecord(eventRuleEditor.eventRef, 'event');
    if (event.target.matches?.('[data-event-rule-event-name]') && eventRecord) {
      const value = event.target.value.trim();
      if (value) eventRecord.property.name = value;
      else delete eventRecord.property.name;
      renderEventRuleSection();
      renderEventRuleModal();
      return;
    }
    if (event.target.matches?.('[data-event-rule-event-type]') && eventRecord) {
      const value = event.target.value.trim();
      if (!value) { status('Event type is required'); renderEventRuleModal(); return; }
      eventRecord.property.value.event_type_ref = value;
      renderEventRuleModal();
      return;
    }

    const effectName = event.target.closest?.('[data-event-rule-effect-name]');
    if (effectName) {
      const record = eventRulePropertyRecord(effectName.dataset.eventRuleEffectName, 'effect');
      if (record) {
        const value = effectName.value.trim();
        if (value) record.property.name = value;
        else delete record.property.name;
        renderEventRuleModal();
      }
      return;
    }

    const effectType = event.target.closest?.('[data-event-rule-effect-type]');
    if (effectType) {
      const record = eventRulePropertyRecord(effectType.dataset.eventRuleEffectType, 'effect');
      const value = effectType.value.trim();
      if (record && value) { record.property.value.effect_type_ref = value; renderEventRuleModal(); }
      else if (record) { status('Effect type is required'); renderEventRuleModal(); }
    }
  });

  window.addEventListener('keydown', event => {
    if (event.key === 'Escape' && eventRuleEditor.eventRef) closeEventRuleEditor();
  });

  const selection = document.querySelector('#selection');
  if (selection) new MutationObserver(renderEventRuleSection).observe(selection, { childList: true, subtree: true, characterData: true });
}

ensureResetEventsControl();
renderProjectionControls();
syncEventRouteVisibility();
ensureEventRuleStyles();
ensureEventRuleSection();
ensureEventRuleModal();
bindEventRuleEditor();
renderEventRuleSection();
