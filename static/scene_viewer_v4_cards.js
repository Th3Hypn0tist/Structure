'use strict';

const SP_originalBuildAtlas = Renderer.prototype.buildAtlas;
const SP_originalBuild = Renderer.prototype.build;
const SP_originalRenderInstances = renderInstances;
const SP_originalLoadScene = loadScene;
let SP_defaultRootsApplied = false;

styleDefaults = function(){ return {even:'#AAB2C2', odd:'#087CFF', title:'#0B356B'}; };

function spNodeRecord(key) {
  const split = key.lastIndexOf('::');
  if (split < 0) return null;
  const objectId = key.slice(0, split);
  const nodeId = key.slice(split + 2);
  const obj = (S.scene?.objects || []).find(o => o.id === objectId);
  const node = (obj?.nodes || []).find(n => String(n.id) === nodeId);
  if (!obj || !node) return null;
  let incoming = 0;
  let outgoing = 0;
  const byChannel = {};
  for (const connection of S.scene?.connections || []) {
    const fromMatch = connection.from?.object === objectId && String(connection.from?.node) === nodeId;
    const toMatch = connection.to?.object === objectId && String(connection.to?.node) === nodeId;
    if (!fromMatch && !toMatch) continue;
    if (fromMatch) outgoing += 1;
    if (toMatch) incoming += 1;
    const channel = String(connection.channel || 'semantic');
    byChannel[channel] = (byChannel[channel] || 0) + 1;
  }
  return {obj, node, incoming, outgoing, byChannel};
}

function spFit(ctx, text, maxWidth) {
  let value = String(text || '');
  if (ctx.measureText(value).width <= maxWidth) return value;
  while (value.length > 1 && ctx.measureText(value + '…').width > maxWidth) value = value.slice(0, -1);
  return value + '…';
}

