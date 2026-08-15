const canvas=document.querySelector('#scene');
const gl=canvas.getContext('webgl2',{antialias:true});
if(!gl) throw new Error('WebGL2 required');

const $=s=>document.querySelector(s);
const status=t=>$('#status').textContent=t;
const V={add:(a,b)=>a.map((v,i)=>v+b[i]),sub:(a,b)=>a.map((v,i)=>v-b[i]),mul:(a,s)=>a.map(v=>v*s),dot:(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2],cross:(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],norm:a=>{const l=Math.hypot(...a)||1;return a.map(v=>v/l)}};
function m4mul(a,b){const o=new Array(16).fill(0);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)o[c*4+r]+=a[k*4+r]*b[c*4+k];return o}
function perspective(fov,aspect,n,f){const t=1/Math.tan(fov*Math.PI/360);return [t/aspect,0,0,0,0,t,0,0,0,0,(f+n)/(n-f),-1,0,0,2*f*n/(n-f),0]}
function lookAt(pos,target,up=[0,1,0]){const z=V.norm(V.sub(pos,target)),x=V.norm(V.cross(up,z)),y=V.cross(z,x);return [x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-V.dot(x,pos),-V.dot(y,pos),-V.dot(z,pos),1]}
function model(p,s=1){return [s,0,0,0,0,s,0,0,0,0,s,0,p[0],p[1],p[2],1]}
function project(p,vp){const x=p[0],y=p[1],z=p[2],w=1;const q=[vp[0]*x+vp[4]*y+vp[8]*z+vp[12]*w,vp[1]*x+vp[5]*y+vp[9]*z+vp[13]*w,vp[3]*x+vp[7]*y+vp[11]*z+vp[15]*w];if(q[2]<=0)return null;return [(q[0]/q[2]*.5+.5)*canvas.width,(-q[1]/q[2]*.5+.5)*canvas.height,q[2]]}

const vs=`#version 300 es
in vec3 p; uniform mat4 mvp; uniform vec3 color; out vec3 c; void main(){c=color;gl_Position=mvp*vec4(p,1.0);}`;
const fs=`#version 300 es
precision highp float; in vec3 c; out vec4 o; void main(){o=vec4(c,1.0);}`;
function shader(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s}
const prog=gl.createProgram();gl.attachShader(prog,shader(gl.VERTEX_SHADER,vs));gl.attachShader(prog,shader(gl.FRAGMENT_SHADER,fs));gl.linkProgram(prog);gl.useProgram(prog);
const loc={p:gl.getAttribLocation(prog,'p'),mvp:gl.getUniformLocation(prog,'mvp'),color:gl.getUniformLocation(prog,'color')};
const cube=new Float32Array([-1,-1,-1, 1,-1,-1, 1,1,-1,-1,1,-1,-1,-1,1,1,-1,1,1,1,1,-1,1,1]);
const edges=new Uint16Array([0,1,1,2,2,3,3,0,4,5,5,6,6,7,7,4,0,4,1,5,2,6,3,7]);
const vb=gl.createBuffer(),ib=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vb);gl.bufferData(gl.ARRAY_BUFFER,cube,gl.STATIC_DRAW);gl.enableVertexAttribArray(loc.p);gl.vertexAttribPointer(loc.p,3,gl.FLOAT,false,0,0);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,edges,gl.STATIC_DRAW);
const lineBuf=gl.createBuffer();

