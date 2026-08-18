// Generic event/list item. The library does not interpret event semantics.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.SceneObject) throw new Error('S3D SceneObject must load before event_item');

  class EventItem extends S3D.SceneObject {
    constructor({ id, label = '', color = [.42, .25, .09], metadata = {} } = {}) {
      super({ id, metadata });
      this.label = String(label);
      this.color = [...color];
    }
    draw(renderer, context = {}) {
      renderer?.box?.(this.worldPosition(), this.scale, this.color, false, this, context);
    }
  }

  S3D.EventItem = EventItem;
})();
