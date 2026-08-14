'use strict';

(function installExplicitSourceSelector(){
  const SUGGESTED_REPO='Th3Hypn0tist/AIGMos-CW';

  function sourceQuery(spec){
    const q=new URLSearchParams();
    if(spec.type==='directory'){
      q.set('source_type','directory');
      q.set('source_path',spec.path||'');
    }else{
      q.set('source_type','github');
      q.set('repo',spec.repo||SUGGESTED_REPO);
      q.set('branch',spec.branch||'main');
    }
    return q.toString();
  }

  function sourceLabel(spec){
    if(!spec)return 'Select source';
    if(spec.type==='directory'){
      const parts=String(spec.path||'').replace(/\\/g,'/').split('/').filter(Boolean);
      return `Source · ${parts.at(-1)||'Directory'}`;
    }
    return `Source · ${spec.repo||SUGGESTED_REPO} · ${spec.branch||'main'}`;
  }

  function ensureStyle(){
    if(document.getElementById('explicitSourcePickerStyle'))return;
    const style=document.createElement('style');
    style.id='explicitSourcePickerStyle';
    style.textContent=`
      .source-backdrop{position:fixed;inset:0;z-index:240;background:#0009;display:grid;place-items:center;padding:20px}
      .source-popup{width:min(540px,calc(100vw - 40px));background:#080b10;border:1px solid var(--line);border-radius:12px;box-shadow:0 24px 80px #000;padding:16px}
      .source-popup h2{margin:0 0 14px;font-size:15px}
      .source-popup .source-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
      .source-popup .source-error{min-height:18px;color:var(--red);font-size:11px;margin-top:6px}
      .source-popup .source-note{color:var(--muted);font-size:10px;margin-top:-3px;margin-bottom:9px}
    `;
    document.head.appendChild(style);
  }

  async function refreshBranches(popup){
    const repo=popup.querySelector('[data-source-repo]').value.trim()||SUGGESTED_REPO;
    const select=popup.querySelector('[data-source-branch]');
    const previous=select.value||S.sourceSpec?.branch||'main';
    select.disabled=true;
    select.innerHTML='<option>loading…</option>';
    try{
      const data=await getJSON(`/api/branches?repo=${encodeURIComponent(repo)}`);
      select.innerHTML=(data.branches||[]).map(b=>`<option value="${esc(b.name)}">${esc(b.name)}</option>`).join('');
      select.value=(data.branches||[]).some(b=>b.name===previous)?previous:((data.branches||[]).some(b=>b.name==='main')?'main':data.branches?.[0]?.name||'main');
    }catch(e){
      select.innerHTML=`<option value="${esc(previous)}">${esc(previous)}</option>`;
      popup.querySelector('.source-error').textContent=e.message||String(e);
    }finally{select.disabled=false}
  }

  function showType(popup){
    const type=popup.querySelector('[data-source-type]').value;
    popup.querySelector('[data-source-github]').style.display=type==='github'?'block':'none';
    popup.querySelector('[data-source-directory]').style.display=type==='directory'?'block':'none';
  }

  async function activateSource(candidate,popup){
    const error=popup.querySelector('.source-error');
    const use=popup.querySelector('[data-source-use]');
    error.textContent='';use.disabled=true;
    setStatus(candidate.type==='directory'?'reading source':'loading source');
    try{
      const catalog=await getJSON(`/api/projection-catalog?${sourceQuery(candidate)}`);
      S.sourceSpec=candidate;S.catalog=catalog;S.source=catalog?.masters?.[0]?.source||null;
      S.scene=null;S.instances=[];S.objectState={};S.objectStyle={};S.channelState={};
      const button=document.getElementById('sourcePickerButton');if(button)button.textContent=sourceLabel(candidate);
      const branch=document.getElementById('branch');if(branch&&candidate.type==='github')branch.value=candidate.branch||'main';
      renderInstances();renderChannels();document.getElementById('rootLabels').innerHTML='';
      document.getElementById('revision').textContent=String(S.source?.revision||'').slice(0,12);
      document.getElementById('sceneInfo').textContent='Source loaded as Master 1. Add a projection to create the first projection.';
      setStatus('master ready');draw();return true;
    }catch(e){
      error.textContent=e.message||String(e);setStatus('source error',true);use.disabled=false;return false;
    }
  }

  function openSourcePopup(){
    ensureStyle();
    const spec=S.sourceSpec||{type:'github',repo:SUGGESTED_REPO,branch:'main'};
    const overlay=document.createElement('div');overlay.className='source-backdrop';
    overlay.innerHTML=`<div class="source-popup">
      <h2>Select source</h2>
      <div class="field"><label>Source type</label><select data-source-type><option value="github" ${spec.type==='github'?'selected':''}>GitHub repository</option><option value="directory" ${spec.type==='directory'?'selected':''}>Local directory</option></select></div>
      <div data-source-github>
        <div class="field"><label>Repository</label><input data-source-repo value="${esc(spec.repo||SUGGESTED_REPO)}" placeholder="owner/repository"></div>
        <div class="field"><label>Branch</label><select data-source-branch><option value="${esc(spec.branch||'main')}">${esc(spec.branch||'main')}</option></select></div>
      </div>
      <div data-source-directory>
        <div class="field"><label>Directory path</label><input data-source-path value="${esc(spec.path||'')}" placeholder="C:\\path\\to\\project or /path/to/project"></div>
        <div class="source-note">The Structure server reads this path. WSL/Windows path conversion is handled by the source backend.</div>
      </div>
      <div class="source-error"></div>
      <div class="source-actions"><button type="button" data-source-cancel>Cancel</button><button type="button" data-source-use>Use source</button></div>
    </div>`;
    document.body.appendChild(overlay);
    const popup=overlay.querySelector('.source-popup');showType(popup);
    popup.querySelector('[data-source-type]').onchange=()=>showType(popup);
    popup.querySelector('[data-source-repo]').onchange=()=>refreshBranches(popup);
    popup.querySelector('[data-source-cancel]').onclick=()=>overlay.remove();
    overlay.onclick=e=>{if(e.target===overlay)overlay.remove()};
    popup.querySelector('[data-source-use]').onclick=async()=>{
      const type=popup.querySelector('[data-source-type]').value;
      const candidate=type==='directory'
        ? {type:'directory',path:popup.querySelector('[data-source-path]').value.trim()}
        : {type:'github',repo:popup.querySelector('[data-source-repo]').value.trim()||SUGGESTED_REPO,branch:popup.querySelector('[data-source-branch]').value||'main'};
      if(await activateSource(candidate,popup))overlay.remove();
    };
    if(spec.type==='github')refreshBranches(popup);
  }

  function wire(){
    let button=document.getElementById('sourcePickerButton');
    if(!button){button=document.createElement('button');button.id='sourcePickerButton';const reload=document.getElementById('reload');reload?.parentElement?.insertBefore(button,reload||null)}
    button.textContent=sourceLabel(S.sourceSpec);button.onclick=openSourcePopup;
    const branch=document.getElementById('branch');const label=branch?.closest('label');if(label)label.style.display='none';
  }

  S.sourceSpec=null;
  wire();
  window.structureOpenSourcePicker=openSourcePopup;
})();
