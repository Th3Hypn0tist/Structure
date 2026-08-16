const canvas = document.querySelector('#scene');
const gl = canvas.getContext('webgl2', { antialias: true });
if (!gl) throw new Error('WebGL2 required');

const $ = selector => document.querySelector(selector);
const status = text => { $('#status').textContent = text; };

const V = {
  add: (a, b) => a.map((value, index) => value + b[index]),
  sub: (a, b) => a.map((value, index) => value - b[index]),
  mul: (a, scalar) => a.map(value => value * scalar),
  cross: (a, b) => [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ],
  norm: value => {
    const length = Math.hypot(...value) || 1;
    return value.map(component => component / length);
  },
  length: value => Math.hypot(...value),
};

function m4(a, b) {
  const out = new Array(16).fill(0);
  for (let column = 0; column < 4; column++) {
    for (let row = 0; row < 4; row++) {
      for (let k = 0; k < 4; k++) out[column * 4 + row] += a[k * 4 + row] * b[column * 4 + k];
    }
  }
  return out;
}

function perspective(fov, aspect, near, far) {
  const scale = 1 / Math.tan(fov * Math.PI / 360);
  return [
    scale / aspect, 0, 0, 0,
    0, scale, 0, 0,
    0, 0, (far + near) / (near - far), -1,
    0, 0, 2 * far * near / (near - far), 0,
  ];
}

function lookAt(position, target) {
  const z = V.norm(V.sub(position, target));
  let x = V.cross([0, 1, 0], z);
  if (V.length(x) < 1e-6) x = [1, 0, 0];
  x = V.norm(x);
  const y = V.cross(z, x);
  const dot = (axis, point) => axis.reduce((sum, value, index) => sum + value * point[index], 0);
  return [
    x[0], y[0], z[0], 0,
    x[1], y[1], z[1], 0,
    x[2], y[2], z[2], 0,
    -dot(x, position), -dot(y, position), -dot(z, position), 1,
  ];
}

function model(position, scale) {
  return [
    scale[0], 0, 0, 0,
    0, scale[1], 0, 0,
    0, 0, scale[2], 0,
    position[0], position[1], position[2], 1,
  ];
}

function project(point, viewProjection) {
  const [x, y, z] = point;
  const clipX = viewProjection[0] * x + viewProjection[4] * y + viewProjection[8] * z + viewProjection[12];
  const clipY = viewProjection[1] * x + viewProjection[5] * y + viewProjection[9] * z + viewProjection[13];
  const clipW = viewProjection[3] * x + viewProjection[7] * y + viewProjection[11] * z + viewProjection[15];
  if (clipW <= 0) return null;
  return [
    (clipX / clipW * .5 + .5) * canvas.width,
    (-clipY / clipW * .5 + .5) * canvas.height,
    clipW,
  ];
}

const vertexShader = `#version 300 es
in vec3 p;
uniform mat4 mvp;
uniform vec3 color;
out vec3 c;
void main() {
  c = color;
  gl_Position = mvp * vec4(p, 1.0);
}`;

const fragmentShader = `#version 300 es
precision highp float;
in vec3 c;
out vec4 o;
void main() {
  o = vec4(c, 1.0);
}`;

function compileShader(type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
  return shader;
}

const program = gl.createProgram();
gl.attachShader(program, compileShader(gl.VERTEX_SHADER, vertexShader));
gl.attachShader(program, compileShader(gl.FRAGMENT_SHADER, fragmentShader));
gl.linkProgram(program);
if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
gl.useProgram(program);

const loc = {
  position: gl.getAttribLocation(program, 'p'),
  mvp: gl.getUniformLocation(program, 'mvp'),
  color: gl.getUniformLocation(program, 'color'),
};

const cubeVertices = new Float32Array([
  -1, -1, -1, 1, -1, -1, 1, 1, -1, -1, 1, -1,
  -1, -1, 1, 1, -1, 1, 1, 1, 1, -1, 1, 1,
]);
const cubeFaces = new Uint16Array([
  0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7,
  0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5,
  0, 1, 5, 0, 5, 4, 3, 7, 6, 3, 6, 2,
]);
const cubeEdges = new Uint16Array([
  0, 1, 1, 2, 2, 3, 3, 0, 4, 5, 5, 6, 6, 7, 7, 4,
  0, 4, 1, 5, 2, 6, 3, 7,
]);

const vertexBuffer = gl.createBuffer();
const faceBuffer = gl.createBuffer();
const edgeBuffer = gl.createBuffer();
const lineBuffer = gl.createBuffer();

gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
gl.bufferData(gl.ARRAY_BUFFER, cubeVertices, gl.STATIC_DRAW);
gl.enableVertexAttribArray(loc.position);
gl.vertexAttribPointer(loc.position, 3, gl.FLOAT, false, 0, 0);
gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, faceBuffer);
gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, cubeFaces, gl.STATIC_DRAW);
gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, edgeBuffer);
gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, cubeEdges, gl.STATIC_DRAW);

