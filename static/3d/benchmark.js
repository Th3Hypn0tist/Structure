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
    linkVertices,
    FrameMetrics,
  });
})();
