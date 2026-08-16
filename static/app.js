const canvas = document.querySelector('#scene');
const gl = canvas.getContext('webgl2', { antialias: true });
if (!gl) throw new Error('WebGL2 required');

const $ = selector => {
  const element = document.querySelector(selector);
  if (!element) throw new Error(`required DOM element missing: ${selector}`);
  return element;
};
const status = text => { $('#status').textContent = text; };

const V = {
  add: (a, b) => a.map((value, index) => value + b[index]),
  sub: (a, b) => a.map((value, index) => value - b[index]),
  mul: (a, scalar) => a.map(value => value * scalar),
  dot: (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0),
  cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
  length: value => Math.hypot(...value),
  norm: value => {
    const length = Math.hypot(...value);
    if (length <= 1e-12) throw new Error('cannot normalize zero-length vector');
    return value.map(component => component / length);
  },
};

function requiredObject(parent, field, context) {
  const value = parent[field];
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error(`${context}.${field} must be an object`);
  return value;
}
function requiredArray(parent, field, context) {
  const value = parent[field];
  if (!Array.isArray(value)) throw new Error(`${context}.${field} must be an array`);
  return value;
}
function requiredNumber(parent, field, context) {
  const value = parent[field];
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${context}.${field} must be numeric`);
  return value;
}

function m4(a, b) {
  const out = new Array(16).fill(0);
  for (let column = 0; column < 4; column++) for (let row = 0; row < 4; row++) for (let k = 0; k < 4; k++) out[column * 4 + row] += a[k * 4 + row] * b[column * 4 + k];
  return out;
}
function perspective(fov, aspect, near, far) {
  const scale = 1 / Math.tan(fov * Math.PI / 360);
  return [scale / aspect, 0, 0, 0, 0, scale, 0, 0, 0, 0, (far + near) / (near - far), -1, 0, 0, 2 * far * near / (near - far), 0];
}
function lookAt(position, target) {
  const z = V.norm(V.sub(position, target));
  let x = V.cross([0, 1, 0], z);
  x = V.length(x) < 1e-6 ? [1, 0, 0] : V.norm(x);
  const y = V.cross(z, x);
  return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -V.dot(x, position), -V.dot(y, position), -V.dot(z, position), 1];
}
function model(position, scale) {
  return [scale[0], 0, 0, 0, 0, scale[1], 0, 0, 0, 0, scale[2], 0, position[0], position[1], position[2], 1];
}
function project(point, matrix) {
  const [x, y, z] = point;
  const clipX = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12];
  const clipY = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13];
  const clipW = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15];
  if (clipW <= 0) return null;
  return [(clipX / clipW * .5 + .5) * canvas.width, (-clipY / clipW * .5 + .5) * canvas.height, clipW];
}

const vertexShader = `#version 300 es
in vec3 p; uniform mat4 mvp; uniform vec3 color; out vec3 c;
void main(){ c=color; gl_Position=mvp*vec4(p,1.0); }`;
const fragmentShader = `#version 300 es
precision highp float; in vec3 c; out vec4 o;
void main(){ o=vec4(c,1.0); }`;
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
const loc = { position: gl.getAttribLocation(program, 'p'), mvp: gl.getUniformLocation(program, 'mvp'), color: gl.getUniformLocation(program, 'color') };

const cubeVertices = new Float32Array([-1,-1,-1, 1,-1,-1, 1,1,-1, -1,1,-1, -1,-1,1, 1,-1,1, 1,1,1, -1,1,1]);
const cubeFaces = new Uint16Array([
  0,2,1, 0,3,2, 4,5,6, 4,6,7,
  0,4,7, 0,7,3, 1,2,6, 1,6,5,
  0,1,5, 0,5,4, 3,7,6, 3,6,2,
]);
const cubeEdges = new Uint16Array([0,1,1,2,2,3,3,0,4,5,5,6,6,7,7,4,0,4,1,5,2,6,3,7]);
const vertexBuffer = gl.createBuffer();
const faceBuffer = gl.createBuffer();
const edgeBuffer = gl.createBuffer();
const lineBuffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
gl.bufferData(gl.ARRAY_BUFFER, cubeVertices, gl.STATIC_DRAW);
gl.enableVertexAttribArray(loc.position);
gl.vertexAttribPointer(loc.position, 3, gl.FLOAT, false, 0, 0);
gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, faceBuffer); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, cubeFaces, gl.STATIC_DRAW);
gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, edgeBuffer); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, cubeEdges, gl.STATIC_DRAW);

let ws = null;
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

function assertWorkspace() {
  if (!ws) throw new Error('workspace is not loaded');
  requiredArray(ws, 'entities', 'workspace');
  requiredArray(ws, 'rulesets', 'workspace');
  requiredArray(ws, 'color_spaces', 'workspace');
  requiredObject(ws, 'camera', 'workspace');
  requiredObject(ws, 'settings', 'workspace');
  return ws;
}
function viewSettings() { return requiredObject(assertWorkspace().settings, 'view_defaults', 'settings'); }
function cameraSettings() { return requiredObject(assertWorkspace().settings, 'camera_defaults', 'settings'); }
function linkSettings() { return requiredObject(assertWorkspace().settings, 'link_visualization', 'settings'); }
function eventSettings() { return requiredObject(assertWorkspace().settings, 'event_playback', 'settings'); }
function nodeMasterSize() { return requiredNumber(viewSettings(), 'node_master_size', 'settings.view_defaults'); }
function nodeHalfSize() { return .45 * nodeMasterSize(); }
function gridSize() { return requiredNumber(viewSettings(), 'grid_size', 'settings.view_defaults'); }
function rulesetMap() { return new Map(assertWorkspace().rulesets.map(ruleset => [ruleset.id, ruleset])); }
function colorSpaceMap() { return new Map(assertWorkspace().color_spaces.map(colorSpace => [colorSpace.id, colorSpace])); }
function linkProperties() { return assertWorkspace().entities.flatMap(owner => owner.properties.filter(property => property.property_type_ref === 'link').map(property => ({ owner, property }))); }
function canonicalIndex() {
  const index = new Map();
  for (const entity of assertWorkspace().entities) {
    index.set(entity.id, { ref: entity.id, kind: 'entity', owner: entity, object: entity });
    for (const property of entity.properties) index.set(property.id, { ref: property.id, kind: 'property', propertyType: property.property_type_ref, owner: entity, object: property });
  }
  return index;
}
function entityForCanonicalRef(ref) { return canonicalIndex().get(ref)?.owner ?? null; }

function freeForward() {
  const camera = assertWorkspace().camera;
  const cosine = Math.cos(camera.pitch);
  return [Math.sin(camera.yaw) * cosine, Math.sin(camera.pitch), -Math.cos(camera.yaw) * cosine];
}
function lookAtEntity() { return lookAtEntityId ? assertWorkspace().entities.find(entity => entity.id === lookAtEntityId) ?? null : null; }
function cameraReference() {
  const entity = lookAtEntity();
  if (entity) { assertWorkspace().camera.reference = [...entity.position]; return entity.position; }
  return assertWorkspace().camera.reference;
}
function detachLookAtReference() { assertWorkspace().camera.reference = [...cameraReference()]; lookAtEntityId = null; return assertWorkspace().camera.reference; }
function viewForward() {
  const direction = V.sub(cameraReference(), assertWorkspace().camera.position);
  if (V.length(direction) <= 1e-6) throw new Error('camera position equals reference');
  return V.norm(direction);
}
function cameraRight() {
  const value = V.cross(viewForward(), [0, 1, 0]);
  return V.length(value) <= 1e-6 ? [1, 0, 0] : V.norm(value);
}
function cameraUp() { return V.norm(V.cross(cameraRight(), viewForward())); }
function syncCameraAnglesToActive() {
  const forward = viewForward();
  assertWorkspace().camera.yaw = Math.atan2(forward[0], -forward[2]);
  assertWorkspace().camera.pitch = Math.asin(Math.max(-1, Math.min(1, forward[1])));
}
function viewProjection() {
  const camera = assertWorkspace().camera;
  const settings = cameraSettings();
  return m4(perspective(camera.fov, canvas.width / canvas.height, requiredNumber(settings, 'near_clip', 'settings.camera_defaults'), requiredNumber(settings, 'far_clip', 'settings.camera_defaults')), lookAt(camera.position, cameraReference()));
}
function worldPixelsAt(point) {
  const vp = viewProjection();
  const density = devicePixelRatio || 1;
  const origin = project(point, vp);
  const right = project(V.add(point, cameraRight()), vp);
  if (!origin || !right) return 0;
  return Math.hypot(right[0] - origin[0], right[1] - origin[1]) / density;
}

function bindCube() { gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer); gl.vertexAttribPointer(loc.position, 3, gl.FLOAT, false, 0, 0); }
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
function selectionCentroid() {
  const entities = assertWorkspace().entities.filter(entity => selected.has(entity.id));
  if (!entities.length) return null;
  return [0, 1, 2].map(axis => entities.reduce((sum, entity) => sum + entity.position[axis], 0) / entities.length);
}
function gizmoTips(center) {
  const length = 1.7 * Math.max(.75, nodeMasterSize());
  return { x: [center[0] + length, center[1], center[2]], y: [center[0], center[1] + length, center[2]], z: [center[0], center[1], center[2] + length] };
}
function drawGizmo() {
  const center = selectionCentroid();
  for (const id of ['gizmoX','gizmoY','gizmoZ']) $(`#${id}`).style.display = 'none';
  if (!center) return;
  const length = 1.45 * Math.max(.75, nodeMasterSize());
  const thickness = .055 * Math.max(.8, nodeMasterSize());
  drawBox([center[0] + length/2, center[1], center[2]], [length/2, thickness, thickness], [1,.15,.15]);
  drawBox([center[0], center[1] + length/2, center[2]], [thickness, length/2, thickness], [.15,1,.15]);
  drawBox([center[0], center[1], center[2] + length/2], [thickness, thickness, length/2], [.15,.4,1]);
  for (const [axis, point] of Object.entries(gizmoTips(center))) {
    const screen = project(point, viewProjection());
    if (!screen) continue;
    const label = $(`#gizmo${axis.toUpperCase()}`);
    label.style.display = 'block'; label.style.left = `${screen[0]/(devicePixelRatio||1)-14}px`; label.style.top = `${screen[1]/(devicePixelRatio||1)-7}px`;
  }
}
function drawGrid() {
  if (!viewSettings().grid_visible) return;
  const spacing = gridSize();
  const half = 30;
  for (let i = -Math.floor(half/spacing); i <= Math.floor(half/spacing); i++) {
    const v = i * spacing; const color = i % 5 === 0 ? [.16,.19,.24] : [.09,.11,.14];
    drawLine([-half,0,v],[half,0,v],color); drawLine([v,0,-half],[v,0,half],color);
  }
}
function render() {
  resize();
  gl.viewport(0,0,canvas.width,canvas.height); gl.clearColor(.035,.045,.065,1); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT); gl.enable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE);
  drawGrid();
  const visible = visibleEntityIds();
  const half = nodeHalfSize();
  for (const entity of assertWorkspace().entities) {
    if (!visible.has(entity.id)) continue;
    let color = [.22,.27,.35];
    if (entity.id === hovered) color = [.31,.39,.5];
    if (selected.has(entity.id)) color = [.12,.46,.78];
    if (entity.id === linkSource) color = [.78,.42,.08];
    if (entity.id === linkTarget) color = [.58,.25,.78];
    drawBox(entity.position,[half,half,half],color);
    if (selected.has(entity.id) || entity.id === linkSource || entity.id === linkTarget) drawBox(entity.position,[half+.01*nodeMasterSize(),half+.01*nodeMasterSize(),half+.01*nodeMasterSize()],entity.id===activeEntityId?[.95,.98,1]:[.7,.9,1],true);
  }
  drawGizmo(); requestAnimationFrame(render);
}
function resize() {
  const density = devicePixelRatio || 1;
  const width = Math.floor(canvas.clientWidth*density), height = Math.floor(canvas.clientHeight*density);
  if (canvas.width !== width || canvas.height !== height) { canvas.width=width; canvas.height=height; }
}
function fitWorkspaceToView() {
  const entities = assertWorkspace().entities;
  if (!entities.length) throw new Error('fit to view requires at least one Entity');
  resize();
  if (canvas.width <= 0 || canvas.height <= 0) throw new Error('fit to view requires a non-zero viewport');

  const half = nodeHalfSize();
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (const entity of entities) {
    for (let axis = 0; axis < 3; axis++) {
      min[axis] = Math.min(min[axis], entity.position[axis] - half);
      max[axis] = Math.max(max[axis], entity.position[axis] + half);
    }
  }
  const center = [0, 1, 2].map(axis => (min[axis] + max[axis]) / 2);
  const camera = assertWorkspace().camera;
  const backward = V.norm(V.sub(camera.position, camera.reference));
  const forward = V.mul(backward, -1);
  let right = V.cross(forward, [0, 1, 0]);
  if (V.length(right) <= 1e-6) right = [1, 0, 0];
  else right = V.norm(right);
  const up = V.norm(V.cross(right, forward));
  const verticalHalfFov = camera.fov * Math.PI / 360;
  const horizontalHalfFov = Math.atan(Math.tan(verticalHalfFov) * (canvas.width / canvas.height));
  const tanVertical = Math.tan(verticalHalfFov);
  const tanHorizontal = Math.tan(horizontalHalfFov);
  if (tanVertical <= 0 || tanHorizontal <= 0) throw new Error('fit to view requires a valid camera FOV');

  let distance = 0;
  let nearestOffset = -Infinity;
  let farthestOffset = Infinity;
  for (const x of [min[0], max[0]]) for (const y of [min[1], max[1]]) for (const z of [min[2], max[2]]) {
    const offset = V.sub([x, y, z], center);
    const lateral = Math.abs(V.dot(offset, right));
    const vertical = Math.abs(V.dot(offset, up));
    const towardCamera = V.dot(offset, backward);
    distance = Math.max(distance, towardCamera + lateral / tanHorizontal, towardCamera + vertical / tanVertical);
    nearestOffset = Math.max(nearestOffset, towardCamera);
    farthestOffset = Math.min(farthestOffset, towardCamera);
  }

  const padding = 1.18;
  const nearClip = requiredNumber(cameraSettings(), 'near_clip', 'settings.camera_defaults');
  const farClip = requiredNumber(cameraSettings(), 'far_clip', 'settings.camera_defaults');
  distance = Math.max(distance * padding, nearestOffset + nearClip * 2);
  if (distance - farthestOffset >= farClip) throw new Error('fit to view exceeds camera far_clip');

  lookAtEntityId = null;
  camera.reference = center;
  camera.position = V.add(center, V.mul(backward, distance));
  syncCameraAnglesToActive();
}
function entityScreenBounds(entity, vp) {
  const scale=nodeHalfSize(), points=[];
  for (const x of [-scale,scale]) for (const y of [-scale,scale]) for (const z of [-scale,scale]) { const p=project([entity.position[0]+x,entity.position[1]+y,entity.position[2]+z],vp); if(p) points.push(p); }
  if(!points.length) return null;
  return {minX:Math.min(...points.map(p=>p[0])),maxX:Math.max(...points.map(p=>p[0])),minY:Math.min(...points.map(p=>p[1])),maxY:Math.max(...points.map(p=>p[1])),depth:Math.min(...points.map(p=>p[2]))};
}
function pickEntity(clientX, clientY) {
  const density=devicePixelRatio||1, x=clientX*density, y=clientY*density, vp=viewProjection(), visible=visibleEntityIds();
  let winner=null,best=Infinity;
  for(const entity of assertWorkspace().entities){ if(!visible.has(entity.id))continue; const b=entityScreenBounds(entity,vp); if(b&&x>=b.minX-4*density&&x<=b.maxX+4*density&&y>=b.minY-4*density&&y<=b.maxY+4*density&&b.depth<best){winner=entity;best=b.depth;} }
  return winner;
}
function gizmoAxisHit(clientX, clientY) {
  const center=selectionCentroid(); if(!center)return null;
  const density=devicePixelRatio||1,x=clientX*density,y=clientY*density,origin=project(center,viewProjection()); if(!origin)return null;
  let winner=null,best=22*density;
  for(const [axis,point] of Object.entries(gizmoTips(center))){const screen=project(point,viewProjection());if(!screen)continue;const vx=screen[0]-origin[0],vy=screen[1]-origin[1],wx=x-origin[0],wy=y-origin[1],den=vx*vx+vy*vy;if(den<1e-8)continue;const t=Math.max(0,Math.min(1,(wx*vx+wy*vy)/den)),d=Math.hypot(x-(origin[0]+vx*t),y-(origin[1]+vy*t));if(d<best){best=d;winner=axis;}}
  return winner;
}

