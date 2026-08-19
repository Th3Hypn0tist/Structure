// Production Structure -> S3D batched rendering bridge.
// Static projection data can be compiled to GPU-resident batches and reused on
// camera-only frames. Until all authoring overlays are resident-aware, the fast
// path is intentionally enabled only for the benchmark workspace.
(() => {
  if (!globalThis.S3D?.WebGLBatchRenderer) throw new Error('S3D WebGLBatchRenderer must load before Structure batch bridge');
  if (typeof gl === 'undefined' || typeof render !== 'function') throw new Error('Structure GL/render runtime unavailable for batch bridge');

  const renderer = new S3D.WebGLBatchRenderer(gl);
  const legacy = Object.freeze({ drawBox, drawLine, drawSceneText3D });
  let frameOpen = false;
  let residentValid = false;
  let residentWorkspace = null;
  let previousDynamic = true;
  let previousSettingsSignature = '';
  let residentCompiles = 0;
  let residentFrames = 0;

  function settingsSignature() {
    if (!ws) return '';
    const view = viewSettings();
    const links = linkSettings();
    return JSON.stringify({
      ruleset_ref: view.ruleset_ref,
      hidden_link_types: view.hidden_link_types,
      event_routes_visible: view.event_routes_visible,
      show_all_props: view.show_all_props,
      property_panel_collapsed: view.property_panel_collapsed,
      node_master_size: view.node_master_size,
      property_panel_size: view.property_panel_size,
      grid_visible: view.grid_visible,
      anchor_spacing: links.anchor_spacing,
      anchor_offset: links.anchor_offset,
      flow_width: links.flow_width,
      base_flow_speed: links.base_flow_speed,
    });
  }

  function residentFastPathEnabled() {
    return Boolean(window.StructureBenchmark?.state?.active);
  }

  function dynamicProjectionActive() {
    if (!ws) return true;
    return Boolean(
      selected?.size ||
      linkSource ||
      linkTarget ||
      dragAxis ||
      boxSelection ||
      causalProjection?.currentEvents?.length
    );
  }

  function invalidateResident(reason = 'unspecified') {
    residentValid = false;
    renderer.invalidatePersistent?.();
    window.StructureRenderResidentReason = reason;
  }

  function ensureBatchFrame() {
    if (frameOpen) return;
    resize();
    renderer.begin(viewProjection());
    frameOpen = true;
  }

  drawBox = function drawBoxBatched(position, scale, color, outline = false) {
    ensureBatchFrame();
    renderer.box(position, scale, color, outline);
  };
  drawLine = function drawLineBatched(start, end, color) {
    ensureBatchFrame();
    renderer.line(start, end, color);
  };

  // Entity names are view labels: keep them camera-facing through the batched
  // billboard text renderer. Node-internal labels (Props/Event rows) are surface
  // UI and must stay attached to the node plane instead of following the camera.
  drawSceneText3D = function drawSceneText3DBatched(text, center, width, height, tint = [.93,.96,1]) {
    ensureBatchFrame();
    renderer.text(text, center, width, height, tint);
  };
  window.drawSceneSurfaceText3D = function drawSceneSurfaceText3D(text, center, width, height, tint = [.93,.96,1]) {
    return legacy.drawSceneText3D(text, center, width, height, tint);
  };

  function drawFlowBatched(start, end, scale, color, phase = 0, speed = 0) {
    ensureBatchFrame();
    renderer.flow(start, end, scale, color, phase, speed);
  }

  if (window.StructureS3D?.renderer?.handlers) window.StructureS3D.renderer.handlers.flow = drawFlowBatched;

  function clearFrame() {
    resize();
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(.035, .045, .065, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);
  }

  function residentFrame() {
    clearFrame();
    const stats = renderer.drawPersistent(viewProjection(), cameraRight(), cameraUp(), performance.now() / 1000);
    residentFrames += 1;
    window.StructureRenderBatchStats = { ...stats, resident: true, residentCompiles, residentFrames };
    requestAnimationFrame(render);
  }

  const renderBeforeBatch = render;
  render = function renderWithS3DBatches() {
    if (!ws) return renderBeforeBatch();

    const allowResident = residentFastPathEnabled();
    const dynamic = !allowResident || dynamicProjectionActive();
    const signature = settingsSignature();

    if (!allowResident && residentValid) invalidateResident('resident_disabled_outside_benchmark');
    if (residentWorkspace !== ws) {
      residentWorkspace = ws;
      invalidateResident('workspace_changed');
    }
    if (signature !== previousSettingsSignature) {
      previousSettingsSignature = signature;
      invalidateResident('projection_settings_changed');
    }
    if (previousDynamic && !dynamic) invalidateResident('dynamic_to_static');
    previousDynamic = dynamic;

    if (!dynamic && residentValid) return residentFrame();

    resize();
    renderer.begin(viewProjection());
    frameOpen = true;
    try {
      const result = renderBeforeBatch();
      let stats;
      if (!dynamic) {
        stats = renderer.flushPersistent(cameraRight(), cameraUp(), performance.now() / 1000);
        residentValid = true;
        residentCompiles += 1;
        stats = { ...stats, resident: false, compiledResident: true, residentCompiles, residentFrames };
      } else {
        invalidateResident(allowResident ? 'dynamic_projection' : 'authoring_dynamic_projection');
        stats = renderer.flush(cameraRight(), cameraUp(), performance.now() / 1000);
        stats = { ...stats, resident: false, residentCompiles, residentFrames };
      }
      window.StructureRenderBatchStats = stats;
      return result;
    } finally {
      frameOpen = false;
    }
  };

  window.StructureRenderBatch = Object.freeze({
    renderer,
    legacy,
    flow: drawFlowBatched,
    surfaceText: window.drawSceneSurfaceText3D,
    invalidate: invalidateResident,
    stats: () => ({ ...(window.StructureRenderBatchStats ?? renderer.stats) }),
    residency: () => ({ residentValid, residentCompiles, residentFrames, reason: window.StructureRenderResidentReason ?? null }),
  });
})();