const DEFAULT_RULESETS = [
  { id: 'RULESET_LINK_DEPENDENCY', name: 'Dependency', property_type_ref: 'link', link_type_ref: 'dependency', color_space_ref: 'COLORSPACE_DEPENDENCY' },
  { id: 'RULESET_LINK_OWNERSHIP', name: 'Ownership', property_type_ref: 'link', link_type_ref: 'ownership', color_space_ref: 'COLORSPACE_OWNERSHIP' },
  { id: 'RULESET_LINK_AUTHORITY', name: 'Authority', property_type_ref: 'link', link_type_ref: 'authority', color_space_ref: 'COLORSPACE_AUTHORITY' },
  { id: 'RULESET_LINK_CONTAINMENT', name: 'Containment', property_type_ref: 'link', link_type_ref: 'containment', color_space_ref: 'COLORSPACE_CONTAINMENT' },
  { id: 'RULESET_LINK_ARCHITECTURE_PARENT', name: 'Architecture Parent', property_type_ref: 'link', link_type_ref: 'architecture_parent', color_space_ref: 'COLORSPACE_ARCHITECTURE' },
  { id: 'RULESET_LINK_RELATION', name: 'Relation', property_type_ref: 'link', link_type_ref: 'relation', color_space_ref: 'COLORSPACE_RELATION' },
  { id: 'RULESET_LINK_EVENT_READ', name: 'Event Read', property_type_ref: 'link', link_type_ref: 'event_read', color_space_ref: 'COLORSPACE_CAUSAL' },
  { id: 'RULESET_LINK_EVENT_INPUT', name: 'Event Input', property_type_ref: 'link', link_type_ref: 'event_input', color_space_ref: 'COLORSPACE_CAUSAL' },
  { id: 'RULESET_LINK_EVENT_OUTPUT', name: 'Event Output', property_type_ref: 'link', link_type_ref: 'event_output', color_space_ref: 'COLORSPACE_CAUSAL' },
  { id: 'RULESET_LINK_EVENT_EFFECT', name: 'Event Effect', property_type_ref: 'link', link_type_ref: 'event_effect', color_space_ref: 'COLORSPACE_CAUSAL' },
  { id: 'RULESET_LINK_EVENT_CAUSE', name: 'Event Cause', property_type_ref: 'link', link_type_ref: 'event_cause', color_space_ref: 'COLORSPACE_CAUSAL' },
  { id: 'RULESET_LINK_EVENT_CONDITION', name: 'Event Condition', property_type_ref: 'link', link_type_ref: 'event_condition', color_space_ref: 'COLORSPACE_CAUSAL' },
  { id: 'RULESET_LINK_EFFECT_TARGET', name: 'Effect Target', property_type_ref: 'link', link_type_ref: 'effect_target', color_space_ref: 'COLORSPACE_CAUSAL' },
  { id: 'RULESET_EVENT', name: 'Event', property_type_ref: 'event' },
  { id: 'RULESET_EFFECT', name: 'Effect', property_type_ref: 'effect' },
  { id: 'RULESET_DATA', name: 'Data', property_type_ref: 'data' },
  { id: 'RULESET_FUNCTION', name: 'Function', property_type_ref: 'function' },
];

const DEFAULT_COLOR_SPACES = [
  { id: 'COLORSPACE_DEPENDENCY', colors: { base: [.18, .42, .9], flow: [.4, .76, 1] } },
  { id: 'COLORSPACE_OWNERSHIP', colors: { base: [.78, .5, .08], flow: [1, .76, .22] } },
  { id: 'COLORSPACE_AUTHORITY', colors: { base: [.72, .18, .28], flow: [1, .38, .42] } },
  { id: 'COLORSPACE_CONTAINMENT', colors: { base: [.22, .6, .32], flow: [.46, .92, .54] } },
  { id: 'COLORSPACE_ARCHITECTURE', colors: { base: [.52, .26, .82], flow: [.76, .48, 1] } },
  { id: 'COLORSPACE_CAUSAL', colors: { base: [.78, .20, .18], flow: [1, .48, .30] } },
  { id: 'COLORSPACE_RELATION', colors: { base: [.20, .62, .64], flow: [.38, .90, .92] } },
];

let ws = {
  version: '0.2.0',
  entities: [],
  rulesets: structuredClone(DEFAULT_RULESETS),
  color_spaces: structuredClone(DEFAULT_COLOR_SPACES),
  view: { ruleset_ref: 'ALL' },
  camera: { position: [0, 1.5, 16], reference: [0, 0, 0], yaw: 0, pitch: 0, fov: 60 },
  settings: {
    camera_defaults: {
      position: [0, 1.5, 16], reference: [0, 0, 0], yaw: 0, pitch: 0, fov: 60,
      movement_speed: 6, mouse_sensitivity: .0025, wheel_zoom_speed: .15, drag_pan_speed: .01,
      near_clip: .05, far_clip: 1000,
    },
    link_visualization: { anchor_spacing: .28, anchor_offset: .58, base_flow_speed: .15 },
    event_playback: { base_link_speed: .15, active_link_speed: 2, effect_travel_duration: 1.2 },
    view_defaults: { node_master_size: 1, grid_visible: true, snap_to_grid: true, grid_size: 1 },
  },
};

let selected = new Set();
let activeEntityId = null;
let lookAtEntityId = null;
let hovered = null;
let keys = new Set();
let orbit = null;
let pan = null;
let last = [0, 0];
let dragAxis = null;
let linkSource = null;
let linkTarget = null;

