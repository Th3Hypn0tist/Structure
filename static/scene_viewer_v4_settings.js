'use strict';

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

  const baseViewProjection=viewProjection;
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