function setActiveEntity(id){activeEntityId=id&&selected.has(id)?id:null;}
function normalizeActiveSelection(){if(activeEntityId&&selected.has(activeEntityId))return;const remaining=[...selected];activeEntityId=remaining.length?remaining.at(-1):null;}
function inspect(){
  const entities=assertWorkspace().entities.filter(entity=>selected.has(entity.id));
  if(!entities.length) $('#selection').innerHTML='No selection';
  else {
    let html=`<div class="selection-count">${entities.length} selected</div><div class="selected-list">${entities.map(entity=>`<code>${entity.id===activeEntityId?'● ':''}${entity.id}</code>`).join('')}</div>`;
    if(entities.length===1){const entity=entities[0];for(const {property} of linkProperties().filter(({property})=>entityForCanonicalRef(property.value.parent_ref)?.id===entity.id||entityForCanonicalRef(property.value.child_ref)?.id===entity.id)){const ruleset=rulesetMap().get(property.ruleset_ref);if(!ruleset)throw new Error(`Ruleset unresolved: ${property.ruleset_ref}`);html+=`<div class="link-row"><span></span><span>${ruleset.name}: <code>${property.value.parent_ref} → ${property.value.child_ref}</code></span></div>`;}}
    $('#selection').innerHTML=html;
  }
  renderEntityEditor(); renderEventRuleSection();
}
function updateButtons(){ $('#addLink').disabled=selected.size!==1; $('#addEvent').disabled=selected.size!==1; $('#deleteEntity').disabled=selected.size===0; }
function nextId(prefix){const used=new Set([...assertWorkspace().entities.map(e=>e.id),...assertWorkspace().entities.flatMap(e=>e.properties.map(p=>p.id))]);let i=1,id;do{id=`${prefix}_${String(i++).padStart(4,'0')}`;}while(used.has(id));return id;}

