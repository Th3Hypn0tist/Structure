const canvas = document.querySelector('#scene');
const gl = canvas.getContext('webgl2', { antialias: true });
if (!gl) throw new Error('WebGL2 required');

const $ = selector => document.querySelector(selector);
const status = text => { $('#status').textContent = text; };

const V = {
  add: (a, b) => a.map((value, index) => value + b[index]),
  sub: (a, b) => a.map((value, index) => value - b[index]),
  mul: (a, scalar) => a.map(value => value * scalar),
  dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
  cross: (a, b) => [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ],
  norm: value => {
    const length = Math.hypot(...value) || 1;
    return value.map(component => component / length);
  },
};

function m4mul(a, b) {
  const out = new Array(16).fill(0);
  for (let column = 0; column < 4; column++) {
    for (let row = 0; row < 4; row++) {
      for (let k = 0; k < 4; k++) {
        out[column * 4 + row] += a[k * 4 + row] * b[column * 4 + k];
      }
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

function lookAt(position, target, up = [0, 1, 0]) {
  const z = V.norm(V.sub(position, target));
  const x = V.norm(V.cross(up, z));
  const y = V.cross(z, x);
  return [
    x[0], y[0], z[0], 0,
    x[1], y[1], z[1], 0,
    x[2], y[2], z[2], 0,
    -V.dot(x, position), -V.dot(y, position), -V.dot(z, position), 1,
  ];
}

function model(position, scale = 1) {
  return [
    scale, 0, 0, 0,
    0, scale, 0, 0,
    0, 0, scale, 0,
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
    (clipX / clipW * 0.5 + 0.5) * canvas.width,
    (-clipY / clipW * 0.5 + 0.5) * canvas.height,
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
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader));
  }
  return shader;
}

const program = gl.createProgram();
gl.attachShader(program, compileShader(gl.VERTEX_SHADER, vertexShader));
gl.attachShader(program, compileShader(gl.FRAGMENT_SHADER, fragmentShader));
gl.linkProgram(program);
if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
  throw new Error(gl.getProgramInfoLog(program));
}
gl.useProgram(program);

const loc = {
  position: gl.getAttribLocation(program, 'p'),
  mvp: gl.getUniformLocation(program, 'mvp'),
  color: gl.getUniformLocation(program, 'color'),
};

const cubeVertices = new Float32Array([
  -1, -1, -1,
   1, -1, -1,
   1,  1, -1,
  -1,  1, -1,
  -1, -1,  1,
   1, -1,  1,
   1,  1,  1,
  -1,  1,  1,
]);

const cubeFaces = new Uint16Array([
  0, 2, 1, 0, 3, 2,
  4, 5, 6, 4, 6, 7,
  0, 4, 7, 0, 7, 3,
  1, 2, 6, 1, 6, 5,
  0, 1, 5, 0, 5, 4,
  3, 7, 6, 3, 6, 2,
]);

const cubeEdges = new Uint16Array([
  0, 1, 1, 2, 2, 3, 3, 0,
  4, 5, 5, 6, 6, 7, 7, 4,
  0, 4, 1, 5, 2, 6, 3, 7,
]);

const cubeVertexBuffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, cubeVertexBuffer);
gl.bufferData(gl.ARRAY_BUFFER, cubeVertices, gl.STATIC_DRAW);
gl.enableVertexAttribArray(loc.position);
gl.vertexAttribPointer(loc.position, 3, gl.FLOAT, false, 0, 0);

const cubeFaceBuffer = gl.createBuffer();
gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, cubeFaceBuffer);
gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, cubeFaces, gl.STATIC_DRAW);

const cubeEdgeBuffer = gl.createBuffer();
gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, cubeEdgeBuffer);
gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, cubeEdges, gl.STATIC_DRAW);

const lineBuffer = gl.createBuffer();

