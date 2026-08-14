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
      .source-load-progress{display:none;margin-top:10px;padding:9px 10px;border:1px solid var(--line);border-radius:8px;background:#05070a}
      .source-load-progress.active{display:block}
      .source-load-progress-head{display:flex;justify-content:space-between;gap:10px;margin-bottom:6px;font-size:10px;color:var(--muted)}
      .source-load-progress-path{max-width:62%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:ui-monospace,monospace}
      .source-load-progress-track{position:relative;height:5px;overflow:hidden;border-radius:999px;background:#111722}
      .source-load-progress-bar{position:absolute;top:0;bottom:0;width:36%;border-radius:999px;background:var(--blue);animation:structureSourceLoad 1.15s ease-in-out infinite}
      @keyframes structureSourceLoad{0%{left:-38%}50%{left:42%}100%{left:102%}}
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

  function installLoadProgress(popup){
    if(!popup||popup.querySelector('[data-source-load-progress]'))return;
    const error=popup.querySelector('.source-error');
    if(!error)return;
    const progress=document.createElement('div');
    progress.className='source-load-progress';
    progress.dataset.sourceLoadProgress='1';
    progress.setAttribute('role','status');
    progress.setAttribute('aria-live','polite');
    progress.innerHTML=`
      <div class="source-load-progress-head">
        <span data-source-load-label>Reading local source and building semantic model…</span>
        <span class="source-load-progress-path" data-source-load-path></span>
      </div>
      <div class="source-load-progress-track" aria-hidden="true"><div class="source-load-progress-bar"></div></div>`;
    error.insertAdjacentElement('beforebegin',progress);

    const use=popup.querySelector('[data-source-use]');
    const type=popup.querySelector('[data-source-type]');
    const path=popup.querySelector('[data-source-path]');
    if(!use||!type)return;

    use.addEventListener('click',()=>{
      if(type.value!=='directory')return;
      progress.querySelector('[data-source-load-path]').textContent=path?.value.trim()||'';
      progress.classList.add('active');
    },{capture:true});

    const stateObserver=new MutationObserver(()=>{
      if(error.textContent.trim()&&use.disabled===false)progress.classList.remove('active');
    });
    stateObserver.observe(error,{childList:true,characterData:true,subtree:true});
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
    installLoadProgress(popup);
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
