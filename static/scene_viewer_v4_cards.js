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
  let incoming = 0, outgoing = 0;
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
  const cellW = 320, cellH = 128;
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
    const col = i % cols, row = Math.floor(i / cols);
    const x = col * cellW, y = row * cellH;
    const info = spNodeRecord(record.key);
    const props = info?.node?.properties || {};
    const pad = 14, maxW = cellW - pad * 2;
    ctx.font = '700 25px Arial, sans-serif';
    ctx.fillText(spFit(ctx, props.name || record.text || info?.node?.id || '', maxW), x + pad, y + 25);
    ctx.font = '600 14px Arial, sans-serif';
    ctx.globalAlpha = .95;
    ctx.fillText(spFit(ctx, `${props.type || '—'} · ${props.status || '—'}`, maxW), x + pad, y + 55);
    ctx.font = '500 13px Arial, sans-serif';
    ctx.globalAlpha = .82;
    ctx.fillText(spFit(ctx, props.source_role || props.kind || '—', maxW), x + pad, y + 78);
    const incoming = info?.incoming || 0, outgoing = info?.outgoing || 0;
    const channelSummary = Object.entries(info?.byChannel || {})
      .sort((a,b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 2).map(([channel,count]) => `${channel}:${count}`).join('  ');
    ctx.font = '600 12px ui-monospace, monospace';
    ctx.globalAlpha = .92;
    ctx.fillText(spFit(ctx, `OUT ${outgoing}  IN ${incoming}  LINKS ${incoming + outgoing}${channelSummary ? '  ' + channelSummary : ''}`, maxW), x + pad, y + 104);
    ctx.globalAlpha = 1;
    this.labelUV.set(record.key, {
      u0:x/canvas.width, v0:1-(y+cellH)/canvas.height,
      u1:(x+cellW)/canvas.width, v1:1-y/canvas.height,
    });
  });

  g.bindTexture(g.TEXTURE_2D, this.labelTexture);
  g.texImage2D(g.TEXTURE_2D, 0, g.RGBA, g.RGBA, g.UNSIGNED_BYTE, canvas);
  g.texParameteri(g.TEXTURE_2D, g.TEXTURE_MIN_FILTER, g.LINEAR);
  g.texParameteri(g.TEXTURE_2D, g.TEXTURE_MAG_FILTER, g.LINEAR);
  g.texParameteri(g.TEXTURE_2D, g.TEXTURE_WRAP_S, g.CLAMP_TO_EDGE);
  g.texParameteri(g.TEXTURE_2D, g.TEXTURE_WRAP_T, g.CLAMP_TO_EDGE);
};

function spCross(a,b){return{x:a.y*b.z-a.z*b.y,y:a.z*b.x-a.x*b.z,z:a.x*b.y-a.y*b.x}}
function spDot(a,b){return a.x*b.x+a.y*b.y+a.z*b.z}
function spNormalizeVector(v, fallback={x:1,y:0,z:0}) {
  const x=Number(v?.x), y=Number(v?.y), z=Number(v?.z), length=Math.hypot(x,y,z);
  if (!Number.isFinite(length) || length < 1e-6) return {...fallback};
  return {x:x/length,y:y/length,z:z/length};
}

function spEnsureLayout(state) {
  state.layout ||= {};
  const layout = state.layout;
  if (!['x','y','z'].includes(layout.child_axis)) {
    const d = state.projection?.child_direction || {x:0,y:-1,z:0};
    const vals = {x:Number(d.x)||0,y:Number(d.y)||0,z:Number(d.z)||0};
    layout.child_axis = ['x','y','z'].sort((a,b)=>Math.abs(vals[b])-Math.abs(vals[a]))[0] || 'y';
    const value = vals[layout.child_axis];
    layout.child_direction = Math.abs(value)<1e-6 ? 'center' : value>0 ? 'up' : 'down';
  }
  if (!['up','center','down'].includes(layout.child_direction)) layout.child_direction='down';
  const spread=Number(layout.base_spread);
  layout.base_spread=Number.isFinite(spread)?Math.max(.25,Math.min(4,spread)):1;
  return layout;
}