const DEFAULT_RULESETS = [
  { id: 'RULESET_LINK_DEPENDENCY', name: 'Dependency', property_type_ref: 'link', link_type_ref: 'dependency', semantic_roles: { parent_ref: 'dependency', child_ref: 'dependent' }, color_space_ref: 'COLORSPACE_DEPENDENCY' },
  { id: 'RULESET_LINK_OWNERSHIP', name: 'Ownership', property_type_ref: 'link', link_type_ref: 'ownership', semantic_roles: { parent_ref: 'owner', child_ref: 'owned' }, color_space_ref: 'COLORSPACE_OWNERSHIP' },
  { id: 'RULESET_LINK_AUTHORITY', name: 'Authority', property_type_ref: 'link', link_type_ref: 'authority', semantic_roles: { parent_ref: 'authority', child_ref: 'governed' }, color_space_ref: 'COLORSPACE_AUTHORITY' },
  { id: 'RULESET_LINK_CONTAINMENT', name: 'Containment', property_type_ref: 'link', link_type_ref: 'containment', semantic_roles: { parent_ref: 'container', child_ref: 'contained' }, color_space_ref: 'COLORSPACE_CONTAINMENT' },
  { id: 'RULESET_LINK_ARCHITECTURE_PARENT', name: 'Architecture Parent', property_type_ref: 'link', link_type_ref: 'architecture_parent', semantic_roles: { parent_ref: 'architecture_parent', child_ref: 'architecture_child' }, color_space_ref: 'COLORSPACE_ARCHITECTURE' },
];

const DEFAULT_COLORS = [
  { id: 'COLORSPACE_LINK_GENERIC', colors: { base: [.42, .48, .58], flow: [.78, .84, .94], selected: [.95, .97, 1] } },
  { id: 'COLORSPACE_DEPENDENCY', colors: { base: [.18, .42, .90], flow: [.40, .76, 1], selected: [.78, .92, 1] } },
  { id: 'COLORSPACE_OWNERSHIP', colors: { base: [.78, .50, .08], flow: [1, .76, .22], selected: [1, .90, .58] } },
  { id: 'COLORSPACE_AUTHORITY', colors: { base: [.72, .18, .28], flow: [1, .38, .42], selected: [1, .72, .74] } },
  { id: 'COLORSPACE_CONTAINMENT', colors: { base: [.22, .60, .32], flow: [.46, .92, .54], selected: [.74, 1, .78] } },
  { id: 'COLORSPACE_ARCHITECTURE', colors: { base: [.52, .26, .82], flow: [.76, .48, 1], selected: [.90, .76, 1] } },
];

let ws = {
  version: '0.2.0',
  entities: [],
  rulesets: structuredClone(DEFAULT_RULESETS),
  color_spaces: structuredClone(DEFAULT_COLORS),
  view: { ruleset_ref: 'ALL' },
  camera: { position: [0, 1.5, 8], yaw: 0, pitch: 0, fov: 60 },
  settings: {
    camera_defaults: { position: [0, 1.5, 8], yaw: 0, pitch: 0, fov: 60, movement_speed: 6, mouse_sensitivity: .0025, near_clip: .05, far_clip: 1000 },
    link_visualization: { anchor_spacing: .28, anchor_offset: .58, base_flow_speed: .15, flow_width: .18 },
    event_playback: { base_link_speed: .15, active_link_speed: 2, effect_travel_duration: 1.2 },
  },
};

let selected = null;
let hovered = null;
let keys = new Set();
let looking = false;
let last = [0, 0];
let dragAxis = null;
let linkMode = false;
let linkChild = null;

function forward() {
  const cosine = Math.cos(ws.camera.pitch);
  return [
    Math.sin(ws.camera.yaw) * cosine,
    Math.sin(ws.camera.pitch),
    -Math.cos(ws.camera.yaw) * cosine,
  ];
}

function right() {
  return V.norm(V.cross(forward(), [0, 1, 0]));
}

function vp() {
  const settings = ws.settings.camera_defaults;
  const projection = perspective(
    ws.camera.fov,
    canvas.width / canvas.height,
    settings.near_clip || .05,
    settings.far_clip || 1000,
  );
  const view = lookAt(ws.camera.position, V.add(ws.camera.position, forward()));
  return m4mul(projection, view);
}

function bindCubeVertices() {
  gl.bindBuffer(gl.ARRAY_BUFFER, cubeVertexBuffer);
  gl.vertexAttribPointer(loc.position, 3, gl.FLOAT, false, 0, 0);
}

function drawLine(start, end, color) {
  gl.bindBuffer(gl.ARRAY_BUFFER, lineBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([...start, ...end]), gl.DYNAMIC_DRAW);
  gl.vertexAttribPointer(loc.position, 3, gl.FLOAT, false, 0, 0);
  gl.uniformMatrix4fv(loc.mvp, false, new Float32Array(vp()));
  gl.uniform3fv(loc.color, color);
  gl.drawArrays(gl.LINES, 0, 2);
  bindCubeVertices();
}