function openLinkTypePopup(){ $('#linkEndpoints').textContent=`${linkSource} → ${linkTarget}`; const rulesets=assertWorkspace().rulesets.filter(r=>r.property_type_ref==='link'); $('#linkTypeButtons').innerHTML=rulesets.map(r=>`<button data-ruleset="${r.id}">${r.name}</button>`).join(''); $('#linkTypePopup').hidden=false; $('#linkTypeButtons').querySelectorAll('button').forEach(button=>button.onclick=()=>createLink(button.dataset.ruleset)); }
function clearLink(){linkSource=null;linkTarget=null;$('#linkTypePopup').hidden=true;status('ready');}
function createLink(rulesetRef){const ruleset=rulesetMap().get(rulesetRef);if(!ruleset)throw new Error(`Ruleset unresolved: ${rulesetRef}`);const source=assertWorkspace().entities.find(e=>e.id===linkSource);if(!source)throw new Error(`Link source unresolved: ${linkSource}`);if(!linkTarget)throw new Error('Link target is required');source.properties.push({id:nextId('LINK'),property_type_ref:'link',ruleset_ref:ruleset.id,status:'unlocked',value:{link_type_ref:ruleset.link_type_ref,parent_ref:linkTarget,child_ref:linkSource,properties:{}}});status(`created ${ruleset.name}: ${linkSource} → ${linkTarget}`);clearLink();inspect();}

