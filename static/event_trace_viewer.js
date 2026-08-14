'use strict';

(function installEventTraceViewer(){
  if (window.__structureEventTraceViewerInstalled) return;
  window.__structureEventTraceViewerInstalled = true;

  const state = {
    selected: null,
    cameraTarget: {x:0,y:0,z:0},
    animationToken: 0,
    currentRefs: new Set(),
    pastRefs: new Set(),
    activeEventId: null,
    activeWave: null,
    hitStart: null,
  };

  function ensureUI(){
    const viewer = document.querySelector('.viewer');
    if (!viewer || document.getElementById('spEventRail')) return;

    const style = document.createElement('style');
    style.id = 'spEventTraceStyle';
    style.textContent = `
      #spEventRail{position:absolute;z-index:70;display:none;min-width:150px;max-width:220px;transform:translateY(-50%);pointer-events:auto}
      #spEventRail .sp-event-title{font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 5px 6px;text-shadow:0 1px 5px #000}
      #spEventRail .sp-event-item{display:block;width:100%;margin:4px 0;padding:5px 9px;border:1px solid #586273;border-radius:999px;background:#05070ae8;color:#fff;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-shadow:0 3px 12px #0008}
      #spEventRail .sp-event-item:hover{border-color:var(--blue)}
      #spEventRail .sp-event-item.active{border-color:var(--gold);color:var(--gold)}
      #spEventRail .sp-event-wave{font:10px ui-monospace,monospace;color:var(--gold);margin:5px 0 0 6px}
      #spEventImpact{position:absolute;inset:0;z-index:65;pointer-events:none;overflow:hidden}
      .sp-impact-dot{position:absolute;width:28px;height:28px;margin:-14px 0 0 -14px;border:2px solid var(--gold);border-radius:50%;box-shadow:0 0 18px var(--gold);animation:spImpactPulse .62s ease-in-out infinite alternate}
      .sp-impact-dot.past{width:18px;height:18px;margin:-9px 0 0 -9px;border-color:var(--blue);box-shadow:none;opacity:.35;animation:none}
      .sp-focus-dot{position:absolute;width:12px;height:12px;margin:-6px 0 0 -6px;border:2px solid #fff;border-radius:50%;box-shadow:0 0 12px #fff8}
      @keyframes spImpactPulse{from{transform:scale(.75);opacity:.45}to{transform:scale(1.35);opacity:1}}
    `;
    document.head.appendChild(style);

    const rail = document.createElement('div');
    rail.id = 'spEventRail';
    viewer.appendChild(rail);
    const impact = document.createElement('div');
    impact.id = 'spEventImpact';
    viewer.appendChild(impact);
  }

  function projectedPoint(p){
    const canvas = document.getElementById('gl');
    if (!canvas) return null;
    const vp = viewProjection();
    const x = Number(p?.x)||0, y = Number(p?.y)||0, z = Number(p?.z)||0;
    const cx = vp[0]*x + vp[4]*y + vp[8]*z + vp[12];
    const cy = vp[1]*x + vp[5]*y + vp[9]*z + vp[13];
    const cw = vp[3]*x + vp[7]*y + vp[11]*z + vp[15];
    if (cw <= 0) return null;
    return {
      x:(cx/cw*.5+.5)*canvas.clientWidth,
      y:(-cy/cw*.5+.5)*canvas.clientHeight,
      depth:cw,
    };
  }

  function renderedNodes(){
    const boxes = S.renderer?.boxes || [];
    const out = [];
    let index = 0;
    for (const obj of S.scene?.objects || []) {
      for (const node of obj.nodes || []) {
        if (index >= boxes.length) return out;
        const box = boxes[index++];
        const m = box?.matrix;
        if (!m) continue;
        out.push({
          objectId:String(obj.id),
          instanceId:String(obj.instance_id || ''),
          nodeId:String(node.id),
          node,
          point:{x:Number(m[12])||0,y:Number(m[13])||0,z:Number(m[14])||0},
        });
      }
    }
    return out;
  }

  function selectedEvents(){
    if (!state.selected) return [];
    return (S.scene?.event_surface?.events || []).filter(event => String(event.owner_ref || '') === state.selected.nodeId);
  }

  function traceFor(eventId){
    return S.scene?.event_surface?.traces?.[eventId] || null;
  }

  function positionRail(){
    const rail = document.getElementById('spEventRail');
    if (!rail || !state.selected) return;
    const p = projectedPoint(state.selected.point);
    if (!p) { rail.style.display='none'; return; }
    const events = selectedEvents();
    if (!events.length) { rail.style.display='none'; return; }
    rail.style.display='block';
    rail.style.left = `${Math.max(8, p.x - rail.offsetWidth - 34)}px`;
    rail.style.top = `${Math.max(34, Math.min((document.querySelector('.viewer')?.clientHeight || 0)-34, p.y))}px`;
  }

  function renderRail(){
    ensureUI();
    const rail = document.getElementById('spEventRail');
    if (!rail) return;
    const events = selectedEvents();
    if (!state.selected || !events.length) { rail.style.display='none'; rail.innerHTML=''; return; }
    const active = state.activeEventId;
    rail.innerHTML = `<div class="sp-event-title">Events · ${esc(state.selected.node?.properties?.name || state.selected.nodeId)}</div>` +
      events.map(event => `<button class="sp-event-item ${String(event.id)===String(active)?'active':''}" data-sp-event="${esc(event.id)}">● ${esc(event.name || event.id)} ●</button>`).join('') +
      (state.activeWave ? `<div class="sp-event-wave">impact ${state.activeWave.index}/${state.activeWave.total}</div>` : '');
    rail.querySelectorAll('[data-sp-event]').forEach(button => {
      button.onclick = () => animateEvent(button.dataset.spEvent);
    });
    positionRail();
  }

  function renderImpact(){
    ensureUI();
    const host = document.getElementById('spEventImpact');
    if (!host) return;
    const nodes = renderedNodes();
    const current = state.currentRefs, past = state.pastRefs;
    let html = '';
    for (const item of nodes) {
      const p = projectedPoint(item.point);
      if (!p) continue;
      if (current.has(item.nodeId)) html += `<div class="sp-impact-dot" style="left:${p.x}px;top:${p.y}px"></div>`;
      else if (past.has(item.nodeId)) html += `<div class="sp-impact-dot past" style="left:${p.x}px;top:${p.y}px"></div>`;
    }
    if (state.selected) {
      const p = projectedPoint(state.selected.point);
      if (p) html += `<div class="sp-focus-dot" style="left:${p.x}px;top:${p.y}px"></div>`;
    }
    host.innerHTML = html;
  }

  function sleep(ms){ return new Promise(resolve => setTimeout(resolve, ms)); }

  async function animateEvent(eventId){
    const trace = traceFor(eventId);
    state.animationToken += 1;
    const token = state.animationToken;
    state.activeEventId = eventId;
    state.currentRefs = new Set();
    state.pastRefs = new Set();
    state.activeWave = null;
    renderRail();
    renderImpact();
    if (!trace) return;

    const waves = Array.isArray(trace.waves) ? trace.waves : [];
    for (let i=0;i<waves.length;i++) {
      if (token !== state.animationToken) return;
      const wave = waves[i] || {};
      const refs = new Set([...(wave.refs || []), ...(wave.step_ids || [])].map(String));
      state.currentRefs = refs;
      state.activeWave = {index:i+1,total:waves.length};
      renderRail();
      renderImpact();
      await sleep(650);
      if (token !== state.animationToken) return;
      for (const ref of refs) state.pastRefs.add(ref);
    }
    state.currentRefs = new Set();
    state.activeWave = waves.length ? {index:waves.length,total:waves.length} : null;
    renderRail();
    renderImpact();
  }

  function animateCameraTarget(target){
    const from = {...state.cameraTarget};
    const to = {x:Number(target.x)||0,y:Number(target.y)||0,z:Number(target.z)||0};
    const started = performance.now();
    const duration = 280;
    function frame(now){
      const t = Math.min(1, (now-started)/duration);
      const e = 1-Math.pow(1-t,3);
      state.cameraTarget.x = from.x + (to.x-from.x)*e;
      state.cameraTarget.y = from.y + (to.y-from.y)*e;
      state.cameraTarget.z = from.z + (to.z-from.z)*e;
      draw();
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function pickNode(clientX, clientY){
    const canvas = document.getElementById('gl');
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const x = clientX-rect.left, y = clientY-rect.top;
    let best = null, bestDistance = 58;
    for (const item of renderedNodes()) {
      const p = projectedPoint(item.point);
      if (!p) continue;
      const distance = Math.hypot(p.x-x,p.y-y);
      if (distance < bestDistance) { best=item; bestDistance=distance; }
    }
    return best;
  }

  function selectNode(item){
    if (!item) return;
    state.selected = item;
    state.animationToken += 1;
    state.activeEventId = null;
    state.currentRefs = new Set();
    state.pastRefs = new Set();
    state.activeWave = null;
    animateCameraTarget(item.point);
    renderRail();
    renderImpact();
  }

  const originalViewProjection = viewProjection;
  viewProjection = function(){
    const canvas = document.getElementById('gl');
    const aspect = Math.max(.01, canvas.clientWidth/canvas.clientHeight);
    let v = m4translate(0,0,-S.distance);
    v = m4mul(v,m4rx(S.rotX));
    v = m4mul(v,m4ry(S.rotY));
    v = m4mul(v,m4translate(-state.cameraTarget.x,-state.cameraTarget.y,-state.cameraTarget.z));
    return m4mul(m4perspective(S.fov*Math.PI/180,aspect,1,100000),v);
  };

  const originalDraw = draw;
  draw = function(){
    originalDraw();
    positionRail();
    renderImpact();
  };

  const originalFit = fit;
  fit = function(redraw=true){
    state.cameraTarget = {x:0,y:0,z:0};
    state.selected = null;
    state.animationToken += 1;
    state.currentRefs = new Set();
    state.pastRefs = new Set();
    state.activeEventId = null;
    state.activeWave = null;
    renderRail();
    return originalFit(redraw);
  };

  const originalResetCamera = resetCamera;
  resetCamera = function(){
    state.cameraTarget = {x:0,y:0,z:0};
    state.selected = null;
    state.animationToken += 1;
    state.currentRefs = new Set();
    state.pastRefs = new Set();
    state.activeEventId = null;
    state.activeWave = null;
    renderRail();
    return originalResetCamera();
  };

  const originalLoadScene = loadScene;
  loadScene = async function(){
    const result = await originalLoadScene();
    if (state.selected) {
      const replacement = renderedNodes().find(item => item.nodeId===state.selected.nodeId && item.instanceId===state.selected.instanceId);
      state.selected = replacement || null;
    }
    renderRail();
    renderImpact();
    return result;
  };

  ensureUI();
  const canvas = document.getElementById('gl');
  if (canvas) {
    canvas.addEventListener('pointerdown', event => {
      if (event.button===0) state.hitStart={x:event.clientX,y:event.clientY};
    }, true);
    canvas.addEventListener('pointerup', event => {
      const start=state.hitStart; state.hitStart=null;
      if (!start || Math.hypot(event.clientX-start.x,event.clientY-start.y)>5) return;
      const item=pickNode(event.clientX,event.clientY);
      if (item) selectNode(item);
    });
  }

  void originalViewProjection;
})();