function ensureWorkspace() {
  ws.entities ??= [];
  ws.rulesets ??= [];
  ws.color_spaces ??= [];
  ws.settings ??= {};
  ws.settings.camera_defaults ??= {};
  ws.settings.link_visualization ??= {};
  ws.settings.event_playback ??= {};
  ws.settings.view_defaults ??= {};
  ws.view ??= { ruleset_ref: 'ALL' };

  for (const ruleset of DEFAULT_RULESETS) {
    if (!ws.rulesets.some(item => item.id === ruleset.id)) ws.rulesets.push(structuredClone(ruleset));
  }
  for (const colorSpace of DEFAULT_COLOR_SPACES) {
    if (!ws.color_spaces.some(item => item.id === colorSpace.id)) ws.color_spaces.push(structuredClone(colorSpace));
  }

  const camera = ws.settings.camera_defaults;
  camera.position ??= [0, 1.5, 16];
  camera.reference ??= [0, 0, 0];
  camera.yaw ??= 0;
  camera.pitch ??= 0;
  camera.fov ??= 60;
  camera.movement_speed ??= 6;
  camera.mouse_sensitivity ??= .0025;
  camera.wheel_zoom_speed ??= .15;
  camera.drag_pan_speed ??= .01;
  camera.near_clip ??= .05;
  camera.far_clip ??= 1000;

  ws.camera ??= { position: [...camera.position], reference: [...camera.reference], yaw: camera.yaw, pitch: camera.pitch, fov: camera.fov };
  ws.camera.reference ??= [...camera.reference];

  const links = ws.settings.link_visualization;
  links.anchor_spacing ??= .28;
  links.anchor_offset ??= .58;
  links.base_flow_speed ??= .15;

  const events = ws.settings.event_playback;
  events.base_link_speed ??= .15;
  events.active_link_speed ??= 2;
  events.effect_travel_duration ??= 1.2;

  const view = ws.settings.view_defaults;
  view.node_master_size ??= 1;
  view.grid_visible ??= true;
  view.snap_to_grid ??= true;
  view.grid_size ??= 1;
}

function viewSettings() { return ws.settings.view_defaults; }
function nodeMasterSize() { return Number(viewSettings().node_master_size || 1); }
function nodeHalfSize() { return .45 * nodeMasterSize(); }
function gridSize() { return Math.max(.05, Number(viewSettings().grid_size || 1)); }

function freeForward() {
  const cosine = Math.cos(ws.camera.pitch);
  return [
    Math.sin(ws.camera.yaw) * cosine,
    Math.sin(ws.camera.pitch),
    -Math.cos(ws.camera.yaw) * cosine,
  ];
}

function lookAtEntity() {
  return lookAtEntityId ? ws.entities.find(entity => entity.id === lookAtEntityId) || null : null;
}

function cameraReference() {
  const entity = lookAtEntity();
  if (entity) {
    ws.camera.reference = [...entity.position];
    return entity.position;
  }
  if (!Array.isArray(ws.camera.reference) || ws.camera.reference.length !== 3) {
    ws.camera.reference = V.add(ws.camera.position, V.mul(freeForward(), 5));
  }
  return ws.camera.reference;
}

function detachLookAtReference() {
  ws.camera.reference = [...cameraReference()];
  lookAtEntityId = null;
  return ws.camera.reference;
}

function viewForward() {
  const direction = V.sub(cameraReference(), ws.camera.position);
  return V.length(direction) > 1e-6 ? V.norm(direction) : freeForward();
}
function cameraRight() { return V.norm(V.cross(viewForward(), [0, 1, 0])); }
function cameraUp() { return V.norm(V.cross(cameraRight(), viewForward())); }
function cameraLocalZ() { return V.mul(viewForward(), -1); }

function syncCameraAnglesToActive() {
  const forward = viewForward();
  ws.camera.yaw = Math.atan2(forward[0], -forward[2]);
  ws.camera.pitch = Math.asin(Math.max(-1, Math.min(1, forward[1])));
}

function viewProjection() {
  const settings = ws.settings.camera_defaults;
  const projection = perspective(ws.camera.fov, canvas.width / canvas.height, settings.near_clip || .05, settings.far_clip || 1000);
  return m4(projection, lookAt(ws.camera.position, cameraReference()));
}

function worldPixelsAt(point) {
  const vp = viewProjection();
  const density = devicePixelRatio || 1;
  const origin = project(point, vp);
  const right = project(V.add(point, cameraRight()), vp);
  if (!origin || !right) return 0;
  return Math.hypot(right[0] - origin[0], right[1] - origin[1]) / density;
}

function bindCube() {
  gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
  gl.vertexAttribPointer(loc.position, 3, gl.FLOAT, false, 0, 0);
}

function drawLine(start, end, color) {
  gl.bindBuffer(gl.ARRAY_BUFFER, lineBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([...start, ...end]), gl.DYNAMIC_DRAW);
  gl.vertexAttribPointer(loc.position, 3, gl.FLOAT, false, 0, 0);
  gl.uniformMatrix4fv(loc.mvp, false, new Float32Array(viewProjection()));
  gl.uniform3fv(loc.color, color);
  gl.drawArrays(gl.LINES, 0, 2);
  bindCube();
}

function drawBox(position, scale, color, outline = false) {
  gl.uniformMatrix4fv(loc.mvp, false, new Float32Array(m4(viewProjection(), model(position, scale))));
  gl.uniform3fv(loc.color, color);
  bindCube();
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, outline ? edgeBuffer : faceBuffer);
  gl.drawElements(outline ? gl.LINES : gl.TRIANGLES, outline ? cubeEdges.length : cubeFaces.length, gl.UNSIGNED_SHORT, 0);
}

function rulesetMap() { return new Map(ws.rulesets.map(ruleset => [ruleset.id, ruleset])); }
function colorSpaceMap() { return new Map(ws.color_spaces.map(colorSpace => [colorSpace.id, colorSpace])); }
function linkProperties() {
  return ws.entities.flatMap(owner => (owner.properties || [])
    .filter(property => property.property_type_ref === 'link')
    .map(property => ({ owner, property })));
}
function activeLinkProperties() {
  return linkProperties().filter(({ property }) => ws.view.ruleset_ref === 'ALL' || property.ruleset_ref === ws.view.ruleset_ref);
}