function beginOrbit(clientX,clientY){const target=cameraReference(),offset=V.sub(assertWorkspace().camera.position,target),radius=V.length(offset);if(radius<.25)throw new Error('camera orbit radius is too small');orbit={radius,azimuth:Math.atan2(offset[0],offset[2]),elevation:Math.asin(Math.max(-1,Math.min(1,offset[1]/radius)))};last=[clientX,clientY];}
function updateOrbit(clientX,clientY){const sensitivity=requiredNumber(cameraSettings(),'mouse_sensitivity','settings.camera_defaults'),dx=clientX-last[0],dy=clientY-last[1];last=[clientX,clientY];const target=cameraReference();orbit.azimuth-=dx*sensitivity;orbit.elevation=Math.max(-1.52,Math.min(1.52,orbit.elevation+dy*sensitivity));const horizontal=Math.cos(orbit.elevation)*orbit.radius;assertWorkspace().camera.position=[target[0]+Math.sin(orbit.azimuth)*horizontal,target[1]+Math.sin(orbit.elevation)*orbit.radius,target[2]+Math.cos(orbit.azimuth)*horizontal];syncCameraAnglesToActive();}
function beginAxisDrag(axis,clientX,clientY){const center=selectionCentroid();if(!center)throw new Error('axis drag requires selection');const vector=axis==='x'?[1,0,0]:axis==='y'?[0,1,0]:[0,0,1],origin=project(center,viewProjection()),tip=project(V.add(center,vector),viewProjection());if(!origin||!tip)throw new Error(`axis ${axis} cannot be projected`);const density=devicePixelRatio||1,dx=(tip[0]-origin[0])/density,dy=(tip[1]-origin[1])/density,pixels=Math.hypot(dx,dy);if(pixels<2){status(`axis ${axis.toUpperCase()} is nearly point-on; rotate camera to drag`);return;}dragAxis={axisIndex:{x:0,y:1,z:2}[axis],total:0,screenDirection:[dx/pixels,dy/pixels],worldPerPixel:1/pixels,startPositions:new Map(assertWorkspace().entities.filter(e=>selected.has(e.id)).map(e=>[e.id,[...e.position]]))};last=[clientX,clientY];}