function spLayoutBasis(layout) {
  const axisVector={x:0,y:0,z:0};
  axisVector[layout.child_axis]=1;
  const sign=layout.child_direction==='up'?1:layout.child_direction==='down'?-1:0;
  const step={x:axisVector.x*sign,y:axisVector.y*sign,z:axisVector.z*sign};
  const worldY={x:0,y:1,z:0}, worldZ={x:0,y:0,z:1};
  const ref=Math.abs(spDot(axisVector,worldY))>.95?worldZ:worldY;
  const right=spNormalizeVector(spCross(ref,axisVector),{x:1,y:0,z:0});
  const forward=spNormalizeVector(spCross(axisVector,right),{x:0,y:0,z:1});
  return {step,right,forward};
}

function spRecursive3DPositions(obj, state) {
  const nodes=obj.nodes||[];
  const byId=new Map(nodes.map(node=>[String(node.id),node]));
  const children=new Map(), roots=[];
  for(const node of nodes){
    const id=String(node.id), rawParent=node.properties?.projection_parent_id;
    const parentId=rawParent==null?null:String(rawParent);
    if(parentId&&byId.has(parentId)){
      if(!children.has(parentId))children.set(parentId,[]);
      children.get(parentId).push(id);
    }else roots.push(id);
  }
  for(const list of children.values())list.sort();

  const layout=spEnsureLayout(state), basis=spLayoutBasis(layout);
  const childGap=300*layout.base_spread, siblingGap=210*layout.base_spread;
  const positions=new Map();
  for(const rootId of roots.sort()){
    const src=byId.get(rootId)?.transform?.position||{};
    positions.set(rootId,{x:(Number(src.x)||0)*layout.base_spread,y:(Number(src.y)||0)*layout.base_spread,z:(Number(src.z)||0)*layout.base_spread});
    const queue=[rootId];
    while(queue.length){
      const parentId=queue.shift(), parentPos=positions.get(parentId), childIds=children.get(parentId)||[];
      if(!parentPos||!childIds.length)continue;
      const cols=Math.max(1,Math.ceil(Math.sqrt(childIds.length)));
      const rows=Math.max(1,Math.ceil(childIds.length/cols));
      childIds.forEach((childId,index)=>{
        const row=Math.floor(index/cols), col=index%cols;
        const ox=(col-(cols-1)/2)*siblingGap, oz=(row-(rows-1)/2)*siblingGap;
        positions.set(childId,{
          x:parentPos.x+basis.step.x*childGap+basis.right.x*ox+basis.forward.x*oz,
          y:parentPos.y+basis.step.y*childGap+basis.right.y*ox+basis.forward.y*oz,
          z:parentPos.z+basis.step.z*childGap+basis.right.z*ox+basis.forward.z*oz,
        });
        queue.push(childId);
      });
    }
  }
  for(const node of nodes){
    const id=String(node.id); if(positions.has(id))continue;
    const src=node?.transform?.position||{};
    positions.set(id,{x:(Number(src.x)||0)*layout.base_spread,y:(Number(src.y)||0)*layout.base_spread,z:(Number(src.z)||0)*layout.base_spread});
  }
  return positions;
}

Renderer.prototype.build=function(scene){
  const restores=[];
  try{
    for(const obj of scene?.objects||[]){
      const inst=S.instances.find(i=>i.id===obj.instance_id);
      if(!inst||inst.projection_dimension!=='3d')continue;
      const state=ensureLocalState(inst,obj), positions=spRecursive3DPositions(obj,state), p=state.projection;
      const oldSpread={x:p.spread_x,y:p.spread_y,z:p.spread_z};
      p.spread_x=p.spread_y=p.spread_z=1;
      restores.push(()=>{p.spread_x=oldSpread.x;p.spread_y=oldSpread.y;p.spread_z=oldSpread.z});
      for(const node of obj.nodes||[]){
        const pos=node.transform?.position, replacement=positions.get(String(node.id));
        if(!pos||!replacement)continue;
        const original={x:Number(pos.x)||0,y:Number(pos.y)||0,z:Number(pos.z)||0};
        pos.x=replacement.x;pos.y=replacement.y;pos.z=replacement.z;
        restores.push(()=>{pos.x=original.x;pos.y=original.y;pos.z=original.z});
      }
    }
    SP_originalBuild.call(this,scene);
  }finally{for(let i=restores.length-1;i>=0;i--)restores[i]();}
  for(const item of this.strips||[])item.matrix=m4mul(item.matrix,m4scale(1,2.35,1));
  for(const item of this.labels||[])item.matrix=m4mul(item.matrix,m4scale(1,2.35,1));
  this.upload();
};

