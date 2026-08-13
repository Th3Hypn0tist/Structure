'use strict';

// Projection layout memory is viewer state only. Instance transform, root,
// relation depth and colors remain shared across projection styles. Layout
// controls are remembered independently per `${projection_style}:${dimension}`.
const SP_memoryEnsureLocalState = ensureLocalState;
const SP_memoryRenderInstances = renderInstances;

function spProjectionMemoryKey(instance) {
  const style = String(instance?.projection_style || 'atlas');
  const dimension = String(instance?.projection_dimension || '2d').toLowerCase();
  return `${style}:${dimension}`;
}

function spCloneProjectionState(value) {
  const source = value || projectionDefaults();
  return {
    spread_x: Number.isFinite(Number(source.spread_x)) ? Number(source.spread_x) : 1,
    spread_y: Number.isFinite(Number(source.spread_y)) ? Number(source.spread_y) : 1,
    spread_z: Number.isFinite(Number(source.spread_z)) ? Number(source.spread_z) : 1,
    node_scale: Number.isFinite(Number(source.node_scale)) ? Number(source.node_scale) : 1,
    edge_opacity: Number.isFinite(Number(source.edge_opacity)) ? Number(source.edge_opacity) : .28,
  };
}

function spProjectionMemory(instance, state) {
  state.projection_memory ||= {};
  const key = spProjectionMemoryKey(instance);
  if (!state.projection_memory[key]) {
    state.projection_memory[key] = spCloneProjectionState(projectionDefaults());
  }
  state.projection = state.projection_memory[key];
  state.projection_memory_active = key;
  return state.projection;
}

ensureLocalState = function(instance, obj) {
  const state = SP_memoryEnsureLocalState(instance, obj);
  spProjectionMemory(instance, state);
  return state;
};

function spResetInstanceTransform(instanceId) {
  const state = S.objectState[instanceId];
  if (!state) return;
  state.transform = objectTransformDefaults();
}

renderInstances = function() {
  SP_memoryRenderInstances();

  // The base handlers remain responsible for instance metadata changes and
  // scene reloads. ensureLocalState() switches the active layout memory after
  // style/dimension changes, so returning to a previous combination restores
  // its exact viewer layout values.
  $('#instances').querySelectorAll('[data-proj]').forEach(el => {
    el.oninput = () => {
      const instance = S.instances.find(item => item.id === el.dataset.proj);
      if (!instance) return;
      const obj = (S.scene?.objects || []).find(item => item.instance_id === instance.id);
      const state = ensureLocalState(instance, obj);
      let value = Number(el.value);
      if (!Number.isFinite(value)) return;
      const key = el.dataset.projKey;
      if (key === 'node_scale' || key.startsWith('spread_')) value = Math.max(.05, value);
      if (key === 'edge_opacity') value = Math.max(0, Math.min(1, value));
      state.projection[key] = value;
      state.projection_memory[spProjectionMemoryKey(instance)] = state.projection;
      rebuildRenderer();
    };
  });

  // Reset transform means exactly transform. It deliberately does not clear
  // style/dimension layout memories, root, relation depth or colors.
  $('#instances').querySelectorAll('[data-reset]').forEach(button => {
    button.onclick = () => {
      const instance = S.instances.find(item => item.id === button.dataset.reset);
      if (!instance) return;
      spResetInstanceTransform(instance.id);
      renderInstances();
      rebuildRenderer();
    };
  });
};
