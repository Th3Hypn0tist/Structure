'use strict';

// Viewer-only card enrichment, compact projection-style UI and per-style
// layout memory. It reads only explicit Scene node properties and explicit
// Scene connections. Viewer state never mutates source or Scene semantics.
const SP_originalBuildAtlas = Renderer.prototype.buildAtlas;
const SP_originalBuild = Renderer.prototype.build;
const SP_originalRenderInstances = renderInstances;
const SP_originalLoadScene = loadScene;
