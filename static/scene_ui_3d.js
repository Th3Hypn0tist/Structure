// Shared 3D scene UI primitives. Anything represented inside the scene uses
// world-space geometry; DOM remains reserved for application/editor chrome.

const sceneUiTextProgram = (() => {
  const vs = `#version 300 es
  in vec3 p; in vec2 uvIn; uniform mat4 mvp; out vec2 uv;
  void main(){ uv=uvIn; gl_Position=mvp*vec4(p,1.0); }`;
  const fs = `#version 300 es
  precision highp float; in vec2 uv; uniform sampler2D tex; uniform vec3 tint; out vec4 o;
  void main(){ vec4 sampleColor=texture(tex,uv); o=vec4(tint,sampleColor.a); }`;
  const pgrm = gl.createProgram();
  gl.attachShader(pgrm, compileShader(gl.VERTEX_SHADER, vs));
  gl.attachShader(pgrm, compileShader(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(pgrm);
  if (!gl.getProgramParameter(pgrm, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pgrm));
  return {
    program: pgrm,
    position: gl.getAttribLocation(pgrm,'p'),
    uv: gl.getAttribLocation(pgrm,'uvIn'),
    mvp: gl.getUniformLocation(pgrm,'mvp'),
    tex: gl.getUniformLocation(pgrm,'tex'),
    tint: gl.getUniformLocation(pgrm,'tint'),
  };
})();

const sceneUiQuadBuffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, sceneUiQuadBuffer);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
  -1,-1,0, 0,1,
   1,-1,0, 1,1,
  -1, 1,0, 0,0,
   1, 1,0, 1,0,
]), gl.STATIC_DRAW);

const sceneUiTextCache = new Map();
function sceneUiTextTexture(text) {
  const key = String(text);
  if (sceneUiTextCache.has(key)) return sceneUiTextCache.get(key);
  const canvas2d = document.createElement('canvas');
  canvas2d.width = 512; canvas2d.height = 128;
  const ctx = canvas2d.getContext('2d');
  ctx.clearRect(0,0,canvas2d.width,canvas2d.height);
  ctx.font = '700 54px system-ui,sans-serif';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillStyle = '#ffffff';
  const label = key.length > 36 ? `${key.slice(0,33)}…` : key;
  ctx.fillText(label, canvas2d.width/2, canvas2d.height/2, canvas2d.width-24);
  const texture = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,canvas2d);
  sceneUiTextCache.set(key, texture);
  return texture;
}

function drawSceneText3D(text, center, width, height, tint=[.93,.96,1]) {
  const texture = sceneUiTextTexture(text);
  gl.useProgram(sceneUiTextProgram.program);
  gl.bindBuffer(gl.ARRAY_BUFFER, sceneUiQuadBuffer);
  const stride = 5*4;
  gl.enableVertexAttribArray(sceneUiTextProgram.position);
  gl.vertexAttribPointer(sceneUiTextProgram.position,3,gl.FLOAT,false,stride,0);
  gl.enableVertexAttribArray(sceneUiTextProgram.uv);
  gl.vertexAttribPointer(sceneUiTextProgram.uv,2,gl.FLOAT,false,stride,3*4);
  gl.uniformMatrix4fv(sceneUiTextProgram.mvp,false,new Float32Array(m4(viewProjection(),model(center,[width/2,height/2,1]))));
  gl.uniform3fv(sceneUiTextProgram.tint,tint);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D,texture);
  gl.uniform1i(sceneUiTextProgram.tex,0);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
  gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
  gl.disable(gl.BLEND);
  gl.useProgram(program);
  bindCube();
}

function sceneWorldBoxScreenBounds(center, halfWidth, halfHeight) {
  const vp=viewProjection(), density=devicePixelRatio||1, points=[];
  for(const x of [-halfWidth,halfWidth]) for(const y of [-halfHeight,halfHeight]) {
    const p=project([center[0]+x,center[1]+y,center[2]],vp); if(p)points.push(p);
  }
  if(!points.length)return null;
  return {
    minX:Math.min(...points.map(p=>p[0]))/density,
    maxX:Math.max(...points.map(p=>p[0]))/density,
    minY:Math.min(...points.map(p=>p[1]))/density,
    maxY:Math.max(...points.map(p=>p[1]))/density,
    depth:Math.min(...points.map(p=>p[2])),
  };
}