function drawPoint(position, color, size = .08) {
  const length = size;
  drawLine([position[0] - length, position[1], position[2]], [position[0] + length, position[1], position[2]], color);
  drawLine([position[0], position[1] - length, position[2]], [position[0], position[1] + length, position[2]], color);
}

function drawNode(entity, viewProjection) {
  const transform = model(entity.position, .45);
  const mvp = m4mul(viewProjection, transform);
  const isSelected = entity.id === selected;
  const isHovered = entity.id === hovered;
  const isLinkChild = linkMode && entity.id === linkChild;

  let fill = [.22, .27, .35];
  if (isHovered) fill = [.31, .39, .50];
  if (isSelected) fill = [.12, .46, .78];
  if (isLinkChild) fill = [.78, .42, .08];

  gl.uniformMatrix4fv(loc.mvp, false, new Float32Array(mvp));
  gl.uniform3fv(loc.color, fill);
  bindCubeVertices();
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, cubeFaceBuffer);
  gl.drawElements(gl.TRIANGLES, cubeFaces.length, gl.UNSIGNED_SHORT, 0);

  if (isSelected || isLinkChild) {
    gl.uniform3fv(loc.color, isLinkChild ? [1, .78, .30] : [.55, .86, 1]);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, cubeEdgeBuffer);
    gl.drawElements(gl.LINES, cubeEdges.length, gl.UNSIGNED_SHORT, 0);
  }
}

function rulesetMap() {
  return new Map((ws.rulesets || []).map(ruleset => [ruleset.id, ruleset]));
}

function colorMap() {
  return new Map((ws.color_spaces || []).map(colorSpace => [colorSpace.id, colorSpace]));
}

function allLinkProperties() {
  const result = [];
  for (const owner of ws.entities) {
    for (const property of owner.properties || []) {
      if (property.property_type_ref === 'link') result.push({ owner, p: property });
    }
  }
  return result;
}

function activeLinkProperties() {
  const filter = ws.view?.ruleset_ref || 'ALL';
  return allLinkProperties().filter(({ p }) => filter === 'ALL' || p.ruleset_ref === filter);
}

function visibleEntityIds() {
  const filter = ws.view?.ruleset_ref || 'ALL';
  if (filter === 'ALL') return new Set(ws.entities.map(entity => entity.id));

  const ids = new Set();
  for (const { p } of activeLinkProperties()) {
    if (ws.entities.some(entity => entity.id === p.value.parent_ref)) ids.add(p.value.parent_ref);
    if (ws.entities.some(entity => entity.id === p.value.child_ref)) ids.add(p.value.child_ref);
  }
  return ids;
}

function linkSlots() {
  const spacing = Number(ws.settings.link_visualization?.anchor_spacing || .28);
  const offset = Number(ws.settings.link_visualization?.anchor_offset || .58);
  const incoming = new Map();
  const outgoing = new Map();

  for (const { p } of activeLinkProperties()) {
    if (ws.entities.some(entity => entity.id === p.value.parent_ref)) {
      if (!incoming.has(p.value.parent_ref)) incoming.set(p.value.parent_ref, []);
      incoming.get(p.value.parent_ref).push(p.id);
    }
    if (ws.entities.some(entity => entity.id === p.value.child_ref)) {
      if (!outgoing.has(p.value.child_ref)) outgoing.set(p.value.child_ref, []);
      outgoing.get(p.value.child_ref).push(p.id);
    }
  }

  for (const list of [...incoming.values(), ...outgoing.values()]) list.sort();

  const points = new Map();
  for (const entity of ws.entities) {
    for (const [kind, map, sign] of [['in', incoming, -1], ['out', outgoing, 1]]) {
      const list = map.get(entity.id) || [];
      const start = -(list.length - 1) * spacing / 2;
      list.forEach((id, index) => {
        points.set(`${id}:${kind}`, [
          entity.position[0] + sign * offset,
          entity.position[1] + start + index * spacing,
          entity.position[2],
        ]);
      });
    }
  }
  return points;
}

function lerp(a, b, t) {
  return a.map((value, index) => value + (b[index] - value) * t);
}