canvas.oncontextmenu=event=>event.preventDefault();
canvas.ondblclick=event=>{if(event.button!==0)return;const entity=pickEntity(event.clientX,event.clientY);if(!entity)return;lookAtEntityId=entity.id;assertWorkspace().camera.reference=[...entity.position];syncCameraAnglesToActive();status(`lookAt: ${entity.id}`);};
canvas.onwheel=event=>{event.preventDefault();const step=Math.sign(event.deltaY)*requiredNumber(cameraSettings(),'wheel_zoom_speed','settings.camera_defaults'),target=cameraReference(),offset=V.sub(assertWorkspace().camera.position,target),distance=V.length(offset);if(distance<=1e-6)throw new Error('camera cannot zoom from its reference point');assertWorkspace().camera.position=V.add(target,V.mul(V.norm(offset),Math.max(.25,distance+step)));syncCameraAnglesToActive();};
canvas.onmousedown=event=>{if(event.button===2){beginOrbit(event.clientX,event.clientY);return;}if(event.button!==0)return;const axis=gizmoAxisHit(event.clientX,event.clientY);if(axis&&selected.size){if(lookAtEntityId&&selected.has(lookAtEntityId))detachLookAtReference();beginAxisDrag(axis,event.clientX,event.clientY);return;}const entity=pickEntity(event.clientX,event.clientY);if(linkSource){if(entity&&entity.id!==linkSource){linkTarget=entity.id;openLinkTypePopup();return;}if(!entity){pan={x:event.clientX,y:event.clientY,moved:false};last=[event.clientX,event.clientY];}return;}if(!entity){pan={x:event.clientX,y:event.clientY,moved:false};last=[event.clientX,event.clientY];return;}if(event.ctrlKey||event.shiftKey){if(selected.has(entity.id)){selected.delete(entity.id);normalizeActiveSelection();}else{selected.add(entity.id);setActiveEntity(entity.id);}}else{selected=new Set([entity.id]);setActiveEntity(entity.id);}inspect();updateButtons();};
window.onmouseup=event=>{orbit=null;dragAxis=null;if(pan){const click=!pan.moved;pan=null;if(click&&event.button===0&&!event.ctrlKey&&!event.shiftKey&&!linkSource){selected.clear();activeEntityId=null;inspect();updateButtons();}}};
window.onmousemove=event=>{if(orbit){updateOrbit(event.clientX,event.clientY);hovered=null;return;}if(pan){const dx=event.clientX-last[0],dy=event.clientY-last[1],total=Math.abs(event.clientX-pan.x)+Math.abs(event.clientY-pan.y);if(!pan.moved&&total>2){pan.moved=true;detachLookAtReference();}if(pan.moved){const speed=requiredNumber(cameraSettings(),'drag_pan_speed','settings.camera_defaults'),delta=V.add(V.mul(cameraRight(),-dx*speed),V.mul(cameraUp(),dy*speed));assertWorkspace().camera.reference=V.add(cameraReference(),delta);assertWorkspace().camera.position=V.add(assertWorkspace().camera.position,delta);syncCameraAnglesToActive();}last=[event.clientX,event.clientY];hovered=null;return;}if(dragAxis&&selected.size){const dx=event.clientX-last[0],dy=event.clientY-last[1],screenDelta=dx*dragAxis.screenDirection[0]+dy*dragAxis.screenDirection[1];dragAxis.total+=screenDelta*dragAxis.worldPerPixel;const spacing=gridSize();for(const entity of assertWorkspace().entities){const start=dragAxis.startPositions.get(entity.id);if(!start)continue;const raw=start[dragAxis.axisIndex]+dragAxis.total;entity.position[dragAxis.axisIndex]=viewSettings().snap_to_grid?Math.round(raw/spacing)*spacing:raw;}last=[event.clientX,event.clientY];inspect();return;}hovered=pickEntity(event.clientX,event.clientY)?.id??null;};
window.onkeydown=event=>keys.add(event.key.toLowerCase()); window.onkeyup=event=>keys.delete(event.key.toLowerCase());
let previousFrame=performance.now();
function tick(time){const dt=Math.min(.05,(time-previousFrame)/1000);previousFrame=time;if(ws){const speed=requiredNumber(cameraSettings(),'movement_speed','settings.camera_defaults')*dt,forward=viewForward(),right=cameraRight();let moved=false;if(keys.has('w')){assertWorkspace().camera.position=V.add(assertWorkspace().camera.position,V.mul(forward,speed));moved=true;}if(keys.has('s')){assertWorkspace().camera.position=V.sub(assertWorkspace().camera.position,V.mul(forward,speed));moved=true;}if(keys.has('a')){assertWorkspace().camera.position=V.sub(assertWorkspace().camera.position,V.mul(right,speed));moved=true;}if(keys.has('d')){assertWorkspace().camera.position=V.add(assertWorkspace().camera.position,V.mul(right,speed));moved=true;}if(keys.has('q')){assertWorkspace().camera.position[1]-=speed;moved=true;}if(keys.has('e')){assertWorkspace().camera.position[1]+=speed;moved=true;}if(moved)syncCameraAnglesToActive();}requestAnimationFrame(tick);}

