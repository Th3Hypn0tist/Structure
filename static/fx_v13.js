/* StructureProjector universal 3D effect renderer — presentation only. */
(function(){
  function fxStatusColor(status){
    const s=String(status||'').toLowerCase();
    if(s==='unlocked') return '#FFD83D';
    if(s==='locked') return '#087CFF';
    if(s==='validated') return '#AAB2C2';
    if(['superseded','deprecated','rejected','invalid','failed','conflict','error'].includes(s)) return '#FF176B';
    return '#596170';
  }
  function edgeColor(dimension){
    if(dimension==='authority'||dimension==='ownership') return '#FF176B';
    if(dimension==='dependencies') return '#FFD83D';
    if(dimension==='containment') return '#087CFF';
    return '#AAB2C2';
  }

  function effectGroups(){return S.data?.projection?.effect_library?.groups||[];}
  function activeValues(){return S.params.get(S.view)||S.data?.projection?.control_values||{};}
  function renderY(y){return -(Number(y)||0);}

  function currentEffectGroup(){
    const values=activeValues();
    const close=(a,b)=>typeof b==='number'?Math.abs(Number(a??0)-Number(b))<.051:String(a??'')===String(b??'');
    for(const group of effectGroups()){
      const entries=Object.entries(group.values||{});
      if(entries.length&&entries.every(([k,v])=>close(values[k],v)))return group.id;
    }
    return 'custom';
  }

  function applyEffectGroup(groupId){
    const p=S.data?.projection;if(!p)return;
    const group=effectGroups().find(g=>g.id===groupId);if(!group)return;
    const current={...activeValues()};
    Object.assign(current,group.values||{});
    S.params.set(S.view,current);
    load({keepCamera:true});
  }

  window.__spOriginalRender3d = typeof render3d==='function' ? render3d : null;
  render3d=function(){
    const p=S.data?.projection;if(!p)return;
    const scene=$('#scene3d'),space=$('#space3d'),nodes=p.nodes||[],pos=new Map(nodes.map(n=>[String(n.id),n]));
    const local=activeValues();
    const op=local.edge_opacity??p.style?.edge_opacity??.22;
    const nodeScale=local.node_scale??p.style?.node_scale??1;
    const labelScale=local.label_scale??p.style?.label_scale??1;
    const glow=local.glow??p.style?.glow??.65;
    const extrusion=local.extrusion??p.style?.extrusion??40;
    const edgeGlow=local.edge_glow??p.style?.edge_glow??.45;
    const perspective=local.perspective??p.style?.perspective??1100;
    const sceneGlow=local.scene_glow??p.style?.scene_glow??.35;
    const vignette=local.vignette??p.style?.vignette??.65;
    const depthShadow=local.depth_shadow??p.style?.depth_shadow??.65;
    const faceContrast=local.face_contrast??p.style?.face_contrast??.75;

    space.classList.add('fx-space');
    space.style.perspective=perspective+'px';
    space.style.setProperty('--scene-glow',sceneGlow);
    space.style.setProperty('--vignette',vignette);
    space.style.background=`radial-gradient(circle at 50% 44%, rgba(8,124,255,${Math.min(.24,.025+.13*sceneGlow)}), transparent 34%),radial-gradient(circle at 50% 80%, rgba(8,124,255,${Math.min(.12,.012+.06*sceneGlow)}), transparent 40%),#020304`;

    let h='';
    for(const g of p.groups||[]){
      if(g.y!==undefined&&p.kind==='layers')h+=`<div class="plane3d fx-plane" style="width:1200px;height:800px;transform:translate3d(-600px,${renderY(g.y)-400}px,-400px) rotateX(90deg)"></div>`;
    }

    /*
      Projection coordinates use a mathematical right-handed convention where
      +Y is up. CSS translate3d uses +Y down, so the renderer alone performs
      Y_render = -Y_projection. Projection modules never compensate for CSS.

      Nodes are true cuboids. Their visible front face sits at local
      +extrusion/2 on Z, and parent node_scale scales that depth as well.
      Edges therefore use the same front-plane anchor instead of the semantic
      node centre.
    */
    const edgeAnchorZ=(Math.max(0,Number(extrusion)||0)*Math.max(0,Number(nodeScale)||0))/2;

    for(const e of p.edges||[]){
      const a=pos.get(String(e.source)),b=pos.get(String(e.target));if(!a||!b)continue;
      const ax=Number(a.x)||0,ay=renderY(a.y),az=(Number(a.z)||0)+edgeAnchorZ;
      const bx=Number(b.x)||0,by=renderY(b.y),bz=(Number(b.z)||0)+edgeAnchorZ;
      const dx=bx-ax,dy=by-ay,dz=bz-az;
      const len=Math.sqrt(dx*dx+dy*dy+dz*dz),yaw=Math.atan2(dz,dx)*180/Math.PI,pitch=-Math.atan2(dy,Math.sqrt(dx*dx+dz*dz))*180/Math.PI;
      const dim=esc(e.dimension||'');
      h+=`<div class="line3d fx-line ${dim}" style="--edge-color:${edgeColor(e.dimension)};--edge-glow:${edgeGlow};opacity:${op};width:${len}px;transform:translate3d(${ax}px,${ay}px,${az}px) rotateY(${-yaw}deg) rotateZ(${pitch}deg)"></div>`;
    }
    for(const n of nodes){
      const sel=S.selected===n.id?' selected':'';
      const title=esc((n.name||n.id).slice(0,34));
      const sub=esc((n.type||n.source_role||'').slice(0,38));
      h+=`<div class="node3d fx-box${sel}" data-id="${esc(n.id)}" title="${esc(n.name||n.id)}" style="--fx:${fxStatusColor(n.status)};--glow:${glow};--extrusion:${extrusion}px;--depth-shadow:${depthShadow};--face-contrast:${faceContrast};font-size:${11*labelScale}px;transform:translate3d(${n.x}px,${renderY(n.y)}px,${n.z}px) translate(-50%,-50%) scale(${nodeScale})"><div class="fx-face fx-front"><span class="fx-title">${title}</span><span class="fx-sub">${sub}</span></div><div class="fx-face fx-back"></div><div class="fx-face fx-left"></div><div class="fx-face fx-right"></div><div class="fx-face fx-top"></div><div class="fx-face fx-bottom"></div></div>`;
    }
    scene.innerHTML=h;
    scene.querySelectorAll('.node3d').forEach(el=>el.onclick=e=>{e.stopPropagation();const n=pos.get(el.dataset.id);if(n){S.selected=n.id;inspect(n);render3d()}});
    apply3d();
  };

  const fitButton=$('#fit');
  if(fitButton){fitButton.addEventListener('click',function(e){const p=S.data?.projection;if(!p)return;e.preventDefault();e.stopImmediatePropagation();S.z3=1;apply3d();},true);}

  const originalRenderControls=typeof renderControls==='function'?renderControls:null;
  if(originalRenderControls){
    renderControls=function(){
      originalRenderControls();
      const p=S.data?.projection;if(!p)return;
      const panel=$('#controls');if(!panel)return;
      const heading=panel.querySelector('h2'),row=document.createElement('div');
      row.className='preset-row sp-fx-mode';
      const current=currentEffectGroup(),groups=effectGroups();
      const options=groups.map(g=>`<option value="${esc(g.id)}" ${current===g.id?'selected':''}>${esc(g.title||g.id)}</option>`).join('');
      row.innerHTML=`<label style="min-width:78px;color:var(--silver);font-size:12px">Effect Group</label><select id="spEffectGroup" style="flex:1">${options}<option value="custom" ${current==='custom'?'selected':''} disabled>Custom</option></select>`;
      if(heading&&heading.nextSibling)panel.insertBefore(row,heading.nextSibling);else panel.prepend(row);
      const selector=row.querySelector('#spEffectGroup');if(selector)selector.onchange=e=>applyEffectGroup(e.target.value);
    };
  }
})();