let ws={version:'0.1.0',entities:[],camera:{position:[0,1.5,8],yaw:0,pitch:0,fov:60},settings:{camera_defaults:{position:[0,1.5,8],yaw:0,pitch:0,fov:60,movement_speed:6,mouse_sensitivity:.0025,near_clip:.05,far_clip:1000},event_playback:{base_link_speed:.15,active_link_speed:2,effect_travel_duration:1.2}}};
let selected=null,keys=new Set(),looking=false,last=[0,0],dragAxis=null;
function forward(){const c=Math.cos(ws.camera.pitch);return [Math.sin(ws.camera.yaw)*c,Math.sin(ws.camera.pitch),-Math.cos(ws.camera.yaw)*c]}
function right(){return V.norm(V.cross(forward(),[0,1,0]))}
function vp(){const s=ws.settings.camera_defaults;const pr=perspective(ws.camera.fov,canvas.width/canvas.height,s.near_clip||.05,s.far_clip||1000);return m4mul(pr,lookAt(ws.camera.position,V.add(ws.camera.position,forward())))}
function drawLine(a,b,color){gl.bindBuffer(gl.ARRAY_BUFFER,lineBuf);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([...a,...b]),gl.DYNAMIC_DRAW);gl.vertexAttribPointer(loc.p,3,gl.FLOAT,false,0,0);gl.uniformMatrix4fv(loc.mvp,false,new Float32Array(vp()));gl.uniform3fv(loc.color,color);gl.drawArrays(gl.LINES,0,2);gl.bindBuffer(gl.ARRAY_BUFFER,vb);gl.vertexAttribPointer(loc.p,3,gl.FLOAT,false,0,0)}
function render(){resize();gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(.035,.045,.065,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);const VP=vp();for(const e of ws.entities){const M=model(e.position,.45),MVP=m4mul(VP,M);gl.uniformMatrix4fv(loc.mvp,false,new Float32Array(MVP));gl.uniform3fv(loc.color,e.id===selected?[.25,.75,1]:[.62,.68,.78]);gl.drawElements(gl.LINES,edges.length,gl.UNSIGNED_SHORT,0)}if(selected){const e=ws.entities.find(x=>x.id===selected);if(e){const p=e.position,L=1.5;drawLine(p,[p[0]+L,p[1],p[2]],[1,.2,.2]);drawLine(p,[p[0],p[1]+L,p[2]],[.2,1,.2]);drawLine(p,[p[0],p[1],p[2]+L],[.2,.45,1])}}requestAnimationFrame(render)}
function resize(){const d=devicePixelRatio||1,w=Math.floor(canvas.clientWidth*d),h=Math.floor(canvas.clientHeight*d);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h}}
function nearestNode(x,y){const VP=vp(),d=devicePixelRatio||1,px=x*d,py=y*d;let best=null,dist=32*d;for(const e of ws.entities){const s=project(e.position,VP);if(!s)continue;const dd=Math.hypot(s[0]-px,s[1]-py);if(dd<dist){dist=dd;best=e}}return best}
function axisHit(x,y){if(!selected)return null;const e=ws.entities.find(n=>n.id===selected);if(!e)return null;const VP=vp(),d=devicePixelRatio||1,px=x*d,py=y*d;const base=project(e.position,VP);if(!base)return null;const axes={x:[e.position[0]+1.5,e.position[1],e.position[2]],y:[e.position[0],e.position[1]+1.5,e.position[2]],z:[e.position[0],e.position[1],e.position[2]+1.5]};let winner=null,best=18*d;for(const [k,p] of Object.entries(axes)){const s=project(p,VP);if(!s)continue;const vx=s[0]-base[0],vy=s[1]-base[1],wx=px-base[0],wy=py-base[1],t=Math.max(0,Math.min(1,(wx*vx+wy*vy)/(vx*vx+vy*vy||1)));const dd=Math.hypot(px-(base[0]+vx*t),py-(base[1]+vy*t));if(dd<best){best=dd;winner=k}}return winner}
function inspect(){const e=ws.entities.find(x=>x.id===selected);$('#selection').innerHTML=e?`<code>${e.id}</code><br>position ${e.position.map(v=>v.toFixed(2)).join(', ')}`:'No selection'}
canvas.addEventListener('contextmenu',e=>e.preventDefault());
canvas.addEventListener('mousedown',e=>{if(e.button===2){looking=true;last=[e.clientX,e.clientY];return}if(e.button===0){const a=axisHit(e.clientX,e.clientY);if(a){dragAxis=a;last=[e.clientX,e.clientY];return}const n=nearestNode(e.clientX,e.clientY);selected=n?.id||null;inspect()}});
window.addEventListener('mouseup',()=>{looking=false;dragAxis=null});
window.addEventListener('mousemove',e=>{if(looking){const sens=ws.settings.camera_defaults.mouse_sensitivity||.0025;ws.camera.yaw-=(e.clientX-last[0])*sens;ws.camera.pitch=Math.max(-1.55,Math.min(1.55,ws.camera.pitch-(e.clientY-last[1])*sens));last=[e.clientX,e.clientY]}else if(dragAxis&&selected){const n=ws.entities.find(x=>x.id===selected),dx=e.clientX-last[0],dy=e.clientY-last[1],amount=(Math.abs(dx)>Math.abs(dy)?dx:-dy)*.015;const i={x:0,y:1,z:2}[dragAxis];n.position[i]+=amount;last=[e.clientX,e.clientY];inspect()}});
window.addEventListener('keydown',e=>keys.add(e.key.toLowerCase()));window.addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
let prev=performance.now();function tick(t){const dt=Math.min(.05,(t-prev)/1000);prev=t;const sp=(ws.settings.camera_defaults.movement_speed||6)*dt,f=forward(),r=right();if(keys.has('w'))ws.camera.position=V.add(ws.camera.position,V.mul(f,sp));if(keys.has('s'))ws.camera.position=V.sub(ws.camera.position,V.mul(f,sp));if(keys.has('a'))ws.camera.position=V.sub(ws.camera.position,V.mul(r,sp));if(keys.has('d'))ws.camera.position=V.add(ws.camera.position,V.mul(r,sp));if(keys.has('q'))ws.camera.position[1]-=sp;if(keys.has('e'))ws.camera.position[1]+=sp;requestAnimationFrame(tick)}requestAnimationFrame(tick);
$('#add').onclick=()=>{const id=`ENTITY_${String(ws.entities.length+1).padStart(3,'0')}`;ws.entities.push({id,name:id,position:V.add(ws.camera.position,V.mul(forward(),5)),properties:[]});selected=id;inspect();status(`created ${id}`)};
$('#delete').onclick=()=>{if(!selected)return;ws.entities=ws.entities.filter(e=>e.id!==selected);selected=null;inspect();status('deleted')};
$('#save').onclick=async()=>{const r=await fetch('/api/workspace',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(ws)});const j=await r.json();if(!j.ok)throw new Error(j.error);status('saved')};
$('#load').onclick=async()=>{const r=await fetch('/api/workspace');const j=await r.json();if(!j.ok)throw new Error(j.error);ws=j.workspace;syncSettings();selected=null;inspect();status('loaded')};
$('#settingsButton').onclick=()=>$('#settings').hidden=!$('#settings').hidden;
function syncSettings(){const c=ws.settings.camera_defaults,e=ws.settings.event_playback;$('#fov').value=ws.camera.fov;$('#fovValue').value=`${Math.round(ws.camera.fov)}°`;$('#moveSpeed').value=c.movement_speed;$('#mouseSensitivity').value=c.mouse_sensitivity;$('#baseLinkSpeed').value=e.base_link_speed;$('#activeLinkSpeed').value=e.active_link_speed;$('#effectTravel').value=e.effect_travel_duration}
$('#fov').oninput=e=>{ws.camera.fov=Number(e.target.value);$('#fovValue').value=`${e.target.value}°`};$('#moveSpeed').onchange=e=>ws.settings.camera_defaults.movement_speed=Number(e.target.value);$('#mouseSensitivity').onchange=e=>ws.settings.camera_defaults.mouse_sensitivity=Number(e.target.value);$('#baseLinkSpeed').onchange=e=>ws.settings.event_playback.base_link_speed=Number(e.target.value);$('#activeLinkSpeed').onchange=e=>ws.settings.event_playback.active_link_speed=Number(e.target.value);$('#effectTravel').onchange=e=>ws.settings.event_playback.effect_travel_duration=Number(e.target.value);
$('#setCameraDefault').onclick=()=>{const c=ws.settings.camera_defaults;c.position=[...ws.camera.position];c.yaw=ws.camera.yaw;c.pitch=ws.camera.pitch;c.fov=ws.camera.fov;status('camera default set')};$('#resetCamera').onclick=()=>{const c=ws.settings.camera_defaults;ws.camera={position:[...c.position],yaw:c.yaw,pitch:c.pitch,fov:c.fov};syncSettings();status('camera reset')};
syncSettings();render();fetch('/api/health').then(r=>r.json()).then(j=>status(j.ok?'server connected':'server error')).catch(()=>status('server offline'));
