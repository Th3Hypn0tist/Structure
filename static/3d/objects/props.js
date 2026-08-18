// Generic collapsible property/list group attached to a scene object.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.Group || !S3D?.PropsItem) throw new Error('S3D Group and PropsItem must load before props');

  class Props extends S3D.Group {
    constructor({ id, attachTo = null, offset = [0, 0, 0], gap = .05, collapsed = false, metadata = {} } = {}) {
      super({ id, gap, collapsed, metadata });
      this.attachTo = attachTo;
      this.offset = [...offset];
    }
    addItem(item) {
      if (!(item instanceof S3D.PropsItem)) throw new Error('Props accepts PropsItem children');
      return this.add(item);
    }
    worldPosition() {
      const base = this.attachTo?.worldPosition?.() ?? super.worldPosition();
      return base.map((component, index) => component + this.offset[index]);
    }
  }

  S3D.Props = Props;
})();
