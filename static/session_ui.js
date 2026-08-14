'use strict';

(function installStructureSessionUI(){
  let projectionBusy=false;
  let progressHideTimer=null;

  function masters(){return S.catalog?.masters||[]}
  function bases(){return S.catalog?.projection_bases||[]}
  function scopeStyles(){return S.catalog?.scope_styles||[]}
  function baseFor(inst){return bases().find(x=>x.id===inst.projection_base)||bases()[0]||null}
  function stylesForBase(instOrBase){
    const baseId=typeof instOrBase==='string'?instOrBase:instOrBase?.projection_base;
    return S.catalog?.projection_styles_by_base?.[baseId]||[];
  }
  function styleFor(inst){return stylesForBase(inst).find(x=>x.id===inst.projection_style)||stylesForBase(inst)[0]||null}
  function masterFor(inst){return masters().find(m=>m.id===inst.master_ref)||masters()[0]||null}

  function opt(items,selected,labelFn=x=>x.label||x.name||x.id){
    return(items||[]).map(x=>`<option value="${esc(x.id)}" ${String(x.id)===String(selected)?'selected':''}>${esc(labelFn(x))}</option>`).join('');
  }

  function scopeItems(inst){
    const m=masterFor(inst),type=inst.scope_type;
    if(!m)return[];
    if(type==='all')return[{id:'all',label:'all'}];
    if(type==='event')return m.scopes?.events||[];
    if(type==='flow')return m.scopes?.flows||[];
    if(type==='identity')return m.scopes?.identities||[];
    if(type==='topic')return (m.scopes?.topics||[]).filter(x=>x.id!=='all'&&x.topic_heading===true);
    return[];
  }

  function preferredDimension(styleId,dims){
    if(!Array.isArray(dims)||!dims.length)return'3d';
    if(styleId==='atlas'&&dims.includes('3d'))return'3d';
    return dims.includes('3d')?'3d':dims[0];
  }

  function defaultScopeFor(inst){
    const base=baseFor(inst),allowed=base?.scope_types||['all'];
    if(inst.projection_base==='map'&&allowed.includes('all'))return['all','all'];
    if(inst.projection_base==='event'&&allowed.includes('event')){
      const first=masterFor(inst)?.scopes?.events?.[0];return['event',String(first?.id||'')];
    }
    if(allowed.includes('topic')){
      const first=(masterFor(inst)?.scopes?.topics||[]).find(x=>x.topic_heading===true);
      if(first)return['topic',String(first.id)];
    }
    if(allowed.includes('identity')){
      const first=masterFor(inst)?.scopes?.identities?.[0];return['identity',String(first?.id||'')];
    }
    const type=allowed[0]||'all';
    const first=scopeItems({...inst,scope_type:type})[0];
    return[type,String(first?.id||'')];
  }

  function normalize(inst,{resetBase=false}={}){
    inst.master_ref ||= masters()[0]?.id||'master-1';
    inst.projection_base ||= S.catalog?.defaults?.projection_base||'map';
    if(!bases().some(x=>x.id===inst.projection_base))inst.projection_base=bases()[0]?.id||'map';

    const allowedStyles=stylesForBase(inst);
    const base=baseFor(inst);
    if(resetBase||!allowedStyles.some(x=>x.id===inst.projection_style)){
      inst.projection_style=base?.default_style||allowedStyles[0]?.id||'atlas';
    }
    const style=styleFor(inst),dims=style?.dimensions||['2d','3d'];
    if(!dims.includes(inst.projection_dimension))inst.projection_dimension=preferredDimension(inst.projection_style,dims);

    inst.scope_style ||= S.catalog?.defaults?.scope_style||'semantic_roles';
    if(!scopeStyles().some(x=>x.id===inst.scope_style))inst.scope_style=scopeStyles()[0]?.id||'semantic_roles';

    const allowedScopes=base?.scope_types||['all'];
    if(resetBase||!allowedScopes.includes(inst.scope_type)){
      [inst.scope_type,inst.scope_ref]=defaultScopeFor(inst);
    }else{
      const items=scopeItems(inst);
      if(!items.some(x=>String(x.id)===String(inst.scope_ref)))inst.scope_ref=String(items[0]?.id||'');
    }

    inst.relation_depth=Math.max(0,Math.min(32,Number(inst.relation_depth)||0));
    inst.impact_depth=Math.max(0,Math.min(64,Number(inst.impact_depth)||32));
    return inst;
  }

  function schemeFor(scopeStyle){
    if(scopeStyle==='monochrome')return{even:'#AAB2C2',odd:'#AAB2C2',title:'#AAB2C2'};
    if(scopeStyle==='depth')return{even:'#087CFF',odd:'#AAB2C2',title:'#0B356B'};
    return{even:'#087CFF',odd:'#AAB2C2',title:'#FFD83D'};
  }

  function applyScopeScheme(inst){
    S.objectStyle[inst.id]={...schemeFor(inst.scope_style)};
  }

  function ensureProjectionProgressUI(){
    if(document.getElementById('projectionProgressStyle'))return;
    const style=document.createElement('style');
    style.id='projectionProgressStyle';
    style.textContent=`
      #projectionProgress{position:fixed;z-index:330;left:50%;top:58px;transform:translateX(-50%);width:min(620px,calc(100vw - 32px));padding:9px 11px;background:#080b10ee;border:1px solid var(--line);border-radius:9px;box-shadow:0 12px 40px #0008;display:none;pointer-events:none}
      #projectionProgress.active{display:block}#projectionProgress.error{border-color:var(--red)}
      #projectionProgress .projection-progress-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:7px;font-size:10px}
      #projectionProgress .projection-progress-label{color:#fff;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      #projectionProgress .projection-progress-stage{color:var(--muted);white-space:nowrap}
      #projectionProgress .projection-progress-track{height:4px;background:#151b26;border-radius:999px;overflow:hidden}
      #projectionProgress .projection-progress-bar{height:100%;width:0%;background:var(--blue);border-radius:999px;transition:width .18s ease}
      #projectionProgress.error .projection-progress-bar{background:var(--red)}
      #instances.projection-busy{opacity:.72}#instances.projection-busy select,#instances.projection-busy input,#instances.projection-busy button{cursor:wait}
    `;
    document.head.appendChild(style);
    const box=document.createElement('div');box.id='projectionProgress';
    box.innerHTML='<div class="projection-progress-head"><span class="projection-progress-label">Projection</span><span class="projection-progress-stage">Waiting</span></div><div class="projection-progress-track"><div class="projection-progress-bar"></div></div>';
    document.body.appendChild(box);
  }

  function currentProjectionLabel(){
    if(!S.instances.length)return'Projection';
    const inst=normalize(S.instances[S.instances.length-1]);
    return `${inst.name} · ${baseFor(inst)?.label||inst.projection_base} · ${styleFor(inst)?.label||inst.projection_style} ${String(inst.projection_dimension).toUpperCase()}`;
  }

  function setProjectionProgress(percent,stage,label=null,bad=false){
    ensureProjectionProgressUI();clearTimeout(progressHideTimer);
    const box=document.getElementById('projectionProgress');box.classList.add('active');box.classList.toggle('error',bad);
    box.querySelector('.projection-progress-label').textContent=label||currentProjectionLabel();
    box.querySelector('.projection-progress-stage').textContent=stage;
    box.querySelector('.projection-progress-bar').style.width=`${Math.max(0,Math.min(100,Number(percent)||0))}%`;
  }
  function hideProjectionProgress(delay=260){clearTimeout(progressHideTimer);progressHideTimer=setTimeout(()=>document.getElementById('projectionProgress')?.classList.remove('active','error'),delay)}
  function applyProjectionLock(){
    const host=document.getElementById('instances');if(host){host.classList.toggle('projection-busy',projectionBusy);host.querySelectorAll('select,input,button').forEach(el=>el.disabled=projectionBusy)}
    for(const id of['addInstance','reload','sourcePickerButton']){const el=document.getElementById(id);if(el)el.disabled=projectionBusy}
  }
  function beginProjectionWork(label=null){if(projectionBusy)return false;projectionBusy=true;clearTimeout(S.reloadTimer);S.reloadTimer=null;setProjectionProgress(6,'Selected — preparing…',label||currentProjectionLabel());applyProjectionLock();return true}
  function finishProjectionWork(){setProjectionProgress(100,'Rendered',currentProjectionLabel());projectionBusy=false;applyProjectionLock();hideProjectionProgress(420)}
  function failProjectionWork(error){setProjectionProgress(100,'Failed',currentProjectionLabel(),true);projectionBusy=false;applyProjectionLock();hideProjectionProgress(1800);showError(error)}
  const nextAnimationFrame=()=>new Promise(resolve=>requestAnimationFrame(resolve));
  async function waitUntilPainted(){await nextAnimationFrame();await nextAnimationFrame()}

  newInstance=function(){
    if(!S.sourceSpec||!masters().length)throw new Error('Select a source before creating a projection.');
    const id=`p${S.nextId++}`;
    const inst={
      id,name:`Projection ${id.slice(1)}`,master_ref:masters()[0].id,
      projection_base:S.catalog?.defaults?.projection_base||'map',
      projection_style:S.catalog?.defaults?.projection_style||'atlas',
      projection_dimension:S.catalog?.defaults?.projection_dimension||'3d',
      scope_type:S.catalog?.defaults?.scope_type||'all',scope_ref:S.catalog?.defaults?.scope_ref||'all',
      scope_style:S.catalog?.defaults?.scope_style||'semantic_roles',relation_depth:0,impact_depth:32,
    };
    normalize(inst,{resetBase:true});applyScopeScheme(inst);return inst;
  };

  instancePayload=function(){return S.instances.map(raw=>{
    const i=normalize(raw);return{
      id:i.id,name:i.name,master_ref:i.master_ref,
      projection_base:i.projection_base,projection_style:i.projection_style,projection_dimension:i.projection_dimension,
      scope_type:i.scope_type,scope_ref:i.scope_ref,scope_style:i.scope_style,
      relation_depth:i.relation_depth,impact_depth:i.impact_depth,
    };
  })};

  function transformFields(inst){
    const state=ensureLocalState(inst,(S.scene?.objects||[]).find(o=>o.instance_id===inst.id));
    const t=state.transform;
    const row=(section,values,step)=>`<div class="subhead"><span>${section}</span><span>XYZ</span></div><div class="grid3">${['x','y','z'].map(axis=>`<div class="field axis ${axis}"><label>${axis.toUpperCase()}</label><input type="number" data-transform="${inst.id}" data-section="${section}" data-axis="${axis}" step="${step}" value="${Number(values[axis]).toFixed(section==='rotation'?1:2)}"></div>`).join('')}</div>`;
    return row('position',t.position,25)+row('rotation',t.rotation,5)+row('scale',t.scale,.05);
  }

  instanceHTML=function(raw){
    const inst=normalize(raw),base=baseFor(inst),styles=stylesForBase(inst),style=styleFor(inst),dims=style?.dimensions||['2d','3d'];
    const depthLabel=inst.projection_base==='event'?'Impact depth':'Relation depth';
    const depthKey=inst.projection_base==='event'?'impact_depth':'relation_depth';
    const depthMax=inst.projection_base==='event'?64:32;
    return `<details class="instance" open data-card="${inst.id}">
      <summary>${esc(inst.name)} · ${esc(base?.label||inst.projection_base)} · ${esc(style?.label||inst.projection_style)} ${esc(inst.projection_dimension.toUpperCase())}</summary>
      <div class="instance-body">
        <div class="field"><label>Instance name</label><input data-session="${inst.id}" data-session-key="name" value="${esc(inst.name)}"></div>
        <div class="grid2">
          <div class="field"><label>Master / source</label><select data-session="${inst.id}" data-session-key="master_ref">${opt(masters(),inst.master_ref)}</select></div>
          <div class="field"><label>Projection base</label><select data-session="${inst.id}" data-session-key="projection_base">${opt(bases(),inst.projection_base)}</select></div>
        </div>
        <div class="grid2">
          <div class="field"><label>Projection style</label><select data-session="${inst.id}" data-session-key="projection_style">${opt(styles,inst.projection_style)}</select></div>
          <div class="field"><label>Dimension</label><select data-session="${inst.id}" data-session-key="projection_dimension">${dims.map(v=>`<option value="${v}" ${v===inst.projection_dimension?'selected':''}>${v.toUpperCase()}</option>`).join('')}</select></div>
        </div>
        <div class="grid2">
          <div class="field"><label>Scope type</label><select data-session="${inst.id}" data-session-key="scope_type">${(base?.scope_types||[]).map(v=>`<option value="${esc(v)}" ${v===inst.scope_type?'selected':''}>${esc(v)}</option>`).join('')}</select></div>
          <div class="field"><label>Scope</label><select data-session="${inst.id}" data-session-key="scope_ref">${opt(scopeItems(inst),inst.scope_ref)}</select></div>
        </div>
        <div class="grid2">
          <div class="field"><label>Scope style</label><select data-session="${inst.id}" data-session-key="scope_style">${opt(scopeStyles(),inst.scope_style)}</select></div>
          <div class="field"><label>${depthLabel}</label><input type="number" min="0" max="${depthMax}" step="1" data-session="${inst.id}" data-session-key="${depthKey}" value="${inst[depthKey]}"></div>
        </div>
        ${transformFields(inst)}
        <div class="grid2"><button data-reset="${inst.id}">Reset transform</button><button class="remove" data-remove="${inst.id}">Remove projection</button></div>
      </div>
    </details>`;
  };

  renderInstances=function(){
    const host=$('#instances');host.innerHTML=S.instances.map(instanceHTML).join('');
    host.querySelectorAll('[data-session]').forEach(el=>el.onchange=async()=>{
      if(projectionBusy)return;
      const inst=S.instances.find(x=>x.id===el.dataset.session);if(!inst)return;
      const key=el.dataset.sessionKey;
      if(key==='relation_depth'||key==='impact_depth')inst[key]=Math.max(0,Number(el.value)||0);else inst[key]=el.value;
      if(key==='master_ref'){normalize(inst,{resetBase:true})}
      if(key==='projection_base'){normalize(inst,{resetBase:true})}
      else if(key==='projection_style'){
        const dims=styleFor(inst)?.dimensions||['2d','3d'];if(!dims.includes(inst.projection_dimension))inst.projection_dimension=preferredDimension(inst.projection_style,dims);
      }else if(key==='scope_type'){
        const items=scopeItems(inst);inst.scope_ref=String(items[0]?.id||'');
      }
      normalize(inst);applyScopeScheme(inst);renderInstances();await loadScene({label:currentProjectionLabel()});
    });
    host.querySelectorAll('[data-transform]').forEach(el=>el.oninput=()=>{
      const state=S.objectState[el.dataset.transform];if(!state)return;let v=Number(el.value);if(!Number.isFinite(v))return;if(el.dataset.section==='scale')v=Math.max(.05,v);state.transform[el.dataset.section][el.dataset.axis]=v;rebuildRenderer();
    });
    host.querySelectorAll('[data-reset]').forEach(btn=>btn.onclick=()=>{const inst=S.instances.find(x=>x.id===btn.dataset.reset);if(!inst)return;delete S.objectState[inst.id];ensureLocalState(inst,(S.scene?.objects||[]).find(o=>o.instance_id===inst.id));renderInstances();rebuildRenderer()});
    host.querySelectorAll('[data-remove]').forEach(btn=>btn.onclick=async()=>{if(projectionBusy)return;const id=btn.dataset.remove;S.instances=S.instances.filter(x=>x.id!==id);delete S.objectState[id];delete S.objectStyle[id];renderInstances();await loadScene({label:'Projection removed'})});
    applyProjectionLock();
  };

  async function refreshSessionCatalog(){
    if(!S.sourceSpec)throw new Error('No source/master selected.');
    const q=new URLSearchParams();
    if(S.sourceSpec.type==='directory'){q.set('source_type','directory');q.set('source_path',S.sourceSpec.path||'')}
    else{q.set('source_type','github');q.set('repo',S.sourceSpec.repo||'');q.set('branch',S.sourceSpec.branch||'main')}
    S.catalog=await getJSON(`/api/projection-catalog?${q}`);S.instances.forEach(i=>{normalize(i);applyScopeScheme(i)});renderInstances();
  }

  function synchronizeResolvedInstances(data){
    if(!Array.isArray(data?.instances))return;
    for(const resolved of data.instances){const local=S.instances.find(item=>item.id===resolved.id);if(!local)continue;Object.assign(local,resolved);normalize(local);applyScopeScheme(local)}
  }

  function verifyRenderedProjectionIdentity(){
    for(const inst of S.instances){const obj=(S.scene?.objects||[]).find(item=>item.instance_id===inst.id);if(!obj)throw new Error(`Rendered scene is missing projection object ${inst.id}`);if(String(obj.projection_dimension)!==String(inst.projection_dimension))throw new Error(`Projection dimension mismatch for ${inst.id}`);if(String(obj.projection_base)!==String(inst.projection_base))throw new Error(`Projection base mismatch for ${inst.id}`);if(String(obj.projection_style)!==String(inst.projection_style))throw new Error(`Projection style mismatch for ${inst.id}`)}
  }

  loadScene=async function(options={}){
    if(!S.instances.length){S.scene=null;if(S.renderer){S.renderer.boxes=[];S.renderer.lines=[];S.renderer.strips=[];S.renderer.labels=[];S.renderer.upload?.()}renderSceneInfo();draw();setStatus(S.sourceSpec?'master ready':'choose source');return true}
    if(!S.sourceSpec){showError(new Error('Projection has no selected source/master.'));return false}
    if(!beginProjectionWork(options.label))return false;
    setStatus('projecting');$('#error').textContent='None.';
    try{
      await nextAnimationFrame();setProjectionProgress(18,'Selecting StructureTree surface…');
      if(!S.catalog?.projection_bases)await refreshSessionCatalog();
      const source=S.sourceSpec;
      const data=await postJSON('/api/scene',{sources:[{id:'master-1',name:source.type==='directory'?(source.path||'Directory'):(source.repo||'Repository'),source}],instances:instancePayload()});
      setProjectionProgress(62,'Base resolved — applying projection style…');S.scene=data.scene;S.catalog=data.catalog||S.catalog;synchronizeResolvedInstances(data);verifyRenderedProjectionIdentity();
      S.source=data.masters?.[0]?.source||{};$('#revision').textContent=(S.source.revision||'').slice(0,12);
      for(const inst of S.instances){ensureLocalState(inst,(S.scene.objects||[]).find(o=>o.instance_id===inst.id));applyScopeScheme(inst)}
      syncChannels();renderInstances();renderChannels();setProjectionProgress(78,'Building geometry…');rebuildRenderer(false);fit(false);renderSceneInfo();setProjectionProgress(92,'Rendering first frame…');draw();await waitUntilPainted();
      const nodeCount=S.scene?.objects?.reduce((n,o)=>n+(o.nodes?.length||0),0)||0,active=S.instances[S.instances.length-1],generator=active?.projection_generator?` · ${active.projection_generator}`:'';
      setStatus(`${S.instances.length} projection${S.instances.length===1?'':'s'} · ${nodeCount} nodes${generator}`);finishProjectionWork();return true;
    }catch(e){failProjectionWork(e);return false}
  };

  function bindProjectionActions(){
    const add=$('#addInstance');if(add)add.onclick=async()=>{if(projectionBusy)return;if(!S.sourceSpec||!masters().length){showError(new Error('Select a source first.'));return}try{const inst=newInstance();S.instances.push(inst);renderInstances();await loadScene({label:currentProjectionLabel()})}catch(e){showError(e)}};
    const reload=$('#reload');if(reload)reload.onclick=()=>{if(!projectionBusy)loadScene({label:currentProjectionLabel()})};applyProjectionLock();
  }

  ensureProjectionProgressUI();bindProjectionActions();
  window.spRefreshSessionCatalog=refreshSessionCatalog;window.spBindProjectionActions=bindProjectionActions;window.spProjectionBusy=()=>projectionBusy;
})();
