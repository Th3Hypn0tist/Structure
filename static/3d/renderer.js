// Renderer interface for the generic 3D foundation.
// Concrete consumers provide drawing callbacks; this layer has no WebGL/CW dependency.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D) throw new Error('S3D core must load before renderer');

  class Renderer {
    constructor({ box = null, line = null, flow = null, point = null, text = null, primitive = null } = {}) {
      for (const [name, fn] of Object.entries({ box, line, flow, point, text, primitive })) {
        if (fn !== null && typeof fn !== 'function') throw new Error(`Renderer ${name} callback must be a function or null`);
      }
      this.handlers = { box, line, flow, point, text, primitive };
    }
    box(...args) { return this.handlers.box?.(...args); }
    line(...args) { return this.handlers.line?.(...args); }
    flow(...args) { return this.handlers.flow?.(...args); }
    point(...args) {
      if (this.handlers.point) return this.handlers.point(...args);
      const [position, scale, color, object, context] = args;
      return this.handlers.box?.(position, scale, color, false, object, context);
    }
    text(...args) { return this.handlers.text?.(...args); }
    primitive(...args) { return this.handlers.primitive?.(...args); }
  }

  S3D.Renderer = Renderer;
})();
