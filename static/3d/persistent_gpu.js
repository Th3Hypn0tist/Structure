// Persistent GPU residency for S3D WebGLBatchRenderer.
// A compiled scene uploads batch data once; camera/time-only frames redraw the
// resident buffers without rebuilding JS projection data or uploading objects.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.WebGLBatchRenderer) throw new Error('S3D WebGLBatchRenderer must load before persistent_gpu');

  const proto = S3D.WebGLBatchRenderer.prototype;
  if (proto.commitPersistent && proto.drawPersistent) return;

  function uniforms(renderer) {
    if (renderer._persistentUniforms) return renderer._persistentUniforms;
    const gl = renderer.gl;
    renderer._persistentUniforms = {
      boxVp: gl.getUniformLocation(renderer.boxProgram, 'vp'),
      lineVp: gl.getUniformLocation(renderer.lineProgram, 'vp'),
      flowVp: gl.getUniformLocation(renderer.flowProgram, 'vp'),
      flowTime: gl.getUniformLocation(renderer.flowProgram, 'timeSeconds'),
      textVp: gl.getUniformLocation(renderer.textProgram, 'vp'),
      textRight: gl.getUniformLocation(renderer.textProgram, 'cameraRight'),
      textUp: gl.getUniformLocation(renderer.textProgram, 'cameraUp'),
      textAtlas: gl.getUniformLocation(renderer.textProgram, 'atlas'),
    };
    return renderer._persistentUniforms;
  }

  function ensurePersistentBuffers(renderer) {
    if (renderer._persistentBuffers) return renderer._persistentBuffers;
    const gl = renderer.gl;
    renderer._persistentBuffers = {
      solidBoxes: gl.createBuffer(),
      outlineBoxes: gl.createBuffer(),
    };
    renderer._persistentCounts = {
      solidBoxes: 0,
      outlineBoxes: 0,
      lineVertices: 0,
      glyphs: 0,
      flowPulses: 0,
    };
    renderer._persistentResident = false;
    return renderer._persistentBuffers;
  }

  function upload(renderer, buffer, data) {
    const gl = renderer.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    renderer.stats.uploads += 1;
    renderer.stats.uploadBytes = (renderer.stats.uploadBytes ?? 0) + data.byteLength;
  }

  function bindBoxInstances(renderer, instanceBuffer) {
    const gl = renderer.gl;
    gl.bindVertexArray(renderer.boxVao);
    gl.bindBuffer(gl.ARRAY_BUFFER, instanceBuffer);
    const stride = 9 * 4;
    for (let attr = 1; attr <= 3; attr++) {
      gl.enableVertexAttribArray(attr);
      gl.vertexAttribPointer(attr, 3, gl.FLOAT, false, stride, (attr - 1) * 3 * 4);
      gl.vertexAttribDivisor(attr, 1);
    }
  }

  proto.commitPersistent = function commitPersistent() {
    const snapshot = this.store.snapshot();
    const buffers = ensurePersistentBuffers(this);
    this.stats.uploads = 0;
    this.stats.uploadBytes = 0;

    if (snapshot.counts.solidBoxes) upload(this, buffers.solidBoxes, snapshot.solidBoxes);
    if (snapshot.counts.outlineBoxes) upload(this, buffers.outlineBoxes, snapshot.outlineBoxes);
    if (snapshot.counts.lineVertices) upload(this, this.lineBuffer, snapshot.lines);
    if (snapshot.counts.flowPulses) upload(this, this.flowInstanceBuffer, snapshot.flowPulses);
    if (snapshot.counts.glyphs) upload(this, this.textInstanceBuffer, snapshot.glyphs);

    this._persistentCounts = { ...snapshot.counts };
    this._persistentResident = true;
    this.stats.solidBoxes = snapshot.counts.solidBoxes;
    this.stats.outlineBoxes = snapshot.counts.outlineBoxes;
    this.stats.lineVertices = snapshot.counts.lineVertices;
    this.stats.glyphs = snapshot.counts.glyphs;
    this.stats.flowPulses = snapshot.counts.flowPulses;
    return {
      uploads: this.stats.uploads,
      uploadBytes: this.stats.uploadBytes,
      counts: { ...this._persistentCounts },
    };
  };

  proto.drawPersistent = function drawPersistent(viewProjection, cameraRight, cameraUp, nowSeconds = performance.now() / 1000) {
    if (!this._persistentResident) throw new Error('drawPersistent requires commitPersistent() first');
    const gl = this.gl;
    const loc = uniforms(this);
    const buffers = ensurePersistentBuffers(this);
    const counts = this._persistentCounts;
    this.stats.drawCalls = 0;
    this.stats.uploads = 0;
    this.stats.uploadBytes = 0;

    if (counts.lineVertices) {
      gl.useProgram(this.lineProgram);
      gl.uniformMatrix4fv(loc.lineVp, false, new Float32Array(viewProjection));
      gl.bindVertexArray(this.lineVao);
      gl.drawArrays(gl.LINES, 0, counts.lineVertices);
      this.stats.drawCalls += 1;
    }

    if (counts.solidBoxes) {
      gl.useProgram(this.boxProgram);
      gl.uniformMatrix4fv(loc.boxVp, false, new Float32Array(viewProjection));
      bindBoxInstances(this, buffers.solidBoxes);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.boxFaceIndexBuffer);
      gl.drawElementsInstanced(gl.TRIANGLES, this.boxFaces.length, gl.UNSIGNED_SHORT, 0, counts.solidBoxes);
      this.stats.drawCalls += 1;
    }

    if (counts.outlineBoxes) {
      gl.useProgram(this.boxProgram);
      gl.uniformMatrix4fv(loc.boxVp, false, new Float32Array(viewProjection));
      bindBoxInstances(this, buffers.outlineBoxes);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.boxEdgeIndexBuffer);
      gl.drawElementsInstanced(gl.LINES, this.boxEdges.length, gl.UNSIGNED_SHORT, 0, counts.outlineBoxes);
      this.stats.drawCalls += 1;
    }

    if (counts.flowPulses) {
      gl.useProgram(this.flowProgram);
      gl.uniformMatrix4fv(loc.flowVp, false, new Float32Array(viewProjection));
      gl.uniform1f(loc.flowTime, nowSeconds);
      gl.bindVertexArray(this.flowVao);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.boxFaceIndexBuffer);
      gl.drawElementsInstanced(gl.TRIANGLES, this.boxFaces.length, gl.UNSIGNED_SHORT, 0, counts.flowPulses);
      this.stats.drawCalls += 1;
    }

    if (counts.glyphs) {
      gl.useProgram(this.textProgram);
      gl.uniformMatrix4fv(loc.textVp, false, new Float32Array(viewProjection));
      gl.uniform3fv(loc.textRight, cameraRight);
      gl.uniform3fv(loc.textUp, cameraUp);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.atlas.texture);
      gl.uniform1i(loc.textAtlas, 0);
      gl.bindVertexArray(this.textVao);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, counts.glyphs);
      gl.disable(gl.BLEND);
      this.stats.drawCalls += 1;
    }

    gl.bindVertexArray(null);
    this.stats.solidBoxes = counts.solidBoxes;
    this.stats.outlineBoxes = counts.outlineBoxes;
    this.stats.lineVertices = counts.lineVertices;
    this.stats.glyphs = counts.glyphs;
    this.stats.flowPulses = counts.flowPulses;
    return { ...this.stats };
  };

  proto.flushPersistent = function flushPersistent(cameraRight, cameraUp, nowSeconds = performance.now() / 1000) {
    const snapshot = this.store.snapshot();
    const committed = this.commitPersistent();
    const drawn = this.drawPersistent(snapshot.viewProjection, cameraRight, cameraUp, nowSeconds);
    drawn.uploads = committed.uploads;
    drawn.uploadBytes = committed.uploadBytes;
    this.stats.uploads = committed.uploads;
    this.stats.uploadBytes = committed.uploadBytes;
    return drawn;
  };

  proto.invalidatePersistent = function invalidatePersistent() {
    this._persistentResident = false;
  };
})();
