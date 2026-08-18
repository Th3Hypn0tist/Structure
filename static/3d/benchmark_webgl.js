// WebGL2 high-density benchmark harness for S3D.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.Benchmark || !S3D?.Mat4) throw new Error('S3D benchmark and math must load before benchmark_webgl');

  function shader(gl, type, source) {
    const value = gl.createShader(type);
    gl.shaderSource(value, source);
    gl.compileShader(value);
    if (!gl.getShaderParameter(value, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(value) || 'shader compile failed');
    return value;
  }
  function program(gl, vertex, fragment) {
    const value = gl.createProgram();
    gl.attachShader(value, shader(gl, gl.VERTEX_SHADER, vertex));
    gl.attachShader(value, shader(gl, gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(value);
    if (!gl.getProgramParameter(value, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(value) || 'program link failed');
    return value;
  }

  const NODE_VERTEX = `#version 300 es
  layout(location=0) in vec3 p;
  layout(location=1) in vec3 instancePosition;
  uniform mat4 vp;
  uniform float nodeScale;
  void main(){ gl_Position = vp * vec4(instancePosition + p * nodeScale, 1.0); }`;
  const LINK_VERTEX = `#version 300 es
  layout(location=0) in vec3 p;
  uniform mat4 vp;
  void main(){ gl_Position = vp * vec4(p, 1.0); }`;
  const FRAGMENT = `#version 300 es
  precision highp float;
  uniform vec3 color;
  out vec4 outColor;
  void main(){ outColor = vec4(color, 1.0); }`;

  class WebGLBenchmark {
    constructor(canvas, output) {
      this.canvas = canvas;
      this.output = output;
      this.gl = canvas.getContext('webgl2', { antialias: false, alpha: false, depth: true });
      if (!this.gl) throw new Error('WebGL2 required for S3D benchmark');
      this.metrics = new S3D.Benchmark.FrameMetrics(300);
      this.nodeProgram = program(this.gl, NODE_VERTEX, FRAGMENT);
      this.linkProgram = program(this.gl, LINK_VERTEX, FRAGMENT);
      this.nodeVao = this.gl.createVertexArray();
      this.nodeVertexBuffer = this.gl.createBuffer();
      this.nodeInstanceBuffer = this.gl.createBuffer();
      this.linkVao = this.gl.createVertexArray();
      this.linkBuffer = this.gl.createBuffer();
      this.nodeCount = 0;
      this.linkCount = 0;
      this.drawCalls = 0;
      this.uploads = 0;
      this.frameUploads = 0;
      this.running = false;
      this.angle = 0;
      this.radius = 58;
      this.currentPreset = null;
      this.lastReport = 0;
      this.initGeometry();
    }
    initGeometry() {
      const gl = this.gl;
      const cube = new Float32Array([
        -1,-1,-1, 1,-1,-1, 1,1,-1, -1,-1,-1, 1,1,-1, -1,1,-1,
        -1,-1, 1, 1,1, 1, 1,-1,1, -1,-1,1, -1,1,1, 1,1,1,
        -1,-1,-1, -1,-1,1, 1,-1,1, -1,-1,-1, 1,-1,1, 1,-1,-1,
        -1,1,-1, 1,1,1, -1,1,1, -1,1,-1, 1,1,-1, 1,1,1,
        -1,-1,-1, -1,1,1, -1,-1,1, -1,-1,-1, -1,1,-1, -1,1,1,
        1,-1,-1, 1,-1,1, 1,1,1, 1,-1,-1, 1,1,1, 1,1,-1,
      ]);
      gl.bindVertexArray(this.nodeVao);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.nodeVertexBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, cube, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.nodeInstanceBuffer);
      gl.enableVertexAttribArray(1);
      gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
      gl.vertexAttribDivisor(1, 1);

      gl.bindVertexArray(this.linkVao);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.linkBuffer);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
      gl.bindVertexArray(null);
    }
    upload(buffer, data, usage) {
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, data, usage);
      this.uploads += 1;
      this.frameUploads += 1;
    }
    loadPreset(preset) {
      const started = performance.now();
      const positions = S3D.Benchmark.nodePositions(preset.nodes);
      const links = S3D.Benchmark.linkVertices(positions, preset.links);
      this.frameUploads = 0;
      this.upload(this.nodeInstanceBuffer, positions, this.gl.STATIC_DRAW);
      this.upload(this.linkBuffer, links, this.gl.STATIC_DRAW);
      this.nodeCount = preset.nodes;
      this.linkCount = preset.links;
      this.currentPreset = preset;
      this.metrics = new S3D.Benchmark.FrameMetrics(300);
      this.buildMs = performance.now() - started;
      return this.buildMs;
    }
    resize() {
      const density = devicePixelRatio || 1;
      const width = Math.max(1, Math.floor(this.canvas.clientWidth * density));
      const height = Math.max(1, Math.floor(this.canvas.clientHeight * density));
      if (this.canvas.width !== width || this.canvas.height !== height) {
        this.canvas.width = width;
        this.canvas.height = height;
      }
    }
    viewProjection() {
      const aspect = this.canvas.width / Math.max(1, this.canvas.height);
      const camera = [Math.sin(this.angle) * this.radius, this.radius * .45, Math.cos(this.angle) * this.radius];
      return S3D.Mat4.multiply(S3D.Mat4.perspective(55, aspect, .1, 400), S3D.Mat4.lookAt(camera, [0, 0, 0]));
    }
    drawProgram(programValue, color, vp) {
      const gl = this.gl;
      gl.useProgram(programValue);
      gl.uniformMatrix4fv(gl.getUniformLocation(programValue, 'vp'), false, new Float32Array(vp));
      gl.uniform3fv(gl.getUniformLocation(programValue, 'color'), color);
    }
    render(now) {
      this.resize();
      const gl = this.gl;
      const vp = this.viewProjection();
      this.drawCalls = 0;
      this.frameUploads = 0;
      gl.viewport(0, 0, this.canvas.width, this.canvas.height);
      gl.clearColor(.025, .03, .045, 1);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST);
      gl.disable(gl.CULL_FACE);

      if (this.linkCount) {
        this.drawProgram(this.linkProgram, [.12,.20,.30], vp);
        gl.bindVertexArray(this.linkVao);
        gl.drawArrays(gl.LINES, 0, this.linkCount * 2);
        this.drawCalls += 1;
      }

      this.drawProgram(this.nodeProgram, [.18,.52,.88], vp);
      gl.uniform1f(gl.getUniformLocation(this.nodeProgram, 'nodeScale'), .22);
      gl.bindVertexArray(this.nodeVao);
      gl.drawArraysInstanced(gl.TRIANGLES, 0, 36, this.nodeCount);
      this.drawCalls += 1;
      gl.bindVertexArray(null);

      this.metrics.push(now);
      if (now - this.lastReport > 250) {
        this.lastReport = now;
        const metric = this.metrics.snapshot();
        const memory = performance.memory ? `${(performance.memory.usedJSHeapSize / 1048576).toFixed(1)} MB` : 'n/a';
        this.output.textContent = [
          `preset       ${this.currentPreset?.id ?? '-'}`,
          `nodes        ${this.nodeCount.toLocaleString()}`,
          `links        ${this.linkCount.toLocaleString()}`,
          `fps          ${metric.fps.toFixed(1)}`,
          `avg frame    ${metric.avg_ms.toFixed(2)} ms`,
          `p95 frame    ${metric.p95_ms.toFixed(2)} ms`,
          `p99 frame    ${metric.p99_ms.toFixed(2)} ms`,
          `draw calls   ${this.drawCalls}`,
          `uploads/frame ${this.frameUploads}`,
          `uploads total ${this.uploads}`,
          `build        ${(this.buildMs ?? 0).toFixed(1)} ms`,
          `JS heap      ${memory}`,
          '',
          'contract:',
          '- nodes: 1 instanced draw',
          '- links: <= 1 batched draw',
          '- camera-only frame: 0 object uploads',
        ].join('\n');
      }
    }
    frame = now => {
      if (!this.running) return;
      this.angle = now * 0.00008;
      this.render(now);
      requestAnimationFrame(this.frame);
    };
    start() {
      if (this.running) return;
      this.running = true;
      requestAnimationFrame(this.frame);
    }
    stop() { this.running = false; }
  }

  S3D.WebGLBenchmark = WebGLBenchmark;
})();
