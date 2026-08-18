// Generic 3D math used by the authoring foundation.
(() => {
  const S3D = globalThis.S3D;
  if (!S3D) throw new Error('S3D core must load before math');

  const Vec3 = Object.freeze({
    add: (a, b) => a.map((value, index) => value + b[index]),
    sub: (a, b) => a.map((value, index) => value - b[index]),
    mul: (a, scalar) => a.map(value => value * scalar),
    dot: (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0),
    cross: (a, b) => [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0],
    ],
    length: value => Math.hypot(...value),
    norm: value => {
      const length = Math.hypot(...value);
      if (length <= 1e-12) throw new Error('cannot normalize zero-length vector');
      return value.map(component => component / length);
    },
    lerp: (a, b, t) => a.map((value, index) => value + (b[index] - value) * t),
  });

  const Mat4 = Object.freeze({
    multiply(a, b) {
      const out = new Array(16).fill(0);
      for (let column = 0; column < 4; column++) {
        for (let row = 0; row < 4; row++) {
          for (let k = 0; k < 4; k++) out[column * 4 + row] += a[k * 4 + row] * b[column * 4 + k];
        }
      }
      return out;
    },
    perspective(fov, aspect, near, far) {
      const scale = 1 / Math.tan(fov * Math.PI / 360);
      return [
        scale / aspect, 0, 0, 0,
        0, scale, 0, 0,
        0, 0, (far + near) / (near - far), -1,
        0, 0, 2 * far * near / (near - far), 0,
      ];
    },
    lookAt(position, target) {
      const z = Vec3.norm(Vec3.sub(position, target));
      let x = Vec3.cross([0, 1, 0], z);
      x = Vec3.length(x) < 1e-6 ? [1, 0, 0] : Vec3.norm(x);
      const y = Vec3.cross(z, x);
      return [
        x[0], y[0], z[0], 0,
        x[1], y[1], z[1], 0,
        x[2], y[2], z[2], 0,
        -Vec3.dot(x, position), -Vec3.dot(y, position), -Vec3.dot(z, position), 1,
      ];
    },
    model(position, scale) {
      return [
        scale[0], 0, 0, 0,
        0, scale[1], 0, 0,
        0, 0, scale[2], 0,
        position[0], position[1], position[2], 1,
      ];
    },
    project(point, matrix, width, height) {
      const [x, y, z] = point;
      const clipX = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12];
      const clipY = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13];
      const clipW = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15];
      if (clipW <= 0) return null;
      return [(clipX / clipW * .5 + .5) * width, (-clipY / clipW * .5 + .5) * height, clipW];
    },
  });

  S3D.Vec3 = Vec3;
  S3D.Mat4 = Mat4;
})();