function animatedColor(colorSpace, time) {
  const base = colorSpace?.colors?.base || [.45, .5, .58];
  const flow = colorSpace?.colors?.flow || [.85, .9, 1];
  const speed = Number(ws.settings.link_visualization?.base_flow_speed || .15);
  const pulse = .5 + .5 * Math.sin(time * .001 * Math.max(.01, speed) * Math.PI * 2);
  return lerp(base, flow, .20 + .35 * pulse);
}

function render() {
  resize();
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.clearColor(.035, .045, .065, 1);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST);
  gl.disable(gl.CULL_FACE);

  const viewProjection = vp();
  const visible = visibleEntityIds();
  const slots = linkSlots();
  const rulesets = rulesetMap();
  const colors = colorMap();
  const now = performance.now();

  for (const { p } of activeLinkProperties()) {
    const start = slots.get(`${p.id}:out`);
    const end = slots.get(`${p.id}:in`);
    if (!start || !end) continue;
    const ruleset = rulesets.get(p.ruleset_ref);
    const colorSpace = colors.get(ruleset?.color_space_ref);
    drawLine(start, end, animatedColor(colorSpace, now));
  }

  for (const entity of ws.entities) {
    if (!visible.has(entity.id)) continue;
    drawNode(entity, viewProjection);
  }

  for (const { p } of activeLinkProperties()) {
    const start = slots.get(`${p.id}:out`);
    const end = slots.get(`${p.id}:in`);
    if (!start || !end) continue;
    const ruleset = rulesets.get(p.ruleset_ref);
    const colorSpace = colors.get(ruleset?.color_space_ref);
    const anchorColor = colorSpace?.colors?.flow || [.8, .8, .8];
    drawPoint(start, anchorColor, .06);
    drawPoint(end, anchorColor, .06);
  }

  if (selected && visible.has(selected)) {
    const entity = ws.entities.find(item => item.id === selected);
    if (entity) {
      const position = entity.position;
      const length = 1.5;
      drawLine(position, [position[0] + length, position[1], position[2]], [1, .2, .2]);
      drawLine(position, [position[0], position[1] + length, position[2]], [.2, 1, .2]);
      drawLine(position, [position[0], position[1], position[2] + length], [.2, .45, 1]);
    }
  }

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

function nodeScreenBounds(entity, viewProjection) {
  const scale = .45;
  const points = [];
  for (const x of [-scale, scale]) {
    for (const y of [-scale, scale]) {
      for (const z of [-scale, scale]) {
        const projected = project([
          entity.position[0] + x,
          entity.position[1] + y,
          entity.position[2] + z,
        ], viewProjection);
        if (projected) points.push(projected);
      }
    }
  }
  if (points.length < 4) return null;
  return {
    minX: Math.min(...points.map(point => point[0])),
    maxX: Math.max(...points.map(point => point[0])),
    minY: Math.min(...points.map(point => point[1])),
    maxY: Math.max(...points.map(point => point[1])),
    depth: Math.min(...points.map(point => point[2])),
  };
}

function pickNode(clientX, clientY) {
  const viewProjection = vp();
  const density = devicePixelRatio || 1;
  const x = clientX * density;
  const y = clientY * density;
  const visible = visibleEntityIds();
  const padding = 4 * density;
  let winner = null;
  let bestDepth = Infinity;

  for (const entity of ws.entities) {
    if (!visible.has(entity.id)) continue;
    const bounds = nodeScreenBounds(entity, viewProjection);
    if (!bounds) continue;
    if (
      x >= bounds.minX - padding &&
      x <= bounds.maxX + padding &&
      y >= bounds.minY - padding &&
      y <= bounds.maxY + padding &&
      bounds.depth < bestDepth
    ) {
      winner = entity;
      bestDepth = bounds.depth;
    }
  }
  return winner;
}

