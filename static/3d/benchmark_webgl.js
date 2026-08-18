// WebGL2 high-density benchmark harness for S3D.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.Benchmark || !S3D?.Mat4 || !S3D?.Vec3) throw new Error('S3D benchmark and math must load before benchmark_webgl');

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
      this.autoAngle = 0;
      this.yawOffset = 0;
      this.pitch = Math.atan(.45);
      this.distance = 64;
      this.target = [0, 0, 0];
      this.pointer = null;
      this.currentPreset = null;
      this.lastReport = 0;
      this.initGeometry();
      this.installInteraction();
    }
    initGeometry() {
      const gl = this.gl;
      const cube = new Float32Array([
        -1,-1,-1, 1,-1,-1, 1,1,-1, -1,-1,-1, 1,1,-1, -1,1,-1,
        -1,-1, 1, 1,1, 1, 1,-1,1, -1,-1,1, -1,1,1, 1,1,1,
        -1,-1,-1, -1,-1,1, 1,-1,1, -1,-1,-1, 1,-1,1, 1,-1,-1,
        -1,1,-1, 1,1,1, -1,1,1, -1,1,-1, 1,1,-1, 1,1,1,
        -1,-1,-1, -1,1,1, -1,-1,1, -1,-1,-1, -1,1,-1, -1,1,1,
        1,-1,-1, 1,-1,1, 1,1,1, 1,-1,-1, 1,1,1, 1,-1,-1, 1,1,1, 1,1,-1,
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
    installInteraction() {
      const canvas = this.canvas;
      canvas.addEventListener('contextmenu', event => event.preventDefault());
      canvas.addEventListener('pointerdown', event => {
        if (event.button !== 0 && event.button !== 2) return;
        this.pointer = { id: event.pointerId, button: event.button, x: event.clientX, y: event.clientY };
        canvas.setPointerCapture(event.pointerId);
        event.preventDefault();
      });
      canvas.addEventListener('pointermove', event => {
        if (!this.pointer || event.pointerId !== this.pointer.id) return;
        const dx = event.clientX - this.pointer.x;
        const dy = event.clientY - this.pointer.y;
        this.pointer.x = event.clientX;
        this.pointer.y = event.clientY;
        if (this.pointer.button === 2) this.orbit(dx, dy);
        else if (this.pointer.button === 0) this.pan(dx, dy);
        event.preventDefault();
      });
      const release = event => {
        if (!this.pointer || event.pointerId !== this.pointer.id) return;
        this.pointer = null;
        if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      };
      canvas.addEventListener('pointerup', release);
      canvas.addEventListener('pointercancel', release);
      canvas.addEventListener('wheel', event => {
        this.zoom(event.deltaY);
        event.preventDefault();
      }, { passive: false });
    }
    orbit(dx, dy) {
      this.yawOffset -= dx * .0025;
      this.pitch = Math.max(-1.48, Math.min(1.48, this.pitch + dy * .0025));
    }
    pan(dx, dy) {
      const yaw = this.autoAngle + this.yawOffset;
      const cp = Math.cos(this.pitch);
      const forward = S3D.Vec3.norm([
        -Math.sin(yaw) * cp,
        -Math.sin(this.pitch),
        -Math.cos(yaw) * cp,
      ]);
      let right = S3D.Vec3.cross(forward, [0, 1, 0]);
      right = S3D.Vec3.length(right) < 1e-6 ? [1, 0, 0] : S3D.Vec3.norm(right);
      const up = S3D.Vec3.norm(S3D.Vec3.cross(right, forward));
      const scale = this.distance * .0015;
      this.target = S3D.Vec3.add(
        this.target,
        S3D.Vec3.add(S3D.Vec3.mul(right, -dx * scale), S3D.Vec3.mul(up, dy * scale)),
      );
    }
    zoom(deltaY) {
      this.distance = Math.max(3, Math.min(320, this.distance * Math.exp(deltaY * .001)));
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
    cameraPosition() {
      const yaw = this.autoAngle + this.yawOffset;
      const cp = Math.cos(this.pitch);
      return [
        this.target[0] + Math.sin(yaw) * cp * this.distance,
        this.target[1] + Math.sin(this.pitch) * this.distance,
        this.target[2] + Math.cos(yaw) * cp * this.distance,
      ];
    }
    viewProjection() {
      const aspect = this.canvas.width / Math.max(1, this.canvas.height);
      return S3D.Mat4.multiply(
        S3D.Mat4.perspective(55, aspect, .1, 500),
        S3D.Mat4.lookAt(this.cameraPosition(), this.target),
      );
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
          'mouse:',
          '- LMB drag: pan',
          '- RMB drag: orbit',
          '- wheel: zoom',
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
      this.autoAngle = now * 0.00008;
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
