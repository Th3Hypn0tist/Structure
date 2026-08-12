'use strict';

// Viewer-only card enrichment. It reads only explicit Scene node properties and
// explicit Scene connections. No prose/key/name inference is performed.
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
  // Expand the colored title surface and white card plane over most of the face.
  for (const item of this.strips || []) item.matrix = m4mul(item.matrix, m4scale(1, 2.35, 1));
  for (const item of this.labels || []) item.matrix = m4mul(item.matrix, m4scale(1, 2.35, 1));
  this.upload();
};

renderInstances = function() {
  SP_originalRenderInstances();
  document.querySelectorAll('.field label').forEach(label => {
    if (label.textContent.trim().startsWith('Dependency depth downward')) {
      label.textContent = 'Relation depth outward (0–32)';
    }
  });
};

function spApplyPrimaryDefaults() {
  if (SP_defaultRootsApplied || !S.catalog) return;
  const available = new Set((S.catalog.topics || []).map(x => x.id));
  const roots = ['IAM', 'AccessCore', 'DWH'].filter(root => available.has(root));
  if (!roots.length) return;
  const style = (S.catalog.styles || []).find(x => x.id === 'atlas_2d')?.id || S.catalog.styles?.[0]?.id || 'atlas_2d';
  S.instances = roots.map((root, index) => ({
    id: `p${index + 1}`,
    name: root,
    projection_style: style,
    root_topic: root,
    dependency_depth: 1,
  }));
  S.nextId = roots.length + 1;
  SP_defaultRootsApplied = true;
}

loadScene = async function() {
  spApplyPrimaryDefaults();
  return SP_originalLoadScene();
};
