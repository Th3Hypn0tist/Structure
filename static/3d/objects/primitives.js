// Generic drawable primitive descriptors.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.SceneObject) throw new Error('S3D SceneObject must load before primitives');

  class Primitive extends S3D.SceneObject {
    constructor({ primitive = 'box', color = [.5, .5, .5], outline = false, ...options } = {}) {
      super(options);
      this.primitive = primitive;
      this.color = [...color];
      this.outline = Boolean(outline);
    }
    draw(renderer, context = {}) {
      if (!renderer) return;
      const position = this.worldPosition();
      if (this.primitive === 'box') renderer.box?.(position, this.scale, this.color, this.outline, this, context);
      else if (this.primitive === 'point') renderer.point?.(position, this.scale, this.color, this, context);
      else renderer.primitive?.(this, context);
    }
  }

  class Box extends Primitive {
    constructor(options = {}) { super({ ...options, primitive: 'box' }); }
  }

  class Point extends Primitive {
    constructor(options = {}) { super({ ...options, primitive: 'point' }); }
  }

  S3D.Primitive = Primitive;
  S3D.Box = Box;
  S3D.Point = Point;
})();
