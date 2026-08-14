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
      .directory-browser-roots{display:flex;gap:5px;overflow-x:auto;padding:6px 7px;border-bottom:1px solid var(--line)}
      .directory-browser-list{max-height:260px;overflow:auto;padding:5px}
      .directory-browser-item{display:block;width:100%;text-align:left;border:0;border-radius:5px;padding:7px 8px;background:transparent}
      .directory-browser-item:hover{background:#0b1420}
      .directory-path-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px}
    `;
    document.head.appendChild(style);
  }

  async function renderBrowser(host,path){
    host.innerHTML='<div class="muted" style="padding:9px">Loading directories…</div>';
    try{
      const data=await directoryData(path);
      host.dataset.currentPath=data.path||'';
      host.innerHTML=`
        <div class="directory-browser-head">
          <button data-dir-parent ${data.parent?'':'disabled'}>↑</button>
          <span class="directory-browser-path" title="${esc(data.path||'')}">${esc(data.path||'')}</span>
          <button data-dir-select>Use this folder</button>
        </div>
        ${(data.roots||[]).length?`<div class="directory-browser-roots">${data.roots.map(root=>`<button data-dir-open="${esc(root)}">${esc(root)}</button>`).join('')}</div>`:''}
        <div class="directory-browser-list">
          ${(data.directories||[]).map(item=>`<button class="directory-browser-item" data-dir-open="${esc(item.path)}">▸ ${esc(item.name)}</button>`).join('')||'<div class="muted" style="padding:8px">No subdirectories.</div>'}
        </div>`;
      host.querySelector('[data-dir-parent]')?.addEventListener('click',()=>renderBrowser(host,data.parent));
      host.querySelectorAll('[data-dir-open]').forEach(button=>button.addEventListener('click',()=>renderBrowser(host,button.dataset.dirOpen)));
      host.querySelector('[data-dir-select]')?.addEventListener('click',()=>{
        const popup=host.closest('.source-popup');
        const input=popup?.querySelector('[data-source-path]');
        if(input)input.value=data.path||'';
      });
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