function entityForCanonicalRef(ref) {
  const direct = ws.entities.find(entity => entity.id === ref);
  if (direct) return direct;
  for (const entity of ws.entities) {
    if ((entity.properties || []).some(property => property.id === ref)) return entity;
  }
  return null;
}

function visibleEntityIds() {
  if (ws.view.ruleset_ref === 'ALL') return new Set(ws.entities.map(entity => entity.id));
  const ids = new Set();
  for (const { property } of activeLinkProperties()) {
    const parent = entityForCanonicalRef(property.value.parent_ref);
    const child = entityForCanonicalRef(property.value.child_ref);
    if (parent) ids.add(parent.id);
    if (child) ids.add(child.id);
  }
  return ids;
}

function linkSlots() {
  const size = nodeMasterSize();
  const spacing = (ws.settings.link_visualization.anchor_spacing || .28) * size;
  const offset = (ws.settings.link_visualization.anchor_offset || .58) * size;
  const slots = new Map();
  const dependencyOut = new Map();
  const dependencyIn = new Map();
  const sideOut = new Map();
  const sideIn = new Map();
  const push = (map, entityId, propertyId) => {
    if (!map.has(entityId)) map.set(entityId, []);
    map.get(entityId).push(propertyId);
  };

  for (const { property } of activeLinkProperties()) {
    const childEntity = entityForCanonicalRef(property.value.child_ref);
    const parentEntity = entityForCanonicalRef(property.value.parent_ref);
    if (!childEntity || !parentEntity) continue;
    if (property.value.link_type_ref === 'dependency') {
      push(dependencyOut, childEntity.id, property.id);
      push(dependencyIn, parentEntity.id, property.id);
    } else {
      push(sideOut, childEntity.id, property.id);
      push(sideIn, parentEntity.id, property.id);
    }
  }

  for (const entity of ws.entities) {
    const route = (ids, kind, axis, sign) => {
      const sorted = ids.sort();
      const start = -(sorted.length - 1) * spacing / 2;
      sorted.forEach((id, index) => {
        const p = [...entity.position];
        if (axis === 'y') {
          p[0] += start + index * spacing;
          p[1] += sign * offset;
        } else {
          p[0] += sign * offset;
          p[1] += start + index * spacing;
        }
        slots.set(`${id}:${kind}`, p);
      });
    };
    route(dependencyOut.get(entity.id) || [], 'out', 'y', 1);
    route(dependencyIn.get(entity.id) || [], 'in', 'y', -1);
    route(sideOut.get(entity.id) || [], 'out', 'x', 1);
    route(sideIn.get(entity.id) || [], 'in', 'x', -1);
  }
  return slots;
}

function selectionCentroid() {
  const entities = ws.entities.filter(entity => selected.has(entity.id));
  if (!entities.length) return null;
  return [0, 1, 2].map(axis => entities.reduce((sum, entity) => sum + entity.position[axis], 0) / entities.length);
}

function gizmoTips(center) {
  const length = 1.7 * Math.max(.75, nodeMasterSize());
  return { x: [center[0] + length, center[1], center[2]], y: [center[0], center[1] + length, center[2]], z: [center[0], center[1], center[2] + length] };
}

function drawGizmo() {
  const center = selectionCentroid();
  for (const id of ['gizmoX', 'gizmoY', 'gizmoZ']) $(`#${id}`).style.display = 'none';
  if (!center) return;
  const length = 1.45 * Math.max(.75, nodeMasterSize());
  const thickness = .055 * Math.max(.8, nodeMasterSize());
  drawBox([center[0] + length / 2, center[1], center[2]], [length / 2, thickness, thickness], [1, .15, .15]);
  drawBox([center[0], center[1] + length / 2, center[2]], [thickness, length / 2, thickness], [.15, 1, .15]);
  drawBox([center[0], center[1], center[2] + length / 2], [thickness, thickness, length / 2], [.15, .4, 1]);
  const tips = gizmoTips(center);
  const colors = { x: [1, .15, .15], y: [.15, 1, .15], z: [.15, .4, 1] };
  for (const [axis, point] of Object.entries(tips)) {
    const arrow = .24 * Math.max(.8, nodeMasterSize());
    if (axis === 'x') {
      drawLine([point[0] - arrow, point[1] + arrow / 2, point[2]], point, colors[axis]);
      drawLine([point[0] - arrow, point[1] - arrow / 2, point[2]], point, colors[axis]);
    } else if (axis === 'y') {
      drawLine([point[0] + arrow / 2, point[1] - arrow, point[2]], point, colors[axis]);
      drawLine([point[0] - arrow / 2, point[1] - arrow, point[2]], point, colors[axis]);
    } else {
      drawLine([point[0] + arrow / 2, point[1], point[2] - arrow], point, colors[axis]);
      drawLine([point[0] - arrow / 2, point[1], point[2] - arrow], point, colors[axis]);
    }
    const screen = project(point, viewProjection());
    const label = $(`#gizmo${axis.toUpperCase()}`);
    if (screen) {
      label.style.display = 'block';
      label.style.left = `${screen[0] / (devicePixelRatio || 1) - 14}px`;
      label.style.top = `${screen[1] / (devicePixelRatio || 1) - 7}px`;
    }
  }
}

function drawGrid() {
  if (!viewSettings().grid_visible) return;
  const spacing = gridSize();
  const half = 30;
  const majorEvery = 5;
  const count = Math.floor(half / spacing);
  for (let i = -count; i <= count; i++) {
    const v = i * spacing;
    const major = i % majorEvery === 0;
    const color = major ? [.16, .19, .24] : [.09, .11, .14];
    drawLine([-half, 0, v], [half, 0, v], color);
    drawLine([v, 0, -half], [v, 0, half], color);
  }
}