function axisHit(clientX, clientY) {
  if (!selected) return null;
  const entity = ws.entities.find(item => item.id === selected);
  if (!entity) return null;

  const viewProjection = vp();
  const density = devicePixelRatio || 1;
  const x = clientX * density;
  const y = clientY * density;
  const base = project(entity.position, viewProjection);
  if (!base) return null;

  const axes = {
    x: [entity.position[0] + 1.5, entity.position[1], entity.position[2]],
    y: [entity.position[0], entity.position[1] + 1.5, entity.position[2]],
    z: [entity.position[0], entity.position[1], entity.position[2] + 1.5],
  };

  let winner = null;
  let best = 18 * density;
  for (const [axis, point] of Object.entries(axes)) {
    const screen = project(point, viewProjection);
    if (!screen) continue;
    const vx = screen[0] - base[0];
    const vy = screen[1] - base[1];
    const wx = x - base[0];
    const wy = y - base[1];
    const denominator = vx * vx + vy * vy || 1;
    const t = Math.max(0, Math.min(1, (wx * vx + wy * vy) / denominator));
    const distance = Math.hypot(x - (base[0] + vx * t), y - (base[1] + vy * t));
    if (distance < best) {
      best = distance;
      winner = axis;
    }
  }
  return winner;
}

function inspect() {
  const entity = ws.entities.find(item => item.id === selected);
  if (!entity) {
    $('#selection').innerHTML = 'No selection';
    return;
  }

  const links = allLinkProperties().filter(({ p }) =>
    p.value.parent_ref === entity.id || p.value.child_ref === entity.id
  );
  const rulesets = rulesetMap();
  const colors = colorMap();
  let html = `<code>${entity.id}</code><br><span class="muted">position ${entity.position.map(value => value.toFixed(2)).join(', ')}</span>`;

  for (const { p } of links) {
    const ruleset = rulesets.get(p.ruleset_ref);
    const colorSpace = colors.get(ruleset?.color_space_ref);
    const rgb = (colorSpace?.colors?.base || [.5, .5, .5]).map(value => Math.round(value * 255));
    const incoming = p.value.parent_ref === entity.id;
    const other = incoming ? p.value.child_ref : p.value.parent_ref;
    html += `<div class="link-row"><span class="swatch" style="background:rgb(${rgb.join(',')})"></span><span>${incoming ? 'IN' : 'OUT'} ${ruleset?.name || p.ruleset_ref}: <code>${other}</code></span></div>`;
  }
  $('#selection').innerHTML = html;
}

function ensureCatalog() {
  if (!Array.isArray(ws.rulesets) || !ws.rulesets.length) ws.rulesets = structuredClone(DEFAULT_RULESETS);
  if (!Array.isArray(ws.color_spaces) || !ws.color_spaces.length) ws.color_spaces = structuredClone(DEFAULT_COLORS);
  ws.view ??= { ruleset_ref: 'ALL' };
  ws.settings.link_visualization ??= { anchor_spacing: .28, anchor_offset: .58, base_flow_speed: .15, flow_width: .18 };
}

function syncCatalog() {
  ensureCatalog();
  const linkRulesets = ws.rulesets.filter(ruleset => ruleset.property_type_ref === 'link');
  $('#rulesetView').innerHTML = [
    '<option value="ALL">All link Rulesets</option>',
    ...linkRulesets.map(ruleset => `<option value="${ruleset.id}">${ruleset.name}</option>`),
  ].join('');
  $('#rulesetView').value = ws.view.ruleset_ref || 'ALL';
  $('#linkRuleset').innerHTML = linkRulesets
    .map(ruleset => `<option value="${ruleset.id}">${ruleset.name}</option>`)
    .join('');
}

function nextPropertyId(prefix = 'LINK') {
  const used = new Set(ws.entities.flatMap(entity => (entity.properties || []).map(property => property.id)));
  let index = 1;
  let id;
  do {
    id = `${prefix}_${String(index++).padStart(4, '0')}`;
  } while (used.has(id) || ws.entities.some(entity => entity.id === id));
  return id;
}

function updateLinkPrompt() {
  if (!linkMode) return;
  if (!linkChild) {
    $('#linkStep').textContent = 'Select child / outgoing Entity';
    return;
  }
  $('#linkStep').innerHTML = `Child/outgoing: <code>${linkChild}</code><br>Select parent / incoming Entity`;
}

function cancelLink() {
  linkMode = false;
  linkChild = null;
  $('#linkMode').classList.remove('active');
  $('#linkComposer').hidden = true;
  $('#linkStep').textContent = 'Select child / outgoing Entity';
}

function beginLink() {
  if (linkMode) {
    cancelLink();
    return;
  }
  linkMode = true;
  linkChild = selected && visibleEntityIds().has(selected) ? selected : null;
  $('#linkMode').classList.add('active');
  $('#linkComposer').hidden = false;
  updateLinkPrompt();
  status(linkChild ? `link child selected: ${linkChild}` : 'select link child');
}

