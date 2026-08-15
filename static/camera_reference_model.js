// Camera reference model intentionally lives separately from semantic rendering.
// Loaded after app.js; replaces only camera interaction handlers.

let lookAtEntityId = null;

function lookAtEntity() {
  return lookAtEntityId ? ws.entities.find(entity => entity.id === lookAtEntityId) || null : null;
}

function ensureCameraReference() {
  if (!Array.isArray(ws.camera.reference) || ws.camera.reference.length !== 3) {
    ws.camera.reference = V.add(ws.camera.position, V.mul(freeForward(), 5));
  }
  return ws.camera.reference;
}

function cameraReference() {
  const entity = lookAtEntity();
  if (entity) {
    ws.camera.reference = [...entity.position];
    return entity.position;
  }
  return ensureCameraReference();
}

function detachLookAtReference() {
  ws.camera.reference = [...cameraReference()];
  lookAtEntityId = null;
  return ws.camera.reference;
}

function referenceForward() {
  const target = cameraReference();
  const direction = V.sub(target, ws.camera.position);
  return V.length(direction) > 1e-6 ? V.norm(direction) : freeForward();
}

function referenceRight() {
  return V.norm(V.cross(referenceForward(), [0, 1, 0]));
}

function referenceUp() {
  return V.norm(V.cross(referenceRight(), referenceForward()));
}

function syncCameraAnglesToReference() {
  const forward = referenceForward();
  ws.camera.yaw = Math.atan2(forward[0], -forward[2]);
  ws.camera.pitch = Math.asin(Math.max(-1, Math.min(1, forward[1])));
}

// Replace the old active-selection camera binding with an explicit reference point.
viewForward = referenceForward;
cameraRight = referenceRight;
cameraUp = referenceUp;
cameraLocalZ = () => V.mul(referenceForward(), -1);
syncCameraAnglesToActive = syncCameraAnglesToReference;

viewProjection = function () {
  const settings = ws.settings.camera_defaults;
  const projection = perspective(
    ws.camera.fov,
    canvas.width / canvas.height,
    settings.near_clip || .05,
    settings.far_clip || 1000,
  );
  return m4(projection, lookAt(ws.camera.position, cameraReference()));
};

beginOrbit = function (clientX, clientY) {
  const target = cameraReference();
  const offset = V.sub(ws.camera.position, target);
  const radius = Math.max(.25, V.length(offset));
  orbit = {
    radius,
    azimuth: Math.atan2(offset[0], offset[2]),
    elevation: Math.asin(Math.max(-1, Math.min(1, offset[1] / radius))),
  };
  last = [clientX, clientY];
};

updateOrbit = function (clientX, clientY) {
  if (!orbit) return;
  const sensitivity = ws.settings.camera_defaults.mouse_sensitivity || .0025;
  const dx = clientX - last[0];
  const dy = clientY - last[1];
  last = [clientX, clientY];

  const target = cameraReference();
  orbit.azimuth -= dx * sensitivity;
  orbit.elevation = Math.max(-1.52, Math.min(1.52, orbit.elevation + dy * sensitivity));
  const horizontal = Math.cos(orbit.elevation) * orbit.radius;
  ws.camera.position = [
    target[0] + Math.sin(orbit.azimuth) * horizontal,
    target[1] + Math.sin(orbit.elevation) * orbit.radius,
    target[2] + Math.cos(orbit.azimuth) * horizontal,
  ];
  syncCameraAnglesToReference();
};

ensureCameraReference();
syncCameraAnglesToReference();

canvas.ondblclick = event => {
  if (event.button !== 0) return;
  const entity = pickEntity(event.clientX, event.clientY);
  if (!entity) return;
  lookAtEntityId = entity.id;
  ws.camera.reference = [...entity.position];
  syncCameraAnglesToReference();
  status(`lookAt: ${entity.id}`);
};

canvas.onwheel = event => {
  event.preventDefault();
  const speed = Number(ws.settings.camera_defaults.wheel_zoom_speed || .15);
  const step = Math.sign(event.deltaY) * speed;
  const target = cameraReference();
  const offset = V.sub(ws.camera.position, target);
  const distance = Math.max(.25, V.length(offset));
  const localZ = V.length(offset) > 1e-6 ? V.norm(offset) : cameraLocalZ();
  const nextDistance = Math.max(.25, distance + step);
  ws.camera.position = V.add(target, V.mul(localZ, nextDistance));
  syncCameraAnglesToReference();
};

canvas.onmousedown = event => {
  if (event.button === 2) {
    beginOrbit(event.clientX, event.clientY);
    return;
  }
  if (event.button !== 0) return;

  const axis = gizmoAxisHit(event.clientX, event.clientY);
  if (axis && selected.size) {
    dragAxis = axis;
    last = [event.clientX, event.clientY];
    return;
  }

  const entity = pickEntity(event.clientX, event.clientY);
  if (linkSource) {
    if (entity && entity.id !== linkSource) {
      linkTarget = entity.id;
      openLinkTypePopup();
      return;
    }
    if (!entity) {
      pan = { x: event.clientX, y: event.clientY, moved: false, referenceDetached: false };
      last = [event.clientX, event.clientY];
    }
    return;
  }

  if (!entity) {
    pan = { x: event.clientX, y: event.clientY, moved: false, referenceDetached: false };
    last = [event.clientX, event.clientY];
    return;
  }

  if (event.ctrlKey || event.shiftKey) {
    if (selected.has(entity.id)) {
      selected.delete(entity.id);
      normalizeActiveSelection();
    } else {
      selected.add(entity.id);
      setActiveEntity(entity.id);
    }
  } else {
    selected = new Set([entity.id]);
    setActiveEntity(entity.id);
  }

  inspect();
  updateButtons();
};

window.onmousemove = event => {
  if (orbit) {
    updateOrbit(event.clientX, event.clientY);
    hovered = null;
    return;
  }

  if (pan) {
    const dx = event.clientX - last[0];
    const dy = event.clientY - last[1];
    const totalDrag = Math.abs(event.clientX - pan.x) + Math.abs(event.clientY - pan.y);
    if (!pan.moved && totalDrag > 2) {
      pan.moved = true;
      detachLookAtReference();
      pan.referenceDetached = true;
    }

    if (pan.moved) {
      const speed = Number(ws.settings.camera_defaults.drag_pan_speed || .01);
      const delta = V.add(
        V.mul(referenceRight(), -dx * speed),
        V.mul(referenceUp(), dy * speed),
      );
      ws.camera.reference = V.add(cameraReference(), delta);
      ws.camera.position = V.add(ws.camera.position, delta);
      syncCameraAnglesToReference();
    }

    last = [event.clientX, event.clientY];
    hovered = null;
    return;
  }

  if (dragAxis && selected.size) {
    const dx = event.clientX - last[0];
    const dy = event.clientY - last[1];
    const amount = (Math.abs(dx) > Math.abs(dy) ? dx : -dy) * .015;
    const axisIndex = { x: 0, y: 1, z: 2 }[dragAxis];
    for (const entity of ws.entities) {
      if (selected.has(entity.id)) entity.position[axisIndex] += amount;
    }
    if (lookAtEntityId && selected.has(lookAtEntityId)) {
      ws.camera.reference = [...cameraReference()];
    }
    syncCameraAnglesToReference();
    last = [event.clientX, event.clientY];
    inspect();
    return;
  }

  hovered = pickEntity(event.clientX, event.clientY)?.id || null;
};
