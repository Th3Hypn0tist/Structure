// Generic Anchor-to-Anchor link object. No graph/CW semantics live here.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.SceneObject || !S3D?.Anchor || !S3D?.Vec3) throw new Error('S3D object, anchor and math layers must load before links');

  class Link extends S3D.SceneObject {
    constructor({ id, from, to, color = [.45, .45, .45], flowColor = [.9, .9, .9], flow = true, speed = .15, pulseScale = [.04, .04, .04], metadata = {} } = {}) {
      super({ id, selectable: true, metadata });
      if (!(from instanceof S3D.Anchor) || !(to instanceof S3D.Anchor)) throw new Error('Link endpoints must be Anchor instances');
      this.from = from;
      this.to = to;
      this.color = [...color];
      this.flowColor = [...flowColor];
      this.flow = Boolean(flow);
      this.speed = Number(speed);
      this.pulseScale = [...pulseScale];
      this.phase = 0;
    }
    endpoints() { return { start: this.from.worldPosition(), end: this.to.worldPosition() }; }
    update(deltaSeconds) {
      if (!this.flow) return;
      if (!Number.isFinite(this.speed) || this.speed < 0) throw new Error('Link speed must be non-negative');
      this.phase = (this.phase + Math.max(0, deltaSeconds) * this.speed) % 1;
    }
    pointAt(progress = this.phase) {
      const { start, end } = this.endpoints();
      return S3D.Vec3.lerp(start, end, Math.max(0, Math.min(1, progress)));
    }
    draw(renderer, context = {}) {
      if (!renderer) return;
      const { start, end } = this.endpoints();
      renderer.line?.(start, end, this.color, this, context);
      if (!this.flow) return;
      if (renderer.handlers?.flow || typeof renderer.flow === 'function') {
        renderer.flow?.(start, end, this.pulseScale, this.flowColor, this.phase, this.speed, this, context);
      } else {
        renderer.box?.(this.pointAt(), this.pulseScale, this.flowColor, false, this, context);
      }
    }
  }

  S3D.Link = Link;
})();
