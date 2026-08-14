'use strict';

(function installDirectoryBrowse(){
  async function directoryData(path){
    const suffix=path?`?path=${encodeURIComponent(path)}`:'';
    return getJSON(`/api/directories${suffix}`);
  }

  function ensureBrowseStyle(){
    if(document.getElementById('directoryBrowseStyle'))return;
    const style=document.createElement('style');
    style.id='directoryBrowseStyle';
    style.textContent=`
      .directory-browser{margin-top:8px;border:1px solid var(--line);border-radius:9px;overflow:hidden;background:#05070a}
      .directory-browser-head{display:flex;gap:6px;align-items:center;padding:7px;border-bottom:1px solid var(--line)}
      .directory-browser-path{flex:1;min-width:0;font:11px ui-monospace,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--muted)}
      .directory-browser-format{font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:var(--blue);white-space:nowrap}
      .directory-browser-roots{display:flex;gap:5px;overflow-x:auto;padding:6px 7px;border-bottom:1px solid var(--line)}
      .directory-browser-list{max-height:300px;overflow:auto;padding:5px}
      .directory-browser-item{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;width:100%;text-align:left;border:0;border-radius:5px;padding:8px;background:transparent}
      .directory-browser-item:hover{background:#0b1420}
      .directory-browser-item .dir-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .directory-browser-item .dir-format{font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:var(--blue)}
      .directory-path-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px}
      .directory-browser-help{padding:6px 8px;border-top:1px solid var(--line);color:var(--muted);font-size:10px}
    `;
    document.head.appendChild(style);
  }

  function formatLabel(value){
    if(value==='canonical_project_root')return 'Canonical project';
    if(value==='canonical_root')return 'Canonical';
    if(value==='canonical_json_root')return 'Canonical JSON';
    return '';
  }

  function syncDirectoryPath(popup,path){
    const input=popup?.querySelector('[data-source-path]');
    const type=popup?.querySelector('[data-source-type]');
    if(!input)return;
    if(type)type.value='directory';
    input.value=path||'';
    input.dispatchEvent(new Event('input',{bubbles:true}));
  }

  function activateDirectory(popup,path){
    const use=popup?.querySelector('[data-source-use]');
    if(!use)return;
    syncDirectoryPath(popup,path);
    use.click();
  }

  async function renderBrowser(host,path){
    host.innerHTML='<div class="muted" style="padding:9px">Loading directories…</div>';
    try{
      const data=await directoryData(path);
      host.dataset.currentPath=data.path||'';
      syncDirectoryPath(host.closest('.source-popup'),data.path||'');
      const currentFormat=formatLabel(data.source_format);
      host.innerHTML=`
        <div class="directory-browser-head">
          <button type="button" data-dir-parent ${data.parent?'':'disabled'}>↑</button>
          <span class="directory-browser-path" title="${esc(data.path||'')}">${esc(data.path||'')}</span>
          ${currentFormat?`<span class="directory-browser-format">${esc(currentFormat)}</span>`:''}
        </div>
        ${(data.roots||[]).length?`<div class="directory-browser-roots">${data.roots.map(root=>`<button type="button" data-dir-open="${esc(root)}">${esc(root)}</button>`).join('')}</div>`:''}
        <div class="directory-browser-list">
          ${(data.directories||[]).map(item=>{
            const hint=formatLabel(item.source_format);
            return `<button type="button" class="directory-browser-item" data-dir-open="${esc(item.path)}"><span class="dir-name">▸ ${esc(item.name)}</span>${hint?`<span class="dir-format">${esc(hint)}</span>`:''}</button>`;
          }).join('')||'<div class="muted" style="padding:8px">No subdirectories.</div>'}
        </div>
        <div class="directory-browser-help">Click to open · Use source uses the currently open directory · double-click to use immediately</div>`;

      host.querySelector('[data-dir-parent]')?.addEventListener('click',()=>renderBrowser(host,data.parent));
      host.querySelectorAll('[data-dir-open]').forEach(button=>{
        let singleClickTimer=null;
        button.addEventListener('click',()=>{
          clearTimeout(singleClickTimer);
          singleClickTimer=setTimeout(()=>renderBrowser(host,button.dataset.dirOpen),220);
        });
        button.addEventListener('dblclick',event=>{
          event.preventDefault();
          clearTimeout(singleClickTimer);
          activateDirectory(host.closest('.source-popup'),button.dataset.dirOpen);
        });
      });
      const pathEl=host.querySelector('.directory-browser-path');
      if(pathEl){
        pathEl.style.cursor='default';
        pathEl.addEventListener('dblclick',()=>activateDirectory(host.closest('.source-popup'),data.path));
      }
    }catch(error){
      host.innerHTML=`<div class="source-error" style="padding:9px">${esc(error.message||String(error))}</div>`;
    }
  }

  function enhancePopup(popup){
    if(!popup||popup.dataset.directoryBrowseEnhanced==='1')return;
    popup.dataset.directoryBrowseEnhanced='1';
    ensureBrowseStyle();
    const directorySection=popup.querySelector('[data-source-directory]');
    const input=popup.querySelector('[data-source-path]');
    if(!directorySection||!input)return;

    const field=input.closest('.field');
    if(field){
      const row=document.createElement('div');
      row.className='directory-path-row';
      input.parentNode.insertBefore(row,input);
      row.appendChild(input);
      const browse=document.createElement('button');
      browse.type='button';browse.textContent='Browse…';browse.dataset.directoryBrowse='1';row.appendChild(browse);
      const host=document.createElement('div');host.className='directory-browser';host.style.display='none';field.appendChild(host);
      browse.onclick=async()=>{
        host.style.display=host.style.display==='none'?'block':'none';
        if(host.style.display==='block'&&!host.dataset.currentPath){
          await renderBrowser(host,input.value.trim()||null);
        }
      };
      input.addEventListener('change',()=>{host.dataset.currentPath='';});
    }
  }

  const observer=new MutationObserver(()=>{
    const popup=document.querySelector('.source-popup');
    if(popup)enhancePopup(popup);
  });
  observer.observe(document.body,{childList:true,subtree:true});
  enhancePopup(document.querySelector('.source-popup'));
})();

