// Frame-local Structure projection cache.
// Rendering must not rebuild canonical indexes and derived projection collections
// hundreds of times inside one frame. The cache is deliberately frame-scoped:
// authoring may mutate the workspace between frames without explicit invalidation.
(() => {
  if (!window.StructureRenderPipeline || typeof canonicalIndex !== 'function') throw new Error('Structure frame cache requires render pipeline and canonical runtime');

  const state = {
    frame: 0,
    canonicalIndex: null,
    linkProperties: null,
    canonicalLinks: null,
    rulesetMap: null,
    colorSpaceMap: null,
    propertyGroups: null,
    activeLinkProperties: null,
    visibleEntityIds: null,
    layouts: null,
    layoutIndex: null,
    linkSlots: null,
    eventRoutes: null,
    eventRoutesLayouts: null,
    counters: {},
  };

  function count(name) { state.counters[name] = (state.counters[name] ?? 0) + 1; }
  function resetFrame() {
    state.frame += 1;
    state.canonicalIndex = null;
    state.linkProperties = null;
    state.canonicalLinks = null;
    state.rulesetMap = null;
    state.colorSpaceMap = null;
    state.propertyGroups = null;
    state.activeLinkProperties = null;
    state.visibleEntityIds = null;
    state.layouts = null;
    state.layoutIndex = null;
    state.linkSlots = null;
    state.eventRoutes = null;
    state.eventRoutesLayouts = null;
    state.counters = {};
  }

  const canonicalIndexBase = canonicalIndex;
  canonicalIndex = function canonicalIndexCached() {
    if (!state.canonicalIndex) {
      count('canonicalIndex');
      state.canonicalIndex = canonicalIndexBase();
    }
    return state.canonicalIndex;
  };

  const linkPropertiesBase = linkProperties;
  linkProperties = function linkPropertiesCached() {
    if (!state.linkProperties) {
      count('linkProperties');
      state.linkProperties = linkPropertiesBase();
    }
    return state.linkProperties;
  };

  if (typeof canonicalLinks === 'function') {
    const canonicalLinksBase = canonicalLinks;
    canonicalLinks = function canonicalLinksCached() {
      if (!state.canonicalLinks) {
        count('canonicalLinks');
        state.canonicalLinks = canonicalLinksBase();
      }
      return state.canonicalLinks;
    };
  }

  const rulesetMapBase = rulesetMap;
  rulesetMap = function rulesetMapCached() {
    if (!state.rulesetMap) {
      count('rulesetMap');
      state.rulesetMap = rulesetMapBase();
    }
    return state.rulesetMap;
  };

  const colorSpaceMapBase = colorSpaceMap;
  colorSpaceMap = function colorSpaceMapCached() {
    if (!state.colorSpaceMap) {
      count('colorSpaceMap');
      state.colorSpaceMap = colorSpaceMapBase();
    }
    return state.colorSpaceMap;
  };

  if (typeof propertyGroups === 'function') {
    const propertyGroupsBase = propertyGroups;
    propertyGroups = function propertyGroupsCached(index) {
      const canonical = canonicalIndex();
      if (index !== canonical) return propertyGroupsBase(index);
      if (!state.propertyGroups) {
        count('propertyGroups');
        state.propertyGroups = propertyGroupsBase(canonical);
      }
      return state.propertyGroups;
    };
  }

  if (typeof activeLinkProperties === 'function') {
    const activeLinkPropertiesBase = activeLinkProperties;
    activeLinkProperties = function activeLinkPropertiesCached() {
      if (!state.activeLinkProperties) {
        count('activeLinkProperties');
        state.activeLinkProperties = activeLinkPropertiesBase();
      }
      return state.activeLinkProperties;
    };
  }

  if (typeof visibleEntityIds === 'function') {
    const visibleEntityIdsBase = visibleEntityIds;
    visibleEntityIds = function visibleEntityIdsCached() {
      if (!state.visibleEntityIds) {
        count('visibleEntityIds');
        state.visibleEntityIds = visibleEntityIdsBase();
      }
      return state.visibleEntityIds;
    };
  }

  if (typeof buildSceneLayouts === 'function') {
    const buildSceneLayoutsBase = buildSceneLayouts;
    buildSceneLayouts = function buildSceneLayoutsCached(index) {
      if (state.layouts && state.layoutIndex === index) return state.layouts;
      count('buildSceneLayouts');
      state.layouts = buildSceneLayoutsBase(index);
      state.layoutIndex = index;
      return state.layouts;
    };
  }

  if (typeof linkSlots === 'function') {
    const linkSlotsBase = linkSlots;
    linkSlots = function linkSlotsCached() {
      if (!state.linkSlots) {
        count('linkSlots');
        state.linkSlots = linkSlotsBase();
      }
      return state.linkSlots;
    };
  }

  if (typeof allEventRoutes === 'function') {
    const allEventRoutesBase = allEventRoutes;
    allEventRoutes = function allEventRoutesCached(layouts) {
      if (state.eventRoutes && state.eventRoutesLayouts === layouts) return state.eventRoutes;
      count('allEventRoutes');
      state.eventRoutes = allEventRoutesBase(layouts);
      state.eventRoutesLayouts = layouts;
      return state.eventRoutes;
    };
  }

  window.StructureRenderPipeline.addBeforeFrame('frame-cache-reset', resetFrame, -1000);

  window.StructureFrameCache = Object.freeze({
    state,
    reset: resetFrame,
    stats: () => ({ frame: state.frame, ...state.counters }),
  });
})();