Renderer.prototype.buildAtlas = function(records) {
  const g = this.gl;
  const max = g.getParameter(g.MAX_TEXTURE_SIZE) || 4096;
  const cellW = 320;
  const cellH = 128;
  const cols = Math.max(1, Math.min(4, Math.floor(max / cellW)));
  const rowsMax = Math.max(1, Math.floor(max / cellH));
  const used = records.slice(0, Math.min(S.limits.labels, cols * rowsMax));
  const rows = Math.max(1, Math.ceil(Math.max(1, used.length) / cols));
  const canvas = document.createElement('canvas');
  canvas.width = cols * cellW;
  canvas.height = rows * cellH;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = '#fff';
  this.labelUV.clear();

  used.forEach((record, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = col * cellW;
    const y = row * cellH;
    const info = spNodeRecord(record.key);
    const props = info?.node?.properties || {};
    const pad = 14;
    const maxW = cellW - pad * 2;
    ctx.font = '700 25px Arial, sans-serif';
    ctx.fillText(spFit(ctx, props.name || record.text || info?.node?.id || '', maxW), x + pad, y + 25);
    const type = props.type || '—';
    const status = props.status || '—';
    ctx.font = '600 14px Arial, sans-serif';
    ctx.globalAlpha = .95;
    ctx.fillText(spFit(ctx, `${type} · ${status}`, maxW), x + pad, y + 55);
    const role = props.source_role || props.kind || '—';
    ctx.font = '500 13px Arial, sans-serif';
    ctx.globalAlpha = .82;
    ctx.fillText(spFit(ctx, role, maxW), x + pad, y + 78);
    const incoming = info?.incoming || 0;
    const outgoing = info?.outgoing || 0;
    const total = incoming + outgoing;
    const channelSummary = Object.entries(info?.byChannel || {})
      .sort((a,b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 2)
      .map(([channel,count]) => `${channel}:${count}`)
      .join('  ');
    ctx.font = '600 12px ui-monospace, monospace';
    ctx.globalAlpha = .92;
    ctx.fillText(spFit(ctx, `OUT ${outgoing}  IN ${incoming}  LINKS ${total}${channelSummary ? '  ' + channelSummary : ''}`, maxW), x + pad, y + 104);
    ctx.globalAlpha = 1;
    this.labelUV.set(record.key, {
      u0: x / canvas.width,
      v0: 1 - (y + cellH) / canvas.height,
      u1: (x + cellW) / canvas.width,
      v1: 1 - y / canvas.height,
    });
  });

  g.bindTexture(g.TEXTURE_2D, this.labelTexture);
  g.texImage2D(g.TEXTURE_2D, 0, g.RGBA, g.RGBA, g.UNSIGNED_BYTE, canvas);
  g.texParameteri(g.TEXTURE_2D, g.TEXTURE_MIN_FILTER, g.LINEAR);
  g.texParameteri(g.TEXTURE_2D, g.TEXTURE_MAG_FILTER, g.LINEAR);
  g.texParameteri(g.TEXTURE_2D, g.TEXTURE_WRAP_S, g.CLAMP_TO_EDGE);
  g.texParameteri(g.TEXTURE_2D, g.TEXTURE_WRAP_T, g.CLAMP_TO_EDGE);
};

function spNormalizeVector(v, fallback={x:0,y:-1,z:0}) {
  const x=Number(v?.x), y=Number(v?.y), z=Number(v?.z);
  const length=Math.hypot(x,y,z);
  if (!Number.isFinite(length) || length < 1e-6) return {...fallback};
  return {x:x/length,y:y/length,z:z/length};
}
function spCross(a,b){return{x:a.y*b.z-a.z*b.y,y:a.z*b.x-a.x*b.z,z:a.x*b.y-a.y*b.x}}
function spDot(a,b){return a.x*b.x+a.y*b.y+a.z*b.z}
function spBasisForChildDirection(direction) {
  const down=spNormalizeVector(direction);
  const worldY={x:0,y:1,z:0}, worldZ={x:0,y:0,z:1};
  const ref=Math.abs(spDot(down,worldY))>.95?worldZ:worldY;
  const right=spNormalizeVector(spCross(ref,down),{x:1,y:0,z:0});
  const forward=spNormalizeVector(spCross(down,right),{x:0,y:0,z:1});
  return {right,down,forward};
}

function spRecursive3DPositions(obj, state) {
  const nodes = obj.nodes || [];
  const byId = new Map(nodes.map(node => [String(node.id), node]));
  const children = new Map();
  const roots = [];
  for (const node of nodes) {
    const id = String(node.id);
    const parent = node.properties?.projection_parent_id;
    const parentId = parent == null ? null : String(parent);
    if (parentId && byId.has(parentId)) {
      if (!children.has(parentId)) children.set(parentId, []);
      children.get(parentId).push(id);
    } else {
      roots.push(id);
    }
  }
  for (const list of children.values()) list.sort();

  const p = state.projection;
  const basis = spBasisForChildDirection(p.child_direction || {x:0,y:-1,z:0});
  const childGap = 300 * Math.max(.05, Number(p.spread_y)||1);
  const siblingGapX = 210 * Math.max(.05, Number(p.spread_x)||1);
  const siblingGapZ = 210 * Math.max(.05, Number(p.spread_z)||1);
  const positions = new Map();

  for (const rootId of roots.sort()) {
    const node = byId.get(rootId);
    const src = node?.transform?.position || {};
    positions.set(rootId, {
      x:(Number(src.x)||0) * Math.max(.05, Number(p.spread_x)||1),
      y:(Number(src.y)||0) * Math.max(.05, Number(p.spread_y)||1),
      z:(Number(src.z)||0) * Math.max(.05, Number(p.spread_z)||1),
    });
    const queue=[rootId];
    while(queue.length){
      const parentId=queue.shift();
      const parentPos=positions.get(parentId);
      const childIds=children.get(parentId)||[];
      if(!parentPos||!childIds.length)continue;
      const cols=Math.max(1,Math.ceil(Math.sqrt(childIds.length)));
      const rows=Math.max(1,Math.ceil(childIds.length/cols));
      childIds.forEach((childId,index)=>{
        const row=Math.floor(index/cols), col=index%cols;
        const ox=(col-(cols-1)/2)*siblingGapX;
        const oz=(row-(rows-1)/2)*siblingGapZ;
        positions.set(childId,{
          x:parentPos.x+basis.down.x*childGap+basis.right.x*ox+basis.forward.x*oz,
          y:parentPos.y+basis.down.y*childGap+basis.right.y*ox+basis.forward.y*oz,
          z:parentPos.z+basis.down.z*childGap+basis.right.z*ox+basis.forward.z*oz,
        });
        queue.push(childId);
      });
    }
  }

  for(const node of nodes){
    const id=String(node.id);
    if(positions.has(id))continue;
    const src=node?.transform?.position||{};
    positions.set(id,{
      x:(Number(src.x)||0)*Math.max(.05,Number(p.spread_x)||1),
      y:(Number(src.y)||0)*Math.max(.05,Number(p.spread_y)||1),
      z:(Number(src.z)||0)*Math.max(.05,Number(p.spread_z)||1),
    });
  }
  return positions;
}

Renderer.prototype.build = function(scene) {
  const restores=[];
  try {
    for (const obj of scene?.objects || []) {
      const inst=S.instances.find(i=>i.id===obj.instance_id);
      if (!inst || inst.projection_dimension!=='3d') continue;
      const state=ensureLocalState(inst,obj), p=state.projection;
      const positions=spRecursive3DPositions(obj,state);
      const oldSpread={x:p.spread_x,y:p.spread_y,z:p.spread_z};
      p.spread_x=p.spread_y=p.spread_z=1;
      restores.push(()=>{p.spread_x=oldSpread.x;p.spread_y=oldSpread.y;p.spread_z=oldSpread.z});
      for(const node of obj.nodes||[]){
        const pos=node.transform?.position;
        const replacement=positions.get(String(node.id));
        if(!pos||!replacement)continue;
        const original={x:Number(pos.x)||0,y:Number(pos.y)||0,z:Number(pos.z)||0};
        pos.x=replacement.x;pos.y=replacement.y;pos.z=replacement.z;
        restores.push(()=>{pos.x=original.x;pos.y=original.y;pos.z=original.z});
      }
    }
    SP_originalBuild.call(this, scene);
  } finally {
    for (let i=restores.length-1;i>=0;i--) restores[i]();
  }
  for (const item of this.strips || []) item.matrix = m4mul(item.matrix, m4scale(1, 2.35, 1));
  for (const item of this.labels || []) item.matrix = m4mul(item.matrix, m4scale(1, 2.35, 1));
  this.upload();
};

function spStyle(inst) {
  return (S.catalog?.styles || []).find(style => style.id === inst.projection_style) || null;
}
function spNormalizeDimension(inst) {
  const style = spStyle(inst);
  const dimensions = style?.dimensions || ['2d'];
  if (!dimensions.includes(inst.projection_dimension)) {
    inst.projection_dimension = dimensions.includes('2d') ? '2d' : dimensions[0];
  }
  return dimensions;
}
styleOptions = function(selected) {
  return (S.catalog?.styles || []).map(style => `<option value="${esc(style.id)}" ${style.id===selected?'selected':''}>${esc(style.label)}</option>`).join('');
};
function spDimensionOptions(inst) {
  const dimensions = spNormalizeDimension(inst);
  return ['2d','3d'].map(dimension => {
    const available = dimensions.includes(dimension);
    return `<option value="${dimension}" ${inst.projection_dimension===dimension?'selected':''} ${available?'':'disabled'}>${dimension.toUpperCase()}</option>`;
  }).join('');
}

newInstance = function() {
  const id = `p${S.nextId++}`;
  const style = (S.catalog?.styles || []).find(item => item.id === 'atlas') || S.catalog?.styles?.[0];
  const root = (S.catalog?.topics || []).find(item => item.id === 'IAM') || (S.catalog?.topics || []).find(item => item.id !== 'all');
  const dimension = style?.dimensions?.includes('3d') ? '3d' : style?.dimensions?.[0] || '2d';
  return {id,name:`Projection ${id.slice(1)}`,projection_style:style?.id||'atlas',projection_dimension:dimension,root_topic:root?.id||'all',dependency_depth:1};
};

instancePayload = function() {
  return S.instances.map(instance => {
    spNormalizeDimension(instance);
    return {id:instance.id,name:instance.name,master:!!instance.master,projection_style:instance.projection_style,projection_dimension:instance.projection_dimension,root_topic:instance.root_topic,dependency_depth:instance.dependency_depth};
  });
};

function spDirectionFields(id, direction) {
  return ['x','y','z'].map(axis=>`<div class="field axis ${axis}"><label>${axis.toUpperCase()}</label><input type="number" step=".1" min="-1" max="1" data-child-direction="${id}" data-axis="${axis}" value="${Number(direction?.[axis] ?? (axis==='y'?-1:0)).toFixed(2)}"></div>`).join('');
}

instanceHTML = function(inst) {
  spNormalizeDimension(inst);
  const obj = (S.scene?.objects || []).find(o => o.instance_id === inst.id);
  const st = ensureLocalState(inst, obj);
  const col = S.objectStyle[inst.id];
  const p = st.projection;
  p.child_direction ||= {x:0,y:-1,z:0};
  const style = spStyle(inst);
  return `<details class="instance" open data-card="${inst.id}">
    <summary>${esc(inst.name)} · ${esc(style?.label || inst.projection_style)} · ${esc(inst.projection_dimension.toUpperCase())}</summary>
    <div class="instance-body">
      <div class="field"><label>Instance name</label><input data-instance="${inst.id}" data-key="name" value="${esc(inst.name)}"></div>
      <div class="grid3">
        <div class="field"><label>Projection style</label><select data-instance="${inst.id}" data-key="projection_style">${styleOptions(inst.projection_style)}</select></div>
        <div class="field"><label>Dimension</label><select data-instance="${inst.id}" data-key="projection_dimension">${spDimensionOptions(inst)}</select></div>
        <div class="field"><label>Root topic</label><select data-instance="${inst.id}" data-key="root_topic">${topicOptions(inst.root_topic)}</select></div>
      </div>
      <div class="field"><label>Relation depth outward (0–32)</label><input type="number" min="0" max="32" step="1" data-instance="${inst.id}" data-key="dependency_depth" value="${inst.dependency_depth}"></div>
      <div class="subhead"><span>Instance colors</span><span>generation parity</span></div>
      <div class="color-row"><label>Even generation</label><input type="color" data-color="${inst.id}" data-color-key="even" value="${col.even}"></div>
      <div class="color-row"><label>Odd generation</label><input type="color" data-color="${inst.id}" data-color-key="odd" value="${col.odd}"></div>
      <div class="color-row"><label>Title surface</label><input type="color" data-color="${inst.id}" data-color-key="title" value="${col.title}"></div>
      <div class="subhead"><span>Position</span><span>XYZ</span></div><div class="grid3">${axisFields(inst.id,'position',st.transform.position,25)}</div>
      <div class="subhead"><span>Rotation</span><span>degrees</span></div><div class="grid3">${axisFields(inst.id,'rotation',st.transform.rotation,5,-360,360)}</div>
      <div class="subhead"><span>Scale</span><span>XYZ</span></div><div class="grid3">${axisFields(inst.id,'scale',st.transform.scale,.05,.05,20)}</div>
      <div class="subhead"><span>Projection layout</span><span>local</span></div>
      ${inst.projection_dimension==='3d'?`<div class="subhead"><span>Child direction</span><span>XYZ vector</span></div><div class="grid3">${spDirectionFields(inst.id,p.child_direction)}</div>`:''}
      <div class="grid3">
        <div class="field axis x"><label>X spread</label><input type="number" step=".05" min=".05" max="20" data-proj="${inst.id}" data-proj-key="spread_x" value="${p.spread_x}"></div>
        <div class="field axis y"><label>Y spread</label><input type="number" step=".05" min=".05" max="20" data-proj="${inst.id}" data-proj-key="spread_y" value="${p.spread_y}"></div>
        <div class="field axis z"><label>Z spread</label><input type="number" step=".05" min=".05" max="20" data-proj="${inst.id}" data-proj-key="spread_z" value="${p.spread_z}"></div>
      </div>
      <div class="grid2">
        <div class="field"><label>Node size</label><input type="number" step=".05" min=".05" max="20" data-proj="${inst.id}" data-proj-key="node_scale" value="${p.node_scale}"></div>
        <div class="field"><label>Internal edge opacity</label><input type="number" step=".05" min="0" max="1" data-proj="${inst.id}" data-proj-key="edge_opacity" value="${p.edge_opacity}"></div>
      </div>
      <div class="grid2"><button data-reset="${inst.id}">Reset transform</button><button class="remove" data-remove="${inst.id}">Remove instance</button></div>
    </div>
  </details>`;
};

renderInstances = function() {
  SP_originalRenderInstances();
  $('#instances').querySelectorAll('[data-child-direction]').forEach(el=>{
    el.oninput=()=>{
      const inst=S.instances.find(x=>x.id===el.dataset.childDirection); if(!inst)return;
      const obj=(S.scene?.objects||[]).find(o=>o.instance_id===inst.id), state=ensureLocalState(inst,obj);
      const value=Number(el.value); if(!Number.isFinite(value))return;
      state.projection.child_direction ||= {x:0,y:-1,z:0};
      state.projection.child_direction[el.dataset.axis]=value;
      const d=state.projection.child_direction;
      if(Math.hypot(Number(d.x)||0,Number(d.y)||0,Number(d.z)||0)<1e-6)return;
      rebuildRenderer();
    };
  });
};

const SP_baseEnsureLocalState=ensureLocalState;
ensureLocalState=function(instance,obj){
  const state=SP_baseEnsureLocalState(instance,obj);
  state.projection.child_direction ||= {x:0,y:-1,z:0};
  if(state.projection_memory){
    for(const value of Object.values(state.projection_memory)) value.child_direction ||= {x:0,y:-1,z:0};
  }
  return state;
};

function spApplyPrimaryDefaults() {
  if (SP_defaultRootsApplied || !S.catalog) return;
  const available = new Set((S.catalog.topics || []).map(x => x.id));
  const roots = ['IAM', 'AccessCore', 'DWH'].filter(root => available.has(root));
  if (!roots.length) return;
  const style = (S.catalog.styles || []).find(item => item.id === 'atlas') || S.catalog.styles?.[0];
  const dimension = style?.dimensions?.includes('3d') ? '3d' : style?.dimensions?.[0] || '2d';
  const defaultPositions = {IAM:{x:0,y:420,z:-120},AccessCore:{x:0,y:0,z:0},DWH:{x:0,y:-420,z:120}};
  S.instances = roots.map((root, index) => ({id:`p${index+1}`,name:root,master:index===0,projection_style:style?.id||'atlas',projection_dimension:dimension,root_topic:root,dependency_depth:1}));
  for (const inst of S.instances) {
    const position = defaultPositions[inst.root_topic] || {x:0,y:0,z:0};
    S.objectState[inst.id] = {transform:{position:{...position},rotation:{x:0,y:0,z:0},scale:{x:1,y:1,z:1}},projection:{...projectionDefaults(),child_direction:{x:0,y:-1,z:0}}};
  }
  S.nextId = roots.length + 1;
  SP_defaultRootsApplied = true;
}

loadScene = async function() {
  spApplyPrimaryDefaults();
  return SP_originalLoadScene();
};
