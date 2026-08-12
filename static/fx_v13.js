/* StructureProjector 3D FX renderer override — presentation only. */
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

  const FX_MODES={
    off:{glow:0,extrusion:0,edge_glow:0},
    subtle:{glow:.30,extrusion:20,edge_glow:.18},
    neon:{glow:1.05,extrusion:38,edge_glow:.80}
  };

  function currentFxMode(){
    const p=S.data?.projection;
    if(!p||p.dimension!=='3d')return null;
    const v=S.params.get(S.view)||p.control_values||{};
    const close=(a,b)=>Math.abs(Number(a||0)-Number(b||0))<.051;
    for(const [name,m] of Object.entries(FX_MODES)){
      if(close(v.glow,m.glow)&&close(v.extrusion,m.extrusion)&&close(v.edge_glow,m.edge_glow))return name;
    }
    return 'custom';
  }

  function applyFxMode(name){
    const p=S.data?.projection;
    if(!p||p.dimension!=='3d'||!FX_MODES[name])return;
    const current={...(S.params.get(S.view)||p.control_values||{})};
    Object.assign(current,FX_MODES[name]);
    S.params.set(S.view,current);
    load({keepCamera:true});
  }

  function contentBounds2d(p){
    if(!p)return null;
    if(p.kind==='matrix'){
      const size=Number(p.label_size||0)+(p.order?.length||0)*Number(p.cell_size||0)+60;
      return {x:0,y:0,width:Math.max(1,size),height:Math.max(1,size)};
    }
    const boxes=[];
    for(const g of p.groups||[]){
      if(Number.isFinite(+g.x)&&Number.isFinite(+g.y)&&Number.isFinite(+g.width)&&Number.isFinite(+g.height))boxes.push({x:+g.x,y:+g.y,w:+g.width,h:+g.height});
    }
    for(const n of p.nodes||[]){
      if(Number.isFinite(+n.x)&&Number.isFinite(+n.y)){
        if(Number.isFinite(+n.width)&&Number.isFinite(+n.height))boxes.push({x:+n.x,y:+n.y,w:+n.width,h:+n.height});
        else if(Number.isFinite(+n.radius)){const r=+n.radius;boxes.push({x:+n.x-r,y:+n.y-r,w:r*2,h:r*2});}
      }
    }
    if(!boxes.length)return p.bounds?{x:0,y:0,width:p.bounds.width,height:p.bounds.height}:null;
    let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
    for(const b of boxes){minX=Math.min(minX,b.x);minY=Math.min(minY,b.y);maxX=Math.max(maxX,b.x+b.w);maxY=Math.max(maxY,b.y+b.h);}
    const pad=Math.max(24,Math.min(100,Math.max(maxX-minX,maxY-minY)*.025));
    return {x:minX-pad,y:minY-pad,width:(maxX-minX)+pad*2,height:(maxY-minY)+pad*2};
  }

  window.__spOriginalRender3d = typeof render3d==='function' ? render3d : null;
  render3d=function(){
    const p=S.data?.projection;if(!p)return;
    const scene=$('#scene3d'),nodes=p.nodes||[],pos=new Map(nodes.map(n=>[String(n.id),n]));
    const op=p.style?.edge_opacity??.22,nodeScale=p.style?.node_scale??1,labelScale=p.style?.label_scale??1;
    const glow=p.style?.glow??.65,extrusion=p.style?.extrusion??28,edgeGlow=p.style?.edge_glow??.45;
    $('#space3d').classList.add('fx-space');
    $('#space3d').style.perspective=(p.style?.perspective??1100)+'px';
    let h='';
    for(const g of p.groups||[]){
      if(g.y!==undefined&&p.kind==='layers')h+=`<div class="plane3d fx-plane" style="width:1200px;height:800px;transform:translate3d(-600px,${g.y-400}px,-400px) rotateX(90deg)"></div>`;
    }
    for(const e of p.edges||[]){
      const a=pos.get(String(e.source)),b=pos.get(String(e.target));if(!a||!b)continue;
      const dx=b.x-a.x,dy=b.y-a.y,dz=b.z-a.z,len=Math.sqrt(dx*dx+dy*dy+dz*dz),yaw=Math.atan2(dz,dx)*180/Math.PI,pitch=-Math.atan2(dy,Math.sqrt(dx*dx+dz*dz))*180/Math.PI;
      const dim=esc(e.dimension||'');
      h+=`<div class="line3d fx-line ${dim}" style="--edge-color:${edgeColor(e.dimension)};--edge-glow:${edgeGlow};opacity:${op};width:${len}px;transform:translate3d(${a.x}px,${a.y}px,${a.z}px) rotateY(${-yaw}deg) rotateZ(${pitch}deg)"></div>`;
    }
    for(const n of nodes){
      const sel=S.selected===n.id?' selected':'';
      const title=esc((n.name||n.id).slice(0,34));
      const sub=esc((n.type||n.source_role||'').slice(0,38));
      h+=`<div class="node3d fx-box${sel}" data-id="${esc(n.id)}" title="${esc(n.name||n.id)}" style="--fx:${fxStatusColor(n.status)};--glow:${glow};--extrusion:${extrusion}px;font-size:${11*labelScale}px;transform:translate3d(${n.x}px,${n.y}px,${n.z}px) translate(-50%,-50%) scale(${nodeScale})"><div class="fx-top"></div><div class="fx-side"></div><div class="fx-front"><span class="fx-title">${title}</span><span class="fx-sub">${sub}</span></div></div>`;
    }
    scene.innerHTML=h;
    scene.querySelectorAll('.node3d').forEach(el=>el.onclick=e=>{e.stopPropagation();const n=pos.get(el.dataset.id);if(n){S.selected=n.id;inspect(n);render3d()}});
    apply3d();
  };

  const originalRenderCanonical2d=typeof renderCanonical2d==='function'?renderCanonical2d:null;
  if(originalRenderCanonical2d){
    renderCanonical2d=function(refit=true){
      originalRenderCanonical2d(false);
      if(refit||!S.cameras.has(S.view)){
        const b=contentBounds2d(S.data?.projection);
        if(b)fitBox(b,.94);else applyCam();
      }else applyCam();
    };
  }

  const fitButton=$('#fit');
  if(fitButton){
    fitButton.addEventListener('click',function(e){
      const p=S.data?.projection;
      if(!p)return;
      e.preventDefault();
      e.stopImmediatePropagation();
      if(p.dimension==='3d'){
        S.z3=1;apply3d();
      }else{
        const b=contentBounds2d(p);if(b)fitBox(b,.94);
      }
    },true);
  }

  const originalRenderControls=typeof renderControls==='function'?renderControls:null;
  if(originalRenderControls){
    renderControls=function(){
      originalRenderControls();
      const p=S.data?.projection;
      if(!p)return;
      const panel=$('#controls');
      if(!panel)return;
      const heading=panel.querySelector('h2');
      const row=document.createElement('div');
      row.className='preset-row sp-fx-mode';

      if(p.dimension!=='3d'){
        row.innerHTML=`<label style="min-width:52px;color:var(--silver);font-size:12px">3D FX</label><div style="flex:1;color:var(--silver);font-size:12px;border:1px solid var(--neutral);border-radius:8px;padding:7px 9px">Available in Galaxy 3D, Role Layers, Dependency Tower, Authority Space and Relation Orbits</div>`;
      }else{
        const mode=currentFxMode();
        row.innerHTML=`<label style="min-width:52px;color:var(--silver);font-size:12px">3D FX</label><select id="spFxMode" style="flex:1"><option value="off" ${mode==='off'?'selected':''}>Off</option><option value="subtle" ${mode==='subtle'?'selected':''}>Subtle</option><option value="neon" ${mode==='neon'?'selected':''}>Neon</option><option value="custom" ${mode==='custom'?'selected':''} disabled>Custom</option></select>`;
      }

      if(heading&&heading.nextSibling)panel.insertBefore(row,heading.nextSibling);else panel.prepend(row);
      const selector=row.querySelector('#spFxMode');
      if(selector)selector.onchange=e=>applyFxMode(e.target.value);
    };
  }
})();
