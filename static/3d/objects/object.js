// Base scene object. Contains spatial/runtime presentation state only.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D) throw new Error('S3D core must load before objects/object');

  function vec3(value, fallback) {
    const result = value ?? fallback;
    if (!Array.isArray(result) || result.length !== 3 || result.some(component => typeof component !== 'number' || !Number.isFinite(component))) {
      throw new Error('expected finite [x,y,z]');
    }
    return [...result];
  }

  class SceneObject {
    constructor({ id, position = [0, 0, 0], rotation = [0, 0, 0], scale = [1, 1, 1], visible = true, selectable = true, metadata = {} } = {}) {
      if (typeof id !== 'string' || !id) throw new Error('SceneObject requires a non-empty id');
      this.id = id;
      this.position = vec3(position, [0, 0, 0]);
      this.rotation = vec3(rotation, [0, 0, 0]);
      this.scale = vec3(scale, [1, 1, 1]);
      this.visible = Boolean(visible);
      this.selectable = Boolean(selectable);
      this.metadata = metadata && typeof metadata === 'object' && !Array.isArray(metadata) ? metadata : {};
      this.parent = null;
      this.children = [];
      this.anchors = new Map();
      this.scene = null;
    }
    add(child) {
      if (!(child instanceof SceneObject)) throw new Error('SceneObject child must be a SceneObject');
      if (child === this) throw new Error('SceneObject cannot parent itself');
      if (child.parent) child.parent.remove(child);
      child.parent = this;
      this.children.push(child);
      return child;
    }
    remove(child) {
      const index = this.children.indexOf(child);
      if (index < 0) return null;
      this.children.splice(index, 1);
      child.parent = null;
      return child;
    }
    worldPosition() {
      if (!this.parent) return [...this.position];
      const parent = this.parent.worldPosition();
      return parent.map((component, index) => component + this.position[index]);
    }
    addAnchor(anchor) {
      if (!anchor || typeof anchor.name !== 'string' || !anchor.name) throw new Error('anchor requires a non-empty name');
      if (this.anchors.has(anchor.name)) throw new Error(`anchor already exists: ${anchor.name}`);
      anchor.object = this;
      this.anchors.set(anchor.name, anchor);
      return anchor;
    }
    anchor(name) { return this.anchors.get(name) ?? null; }
    update() {}
    draw() {}
  }

  class Group extends SceneObject {
    constructor(options = {}) {
      super(options);
      this.layout = options.layout ?? null;
      this.gap = Number(options.gap ?? 0);
      this.collapsed = Boolean(options.collapsed);
    }
    setCollapsed(value) { this.collapsed = Boolean(value); return this; }
    layoutRows({
      width,
      rowHeight,
      rowGap = this.gap,
      padding = 0,
      depth = .05,
      itemWidth = width,
      itemHeight = rowHeight,
      itemDepth = depth,
    } = {}) {
      for (const [name, value] of Object.entries({ width, rowHeight, rowGap, padding, depth, itemWidth, itemHeight, itemDepth })) {
        if (!Number.isFinite(value) || value < 0) throw new Error(`Group.layoutRows ${name} must be a non-negative number`);
      }
      const count = this.children.length;
      const rowsHeight = count ? count * rowHeight + Math.max(0, count - 1) * rowGap : 0;
      const height = rowsHeight + padding * 2;
      const top = height / 2 - padding;
      this.children.forEach((child, index) => {
        child.position = [0, top - rowHeight / 2 - index * (rowHeight + rowGap), 0];
        child.scale = [itemWidth / 2, itemHeight / 2, itemDepth];
        child.visible = !this.collapsed;
        child.layoutWidth = itemWidth;
        child.layoutHeight = itemHeight;
      });
      this.layout = { width, height, rowsHeight, rowHeight, rowGap, padding, depth, itemWidth, itemHeight, itemDepth };
      return this.layout;
    }
    update(deltaSeconds, now) {
      for (const child of this.children) if (child.visible !== false) child.update?.(deltaSeconds, now);
    }
    draw(renderer, context = {}) {
      for (const child of this.children) if (child.visible !== false) child.draw?.(renderer, context);
    }
  }

  S3D.SceneObject = SceneObject;
  S3D.Group = Group;
})();
