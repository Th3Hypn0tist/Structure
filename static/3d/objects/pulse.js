// Generic transient point travelling from one world position to another.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.SceneObject || !S3D?.Vec3) throw new Error('S3D SceneObject and math must load before pulse');

  class Pulse extends S3D.SceneObject {
    constructor({ id, from = [0, 0, 0], to = [0, 0, 0], progress = 0, color = [1, 1, 1], scale = [.04, .04, .04], metadata = {} } = {}) {
      super({ id, scale, metadata, selectable: false });
      this.from = [...from];
      this.to = [...to];
      this.progress = Number(progress);
      this.color = [...color];
    }
    worldPosition() { return S3D.Vec3.lerp(this.from, this.to, Math.max(0, Math.min(1, this.progress))); }
    draw(renderer, context = {}) { renderer?.box?.(this.worldPosition(), this.scale, this.color, false, this, context); }
  }

  S3D.Pulse = Pulse;
})();