function spStyle(inst){return(S.catalog?.styles||[]).find(style=>style.id===inst.projection_style)||null}
function spNormalizeDimension(inst){
  const dimensions=spStyle(inst)?.dimensions||['2d'];
  if(!dimensions.includes(inst.projection_dimension))inst.projection_dimension=dimensions.includes('3d')?'3d':dimensions[0];
  return dimensions;
}
styleOptions=function(selected){return(S.catalog?.styles||[]).map(style=>`<option value="${esc(style.id)}" ${style.id===selected?'selected':''}>${esc(style.label)}</option>`).join('')};
function spDimensionOptions(inst){
  const dimensions=spNormalizeDimension(inst);
  return ['2d','3d'].map(d=>`<option value="${d}" ${inst.projection_dimension===d?'selected':''} ${dimensions.includes(d)?'':'disabled'}>${d.toUpperCase()}</option>`).join('');
}

newInstance=function(){
  const id=`p${S.nextId++}`;
  const style=(S.catalog?.styles||[]).find(item=>item.id==='atlas')||S.catalog?.styles?.[0];
  const root=(S.catalog?.topics||[]).find(item=>item.id==='IAM')||(S.catalog?.topics||[]).find(item=>item.id!=='all');
  const dimension=style?.dimensions?.includes('3d')?'3d':style?.dimensions?.[0]||'2d';
  return{id,name:`Projection ${id.slice(1)}`,projection_style:style?.id||'atlas',projection_dimension:dimension,root_topic:root?.id||'all',dependency_depth:1};
};

instancePayload=function(){return S.instances.map(instance=>{spNormalizeDimension(instance);return{id:instance.id,name:instance.name,master:!!instance.master,projection_style:instance.projection_style,projection_dimension:instance.projection_dimension,root_topic:instance.root_topic,dependency_depth:instance.dependency_depth}})};

function spAxisOptions(selected){return['x','y','z'].map(v=>`<option value="${v}" ${v===selected?'selected':''}>${v.toUpperCase()}</option>`).join('')}
function spDirectionOptions(selected){return['up','center','down'].map(v=>`<option value="${v}" ${v===selected?'selected':''}>${v[0].toUpperCase()+v.slice(1)}</option>`).join('')}

instanceHTML=function(inst){
  spNormalizeDimension(inst);
  const obj=(S.scene?.objects||[]).find(o=>o.instance_id===inst.id), st=ensureLocalState(inst,obj), col=S.objectStyle[inst.id], p=st.projection, layout=spEnsureLayout(st), style=spStyle(inst);
  return `<details class="instance" open data-card="${inst.id}">
    <summary>${esc(inst.name)} · ${esc(style?.label||inst.projection_style)} · ${esc(inst.projection_dimension.toUpperCase())}</summary>
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
      ${inst.projection_dimension==='3d'?`<div class="grid2"><div class="field"><label>Child axis</label><select data-child-axis="${inst.id}">${spAxisOptions(layout.child_axis)}</select></div><div class="field"><label>Direction</label><select data-child-direction-mode="${inst.id}">${spDirectionOptions(layout.child_direction)}</select></div></div>`:''}
      <div class="field"><label>Base spread <span data-base-spread-value="${inst.id}">${layout.base_spread.toFixed(2)}×</span></label><input type="range" min=".25" max="4" step=".05" data-base-spread="${inst.id}" value="${layout.base_spread}"></div>
      <div class="grid2"><div class="field"><label>Node size</label><input type="number" step=".05" min=".05" max="20" data-proj="${inst.id}" data-proj-key="node_scale" value="${p.node_scale}"></div><div class="field"><label>Internal edge opacity</label><input type="number" step=".05" min="0" max="1" data-proj="${inst.id}" data-proj-key="edge_opacity" value="${p.edge_opacity}"></div></div>
      <div class="grid2"><button data-reset="${inst.id}">Reset transform</button><button class="remove" data-remove="${inst.id}">Remove instance</button></div>
    </div>
  </details>`;
};