function render() {
  resize();
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.clearColor(.035, .045, .065, 1);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST);
  gl.disable(gl.CULL_FACE);

  drawGrid();
  const visible = visibleEntityIds();
  const slots = linkSlots();
  const rulesets = rulesetMap();
  const colorSpaces = colorSpaceMap();
  const time = performance.now();

  for (const { property } of activeLinkProperties()) {
    const start = slots.get(`${property.id}:out`);
    const end = slots.get(`${property.id}:in`);
    if (!start || !end) continue;
    const colorSpace = colorSpaces.get(rulesets.get(property.ruleset_ref)?.color_space_ref);
    const base = colorSpace?.colors?.base || [.5, .5, .5];
    const flow = colorSpace?.colors?.flow || [.8, .8, .8];
    const pulse = .5 + .5 * Math.sin(time * .001 * (ws.settings.link_visualization.base_flow_speed || .15) * Math.PI * 2);
    const color = base.map((value, index) => value + (flow[index] - value) * (.2 + .35 * pulse));
    drawLine(start, end, color);
  }

  const half = nodeHalfSize();
  for (const entity of ws.entities) {
    if (!visible.has(entity.id)) continue;
    let color = [.22, .27, .35];
    if (entity.id === hovered) color = [.31, .39, .5];
    if (selected.has(entity.id)) color = [.12, .46, .78];
    if (entity.id === linkSource) color = [.78, .42, .08];
    if (entity.id === linkTarget) color = [.58, .25, .78];
    drawBox(entity.position, [half, half, half], color);
    if (selected.has(entity.id) || entity.id === linkSource || entity.id === linkTarget) {
      const outline = entity.id === activeEntityId ? [.95, .98, 1] : [.7, .9, 1];
      const o = half + .01 * nodeMasterSize();
      drawBox(entity.position, [o, o, o], outline, true);
    }
  }
  drawGizmo();
  requestAnimationFrame(render);
}

