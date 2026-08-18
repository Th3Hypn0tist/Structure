// Generic item displayed inside a Props group.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.SceneObject) throw new Error('S3D SceneObject must load before props_item');

  class PropsItem extends S3D.SceneObject {
    constructor({ id, label = '', value = null, color = [.24, .28, .34], metadata = {} } = {}) {
      super({ id, metadata });
      this.label = String(label);
      this.value = value;
      this.color = [...color];
    }
    draw(renderer, context = {}) {
      renderer?.box?.(this.worldPosition(), this.scale, this.color, false, this, context);
    }
  }

  S3D.PropsItem = PropsItem;
})();