renderInstances=function(){
  SP_originalRenderInstances();
  $('#instances').querySelectorAll('[data-child-axis]').forEach(el=>el.onchange=()=>{
    const inst=S.instances.find(x=>x.id===el.dataset.childAxis);if(!inst)return;
    const obj=(S.scene?.objects||[]).find(o=>o.instance_id===inst.id),state=ensureLocalState(inst,obj);
    spEnsureLayout(state).child_axis=el.value;rebuildRenderer();
  });
  $('#instances').querySelectorAll('[data-child-direction-mode]').forEach(el=>el.onchange=()=>{
    const inst=S.instances.find(x=>x.id===el.dataset.childDirectionMode);if(!inst)return;
    const obj=(S.scene?.objects||[]).find(o=>o.instance_id===inst.id),state=ensureLocalState(inst,obj);
    spEnsureLayout(state).child_direction=el.value;rebuildRenderer();
  });
  $('#instances').querySelectorAll('[data-base-spread]').forEach(el=>el.oninput=()=>{
    const inst=S.instances.find(x=>x.id===el.dataset.baseSpread);if(!inst)return;
    const obj=(S.scene?.objects||[]).find(o=>o.instance_id===inst.id),state=ensureLocalState(inst,obj);
    const value=Math.max(.25,Math.min(4,Number(el.value)||1));spEnsureLayout(state).base_spread=value;
    const label=$(`[data-base-spread-value="${inst.id}"]`);if(label)label.textContent=`${value.toFixed(2)}×`;rebuildRenderer();
  });
};

function spApplyPrimaryDefaults(){
  if(SP_defaultRootsApplied||!S.catalog)return;
  const available=new Set((S.catalog.topics||[]).map(x=>x.id));
  const roots=['IAM','AccessCore','DWH'].filter(root=>available.has(root));
  if(!roots.length)return;
  const style=(S.catalog.styles||[]).find(item=>item.id==='atlas')||S.catalog.styles?.[0];
  const dimension=style?.dimensions?.includes('3d')?'3d':style?.dimensions?.[0]||'2d';
  const defaultPositions={IAM:{x:0,y:420,z:-120},AccessCore:{x:0,y:0,z:0},DWH:{x:0,y:-420,z:120}};
  S.instances=roots.map((root,index)=>({id:`p${index+1}`,name:root,master:index===0,projection_style:style?.id||'atlas',projection_dimension:dimension,root_topic:root,dependency_depth:1}));
  for(const inst of S.instances){
    const position=defaultPositions[inst.root_topic]||{x:0,y:0,z:0};
    S.objectState[inst.id]={transform:{position:{...position},rotation:{x:0,y:0,z:0},scale:{x:1,y:1,z:1}},projection:{...projectionDefaults()},layout:{child_axis:'y',child_direction:'down',base_spread:1}};
  }
  S.nextId=roots.length+1;SP_defaultRootsApplied=true;
}

loadScene=async function(){spApplyPrimaryDefaults();return SP_originalLoadScene();};