function resize() {
  const density = devicePixelRatio || 1;
  const width = Math.floor(canvas.clientWidth * density);
  const height = Math.floor(canvas.clientHeight * density);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

function entityScreenBounds(entity, vp) {
  const scale = nodeHalfSize();
  const points = [];
  for (const x of [-scale, scale]) for (const y of [-scale, scale]) for (const z of [-scale, scale]) {
    const point = project([entity.position[0] + x, entity.position[1] + y, entity.position[2] + z], vp);
    if (point) points.push(point);
  }
  if (!points.length) return null;
  return {
    minX: Math.min(...points.map(point => point[0])), maxX: Math.max(...points.map(point => point[0])),
    minY: Math.min(...points.map(point => point[1])), maxY: Math.max(...points.map(point => point[1])),
    depth: Math.min(...points.map(point => point[2])),
  };
}

function pickEntity(clientX, clientY) {
  const vp = viewProjection();
  const density = devicePixelRatio || 1;
  const x = clientX * density;
  const y = clientY * density;
  let winner = null;
  let bestDepth = Infinity;
  for (const entity of ws.entities) {
    if (!visibleEntityIds().has(entity.id)) continue;
    const bounds = entityScreenBounds(entity, vp);
    if (bounds && x >= bounds.minX - 4 * density && x <= bounds.maxX + 4 * density && y >= bounds.minY - 4 * density && y <= bounds.maxY + 4 * density && bounds.depth < bestDepth) {
      winner = entity;
      bestDepth = bounds.depth;
    }
  }
  return winner;
}

function gizmoAxisHit(clientX, clientY) {
  const center = selectionCentroid();
  if (!center) return null;
  const vp = viewProjection();
  const density = devicePixelRatio || 1;
  const x = clientX * density;
  const y = clientY * density;
  const origin = project(center, vp);
  if (!origin) return null;
  let winner = null;
  let best = 22 * density;
  for (const [axis, point] of Object.entries(gizmoTips(center))) {
    const screen = project(point, vp);
    if (!screen) continue;
    const vx = screen[0] - origin[0];
    const vy = screen[1] - origin[1];
    const wx = x - origin[0];
    const wy = y - origin[1];
    const denominator = vx * vx + vy * vy || 1;
    const t = Math.max(0, Math.min(1, (wx * vx + wy * vy) / denominator));
    const distance = Math.hypot(x - (origin[0] + vx * t), y - (origin[1] + vy * t));
    if (distance < best) { best = distance; winner = axis; }
  }
  return winner;
}

function setActiveEntity(id) { activeEntityId = id && selected.has(id) ? id : null; }
function normalizeActiveSelection() {
  if (activeEntityId && selected.has(activeEntityId)) return;
  const remaining = [...selected];
  activeEntityId = remaining.length ? remaining[remaining.length - 1] : null;
}

function inspect() {
  const entities = ws.entities.filter(entity => selected.has(entity.id));
  if (!entities.length) { $('#selection').innerHTML = 'No selection'; return; }
  let html = `<div class="selection-count">${entities.length} selected</div><div class="selected-list">${entities.map(entity => `<code>${entity.id === activeEntityId ? '● ' : ''}${entity.id}</code>`).join('')}</div>`;
  if (entities.length === 1) {
    const entity = entities[0];
    for (const { property } of linkProperties().filter(({ property }) => entityForCanonicalRef(property.value.parent_ref)?.id === entity.id || entityForCanonicalRef(property.value.child_ref)?.id === entity.id)) {
      const ruleset = rulesetMap().get(property.ruleset_ref);
      html += `<div class="link-row"><span></span><span>${ruleset?.name || property.ruleset_ref}: <code>${property.value.parent_ref} → ${property.value.child_ref}</code></span></div>`;
    }
  }
  $('#selection').innerHTML = html;
}

function updateButtons() {
  $('#addLink').disabled = selected.size !== 1;
  $('#addEvent').disabled = selected.size !== 1;
  $('#deleteEntity').disabled = selected.size === 0;
}

function nextId(prefix) {
  const used = new Set([...ws.entities.map(entity => entity.id), ...ws.entities.flatMap(entity => (entity.properties || []).map(property => property.id))]);
  let index = 1;
  let id;
  do { id = `${prefix}_${String(index++).padStart(4, '0')}`; } while (used.has(id));
  return id;
}

function openLinkTypePopup() {
  $('#linkEndpoints').textContent = `${linkSource} → ${linkTarget}`;
  $('#linkTypeButtons').innerHTML = ws.rulesets.filter(ruleset => ruleset.property_type_ref === 'link').map(ruleset => `<button data-ruleset="${ruleset.id}">${ruleset.name}</button>`).join('');
  $('#linkTypePopup').hidden = false;
  $('#linkTypeButtons').querySelectorAll('button').forEach(button => { button.onclick = () => createLink(button.dataset.ruleset); });
}
function clearLink() { linkSource = null; linkTarget = null; $('#linkTypePopup').hidden = true; status('ready'); }
function createLink(rulesetRef) {
  const ruleset = rulesetMap().get(rulesetRef);
  const source = ws.entities.find(entity => entity.id === linkSource);
  if (!ruleset || !source || !linkTarget) return clearLink();
  source.properties.push({
    id: nextId('LINK'), property_type_ref: 'link', ruleset_ref: ruleset.id, status: 'unlocked',
    value: { link_type_ref: ruleset.link_type_ref, parent_ref: linkTarget, child_ref: linkSource, properties: {} },
    metadata: { workspace_entity_ref: source.id },
  });
  status(`created ${ruleset.name}: ${linkSource} → ${linkTarget}`);
  clearLink(); inspect();
}

function beginOrbit(clientX, clientY) {
  const target = cameraReference();
  const offset = V.sub(ws.camera.position, target);
  const radius = Math.max(.25, V.length(offset));
  orbit = { radius, azimuth: Math.atan2(offset[0], offset[2]), elevation: Math.asin(Math.max(-1, Math.min(1, offset[1] / radius))) };
  last = [clientX, clientY];
}
function updateOrbit(clientX, clientY) {
  if (!orbit) return;
  const sensitivity = ws.settings.camera_defaults.mouse_sensitivity || .0025;
  const dx = clientX - last[0];
  const dy = clientY - last[1];
  last = [clientX, clientY];
  const target = cameraReference();
  orbit.azimuth -= dx * sensitivity;
  orbit.elevation = Math.max(-1.52, Math.min(1.52, orbit.elevation + dy * sensitivity));
  const horizontal = Math.cos(orbit.elevation) * orbit.radius;
  ws.camera.position = [
    target[0] + Math.sin(orbit.azimuth) * horizontal,
    target[1] + Math.sin(orbit.elevation) * orbit.radius,
    target[2] + Math.cos(orbit.azimuth) * horizontal,
  ];
  syncCameraAnglesToActive();
}

canvas.oncontextmenu = event => event.preventDefault();
canvas.ondblclick = event => {
  if (event.button !== 0) return;
  const entity = pickEntity(event.clientX, event.clientY);
  if (!entity) return;
  lookAtEntityId = entity.id;
  ws.camera.reference = [...entity.position];
  syncCameraAnglesToActive();
  status(`lookAt: ${entity.id}`);
};
canvas.onwheel = event => {
  event.preventDefault();
  const speed = Number(ws.settings.camera_defaults.wheel_zoom_speed || .15);
  const step = Math.sign(event.deltaY) * speed;
  const target = cameraReference();
  const offset = V.sub(ws.camera.position, target);
  const distance = Math.max(.25, V.length(offset));
  const localZ = V.length(offset) > 1e-6 ? V.norm(offset) : cameraLocalZ();
  ws.camera.position = V.add(target, V.mul(localZ, Math.max(.25, distance + step)));
  syncCameraAnglesToActive();
};

canvas.onmousedown = event => {
  if (event.button === 2) { beginOrbit(event.clientX, event.clientY); return; }
  if (event.button !== 0) return;
  const axis = gizmoAxisHit(event.clientX, event.clientY);
  if (axis && selected.size) {
    if (lookAtEntityId && selected.has(lookAtEntityId)) detachLookAtReference();
    dragAxis = {
      axis,
      total: 0,
      startPositions: new Map(ws.entities.filter(entity => selected.has(entity.id)).map(entity => [entity.id, [...entity.position]])),
    };
    last = [event.clientX, event.clientY];
    return;
  }
  const entity = pickEntity(event.clientX, event.clientY);
  if (linkSource) {
    if (entity && entity.id !== linkSource) { linkTarget = entity.id; openLinkTypePopup(); return; }
    if (!entity) { pan = { x: event.clientX, y: event.clientY, moved: false }; last = [event.clientX, event.clientY]; }
    return;
  }
  if (!entity) { pan = { x: event.clientX, y: event.clientY, moved: false }; last = [event.clientX, event.clientY]; return; }
  if (event.ctrlKey || event.shiftKey) {
    if (selected.has(entity.id)) { selected.delete(entity.id); normalizeActiveSelection(); }
    else { selected.add(entity.id); setActiveEntity(entity.id); }
  } else { selected = new Set([entity.id]); setActiveEntity(entity.id); }
  inspect(); updateButtons();
};

window.onmouseup = event => {
  orbit = null;
  dragAxis = null;
  if (pan) {
    const click = !pan.moved;
    pan = null;
    if (click && event.button === 0 && !event.ctrlKey && !event.shiftKey && !linkSource) {
      selected.clear(); activeEntityId = null; inspect(); updateButtons();
    }
  }
};

window.onmousemove = event => {
  if (orbit) { updateOrbit(event.clientX, event.clientY); hovered = null; return; }
  if (pan) {
    const dx = event.clientX - last[0];
    const dy = event.clientY - last[1];
    const totalDrag = Math.abs(event.clientX - pan.x) + Math.abs(event.clientY - pan.y);
    if (!pan.moved && totalDrag > 2) { pan.moved = true; detachLookAtReference(); }
    if (pan.moved) {
      const speed = Number(ws.settings.camera_defaults.drag_pan_speed || .01);
      const delta = V.add(V.mul(cameraRight(), -dx * speed), V.mul(cameraUp(), dy * speed));
      ws.camera.reference = V.add(cameraReference(), delta);
      ws.camera.position = V.add(ws.camera.position, delta);
      syncCameraAnglesToActive();
    }
    last = [event.clientX, event.clientY]; hovered = null; return;
  }
  if (dragAxis && selected.size) {
    const dx = event.clientX - last[0];
    const dy = event.clientY - last[1];
    dragAxis.total += (Math.abs(dx) > Math.abs(dy) ? dx : -dy) * .015;
    const axisIndex = { x: 0, y: 1, z: 2 }[dragAxis.axis];
    const snap = Boolean(viewSettings().snap_to_grid);
    const spacing = gridSize();
    for (const entity of ws.entities) {
      const start = dragAxis.startPositions.get(entity.id);
      if (!start) continue;
      const raw = start[axisIndex] + dragAxis.total;
      entity.position[axisIndex] = snap ? Math.round(raw / spacing) * spacing : raw;
    }
    last = [event.clientX, event.clientY]; inspect(); return;
  }
  hovered = pickEntity(event.clientX, event.clientY)?.id || null;
};

window.onkeydown = event => keys.add(event.key.toLowerCase());
window.onkeyup = event => keys.delete(event.key.toLowerCase());
let previousFrame = performance.now();
function tick(time) {
  const dt = Math.min(.05, (time - previousFrame) / 1000);
  previousFrame = time;
  const speed = (ws.settings.camera_defaults.movement_speed || 6) * dt;
  const forward = viewForward();
  const right = cameraRight();
  let moved = false;
  if (keys.has('w')) { ws.camera.position = V.add(ws.camera.position, V.mul(forward, speed)); moved = true; }
  if (keys.has('s')) { ws.camera.position = V.sub(ws.camera.position, V.mul(forward, speed)); moved = true; }
  if (keys.has('a')) { ws.camera.position = V.sub(ws.camera.position, V.mul(right, speed)); moved = true; }
  if (keys.has('d')) { ws.camera.position = V.add(ws.camera.position, V.mul(right, speed)); moved = true; }
  if (keys.has('q')) { ws.camera.position[1] -= speed; moved = true; }
  if (keys.has('e')) { ws.camera.position[1] += speed; moved = true; }
  if (moved) syncCameraAnglesToActive();
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

$('#addEntity').onclick = () => {
  let index = 1;
  let id;
  const used = new Set(ws.entities.map(entity => entity.id));
  do { id = `ENTITY_${String(index++).padStart(3, '0')}`; } while (used.has(id));
  const position = V.add(ws.camera.position, V.mul(viewForward(), 5));
  if (viewSettings().snap_to_grid) for (let axis = 0; axis < 3; axis++) position[axis] = Math.round(position[axis] / gridSize()) * gridSize();
  ws.entities.push({ id, name: id, entity_type_ref: 'entity', status: 'unlocked', position, properties: [] });
  selected = new Set([id]); setActiveEntity(id); inspect(); updateButtons(); status(`created ${id}`);
};
$('#deleteEntity').onclick = () => {
  const removed = new Set(selected);
  const removedCanonical = new Set();
  for (const entity of ws.entities) {
    if (!removed.has(entity.id)) continue;
    removedCanonical.add(entity.id);
    for (const property of entity.properties || []) removedCanonical.add(property.id);
  }
  if (lookAtEntityId && removed.has(lookAtEntityId)) detachLookAtReference();
  ws.entities = ws.entities.filter(entity => !removed.has(entity.id));
  for (const entity of ws.entities) {
    entity.properties = (entity.properties || []).filter(property =>
      property.property_type_ref !== 'link' ||
      (!removedCanonical.has(property.value.parent_ref) && !removedCanonical.has(property.value.child_ref))
    );
  }
  selected.clear(); activeEntityId = null; inspect(); updateButtons(); status(`deleted ${removed.size} entities`);
};
$('#addLink').onclick = () => { if (selected.size === 1) { linkSource = [...selected][0]; linkTarget = null; status(`select link target for ${linkSource}`); } };
$('#cancelLink').onclick = clearLink;
$('#addEvent').onclick = () => { if (selected.size === 1) { $('#eventType').value = 'event'; $('#eventPopup').hidden = false; } };
$('#cancelEvent').onclick = () => { $('#eventPopup').hidden = true; };
$('#createEvent').onclick = () => {
  if (selected.size !== 1) return;
  const entity = ws.entities.find(item => selected.has(item.id));
  const type = $('#eventType').value.trim();
  if (!entity || !type) return;
  entity.properties.push({ id: nextId('EVENT'), property_type_ref: 'event', ruleset_ref: 'RULESET_EVENT', status: 'unlocked', value: { event_type_ref: type, properties: {} }, metadata: { workspace_entity_ref: entity.id } });
  $('#eventPopup').hidden = true; status(`created Event on ${entity.id}`); inspect();
};

function syncCatalog() {
  ensureWorkspace();
  const linkRulesets = ws.rulesets.filter(ruleset => ruleset.property_type_ref === 'link');
  $('#rulesetView').innerHTML = ['<option value="ALL">All link Rulesets</option>', ...linkRulesets.map(ruleset => `<option value="${ruleset.id}">${ruleset.name}</option>`)].join('');
  $('#rulesetView').value = ws.view.ruleset_ref || 'ALL';
}
$('#rulesetView').onchange = event => { ws.view.ruleset_ref = event.target.value; selected.clear(); activeEntityId = null; clearLink(); inspect(); updateButtons(); };

$('#save').onclick = async () => {
  const response = await fetch('/api/workspace', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(ws) });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error);
  ws = payload.workspace; ensureWorkspace(); syncCatalog(); syncSettings(); status('saved');
};
$('#load').onclick = async () => {
  const response = await fetch('/api/workspace');
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error);
  ws = payload.workspace; ensureWorkspace(); lookAtEntityId = null; selected.clear(); activeEntityId = null; clearLink(); syncCatalog(); syncSettings(); inspect(); updateButtons(); status('loaded');
};
$('#settingsButton').onclick = () => { $('#settings').hidden = !$('#settings').hidden; };

