// High-density causal traversal indexes for Structure.
// This preserves canonical/Event semantics while replacing repeated full-graph
// scans with derived adjacency and trace lookup tables.
(() => {
  if (typeof buildCausalGraph !== 'function' || typeof causalEdgeSchedules !== 'function') {
    throw new Error('causal_perf requires causal_projection');
  }

  const EVENT_ALLOWED = new Set(['event_effect', 'event_output']);
  const EFFECT_ALLOWED = new Set(['effect_target']);
  const ENTITY_ALLOWED = new Set(['event_condition', 'event_input', 'event_read', 'event_cause']);

  function allowedFor(item) {
    const type = item.kind === 'entity' ? 'entity' : item.propertyType;
    if (type === 'event') return EVENT_ALLOWED;
    if (type === 'effect') return EFFECT_ALLOWED;
    return ENTITY_ALLOWED;
  }

  buildCausalGraph = function buildCausalGraphIndexed(rootRef, maxDepth = 8) {
    const index = canonicalIndex();
    const root = index.get(rootRef);
    if (!root || root.propertyType !== 'event') throw new Error(`causal root must be Event: ${rootRef}`);

    const outgoing = new Map();
    for (const link of canonicalLinks()) {
      const parent = link.value.parent_ref;
      if (!outgoing.has(parent)) outgoing.set(parent, []);
      outgoing.get(parent).push(link);
    }

    const nodes = new Map([[rootRef, { ref: rootRef, depth: 0 }]]);
    const edges = [];
    const seenEdges = new Set();
    const queue = [{ ref: rootRef, depth: 0, path: new Set([rootRef]) }];
    let head = 0;

    while (head < queue.length) {
      const current = queue[head++];
      if (current.depth >= maxDepth) continue;
      const item = index.get(current.ref);
      if (!item) throw new Error(`causal ref unresolved: ${current.ref}`);
      const allowed = allowedFor(item);

      for (const { property, value } of outgoing.get(current.ref) ?? []) {
        if (!allowed.has(value.link_type_ref)) continue;
        const targetRef = value.child_ref;
        if (!index.has(targetRef)) throw new Error(`causal target unresolved: ${targetRef}`);
        const edgeKey = `${property.id}:${current.ref}:${targetRef}`;
        if (seenEdges.has(edgeKey)) continue;
        seenEdges.add(edgeKey);
        const cycle = current.path.has(targetRef);
        const nextDepth = current.depth + 1;
        edges.push({
          id: property.id,
          from: current.ref,
          to: targetRef,
          linkType: value.link_type_ref,
          depth: nextDepth,
          cycle,
          order: edges.length,
        });
        const existing = nodes.get(targetRef);
        if (!existing || nextDepth < existing.depth) nodes.set(targetRef, { ref: targetRef, depth: nextDepth });
        if (!cycle) {
          const path = new Set(current.path);
          path.add(targetRef);
          queue.push({ ref: targetRef, depth: nextDepth, path });
        }
      }
    }

    return { rootRef, index, nodes: [...nodes.values()], edges };
  };

  function compareQueue(a, b) {
    return a.readyAt - b.readyAt || a.incomingOrder - b.incomingOrder || a.ref.localeCompare(b.ref);
  }
  function heapPush(heap, value) {
    heap.push(value);
    let index = heap.length - 1;
    while (index > 0) {
      const parent = (index - 1) >> 1;
      if (compareQueue(heap[parent], value) <= 0) break;
      heap[index] = heap[parent];
      index = parent;
    }
    heap[index] = value;
  }
  function heapPop(heap) {
    if (!heap.length) return null;
    const root = heap[0];
    const tail = heap.pop();
    if (heap.length) {
      let index = 0;
      while (true) {
        const left = index * 2 + 1;
        const right = left + 1;
        if (left >= heap.length) break;
        let child = left;
        if (right < heap.length && compareQueue(heap[right], heap[left]) < 0) child = right;
        if (compareQueue(tail, heap[child]) <= 0) break;
        heap[index] = heap[child];
        index = child;
      }
      heap[index] = tail;
    }
    return root;
  }

  function isEventTarget(graph, ref) {
    const item = graph.index.get(ref);
    return Boolean(item && item.kind === 'property' && item.propertyType === 'event');
  }

  // Playback policy:
  // - Events are the sequencing boundaries.
  // - event_cause is structural: it gates the next Event but has no transient
  //   travel animation of its own; the canonical route remains visible.
  // - non-Event chains (Data/Effect/Function/Entity etc.) flow continuously and
  //   do not pay next_event_delay at every intermediate canonical edge.
  causalEdgeSchedules = function causalEdgeSchedulesHeap(graph) {
    const timing = playbackApi().timingMs();
    const outgoing = new Map();
    const edgeOrder = new Map();
    graph.edges.forEach((edge, index) => {
      edgeOrder.set(edge.id, index);
      if (!outgoing.has(edge.from)) outgoing.set(edge.from, []);
      outgoing.get(edge.from).push(edge);
    });

    const schedules = new Map();
    const bestReady = new Map([[graph.rootRef, timing.activation]]);
    const bestIncomingOrder = new Map([[graph.rootRef, -1]]);
    const queue = [];
    heapPush(queue, { ref: graph.rootRef, readyAt: timing.activation, incomingOrder: -1 });

    while (queue.length) {
      const current = heapPop(queue);
      if (Math.abs((bestReady.get(current.ref) ?? Infinity) - current.readyAt) > 1e-6) continue;
      if ((bestIncomingOrder.get(current.ref) ?? Infinity) !== current.incomingOrder) continue;

      const siblings = outgoing.get(current.ref) ?? [];
      for (let branchIndex = 0; branchIndex < siblings.length; branchIndex++) {
        const edge = siblings[branchIndex];
        const start = current.readyAt + branchIndex * timing.branch;
        const targetIsEvent = isEventTarget(graph, edge.to);
        const staticCause = edge.linkType === 'event_cause';

        // Cause is already represented by the canonical route, so do not animate
        // a pulse along the complete cause chain. It still schedules the target
        // Event activation at this boundary.
        const arrival = staticCause ? start : start + timing.travel;
        const effectEnd = arrival + (targetIsEvent ? timing.activation : timing.target);
        const nextAt = effectEnd + (targetIsEvent ? timing.next : 0);
        const order = edgeOrder.get(edge.id);
        schedules.set(edge.id, {
          start, arrival, effectEnd, nextAt,
          sourceReadyAt: current.readyAt,
          branchIndex,
          order,
          targetIsEvent,
          staticCause,
        });

        if (edge.cycle) continue;
        const previousReady = bestReady.get(edge.to);
        const previousOrder = bestIncomingOrder.get(edge.to) ?? Infinity;
        const earlier = previousReady === undefined || nextAt < previousReady - 1e-6;
        const stableTie = previousReady !== undefined && Math.abs(nextAt - previousReady) <= 1e-6 && order < previousOrder;
        if (!earlier && !stableTie) continue;
        bestReady.set(edge.to, nextAt);
        bestIncomingOrder.set(edge.to, order);
        heapPush(queue, { ref: edge.to, readyAt: nextAt, incomingOrder: order });
      }
    }
    return schedules;
  };

  function ensureIncoming(trace) {
    if (trace.__incomingSchedules) return trace.__incomingSchedules;
    const incoming = new Map();
    for (const edge of trace.graph.edges) {
      const schedule = trace.schedules.get(edge.id);
      if (!schedule) continue;
      if (!incoming.has(edge.to)) incoming.set(edge.to, []);
      incoming.get(edge.to).push(schedule);
    }
    trace.__incomingSchedules = incoming;
    return incoming;
  }

  const traceEndTimesBase = traceEndTimes;
  traceEndTimes = function traceEndTimesIndexed(trace) {
    if (trace.__contentEnd === undefined) {
      let contentEnd = playbackApi().timingMs().activation;
      for (const schedule of trace.schedules.values()) contentEnd = Math.max(contentEnd, schedule.nextAt);
      trace.__contentEnd = contentEnd;
    }
    const timing = playbackApi().timingMs();
    return {
      contentEnd: trace.__contentEnd,
      holdEnd: trace.__contentEnd + timing.hold,
      fadeEnd: trace.__contentEnd + timing.hold + timing.fade,
    };
  };

  activeTraceForRef = function activeTraceForRefIndexed(ref, globalElapsed) {
    const timing = playbackApi().timingMs();
    for (let index = causalProjection.currentEvents.length - 1; index >= 0; index--) {
      const trace = causalProjection.currentEvents[index];
      const local = globalElapsed - trace.startedAt;
      const alpha = traceAlpha(trace, globalElapsed);
      if (alpha <= 0) continue;
      if (ref === trace.rootEventRef && local >= 0 && local < timing.activation) {
        return { trace, alpha, local, reached: 0 };
      }
      for (const schedule of ensureIncoming(trace).get(ref) ?? []) {
        const state = causalPlaybackState(schedule, local);
        if (state.targetActive) return { trace, alpha, local, reached: schedule.arrival };
      }
    }
    return null;
  };

  traceRouteEdges = function traceRouteEdgesIndexed(trace) {
    if (trace.__routeEdges) return trace.__routeEdges;
    const grouped = new Map();
    for (const edge of trace.graph.edges) {
      // event_cause is structural. The canonical cause route is already visible;
      // transient playback only animates the work performed between Event
      // boundaries.
      if (edge.linkType === 'event_cause') continue;
      const sourceOwner = ownerForRef(edge.from, trace.graph.index);
      const targetOwner = ownerForRef(edge.to, trace.graph.index);
      if (!sourceOwner || !targetOwner || sourceOwner.id === targetOwner.id) continue;
      const key = eventRouteKey(sourceOwner, targetOwner);
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(edge);
    }
    for (const edges of grouped.values()) {
      edges.sort((a, b) => (trace.schedules.get(a.id)?.order ?? Infinity) - (trace.schedules.get(b.id)?.order ?? Infinity));
    }
    trace.__routeEdges = grouped;
    return grouped;
  };

  window.StructureCausalPerf = Object.freeze({
    buildGraph: buildCausalGraph,
    schedule: causalEdgeSchedules,
    stats: trace => ({
      edges: trace?.graph?.edges?.length ?? 0,
      incomingRefs: trace?.__incomingSchedules?.size ?? 0,
      routes: trace?.__routeEdges?.size ?? 0,
    }),
  });
})();