(function(){
  const baseRenderInstances = renderInstances;
  const baseSyncView = syncView;
  let selectedProjectionId = null;

  function deg(v){ return Number(v || 0) * 180 / Math.PI; }
  function rad(v){ return Number(v || 0) * Math.PI / 180; }

  function ensureCameras(){
    if (!Array.isArray(S.cameras) || !S.cameras.length) {
      S.cameras = [{
        id:'camera-main', name:'Main',
        position:{x:0,y:0,z:Number(S.distance)||3600},
        rotation:{x:deg(S.rotX),y:deg(S.rotY),z:0},
        scale:{x:1,y:1,z:1},
        fov:Number(S.fov)||60, near:1, far:100000,
      }];
    }
    if (!S.activeCameraId || !S.cameras.some(c => c.id === S.activeCameraId)) S.activeCameraId = S.cameras[0].id;
  }

  function activeCamera(){ ensureCameras(); return S.cameras.find(c => c.id === S.activeCameraId) || S.cameras[0]; }

  function syncCameraFromView(){
    const c = activeCamera();
    c.rotation.x = deg(S.rotX); c.rotation.y = deg(S.rotY);
    c.fov = Number(S.fov)||60; c.position.z = Number(S.distance)||3600;
  }

  function applyCamera(c){
    S.rotX = rad(c.rotation.x); S.rotY = rad(c.rotation.y);
    S.fov = Math.max(5, Math.min(160, Number(c.fov)||60));
    S.distance = Math.max(1, Number(c.position.z)||3600);
  }

  function shell(){
    const instances = $('#instances'), body = instances?.parentElement;
    if (!instances || !body) return null;
    const section = body.closest('.section'), summary = section?.querySelector(':scope > summary');
    if (summary) summary.textContent = 'VIEWER';
    let lists = $('#viewerEntityLists');
    if (!lists) { lists = document.createElement('div'); lists.id = 'viewerEntityLists'; body.insertBefore(lists, instances); }
    let cameraEditor = $('#cameraEditor');
    if (!cameraEditor) { cameraEditor = document.createElement('div'); cameraEditor.id = 'cameraEditor'; instances.insertAdjacentElement('afterend', cameraEditor); }
    const add = $('#addInstance'); if (add) add.style.display = 'none';
    for (const d of document.querySelectorAll('.left > .section')) if (d.querySelector(':scope > summary')?.textContent?.trim() === 'VIEW') d.style.display = 'none';
    if (!$('#structuredViewerStyle')) {
      const s = document.createElement('style'); s.id = 'structuredViewerStyle';
      s.textContent = '#viewerEntityLists{display:grid;gap:10px;margin-bottom:12px}.entity-head{display:flex;justify-content:space-between;margin-bottom:5px;font-size:10px;color:var(--muted);font-weight:800;letter-spacing:.08em}.entity-row{display:flex;gap:6px;overflow-x:auto}.entity-chip{white-space:nowrap;border-radius:999px}.entity-chip.active{border-color:var(--blue)}.entity-chip.add{min-width:34px}.instance{display:none}.instance.selected-instance{display:block;border:0;border-radius:0;overflow:visible}.instance.selected-instance>summary{display:none}.instance.selected-instance .instance-body{padding:0}.editor-title{display:flex;justify-content:space-between;margin:12px 0 8px;padding-top:10px;border-top:1px solid var(--line);font-weight:800}';
      document.head.appendChild(s);
    }
    return {lists,cameraEditor};
  }

  function projectionList(){
    if (!selectedProjectionId || !S.instances.some(i => i.id === selectedProjectionId)) selectedProjectionId = S.instances[0]?.id || null;
    return `<div><div class="entity-head"><span>PROJECTIONS</span><span>${S.instances.length}</span></div><div class="entity-row">${S.instances.map(i=>`<button class="entity-chip ${i.id===selectedProjectionId?'active':''}" data-select-projection="${esc(i.id)}">${esc(i.name)}</button>`).join('')}<button class="entity-chip add" data-add-projection>+</button></div></div>`;
  }

  function cameraList(){
    ensureCameras();
    return `<div><div class="entity-head"><span>CAMERAS</span><span>${S.cameras.length}</span></div><div class="entity-row">${S.cameras.map(c=>`<button class="entity-chip ${c.id===S.activeCameraId?'active':''}" data-select-camera="${esc(c.id)}">${esc(c.name)}</button>`).join('')}<button class="entity-chip add" data-add-camera>+</button></div></div>`;
  }

  function axes(c, section, step, min=null, max=null){
    return ['x','y','z'].map(a=>`<div class="field axis ${a}"><label>${a.toUpperCase()}</label><input type="number" data-camera-section="${section}" data-axis="${a}" step="${step}" ${min!==null?`min="${min}"`:''} ${max!==null?`max="${max}"`:''} value="${Number(c[section][a]).toFixed(section==='rotation'?1:2)}"></div>`).join('');
  }

  function cameraEditor(){
    const c = activeCamera();
    return `<div class="editor-title"><span>CAMERA · ${esc(c.name)}</span><span class="muted">${esc(c.id)}</span></div><div class="field"><label>Name</label><input data-camera-name value="${esc(c.name)}"></div><div class="subhead"><span>Position</span><span>XYZ</span></div><div class="grid3">${axes(c,'position',25)}</div><div class="subhead"><span>Rotation</span><span>degrees</span></div><div class="grid3">${axes(c,'rotation',1,-360,360)}</div><div class="subhead"><span>Scale</span><span>XYZ</span></div><div class="grid3">${axes(c,'scale',.05,.05,20)}</div><div class="grid3"><div class="field"><label>FOV</label><input type="number" min="5" max="160" step="1" data-camera-key="fov" value="${c.fov}"></div><div class="field"><label>Near</label><input type="number" min=".001" step=".1" data-camera-key="near" value="${c.near}"></div><div class="field"><label>Far</label><input type="number" min="1" step="100" data-camera-key="far" value="${c.far}"></div></div>`;
  }

  function bind(){
    const lists = $('#viewerEntityLists');
    lists.querySelectorAll('[data-select-projection]').forEach(b=>b.onclick=()=>{selectedProjectionId=b.dataset.selectProjection;renderInstances();});
    lists.querySelector('[data-add-projection]').onclick=()=>{const i=newInstance();S.instances.push(i);selectedProjectionId=i.id;renderInstances();scheduleSceneReload(0);};
    lists.querySelectorAll('[data-select-camera]').forEach(b=>b.onclick=()=>{syncCameraFromView();S.activeCameraId=b.dataset.selectCamera;applyCamera(activeCamera());baseSyncView();renderInstances();draw();});
    lists.querySelector('[data-add-camera]').onclick=()=>{syncCameraFromView();const source=JSON.parse(JSON.stringify(activeCamera()));let n=2;while(S.cameras.some(c=>c.id===`camera-${n}`))n++;source.id=`camera-${n}`;source.name=`Camera ${n}`;S.cameras.push(source);S.activeCameraId=source.id;renderInstances();};
    const e=$('#cameraEditor');
    e.querySelector('[data-camera-name]').onchange=ev=>{activeCamera().name=ev.target.value.trim()||activeCamera().name;renderInstances();};
    e.querySelectorAll('[data-camera-section]').forEach(input=>input.oninput=()=>{const c=activeCamera(),section=input.dataset.cameraSection,axis=input.dataset.axis;let v=Number(input.value);if(!Number.isFinite(v))return;if(section==='scale')v=Math.max(.05,v);c[section][axis]=v;applyCamera(c);baseSyncView();draw();});
    e.querySelectorAll('[data-camera-key]').forEach(input=>input.oninput=()=>{const c=activeCamera(),key=input.dataset.cameraKey;let v=Number(input.value);if(!Number.isFinite(v))return;if(key==='fov')v=Math.max(5,Math.min(160,v));if(key==='near')v=Math.max(.001,v);if(key==='far')v=Math.max(c.near+.001,v);c[key]=v;applyCamera(c);baseSyncView();draw();});
  }

  function applyLayout(){
    const s=shell(); if(!s)return;
    s.lists.innerHTML=projectionList()+cameraList();
    for(const card of $('#instances').querySelectorAll('.instance')){const selected=card.dataset.card===selectedProjectionId;card.classList.toggle('selected-instance',selected);if(selected)card.open=true;}
    const old=$('#projectionEditorTitle');if(old)old.remove();
    const selected=S.instances.find(i=>i.id===selectedProjectionId);if(selected)$('#instances').insertAdjacentHTML('beforebegin',`<div id="projectionEditorTitle" class="editor-title"><span>PROJECTION · ${esc(selected.name)}</span><span class="muted">${esc(selected.id)}</span></div>`);
    s.cameraEditor.innerHTML=cameraEditor();bind();
  }

  renderInstances=function(){const old=$('#projectionEditorTitle');if(old)old.remove();baseRenderInstances();applyLayout();};

  syncView=function(){syncCameraFromView();baseSyncView();};

  viewProjection=function(){
    const c=activeCamera(), canvas=$('#gl'), aspect=Math.max(.01,canvas.clientWidth/canvas.clientHeight);
    const near=Math.max(.001,Number(c.near)||1), far=Math.max(near+.001,Number(c.far)||100000);
    let v=m4translate(-(Number(c.position.x)||0),-(Number(c.position.y)||0),-(Number(c.position.z)||0));
    v=m4mul(v,m4rz(rad(c.rotation.z)));v=m4mul(v,m4rx(rad(c.rotation.x)));v=m4mul(v,m4ry(rad(c.rotation.y)));
    v=m4mul(v,m4scale(Math.max(.0001,Number(c.scale.x)||1),Math.max(.0001,Number(c.scale.y)||1),Math.max(.0001,Number(c.scale.z)||1)));
    return m4mul(m4perspective((Number(c.fov)||60)*Math.PI/180,aspect,near,far),v);
  };

  ensureCameras();
  setTimeout(()=>renderInstances(),0);
})();