function syncSettings() {
  const camera = ws.settings.camera_defaults;
  const links = ws.settings.link_visualization;
  const events = ws.settings.event_playback;
  const view = viewSettings();
  $('#fov').value = ws.camera.fov;
  $('#fovValue').value = `${Math.round(ws.camera.fov)}°`;
  $('#moveSpeed').value = camera.movement_speed;
  $('#mouseSensitivity').value = camera.mouse_sensitivity;
  $('#wheelZoomSpeed').value = camera.wheel_zoom_speed;
  $('#dragPanSpeed').value = camera.drag_pan_speed;
  $('#anchorSpacing').value = links.anchor_spacing;
  $('#anchorOffset').value = links.anchor_offset;
  $('#baseLinkSpeed').value = links.base_flow_speed;
  $('#activeLinkSpeed').value = events.active_link_speed;
  $('#effectTravel').value = events.effect_travel_duration;
  $('#nodeMasterSize').value = view.node_master_size;
  $('#nodeMasterSizeValue').textContent = `${Number(view.node_master_size).toFixed(2)}×`;
  $('#gridToggle').checked = Boolean(view.grid_visible);
  $('#snapToggle').checked = Boolean(view.snap_to_grid);
  updateViewToggleState();
}
function updateViewToggleState() {
  for (const id of ['gridToggle', 'snapToggle']) {
    const input = $(`#${id}`);
    input.closest('.view-toggle')?.classList.toggle('active', input.checked);
  }
}

