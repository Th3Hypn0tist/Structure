// Object-local attachment points for generic object-to-object linking.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D?.Vec3) throw new Error('S3D math must load before anchors');

  class Anchor {
    constructor({ name, position = [0, 0, 0], direction = null, type = null, metadata = {} } = {}) {
      if (typeof name !== 'string' || !name) throw new Error('Anchor requires a non-empty name');
      if (!Array.isArray(position) || position.length !== 3) throw new Error('Anchor position must be [x,y,z]');
      this.name = name;
      this.position = [...position];
      this.direction = direction ? [...direction] : null;
      this.type = type;
      this.metadata = metadata;
      this.object = null;
    }
    worldPosition() {
      if (!this.object) throw new Error(`Anchor ${this.name} is not attached to an object`);
      return S3D.Vec3.add(this.object.worldPosition(), this.position);
    }
  }

  S3D.Anchor = Anchor;
})();