function openEntityCreatePopup(){$('#newEntityName').value='';$('#entityCreatePopup').hidden=false;$('#newEntityName').focus();}
function createEntityFromPopup(){const name=$('#newEntityName').value.trim();if(!name){status('Entity name is required');return;}let i=1,id;const used=new Set(assertWorkspace().entities.map(e=>e.id));do{id=`ENTITY_${String(i++).padStart(3,'0')}`;}while(used.has(id));const position=V.add(assertWorkspace().camera.position,V.mul(viewForward(),5));if(viewSettings().snap_to_grid)for(let axis=0;axis<3;axis++)position[axis]=Math.round(position[axis]/gridSize())*gridSize();assertWorkspace().entities.push({id,name,status:'unlocked',position,properties:[]});$('#entityCreatePopup').hidden=true;selected=new Set([id]);setActiveEntity(id);inspect();updateButtons();status(`created ${name}`);}
function deleteSelectedEntities(){const removed=new Set(selected),canonical=new Set();for(const entity of assertWorkspace().entities){if(!removed.has(entity.id))continue;canonical.add(entity.id);for(const property of entity.properties)canonical.add(property.id);}if(lookAtEntityId&&removed.has(lookAtEntityId))detachLookAtReference();assertWorkspace().entities=assertWorkspace().entities.filter(e=>!removed.has(e.id));for(const entity of assertWorkspace().entities)entity.properties=entity.properties.filter(property=>property.property_type_ref!=='link'||(!canonical.has(property.value.parent_ref)&&!canonical.has(property.value.child_ref)));selected.clear();activeEntityId=null;inspect();updateButtons();status(`deleted ${removed.size} entities`);}

