// Frame-local Structure projection cache.
// Rendering must not rebuild canonical indexes and derived projection collections
// hundreds of times inside one frame. Immutable trace-derived indexes may live
// across frames because a trace graph/schedule never mutates after creation.
(() => {
  if (!window.StructureRenderPipeline || typeof canonicalIndex !== 'function') throw new Error('Structure frame cache requires render pipeline and canonical runtime');

  const state = {
    frame: 0,
