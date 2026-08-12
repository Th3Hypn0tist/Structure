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
})();
