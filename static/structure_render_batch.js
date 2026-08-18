// Production Structure -> S3D batched rendering bridge.
// Existing semantic projection code keeps calling drawBox/drawLine/drawSceneText3D;
// those calls now enqueue GPU batch data and the final render wrapper flushes once.
(() => {
  if (!globalThis.S3D?.WebGLBatchRenderer) throw new Error('S3D WebGLBatchRenderer must load before Structure batch bridge');
  if (typeof gl === 'undefined' || typeof render !== 'function') throw new Error('Structure GL/render runtime unavailable for batch bridge');

  const renderer = new S3D.WebGLBatchRenderer(gl);
  const legacy = Object.freeze({
    drawBox,
    drawLine,
    drawSceneText3D,
  });
  let frameOpen = false;

  // The bridge is loaded dynamically after Structure has already started its RAF
  // chain. A callback queued before this bridge exists may therefore call the new
  // draw functions once without entering renderWithS3DBatches first. Lazy begin
  // makes that transition frame safe and keeps the rendering API order-independent.
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
  drawSceneText3D = function drawSceneText3DBatched(text, center, width, height, tint = [.93,.96,1]) {
    ensureBatchFrame();
    renderer.text(text, center, width, height, tint);
  };
  function drawFlowBatched(start, end, scale, color, phase = 0, speed = 0) {
    ensureBatchFrame();
    renderer.flow(start, end, scale, color, phase, speed);
  }

  // The generic S3D adapter is loaded before this concrete WebGL renderer.
  // Inject only the generic flow primitive here; no Structure/CW semantics cross
  // into S3D.Link. Flow movement is evaluated by the GPU from time + phase + speed.
  if (window.StructureS3D?.renderer?.handlers) {
    window.StructureS3D.renderer.handlers.flow = drawFlowBatched;
  }

  const renderBeforeBatch = render;
  render = function renderWithS3DBatches() {
    if (!ws) return renderBeforeBatch();
    resize();
    renderer.begin(viewProjection());
    frameOpen = true;
    try {
      const result = renderBeforeBatch();
      const stats = renderer.flush(cameraRight(), cameraUp(), performance.now() / 1000);
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
    stats: () => ({ ...(window.StructureRenderBatchStats ?? renderer.stats) }),
  });
})();