function selectForLink(node) {
  selected = node.id;
  inspect();

  if (!linkChild) {
    linkChild = node.id;
    updateLinkPrompt();
    status(`link child selected: ${node.id}`);
    return;
  }

  if (node.id === linkChild) {
    status('parent and child must differ');
    return;
  }

  const ruleset = rulesetMap().get($('#linkRuleset').value);
  if (!ruleset) {
    status('select a Link Ruleset');
    return;
  }

  const child = ws.entities.find(entity => entity.id === linkChild);
  if (!child) {
    status('link child no longer exists');
    cancelLink();
    return;
  }

  const id = nextPropertyId();
  child.properties.push({
    id,
    property_type_ref: 'link',
    ruleset_ref: ruleset.id,
    status: 'unlocked',
    value: {
      link_type_ref: ruleset.link_type_ref,
      parent_ref: node.id,
      child_ref: child.id,
      properties: {},
    },
    metadata: { workspace_entity_ref: child.id },
  });

  selected = child.id;
  inspect();
  status(`created ${ruleset.name}: ${node.id} < ${child.id}`);
  cancelLink();
}

canvas.addEventListener('contextmenu', event => event.preventDefault());

canvas.addEventListener('mousedown', event => {
  if (event.button === 2) {
    looking = true;
    last = [event.clientX, event.clientY];
    return;
  }
  if (event.button !== 0) return;

  if (!linkMode) {
    const axis = axisHit(event.clientX, event.clientY);
    if (axis) {
      dragAxis = axis;
      last = [event.clientX, event.clientY];
      return;
    }
  }

  const node = pickNode(event.clientX, event.clientY);
  if (linkMode && node) {
    selectForLink(node);
    return;
  }

  selected = node?.id || null;
  inspect();
});

window.addEventListener('mouseup', () => {
  looking = false;
  dragAxis = null;
});

window.addEventListener('mousemove', event => {
  if (looking) {
    const sensitivity = ws.settings.camera_defaults.mouse_sensitivity || .0025;
    ws.camera.yaw -= (event.clientX - last[0]) * sensitivity;
    ws.camera.pitch = Math.max(-1.55, Math.min(1.55, ws.camera.pitch - (event.clientY - last[1]) * sensitivity));
    last = [event.clientX, event.clientY];
    hovered = null;
    return;
  }

  if (dragAxis && selected) {
    const entity = ws.entities.find(item => item.id === selected);
    const dx = event.clientX - last[0];
    const dy = event.clientY - last[1];
    const amount = (Math.abs(dx) > Math.abs(dy) ? dx : -dy) * .015;
    const index = { x: 0, y: 1, z: 2 }[dragAxis];
    entity.position[index] += amount;
    last = [event.clientX, event.clientY];
    inspect();
    return;
  }

  hovered = pickNode(event.clientX, event.clientY)?.id || null;
});

window.addEventListener('keydown', event => keys.add(event.key.toLowerCase()));
window.addEventListener('keyup', event => keys.delete(event.key.toLowerCase()));

let previousFrame = performance.now();
function tick(time) {
  const dt = Math.min(.05, (time - previousFrame) / 1000);
  previousFrame = time;
  const speed = (ws.settings.camera_defaults.movement_speed || 6) * dt;
  const cameraForward = forward();
  const cameraRight = right();

  if (keys.has('w')) ws.camera.position = V.add(ws.camera.position, V.mul(cameraForward, speed));
  if (keys.has('s')) ws.camera.position = V.sub(ws.camera.position, V.mul(cameraForward, speed));
  if (keys.has('a')) ws.camera.position = V.sub(ws.camera.position, V.mul(cameraRight, speed));
  if (keys.has('d')) ws.camera.position = V.add(ws.camera.position, V.mul(cameraRight, speed));
  if (keys.has('q')) ws.camera.position[1] -= speed;
  if (keys.has('e')) ws.camera.position[1] += speed;
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

$('#add').onclick = () => {
  const used = new Set(ws.entities.map(entity => entity.id));
  let index = 1;
  let id;
  do {
    id = `ENTITY_${String(index++).padStart(3, '0')}`;
  } while (used.has(id));

  ws.entities.push({
    id,
    name: id,
    entity_type_ref: 'entity',
    status: 'unlocked',
    position: V.add(ws.camera.position, V.mul(forward(), 5)),
    properties: [],
  });
  selected = id;
  inspect();
  status(`created ${id}`);
};

$('#delete').onclick = () => {
  if (!selected) return;
  const remove = selected;
  ws.entities = ws.entities.filter(entity => entity.id !== remove);
  for (const entity of ws.entities) {
    entity.properties = (entity.properties || []).filter(property =>
      property.property_type_ref !== 'link' ||
      (property.value.parent_ref !== remove && property.value.child_ref !== remove)
    );
  }
  selected = null;
  hovered = null;
  if (linkChild === remove) cancelLink();
  inspect();
  status(`deleted ${remove} and attached links`);
};

$('#linkMode').onclick = beginLink;
$('#cancelLink').onclick = cancelLink;

$('#rulesetView').onchange = event => {
  ws.view.ruleset_ref = event.target.value;
  selected = null;
  hovered = null;
  cancelLink();
  inspect();
  status(event.target.value === 'ALL' ? 'showing all link Rulesets' : `isolated ${event.target.selectedOptions[0].textContent}`);
};

$('#save').onclick = async () => {
  const response = await fetch('/api/workspace', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(ws),
  });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error);
  ws = payload.workspace;
  ensureCatalog();
  syncCatalog();
  status('saved');
};