$('#fov').oninput = event => { ws.camera.fov = Number(event.target.value); $('#fovValue').value = `${event.target.value}°`; };
$('#moveSpeed').onchange = event => { ws.settings.camera_defaults.movement_speed = Number(event.target.value); };
$('#mouseSensitivity').onchange = event => { ws.settings.camera_defaults.mouse_sensitivity = Number(event.target.value); };
$('#wheelZoomSpeed').onchange = event => { ws.settings.camera_defaults.wheel_zoom_speed = Number(event.target.value); };
$('#dragPanSpeed').onchange = event => { ws.settings.camera_defaults.drag_pan_speed = Number(event.target.value); };
$('#anchorSpacing').onchange = event => { ws.settings.link_visualization.anchor_spacing = Number(event.target.value); };
$('#anchorOffset').onchange = event => { ws.settings.link_visualization.anchor_offset = Number(event.target.value); };
$('#baseLinkSpeed').onchange = event => { ws.settings.link_visualization.base_flow_speed = Number(event.target.value); };
$('#activeLinkSpeed').onchange = event => { ws.settings.event_playback.active_link_speed = Number(event.target.value); };
$('#effectTravel').onchange = event => { ws.settings.event_playback.effect_travel_duration = Number(event.target.value); };
$('#nodeMasterSize').oninput = event => { viewSettings().node_master_size = Number(event.target.value); $('#nodeMasterSizeValue').textContent = `${Number(event.target.value).toFixed(2)}×`; };
$('#gridToggle').onchange = event => { viewSettings().grid_visible = event.target.checked; updateViewToggleState(); };
$('#snapToggle').onchange = event => { viewSettings().snap_to_grid = event.target.checked; updateViewToggleState(); };

$('#setCameraDefault').onclick = () => {
  const camera = ws.settings.camera_defaults;
  camera.position = [...ws.camera.position]; camera.reference = [...cameraReference()]; camera.yaw = ws.camera.yaw; camera.pitch = ws.camera.pitch; camera.fov = ws.camera.fov;
  status('camera default set');
};
$('#resetCamera').onclick = () => {
  const camera = ws.settings.camera_defaults;
  lookAtEntityId = null;
  ws.camera = { position: [...camera.position], reference: [...camera.reference], yaw: camera.yaw, pitch: camera.pitch, fov: camera.fov };
  syncCameraAnglesToActive(); syncSettings(); status('camera reset');
};

ensureWorkspace();
syncCatalog();
syncSettings();
inspect();
updateButtons();
render();
fetch('/api/health').then(response => response.json()).then(payload => status(payload.ok ? 'server connected' : 'server error')).catch(() => status('server offline'));
