# Structure

Clean-slate Structure MVP.

Structure is a client/server semantic modelling environment built around Canonical Contract Format 2.0 Entities + Properties and externally governed Rulesets. The HTTP server owns workspace semantics and persistence; the browser owns 3D representation and interaction.

## Run

```bash
python app.py
```

Open `http://127.0.0.1:8765/`.

## Current baseline

- clean client <-> server boundary
- empty 3D workspace
- create/delete Entities
- raw WebGL NodeInstance primitives
- mouse-look camera + WASD/QE movement
- FOV 15..170 degrees
- XYZ translation gizmo
- Ruleset instances using CanonicalWireframe CCF 2.0 Ruleset identities
- Link Properties stored under Entity properties[]
- incoming/outgoing anchor rails derived from Link Properties
- one generic animated line renderer for dependency, ownership, authority, containment and architecture links
- Ruleset view selector
- per-Ruleset ColorSpace instances
- workspace save/load

Canonical semantics never depend on node position, link color, shader animation or visual layout.
