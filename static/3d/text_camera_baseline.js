// Camera-space text baseline for persistent S3D glyph batches.
// Individual glyph quads were already billboards, but their string positions were
// authored along world X. This patch stores the per-glyph baseline offset and
// applies it along cameraRight in the vertex shader, so text never mirrors when
// the camera crosses to the opposite side of the scene.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.WebGLBatchRenderer) throw new Error('S3D WebGLBatchRenderer must load before text_camera_baseline');

  function compile(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) || 'text shader compile failed');
    return shader;
  }
  function makeProgram(gl, vertex, fragment) {
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, vertex));
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) || 'text program link failed');
    return program;
  }

  const TEXT_VS = `#version 300 es
  layout(location=0) in vec2 corner;
  layout(location=1) in vec3 center;
  layout(location=2) in vec2 size;
  layout(location=3) in vec4 uvRect;
  layout(location=4) in vec3 inputColor;
  layout(location=5) in float baselineOffset;
  uniform mat4 vp;
  uniform vec3 cameraRight;
  uniform vec3 cameraUp;
  out vec2 uv;
  out vec3 color;
  void main(){
    vec3 world=center
      + cameraRight*(baselineOffset + corner.x*size.x)
      + cameraUp*(corner.y*size.y);
    uv=mix(uvRect.xy,uvRect.zw,corner*.5+.5);
    color=inputColor;
    gl_Position=vp*vec4(world,1.0);
  }`;
  const TEXT_FS = `#version 300 es
  precision highp float;
  uniform sampler2D atlas;
  in vec2 uv;
  in vec3 color;
  out vec4 outColor;
  void main(){ float a=texture(atlas,uv).a; if(a<.025) discard; outColor=vec4(color,a); }`;

  S3D.WebGLBatchRenderer.prototype.initText = function initCameraSpaceText() {
    const gl = this.gl;
    this.textProgram = makeProgram(gl, TEXT_VS, TEXT_FS);
    this.textVao = gl.createVertexArray();
    this.textCornerBuffer = gl.createBuffer();
    this.textInstanceBuffer = gl.createBuffer();
    gl.bindVertexArray(this.textVao);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.textCornerBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.textInstanceBuffer);
    const stride = 13 * 4;
    const spec = [[1,3,0],[2,2,3],[3,4,5],[4,3,9],[5,1,12]];
    for (const [attr, size, offset] of spec) {
      gl.enableVertexAttribArray(attr);
      gl.vertexAttribPointer(attr, size, gl.FLOAT, false, stride, offset * 4);
      gl.vertexAttribDivisor(attr, 1);
    }
    gl.bindVertexArray(null);
    this._persistentUniforms = null;
  };

  S3D.WebGLBatchRenderer.prototype.text = function cameraSpaceText(text, center, width, height, color) {
    const value = String(text ?? '');
    if (!value.length || width <= 0 || height <= 0) return;
    const clipped = value.length > 36 ? `${value.slice(0, 33)}...` : value;
    const charWidth = width / Math.max(1, clipped.length);
    const start = -(clipped.length - 1) * charWidth * .5;
    for (let index = 0; index < clipped.length; index++) {
      const uv = this.atlas.uv(clipped[index]);
      this.store.glyph(center, [charWidth * .52, height * .5], uv, color, start + index * charWidth);
    }
  };
})();
