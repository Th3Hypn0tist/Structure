// Reusable frame render store for high-density S3D rendering.
// Logical objects enqueue presentation data here; GPU renderers consume batches.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D) throw new Error('S3D core must load before render_store');

  class FloatStore {
    constructor(initialCapacity = 1024) {
      this.buffer = new Float32Array(Math.max(1, initialCapacity));
      this.length = 0;
    }
    clear() { this.length = 0; }
    ensure(additional) {
      const required = this.length + additional;
      if (required <= this.buffer.length) return;
      let capacity = this.buffer.length;
      while (capacity < required) capacity *= 2;
      const next = new Float32Array(capacity);
      next.set(this.buffer.subarray(0, this.length));
      this.buffer = next;
    }
    push(...values) {
      this.ensure(values.length);
      this.buffer.set(values, this.length);
      this.length += values.length;
    }
    view() { return this.buffer.subarray(0, this.length); }
  }

  class RenderStore {
    constructor() {
      this.solidBoxes = new FloatStore(9 * 1024);
      this.outlineBoxes = new FloatStore(9 * 512);
      this.lines = new FloatStore(6 * 2048);
      this.glyphs = new FloatStore(12 * 4096);
      this.viewProjection = null;
      this.counts = { solidBoxes: 0, outlineBoxes: 0, lineVertices: 0, glyphs: 0 };
    }
    begin(viewProjection) {
      if (!viewProjection || viewProjection.length !== 16) throw new Error('RenderStore.begin requires a 4x4 viewProjection matrix');
      this.viewProjection = viewProjection;
      this.solidBoxes.clear();
      this.outlineBoxes.clear();
      this.lines.clear();
      this.glyphs.clear();
      this.counts.solidBoxes = 0;
      this.counts.outlineBoxes = 0;
      this.counts.lineVertices = 0;
      this.counts.glyphs = 0;
    }
    box(position, scale, color, outline = false) {
      if (!this.viewProjection) throw new Error('RenderStore.box requires begin()');
      const target = outline ? this.outlineBoxes : this.solidBoxes;
      target.push(
        Number(position[0]), Number(position[1]), Number(position[2]),
        Number(scale[0]), Number(scale[1]), Number(scale[2]),
        Number(color[0]), Number(color[1]), Number(color[2]),
      );
      if (outline) this.counts.outlineBoxes += 1;
      else this.counts.solidBoxes += 1;
    }
    line(start, end, color) {
      if (!this.viewProjection) throw new Error('RenderStore.line requires begin()');
      this.lines.push(
        Number(start[0]), Number(start[1]), Number(start[2]), Number(color[0]), Number(color[1]), Number(color[2]),
        Number(end[0]), Number(end[1]), Number(end[2]), Number(color[0]), Number(color[1]), Number(color[2]),
      );
      this.counts.lineVertices += 2;
    }
    glyph(center, size, uvRect, color) {
      if (!this.viewProjection) throw new Error('RenderStore.glyph requires begin()');
      this.glyphs.push(
        Number(center[0]), Number(center[1]), Number(center[2]),
        Number(size[0]), Number(size[1]),
        Number(uvRect[0]), Number(uvRect[1]), Number(uvRect[2]), Number(uvRect[3]),
        Number(color[0]), Number(color[1]), Number(color[2]),
      );
      this.counts.glyphs += 1;
    }
    snapshot() {
      return {
        viewProjection: this.viewProjection,
        solidBoxes: this.solidBoxes.view(),
        outlineBoxes: this.outlineBoxes.view(),
        lines: this.lines.view(),
        glyphs: this.glyphs.view(),
        counts: { ...this.counts },
      };
    }
  }

  S3D.FloatStore = FloatStore;
  S3D.RenderStore = RenderStore;
})();