function syncCatalog(){const rulesets=assertWorkspace().rulesets.filter(r=>r.property_type_ref==='link');$('#rulesetView').innerHTML=['<option value="ALL">All Link Rulesets</option>',...rulesets.map(r=>`<option value="${r.id}">${r.name}</option>`)].join('');$('#rulesetView').value=viewSettings().ruleset_ref;}
function syncSettings(){const camera=cameraSettings(),links=linkSettings(),events=eventSettings(),view=viewSettings();$('#fov').value=assertWorkspace().camera.fov;$('#fovValue').value=`${Math.round(assertWorkspace().camera.fov)}°`;$('#moveSpeed').value=camera.movement_speed;$('#mouseSensitivity').value=camera.mouse_sensitivity;$('#wheelZoomSpeed').value=camera.wheel_zoom_speed;$('#dragPanSpeed').value=camera.drag_pan_speed;$('#anchorSpacing').value=links.anchor_spacing;$('#anchorOffset').value=links.anchor_offset;$('#baseLinkSpeed').value=links.base_flow_speed;$('#activeLinkSpeed').value=events.active_link_speed;$('#effectTravel').value=events.effect_travel_duration;$('#nodeMasterSize').value=view.node_master_size;$('#nodeMasterSizeValue').textContent=`${Number(view.node_master_size).toFixed(2)}×`;$('#gridToggle').checked=view.grid_visible;$('#snapToggle').checked=view.snap_to_grid;for(const id of ['gridToggle','snapToggle'])$(`#${id}`).closest('.view-toggle').classList.toggle('active',$(`#${id}`).checked);}
async function fetchJson(url,options){const response=await fetch(url,options);const payload=await response.json();if(!payload.ok)throw new Error(payload.error);return payload;}
async function loadStartingScene(){ws=(await fetchJson('/api/starting-scene')).workspace;assertWorkspace();selected.clear();activeEntityId=null;lookAtEntityId=null;clearLink();fitWorkspaceToView();syncCatalog();syncSettings();renderProjectionControls();syncEventRouteVisibility();inspect();updateButtons();status('starter scene loaded · fit to view');}
async function saveWorkspace(){ws=(await fetchJson('/api/workspace',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(assertWorkspace())})).workspace;assertWorkspace();syncCatalog();syncSettings();inspect();status('saved');}
async function loadWorkspace(){ws=(await fetchJson('/api/workspace')).workspace;assertWorkspace();lookAtEntityId=null;selected.clear();activeEntityId=null;clearLink();syncCatalog();syncSettings();renderProjectionControls();syncEventRouteVisibility();inspect();updateButtons();status('loaded');}
function reportUiError(error){window.reportStructureError(error,{type:'ui_action_error'});status(`error: ${error.message}`);}