(function installManualProjectionBootstrap(){
  // A source never creates or chooses a semantic projection implicitly.
  // The user must explicitly add the first projection after choosing a source.
  let sourceSpecValue=S.sourceSpec||null;
  let manualProjectionEnabled=false;

  try{
    Object.defineProperty(S,'sourceSpec',{
      configurable:true,
      enumerable:true,
      get(){return sourceSpecValue},
      set(value){
        sourceSpecValue=value;
        manualProjectionEnabled=false;
        S.instances=[];
        S.scene=null;
        S.objectState={};
        S.objectStyle={};
        if(typeof renderInstances==='function')renderInstances();
        const info=document.getElementById('sceneInfo');
        if(info)info.textContent='Source selected. Add a projection instance.';
      },
    });
  }catch(_error){}

  if(typeof spApplyPrimaryDefaults==='function'){
    spApplyPrimaryDefaults=function(){
      if(typeof SP_defaultRootsApplied!=='undefined')SP_defaultRootsApplied=true;
    };
  }

  // No IAM/core/other named preference. A new projection is derived only from
  // the currently loaded source catalog and starts with zero relation expansion.
  newInstance=function(){
    const id=`p${S.nextId++}`;
    const styles=S.catalog?.styles||[];
    const topics=S.catalog?.topics||[];
    const style=styles.find(item=>item.id==='atlas')||styles[0];
    const canonicalTopics=topics.filter(item=>item?.canonical_topic===true);
    const root=canonicalTopics[0]||topics.find(item=>item.id==='all')||topics[0];
    const dimensions=style?.dimensions||['2d'];
    const dimension=dimensions.includes('3d')?'3d':dimensions[0]||'2d';
    return {
      id,
      name:`Projection ${id.slice(1)}`,
      projection_style:style?.id||'atlas',
      projection_dimension:dimension,
      root_topic:root?.id||'all',
      dependency_depth:0,
    };
  };

  // Hide legacy pseudo-topics from the selector. `all` is a projection scope,
  // not a semantic Topic, and remains available explicitly.
  topicOptions=function(selected){
    const topics=(S.catalog?.topics||[]).filter(item=>item.id==='all'||item.canonical_topic===true);
    return topics.map(item=>`<option value="${esc(item.id)}" ${item.id===selected?'selected':''}>${esc(item.label)} (${item.entry_count})</option>`).join('');
  };

  const originalLoadScene=loadScene;
  loadScene=async function(){
    if(!manualProjectionEnabled){
      S.instances=[];
      S.scene=null;
      S.objectState={};
      S.objectStyle={};
      renderInstances();
      renderChannels();
      const canonicalCount=(S.catalog?.topics||[]).filter(item=>item?.canonical_topic===true).length;
      setStatus(canonicalCount?`${canonicalCount} topics · add projection`:'no canonical topics · add projection',canonicalCount===0);
      const info=document.getElementById('sceneInfo');
      if(info)info.textContent=canonicalCount?'Source ready. Add the first projection instance.':'Source loaded, but no Canonical Topics were exposed.';
      return;
    }
    return originalLoadScene();
  };

  const add=document.getElementById('addInstance');
  if(add){
    add.addEventListener('click',()=>{manualProjectionEnabled=true},{capture:true});
  }

  // Suppress the original viewer bootstrap projection even if init() completes
  // after this extension has loaded.
  setTimeout(()=>{
    if(!manualProjectionEnabled){
      S.instances=[];
      S.scene=null;
      S.objectState={};
      S.objectStyle={};
      renderInstances();
      renderChannels();
      setStatus('choose source · add projection');
      const info=document.getElementById('sceneInfo');
      if(info)info.textContent='Choose a source, then add the first projection instance.';
    }
  },0);
})();
