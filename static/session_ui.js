'use strict';

(function installStructureSessionUI(){
  function semanticStyles(){return S.catalog?.projection_styles||[]}
  function visualStyles(){return S.catalog?.visual_styles||S.catalog?.styles||[]}
  function masters(){return S.catalog?.masters||[]}
  function masterFor(inst){return masters().find(m=>m.id===inst.master_ref)||masters()[0]||null}
  function semanticFor(inst){return semanticStyles().find(s=>s.id===inst.semantic_projection_style)||semanticStyles()[0]||null}
  function visualFor(inst){return visualStyles().find(s=>s.id===inst.visual_style)||visualStyles()[0]||null}

  function scopeItems(inst){
    const m=masterFor(inst),type=inst.scope_type;
    if(!m)return[];
    if(type==='event')return m.scopes?.events||[];
    if(type==='flow')return m.scopes?.flows||[];
    if(type==='identity')return m.scopes?.identities||[];
    if(type==='all')return[{id:'all',name:'all',label:'all'}];
    return (m.scopes?.topics||[]).filter(x=>x.id==='all'||x.canonical_topic===true);
  }

  function opt(items,selected,labelFn=x=>x.label||x.name||x.id){
    return(items||[]).map(x=>`<option value="${esc(x.id)}" ${String(x.id)===String(selected)?'selected':''}>${esc(labelFn(x))}</option>`).join('');
  }

  function validScopeType(inst){
    const style=semanticFor(inst),allowed=style?.scope_types||['topic'];
    if(!allowed.includes(inst.scope_type))inst.scope_type=allowed[0]||'topic';
    const items=scopeItems(inst);
    if(!items.some(x=>String(x.id)===String(inst.scope_ref)))inst.scope_ref=String(items[0]?.id||'');
  }

  function preferredDimension(styleId,dims){
    if(!Array.isArray(dims)||!dims.length)return'2d';
    if(styleId==='atlas'&&dims.includes('3d'))return'3d';
    if(dims.length===1)return dims[0];
    return dims.includes('3d')?'3d':dims[0];
  }

  function normalizeVisualDimension(inst){
    const visual=visualFor(inst);
    const dims=visual?.dimensions||['2d'];
    if(!dims.includes(inst.projection_dimension)){
      inst.projection_dimension=preferredDimension(inst.visual_style,dims);
    }
    return inst;
  }

  function normalize(inst){
    inst.master_ref ||= masters()[0]?.id||'master-1';
    inst.semantic_projection_style ||= 'topic';
    inst.visual_style ||= inst.projection_style||visualStyles().find(x=>x.id==='atlas')?.id||visualStyles()[0]?.id||'atlas';
    inst.projection_style=inst.visual_style;
    if(!inst.projection_dimension){
      const dims=visualFor(inst)?.dimensions||['2d'];
      inst.projection_dimension=preferredDimension(inst.visual_style,dims);
    }
    normalizeVisualDimension(inst);
    inst.relation_depth=Math.max(0,Math.min(32,Number(inst.relation_depth??inst.dependency_depth??0)||0));
    inst.dependency_depth=inst.relation_depth;
    inst.scope_type ||= inst.semantic_projection_style==='impact'?'event':'topic';
    inst.scope_ref ||= inst.root_topic||'';
    validScopeType(inst);
    inst.root_topic=inst.scope_ref;
    return inst;
  }

  const oldNewInstance=newInstance;
  newInstance=function(){
    if(!S.sourceSpec||!masters().length)throw new Error('Select a source before creating a projection.');
    const base=oldNewInstance();
    base.master_ref=masters()[0].id;
    base.semantic_projection_style='topic';
    base.visual_style=visualStyles().find(x=>x.id==='atlas')?.id||visualStyles()[0]?.id||'atlas';
    base.projection_style=base.visual_style;
    base.projection_dimension='3d';
    base.scope_type='topic';
    base.scope_ref='';
    base.relation_depth=0;
    return normalize(base);
  };

  instancePayload=function(){return S.instances.map(raw=>{
    const i=normalize(raw);
    return {
      id:i.id,
      name:i.name,
      master_ref:i.master_ref,
      semantic_projection_style:i.semantic_projection_style,
      scope_type:i.scope_type,
      scope_ref:i.scope_ref,
      visual_style:i.visual_style,
      projection_dimension:i.projection_dimension,
      relation_depth:i.relation_depth,
      impact_depth:i.impact_depth||32,
    };
  })};

  const oldInstanceHTML=instanceHTML;
  instanceHTML=function(raw){
    const inst=normalize(raw),html=oldInstanceHTML(inst),parser=document.createElement('template');
    parser.innerHTML=html.trim();
    const card=parser.content.firstElementChild,body=card.querySelector('.instance-body');

    const legacyProjection=body.querySelector('[data-key="projection_style"]')?.closest('.grid2');
    const legacyDepth=body.querySelector('[data-key="dependency_depth"]')?.closest('.field');
    if(legacyProjection)legacyProjection.remove();
    if(legacyDepth)legacyDepth.remove();

    const style=semanticFor(inst),scopeTypes=style?.scope_types||['topic'];
    const visual=visualFor(inst),dims=visual?.dimensions||['2d'];
    const controls=document.createElement('div');
    controls.innerHTML=`
      <div class="grid2">
        <div class="field"><label>Master / source</label><select data-session="${inst.id}" data-session-key="master_ref">${opt(masters(),inst.master_ref)}</select></div>
        <div class="field"><label>Projection style</label><select data-session="${inst.id}" data-session-key="semantic_projection_style">${opt(semanticStyles(),inst.semantic_projection_style)}</select></div>
      </div>
      <div class="grid2">
        <div class="field"><label>Scope type</label><select data-session="${inst.id}" data-session-key="scope_type">${scopeTypes.map(v=>`<option value="${esc(v)}" ${v===inst.scope_type?'selected':''}>${esc(v)}</option>`).join('')}</select></div>
        <div class="field"><label>Scope</label><select data-session="${inst.id}" data-session-key="scope_ref">${opt(scopeItems(inst),inst.scope_ref)}</select></div>
      </div>
      <div class="grid3">
        <div class="field"><label>Visual style</label><select data-session="${inst.id}" data-session-key="visual_style">${opt(visualStyles(),inst.visual_style)}</select></div>
        <div class="field"><label>Dimension</label><select data-session="${inst.id}" data-session-key="projection_dimension">${dims.map(v=>`<option value="${v}" ${v===inst.projection_dimension?'selected':''}>${v.toUpperCase()}</option>`).join('')}</select></div>
        <div class="field"><label>${inst.semantic_projection_style==='impact'?'Impact depth':'Relation depth'}</label><input type="number" min="0" max="${inst.semantic_projection_style==='impact'?'64':'32'}" step="1" data-session="${inst.id}" data-session-key="${inst.semantic_projection_style==='impact'?'impact_depth':'relation_depth'}" value="${inst.semantic_projection_style==='impact'?(inst.impact_depth||32):inst.relation_depth}"></div>
      </div>`;
    const nameField=body.querySelector('.field');
    nameField?.insertAdjacentElement('afterend',controls);
    card.querySelector('summary').textContent=`${inst.name} · ${style?.label||inst.semantic_projection_style} · ${masterFor(inst)?.name||inst.master_ref}`;
    return card.outerHTML;
  };

  const oldRenderInstances=renderInstances;
  renderInstances=function(){
    oldRenderInstances();
    $('#instances').querySelectorAll('[data-session]').forEach(el=>{
      el.onchange=()=>{
        const inst=S.instances.find(x=>x.id===el.dataset.session);if(!inst)return;
        const key=el.dataset.sessionKey;
        if(key==='relation_depth'||key==='impact_depth')inst[key]=Math.max(0,Number(el.value)||0);else inst[key]=el.value;
        if(key==='master_ref')inst.scope_ref='';
        if(key==='semantic_projection_style'){inst.scope_type=el.value==='impact'?'event':'topic';inst.scope_ref='';}
        if(key==='scope_type')inst.scope_ref='';
        if(key==='visual_style'){
          inst.projection_style=inst.visual_style;
          const dims=visualFor(inst)?.dimensions||['2d'];
          inst.projection_dimension=preferredDimension(inst.visual_style,dims);
        }
        normalize(inst);
        renderInstances();
        scheduleSceneReload(0);
      };
    });
  };

  async function refreshSessionCatalog(){
    if(!S.sourceSpec)throw new Error('No source/master selected.');
    const q=new URLSearchParams();
    if(S.sourceSpec.type==='directory'){
      q.set('source_type','directory');q.set('source_path',S.sourceSpec.path||'');
    }else{
      q.set('source_type','github');q.set('repo',S.sourceSpec.repo||'');q.set('branch',S.sourceSpec.branch||'main');
    }
    S.catalog=await getJSON(`/api/projection-catalog?${q}`);
    S.instances.forEach(normalize);
    renderInstances();
  }

  loadScene=async function(){
    if(!S.instances.length){
      S.scene=null;
      rebuildRenderer(false);
      renderSceneInfo();
      draw();
      setStatus(S.sourceSpec?'master ready':'choose source');
      return;
    }
    if(!S.sourceSpec){showError(new Error('Projection has no selected source/master.'));return;}

    setStatus('projecting');
    $('#error').textContent='None.';
    try{
      if(!S.catalog?.projection_styles)await refreshSessionCatalog();
      const source=S.sourceSpec;
      const data=await postJSON('/api/scene',{
        sources:[{id:'master-1',name:source.type==='directory'?(source.path||'Directory'):(source.repo||'Repository'),source}],
        instances:instancePayload(),
      });
      S.scene=data.scene;
      S.catalog=data.catalog||S.catalog;
      S.source=data.masters?.[0]?.source||{};
      $('#revision').textContent=(S.source.revision||'').slice(0,12);
      for(const inst of S.instances)ensureLocalState(inst,(S.scene.objects||[]).find(o=>o.instance_id===inst.id));
      syncChannels();
      renderInstances();
      renderChannels();
      rebuildRenderer(false);
      fit(false);
      renderSceneInfo();
      draw();
      const nodeCount=S.scene?.objects?.reduce((n,o)=>n+(o.nodes?.length||0),0)||0;
      setStatus(`${S.instances.length} projection${S.instances.length===1?'':'s'} · ${nodeCount} nodes`);
    }catch(e){showError(e)}
  };

  function bindProjectionActions(){
    const add=$('#addInstance');
    if(add){
      add.onclick=async()=>{
        if(!S.sourceSpec||!masters().length){showError(new Error('Select a source first.'));return;}
        try{
          const inst=newInstance();
          S.instances.push(inst);
          renderInstances();
          await loadScene();
        }catch(e){showError(e)}
      };
    }
    const reload=$('#reload');
    if(reload)reload.onclick=()=>loadScene();
  }

  bindProjectionActions();
  window.spRefreshSessionCatalog=refreshSessionCatalog;
  window.spBindProjectionActions=bindProjectionActions;
})();
