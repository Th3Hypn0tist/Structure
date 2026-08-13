'use strict';

// Viewer-only card enrichment and compact projection-style UI. It reads only
// explicit Scene node properties and explicit Scene connections.
const SP_originalBuildAtlas = Renderer.prototype.buildAtlas;
const SP_originalBuild = Renderer.prototype.build;
const SP_originalRenderInstances = renderInstances;
const SP_originalLoadScene = loadScene;
let SP_defaultRootsApplied = false;

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

Renderer.prototype.build = function(scene) {
  SP_originalBuild.call(this, scene);
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
  return (S.catalog?.styles || [])
    .map(style => `<option value="${esc(style.id)}" ${style.id===selected?'selected':''}>${esc(style.label)}</option>`)
    .join('');
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
  return {
    id,
    name:`Projection ${id.slice(1)}`,
    projection_style: style?.id || 'atlas',
    projection_dimension: dimension,
    root_topic: root?.id || 'all',
    dependency_depth: 1,
  };
};

instancePayload = function() {
  return S.instances.map(instance => {
    spNormalizeDimension(instance);
    return {
      id: instance.id,
      name: instance.name,
      projection_style: instance.projection_style,
      projection_dimension: instance.projection_dimension,
      root_topic: instance.root_topic,
      dependency_depth: instance.dependency_depth,
    };
  });
};

instanceHTML = function(inst) {
  spNormalizeDimension(inst);
  const obj = (S.scene?.objects || []).find(o => o.instance_id === inst.id);
  const st = ensureLocalState(inst, obj);
  const col = S.objectStyle[inst.id];
  const p = st.projection;
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
      <div class="subhead"><span>Instance colors</span><span>depth parity</span></div>
      <div class="color-row"><label>Even depth</label><input type="color" data-color="${inst.id}" data-color-key="even" value="${col.even}"></div>
      <div class="color-row"><label>Odd depth</label><input type="color" data-color="${inst.id}" data-color-key="odd" value="${col.odd}"></div>
      <div class="color-row"><label>Title surface</label><input type="color" data-color="${inst.id}" data-color-key="title" value="${col.title}"></div>
      <div class="subhead"><span>Position</span><span>XYZ</span></div><div class="grid3">${axisFields(inst.id,'position',st.transform.position,25)}</div>
      <div class="subhead"><span>Rotation</span><span>degrees</span></div><div class="grid3">${axisFields(inst.id,'rotation',st.transform.rotation,5,-360,360)}</div>
      <div class="subhead"><span>Scale</span><span>XYZ</span></div><div class="grid3">${axisFields(inst.id,'scale',st.transform.scale,.05,.05,20)}</div>
      <div class="subhead"><span>Projection layout</span><span>local</span></div>
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
};

function spApplyPrimaryDefaults() {
  if (SP_defaultRootsApplied || !S.catalog) return;
  const available = new Set((S.catalog.topics || []).map(x => x.id));
  const roots = ['IAM', 'AccessCore', 'DWH'].filter(root => available.has(root));
  if (!roots.length) return;
  const style = (S.catalog.styles || []).find(item => item.id === 'atlas') || S.catalog.styles?.[0];
  const dimension = style?.dimensions?.includes('3d') ? '3d' : style?.dimensions?.[0] || '2d';
  const defaultPositions = {
    IAM: {x:0, y:420, z:-120},
    AccessCore: {x:0, y:0, z:0},
    DWH: {x:0, y:-420, z:120},
  };
  S.instances = roots.map((root, index) => ({
    id: `p${index + 1}`,
    name: root,
    projection_style: style?.id || 'atlas',
    projection_dimension: dimension,
    root_topic: root,
    dependency_depth: 1,
  }));
  for (const inst of S.instances) {
    const position = defaultPositions[inst.root_topic] || {x:0, y:0, z:0};
    S.objectState[inst.id] = {
      transform: {
        position: {...position},
        rotation: {x:0, y:0, z:0},
        scale: {x:1, y:1, z:1},
      },
      projection: projectionDefaults(),
    };
  }
  S.nextId = roots.length + 1;
  SP_defaultRootsApplied = true;
}

loadScene = async function() {
  spApplyPrimaryDefaults();
  return SP_originalLoadScene();
};
