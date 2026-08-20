// Generic time-bounded highlight state for any scene object.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.SceneObject) throw new Error('S3D SceneObject must load before highlight');

  class Highlight extends S3D.SceneObject {
    constructor({ id, target, color = [1, 1, 1], startedAt = 0, activeEnd = 0, fadeEnd = 0, padding = .03, metadata = {} } = {}) {
      super({ id, selectable: false, metadata });
      if (!target || typeof target.worldPosition !== 'function') throw new Error('Highlight requires a target SceneObject');
      this.target = target;
      this.color = [...color];
      this.startedAt = Number(startedAt);
      this.activeEnd = Number(activeEnd);
      this.fadeEnd = Number(fadeEnd);
      this.padding = Number(padding);
    }
    amount(now) {
      if (now < this.startedAt || now >= this.fadeEnd) return 0;
      if (now <= this.activeEnd || this.fadeEnd <= this.activeEnd) return 1;
      return 1 - (now - this.activeEnd) / (this.fadeEnd - this.activeEnd);
    }
    draw(renderer, context = {}) {
      const amount = this.amount(context.now ?? performance.now());
      if (amount <= 0) return;
      const baseScale = this.target.scale ?? [1, 1, 1];
      const scale = baseScale.map(value => value + this.padding * amount);
      renderer?.box?.(this.target.worldPosition(), scale, this.color, true, this, context);
    }
  }

  S3D.Highlight = Highlight;
})();