$('#load').onclick = async () => {
  const response = await fetch('/api/workspace');
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error);
  ws = payload.workspace;
  ensureCatalog();
  syncCatalog();
  syncSettings();
  selected = null;
  hovered = null;
  cancelLink();
  inspect();
  status('loaded');
};

$('#settingsButton').onclick = () => {
  $('#settings').hidden = !$('#settings').hidden;
};

function syncSettings() {
  ensureCatalog();
  const camera = ws.settings.camera_defaults;
  const link = ws.settings.link_visualization;
  const event = ws.settings.event_playback;
  $('#fov').value = ws.camera.fov;
  $('#fovValue').value = `${Math.round(ws.camera.fov)}°`;
  $('#moveSpeed').value = camera.movement_speed;
  $('#mouseSensitivity').value = camera.mouse_sensitivity;
  $('#anchorSpacing').value = link.anchor_spacing;
  $('#anchorOffset').value = link.anchor_offset;
  $('#baseLinkSpeed').value = link.base_flow_speed;
  $('#activeLinkSpeed').value = event.active_link_speed;
  $('#effectTravel').value = event.effect_travel_duration;
}

$('#fov').oninput = event => {
  ws.camera.fov = Number(event.target.value);
  $('#fovValue').value = `${event.target.value}°`;
};
$('#moveSpeed').onchange = event => { ws.settings.camera_defaults.movement_speed = Number(event.target.value); };
$('#mouseSensitivity').onchange = event => { ws.settings.camera_defaults.mouse_sensitivity = Number(event.target.value); };
$('#anchorSpacing').onchange = event => { ws.settings.link_visualization.anchor_spacing = Number(event.target.value); };
$('#anchorOffset').onchange = event => { ws.settings.link_visualization.anchor_offset = Number(event.target.value); };
$('#baseLinkSpeed').onchange = event => {
  ws.settings.link_visualization.base_flow_speed = Number(event.target.value);
  ws.settings.event_playback.base_link_speed = Number(event.target.value);
};
$('#activeLinkSpeed').onchange = event => { ws.settings.event_playback.active_link_speed = Number(event.target.value); };
$('#effectTravel').onchange = event => { ws.settings.event_playback.effect_travel_duration = Number(event.target.value); };

$('#setCameraDefault').onclick = () => {
  const camera = ws.settings.camera_defaults;
  camera.position = [...ws.camera.position];
  camera.yaw = ws.camera.yaw;
  camera.pitch = ws.camera.pitch;
  camera.fov = ws.camera.fov;
  status('camera default set');
};

$('#resetCamera').onclick = () => {
  const camera = ws.settings.camera_defaults;
  ws.camera = {
    position: [...camera.position],
    yaw: camera.yaw,
    pitch: camera.pitch,
    fov: camera.fov,
  };
  syncSettings();
  status('camera reset');
};

ensureCatalog();
syncCatalog();
syncSettings();
render();
fetch('/api/health')
  .then(response => response.json())
  .then(payload => status(payload.ok ? 'server connected' : 'server error'))
  .catch(() => status('server offline'));
