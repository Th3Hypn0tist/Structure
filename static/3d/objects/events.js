// Generic Event collection attached to a scene object.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.Group || !S3D?.EventItem) throw new Error('S3D Group and EventItem must load before events');

  class Events extends S3D.Group {
    constructor({ id, attachTo = null, offset = [0, 0, 0], gap = .05, metadata = {} } = {}) {
      super({ id, gap, metadata });
      this.attachTo = attachTo;
      this.offset = [...offset];
    }
    addItem(item) {
      if (!(item instanceof S3D.EventItem)) throw new Error('Events accepts EventItem children');
      return this.add(item);
    }
    worldPosition() {
      const base = this.attachTo?.worldPosition?.() ?? super.worldPosition();
      return base.map((component, index) => component + this.offset[index]);
    }
  }

  S3D.Events = Events;
})();
