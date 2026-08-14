'use strict';

// Shared UI runtime bindings used by the renderer, source selector and session UI.
// These are declared once so strict-mode modules can install their concrete
// implementations without relying on implicit globals.
let renderInstances;
let newInstance;
let instancePayload;
let instanceHTML;
let loadScene;
