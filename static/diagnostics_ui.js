'use strict';

(function installStructureDiagnostics(){
  function makeHttpError({method,url,status,data,text,requestBody}){
    const serverError=data?.error;
    const message=String(serverError?.message||data?.message||`${method} ${url}: HTTP ${status}`);
    const error=new Error(message);
    error.structureDiagnostic={
      kind:'http',
      method,
      url,
      status,
      error_id:serverError?.id||data?.id||'',
      server_error:serverError||null,
      response:data??text??null,
      request_body:requestBody??null,
    };
    return error;
  }

  async function requestJSON(method,url,body){
    let response;
    try{
      response=await fetch(url,{
        method,
        headers:body===undefined?undefined:{'Content-Type':'application/json'},
        body:body===undefined?undefined:JSON.stringify(body),
      });
    }catch(cause){
      const error=new Error(`${method} ${url}: network request failed`);
      error.cause=cause;
      error.structureDiagnostic={kind:'network',method,url,status:null,request_body:body??null};
      throw error;
    }

    const text=await response.text();
    let data=null;
    if(text){
      try{data=JSON.parse(text)}
      catch{
        const error=new Error(`${method} ${url}: invalid JSON response (${response.status})`);
        error.structureDiagnostic={kind:'invalid_json',method,url,status:response.status,response:text,request_body:body??null};
        throw error;
      }
    }
    if(!response.ok)throw makeHttpError({method,url,status:response.status,data,text,requestBody:body});
    return data;
  }

  getJSON=async function(url){return requestJSON('GET',url)};
  postJSON=async function(url,body){return requestJSON('POST',url,body)};

  function activeProjectionContext(){
    const instances=(S.instances||[]).map(i=>({
      id:i.id,
      name:i.name,
      master_ref:i.master_ref,
      projection_style:i.semantic_projection_style||i.projection_style,
      scope_type:i.scope_type,
      scope_ref:i.scope_ref||i.root_topic,
      visual_style:i.visual_style||i.projection_style,
      dimension:i.projection_dimension,
      relation_depth:i.relation_depth??i.dependency_depth,
      impact_depth:i.impact_depth,
    }));
    return {source:S.sourceSpec||null,instances};
  }

  function row(label,value,mono=false){
    if(value===undefined||value===null||value==='')return'';
    return `<div class="diag-row"><b>${esc(label)}</b><span class="${mono?'diag-mono':''}">${esc(String(value))}</span></div>`;
  }

  function detailBlock(label,value,open=false){
    if(value===undefined||value===null||value==='')return'';
    const text=typeof value==='string'?value:JSON.stringify(value,null,2);
    return `<details class="diag-detail" ${open?'open':''}><summary>${esc(label)}</summary><pre>${esc(text)}</pre></details>`;
  }

  function ensureStyle(){
    if(document.getElementById('structureDiagnosticsStyle'))return;
    const style=document.createElement('style');
    style.id='structureDiagnosticsStyle';
    style.textContent=`
      #error .diag-card{display:grid;gap:7px}
      #error .diag-message{color:#fff;font-weight:700;line-height:1.35;word-break:break-word}
      #error .diag-row{display:grid;grid-template-columns:76px minmax(0,1fr);gap:7px;align-items:start;font-size:10px}
      #error .diag-row b{color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
      #error .diag-row span{min-width:0;overflow-wrap:anywhere}
      #error .diag-mono{font-family:ui-monospace,monospace}
      #error .diag-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:2px}
      #error .diag-actions button{font-size:10px;padding:4px 7px}
      .diag-backdrop{position:fixed;inset:0;z-index:360;background:#000b;display:grid;place-items:center;padding:20px}
      .diag-modal{width:min(980px,calc(100vw - 40px));max-height:calc(100vh - 40px);overflow:auto;background:#080b10;border:1px solid var(--line);border-radius:12px;box-shadow:0 24px 80px #000;padding:14px}
      .diag-modal-head{position:sticky;top:-14px;z-index:1;display:flex;justify-content:space-between;gap:10px;align-items:center;margin:-14px -14px 12px;padding:12px 14px;background:#080b10;border-bottom:1px solid var(--line)}
      .diag-modal-head strong{font-size:13px}
      .diag-modal-summary{display:grid;gap:6px;margin-bottom:10px}
      .diag-modal .diag-detail{border-top:1px solid var(--line);padding:7px 0}
      .diag-modal .diag-detail summary{cursor:pointer;color:var(--blue);font-size:10px;font-weight:700}
      .diag-modal .diag-detail pre{margin:7px 0 0;max-height:420px;overflow:auto;white-space:pre-wrap;word-break:break-word}
      .diag-modal-actions{display:flex;gap:7px;flex-wrap:wrap}
    `;
    document.head.appendChild(style);
  }

  function openDetails({message,diagnostic,context,stack,full}){
    document.querySelector('.diag-backdrop')?.remove();
    const server=diagnostic.server_error||null;
    const stackWithoutMessage=stack.split('\n').filter(line=>line.trim()&&line.trim()!==message&&line.trim()!==`Error: ${message}`).join('\n');
    const overlay=document.createElement('div');
    overlay.className='diag-backdrop';
    overlay.innerHTML=`<div class="diag-modal" role="dialog" aria-modal="true" aria-label="Error diagnostics">
      <div class="diag-modal-head"><strong>Error diagnostics</strong><div class="diag-modal-actions"><button type="button" data-diag-copy>Copy all</button><button type="button" data-diag-close>Close</button></div></div>
      <div class="diag-modal-summary">
        <div class="diag-message">${esc(message)}</div>
        ${row('Error ID',diagnostic.error_id||server?.id,true)}
        ${row('HTTP',diagnostic.status?`${diagnostic.status} ${diagnostic.method||''}`.trim():diagnostic.method,true)}
        ${row('Endpoint',diagnostic.url,true)}
        ${row('Source',context.source?.type==='directory'?context.source?.path:(context.source?.repo?`${context.source.repo} @ ${context.source.branch||'main'}`:''),true)}
        ${context.instances.length===1?row('Projection',`${context.instances[0].projection_style||'?'} · ${context.instances[0].scope_type||'?'}:${context.instances[0].scope_ref||'?'}`,true):row('Projections',context.instances.length)}
      </div>
      ${detailBlock('Server response',diagnostic.response,true)}
      ${detailBlock('Request payload',diagnostic.request_body)}
      ${detailBlock('Projection context',context)}
      ${detailBlock('Client stack',stackWithoutMessage)}
    </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('[data-diag-close]').onclick=()=>overlay.remove();
    overlay.onclick=e=>{if(e.target===overlay)overlay.remove();};
    overlay.querySelector('[data-diag-copy]').onclick=async event=>{
      try{await navigator.clipboard.writeText(JSON.stringify(full,null,2));event.currentTarget.textContent='Copied';}
      catch{event.currentTarget.textContent='Copy failed';}
    };
  }

  showError=function(error){
    console.error(error);
    ensureStyle();
    setStatus('error',true);
    const diagnostic=error?.structureDiagnostic||{};
    const context=activeProjectionContext();
    const message=error?.message||String(error);
    const server=diagnostic.server_error||null;
    const stack=error?.stack||'';
    const full={message,diagnostic,context,stack};
    const errorCount=Array.isArray(diagnostic.response?.errors)?diagnostic.response.errors.length:null;
    const warningCount=Array.isArray(diagnostic.response?.warnings)?diagnostic.response.warnings.length:null;

    $('#error').innerHTML=`<div class="diag-card">
      <div class="diag-message">${esc(message)}</div>
      ${row('Error ID',diagnostic.error_id||server?.id,true)}
      ${row('HTTP',diagnostic.status?`${diagnostic.status} ${diagnostic.method||''}`.trim():diagnostic.method,true)}
      ${errorCount!==null?row('Findings',`${errorCount} errors${warningCount!==null?`, ${warningCount} warnings`:''}`):''}
      <div class="diag-actions"><button type="button" data-diag-details>Details…</button><button type="button" data-diag-copy>Copy diagnostics</button><button type="button" data-diag-clear>Clear</button></div>
    </div>`;

    $('#error').querySelector('[data-diag-details]')?.addEventListener('click',()=>openDetails({message,diagnostic,context,stack,full}));
    $('#error').querySelector('[data-diag-copy]')?.addEventListener('click',async event=>{
      try{await navigator.clipboard.writeText(JSON.stringify(full,null,2));event.currentTarget.textContent='Copied';}
      catch{event.currentTarget.textContent='Copy failed';}
    });
    $('#error').querySelector('[data-diag-clear]')?.addEventListener('click',()=>{$('#error').textContent='None.';});
  };
})();
