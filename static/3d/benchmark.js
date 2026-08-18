// S3D deterministic high-density benchmark data + metrics.
// Structure-independent. Designed to expose renderer scaling regressions early.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D) throw new Error('S3D core must load before benchmark');

  const PRESETS = Object.freeze({
    nodes20k: Object.freeze({ id: 'nodes20k', nodes: 20000, links: 0 }),
    links50k: Object.freeze({ id: 'links50k', nodes: 20000, links: 50000 }),
    links100k: Object.freeze({ id: 'links100k', nodes: 20000, links: 100000 }),
  });

  function lcg(seed = 0x5eed1234) {
    let state = seed >>> 0;
    return () => {
      state = (Math.imul(1664525, state) + 1013904223) >>> 0;
      return state / 0x100000000;
    };
  }

  function nodePositions(count) {
    if (!Number.isInteger(count) || count < 0) throw new Error('benchmark node count must be a non-negative integer');
    const out = new Float32Array(count * 3);
    const side = Math.ceil(Math.cbrt(Math.max(1, count)));
    const spacing = 1.35;
    const center = (side - 1) * spacing * .5;
    for (let index = 0; index < count; index++) {
      const x = index % side;
      const y = Math.floor(index / side) % side;
      const z = Math.floor(index / (side * side));
      const offset = index * 3;
      out[offset] = x * spacing - center;
      out[offset + 1] = y * spacing - center;
      out[offset + 2] = z * spacing - center;
    }
    return out;
  }

  function positionBounds(positions) {
    if (!(positions instanceof Float32Array) || positions.length % 3) throw new Error('benchmark positions must be Float32Array xyz tuples');
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    for (let offset = 0; offset < positions.length; offset += 3) {
      for (let axis = 0; axis < 3; axis++) {
        min[axis] = Math.min(min[axis], positions[offset + axis]);
        max[axis] = Math.max(max[axis], positions[offset + axis]);
      }
    }
    return { min, max };
  }

  function stressEventPath(positions, pointCount = 28, seed = 0xe71e57) {
    if (!Number.isInteger(pointCount) || pointCount < 2) throw new Error('stress event path requires at least two points');
    const { min, max } = positionBounds(positions);
    const random = lcg(seed);
    const out = new Float32Array(pointCount * 3);
    const spanY = max[1] - min[1];
    const spanZ = max[2] - min[2];
    const marginY = spanY * .08;
    const marginZ = spanZ * .08;
    for (let index = 0; index < pointCount; index++) {
      const t = index / (pointCount - 1);
      const offset = index * 3;
      out[offset] = min[0] + (max[0] - min[0]) * t;
      out[offset + 1] = min[1] + marginY + random() * Math.max(0, spanY - marginY * 2);
      out[offset + 2] = min[2] + marginZ + random() * Math.max(0, spanZ - marginZ * 2);
    }
    return out;
  }

  function nearestPathTriggerData(positions, path) {
    if (!(positions instanceof Float32Array) || positions.length % 3) throw new Error('benchmark positions must be Float32Array xyz tuples');
    if (!(path instanceof Float32Array) || path.length < 6 || path.length % 3) throw new Error('benchmark path must contain xyz points');
    const nodeCount = positions.length / 3;
    const segmentCount = path.length / 3 - 1;
    const out = new Float32Array(nodeCount * 2);
    for (let node = 0; node < nodeCount; node++) {
      const px = positions[node * 3];
      const py = positions[node * 3 + 1];
      const pz = positions[node * 3 + 2];
      let bestDistance2 = Infinity;
      let bestProgress = 0;
      for (let segment = 0; segment < segmentCount; segment++) {
        const a = segment * 3;
        const b = a + 3;
        const ax = path[a], ay = path[a + 1], az = path[a + 2];
        const dx = path[b] - ax, dy = path[b + 1] - ay, dz = path[b + 2] - az;
        const length2 = dx * dx + dy * dy + dz * dz || 1;
        const local = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / length2));
        const qx = ax + dx * local, qy = ay + dy * local, qz = az + dz * local;
        const ex = px - qx, ey = py - qy, ez = pz - qz;
        const distance2 = ex * ex + ey * ey + ez * ez;
        if (distance2 < bestDistance2) {
          bestDistance2 = distance2;
          bestProgress = (segment + local) / segmentCount;
        }
      }
      out[node * 2] = bestProgress;
      out[node * 2 + 1] = Math.sqrt(bestDistance2);
    }
    return out;
  }

  function pathPoint(path, progress) {
    const count = path.length / 3;
    if (count < 2) return [0, 0, 0];
    const value = Math.max(0, Math.min(1, progress)) * (count - 1);
    const segment = Math.min(count - 2, Math.floor(value));
    const local = value - segment;
    const a = segment * 3;
    const b = a + 3;
    return [
      path[a] + (path[b] - path[a]) * local,
      path[a + 1] + (path[b + 1] - path[a + 1]) * local,
      path[a + 2] + (path[b + 2] - path[a + 2]) * local,
    ];
  }

  function linkVertices(positions, linkCount, seed = 0x51d3) {
    if (!(positions instanceof Float32Array) || positions.length % 3) throw new Error('benchmark positions must be Float32Array xyz tuples');
    if (!Number.isInteger(linkCount) || linkCount < 0) throw new Error('benchmark link count must be a non-negative integer');
    const nodeCount = positions.length / 3;
    const out = new Float32Array(linkCount * 6);
    if (!nodeCount || !linkCount) return out;
    const random = lcg(seed);
    for (let index = 0; index < linkCount; index++) {
      const source = Math.floor(random() * nodeCount);
      let target = Math.floor(random() * nodeCount);
      if (nodeCount > 1 && target === source) target = (target + 1) % nodeCount;
      const sourceOffset = source * 3;
      const targetOffset = target * 3;
      const outputOffset = index * 6;
      out[outputOffset] = positions[sourceOffset];
      out[outputOffset + 1] = positions[sourceOffset + 1];
      out[outputOffset + 2] = positions[sourceOffset + 2];
      out[outputOffset + 3] = positions[targetOffset];
      out[outputOffset + 4] = positions[targetOffset + 1];
      out[outputOffset + 5] = positions[targetOffset + 2];
    }
    return out;
  }

  function percentile(sorted, amount) {
    if (!sorted.length) return 0;
    const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * amount) - 1));
    return sorted[index];
  }

  class FrameMetrics {
    constructor(limit = 240) {
      this.limit = limit;
      this.frames = [];
      this.last = 0;
    }
    push(now) {
      if (this.last) {
        this.frames.push(now - this.last);
        if (this.frames.length > this.limit) this.frames.shift();
      }
      this.last = now;
    }
    snapshot() {
      if (!this.frames.length) return { fps: 0, avg_ms: 0, p95_ms: 0, p99_ms: 0, samples: 0 };
      const sorted = [...this.frames].sort((a, b) => a - b);
      const avg = this.frames.reduce((sum, value) => sum + value, 0) / this.frames.length;
      return {
        fps: avg > 0 ? 1000 / avg : 0,
        avg_ms: avg,
        p95_ms: percentile(sorted, .95),
        p99_ms: percentile(sorted, .99),
        samples: this.frames.length,
      };
    }
  }

  S3D.Benchmark = Object.freeze({
    presets: PRESETS,
    nodePositions,
    positionBounds,
    stressEventPath,
    nearestPathTriggerData,
    pathPoint,
    linkVertices,
    FrameMetrics,
  });
})();
