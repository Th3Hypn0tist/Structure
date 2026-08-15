# Structure

Clean-slate Structure MVP.

Structure is a client/server semantic modelling environment built around Entities, Properties and Rulesets. The first implementation intentionally keeps the runtime small: an HTTP server owns workspace semantics and persistence; the browser owns 3D representation and interaction.

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
- camera FOV 15..170 degrees
- camera defaults in Settings
- node selection
- Blender-style XYZ translation gizmo for a selected node
- workspace save/load through server API

Next: incoming/outgoing anchor rails, LineInstance links, Ruleset views, then Event authoring and transient causal visualization.