function bindUi(){
  $('#addEntity').onclick=openEntityCreatePopup; $('#createEntity').onclick=createEntityFromPopup; $('#cancelEntityCreate').onclick=()=>{$('#entityCreatePopup').hidden=true;}; $('#deleteEntity').onclick=deleteSelectedEntities;
  $('#addLink').onclick=()=>{if(selected.size===1){linkSource=[...selected][0];linkTarget=null;status(`select link target for ${linkSource}`);}}; $('#cancelLink').onclick=clearLink;
  $('#addEvent').onclick=()=>{if(selected.size===1){$('#eventType').value='event';$('#eventPopup').hidden=false;}}; $('#cancelEvent').onclick=()=>{$('#eventPopup').hidden=true;}; $('#createEvent').onclick=()=>{if(selected.size!==1)return;const entity=assertWorkspace().entities.find(item=>selected.has(item.id)),type=$('#eventType').value.trim();if(!entity||!type){status('Event type is required');return;}entity.properties.push({id:nextId('EVENT'),property_type_ref:'event',ruleset_ref:'RULESET_EVENT',status:'unlocked',value:{event_type_ref:type,properties:{}}});$('#eventPopup').hidden=true;status(`created Event on ${entity.id}`);inspect();};
  $('#rulesetView').onchange=event=>{viewSettings().ruleset_ref=event.target.value;selected.clear();activeEntityId=null;clearLink();inspect();updateButtons();renderProjectionControls();};
  $('#save').onclick=()=>saveWorkspace().catch(reportUiError); $('#load').onclick=()=>loadWorkspace().catch(reportUiError); $('#settingsButton').onclick=()=>{$('#settings').hidden=!$('#settings').hidden;};
  $('#publishAbstraction').onclick=openPublishAbstraction; $('#mountAbstraction').onclick=()=>openMountAbstraction().catch(reportUiError);
  $('#fov').oninput=event=>{assertWorkspace().camera.fov=Number(event.target.value);$('#fovValue').value=`${event.target.value}°`;}; $('#moveSpeed').onchange=event=>{cameraSettings().movement_speed=Number(event.target.value);}; $('#mouseSensitivity').onchange=event=>{cameraSettings().mouse_sensitivity=Number(event.target.value);}; $('#wheelZoomSpeed').onchange=event=>{cameraSettings().wheel_zoom_speed=Number(event.target.value);}; $('#dragPanSpeed').onchange=event=>{cameraSettings().drag_pan_speed=Number(event.target.value);};
  $('#anchorSpacing').onchange=event=>{linkSettings().anchor_spacing=Number(event.target.value);}; $('#anchorOffset').onchange=event=>{linkSettings().anchor_offset=Number(event.target.value);}; $('#baseLinkSpeed').onchange=event=>{linkSettings().base_flow_speed=Number(event.target.value);}; $('#activeLinkSpeed').onchange=event=>{eventSettings().active_link_speed=Number(event.target.value);}; $('#effectTravel').onchange=event=>{eventSettings().effect_travel_duration=Number(event.target.value);}; $('#nodeMasterSize').oninput=event=>{viewSettings().node_master_size=Number(event.target.value);$('#nodeMasterSizeValue').textContent=`${Number(event.target.value).toFixed(2)}×`;}; $('#gridToggle').onchange=event=>{viewSettings().grid_visible=event.target.checked;syncSettings();}; $('#snapToggle').onchange=event=>{viewSettings().snap_to_grid=event.target.checked;syncSettings();};
  $('#setCameraDefault').onclick=()=>{const camera=cameraSettings();camera.position=[...assertWorkspace().camera.position];camera.reference=[...cameraReference()];camera.yaw=assertWorkspace().camera.yaw;camera.pitch=assertWorkspace().camera.pitch;camera.fov=assertWorkspace().camera.fov;status('camera default set');}; $('#resetCamera').onclick=()=>{const camera=cameraSettings();lookAtEntityId=null;assertWorkspace().camera={position:[...camera.position],reference:[...camera.reference],yaw:camera.yaw,pitch:camera.pitch,fov:camera.fov};syncCameraAnglesToActive();syncSettings();status('camera reset');};
}

window.addEventListener('load',async()=>{try{bindUi();await loadStartingScene();render();requestAnimationFrame(tick);}catch(error){reportUiError(error);}});