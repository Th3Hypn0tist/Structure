# Structure

**Structure** is a local-first workbench for observing, mapping, planning, comparing, projecting and exporting explicit structure.

`Projector` is one Structure tool alongside `Mapper`, `Planner`, `Compare / Conformance`, `Inputs` and `Exporter`.

> Some runtime identifiers still use the historical `StructureProjector` name for compatibility. The product and repository name are now **Structure**.

## Core model

Structure keeps source truth, canonical meaning and presentation separate.

```text
read-only inputs
      ↓
detectors / readers
      ↓
observed StructureTree
      ↓
Mapper ───────────────→ CW
                         ↑
Planner ────────────────┘
                         ↓
                Compare / Conformance
                         ↓
                     Projector
                         ↓
                       Scene
                         ↓
                      Viewer
                         ↓
                     Renderer

CW / Scene / projection → Exporter
```

The governing rule is:

> **Show what is explicitly known. Never invent missing semantics.**

## Product structure

```text
Structure
├── Inputs
├── Mapper
├── Planner
├── Compare / Conformance
├── Projector
│   ├── projection instances
│   ├── projection styles
│   ├── 2D / 3D views
│   ├── Scene
│   ├── cameras
│   └── 3D Fun Mode
└── Exporter
```

## CW — CanonicalWireframe

**CW is a format, not the product.**

Structure is the tool. CW is the shared structural interchange/model format used by Mapper, Planner, Compare / Conformance, Projector and Exporter.

CW contains semantic structure. Viewer state does not belong to CW semantics:

- camera transforms
- projection layout
- colors
- node spread
- zoom
- interaction gains
- Fun Mode state

The dedicated CW Format Contract is the next foundation contract to formalize.

## Inputs

Inputs are named, strictly read-only source scopes.

Typical inputs include:

- canonical specifications / CW
- implementation source code
- JSON and other structured data
- websites
- APIs and schemas
- other observable repositories or directories

Each input has an explicit role, detector and source scope. Projection instances bind to explicit inputs rather than duplicating source configuration.

See [`contracts/Structure_Inputs_Contract_v1.0.json`](contracts/Structure_Inputs_Contract_v1.0.json).

### Input isolation

Input safety is a hard invariant.

- all inputs are read-only
- different logical input roles must not read overlapping scopes
- specification and code inputs may use different repositories
- they may share a repository only with explicit, disjoint directory scopes
- `repo/spec/` + `repo/src/` is valid
- `repo/` + `repo/src/` is invalid
- identical or parent/child input scopes are invalid
- writable output must remain disjoint from every input scope
- there is no force/override bypass

See [`contracts/Structure_Input_Output_Isolation_Contract_v1.2.json`](contracts/Structure_Input_Output_Isolation_Contract_v1.2.json).

Earlier isolation contracts remain as superseded history; v1.2 is the current rule.

## StructureTree

`StructureTree` is the neutral technical observation/staging representation between source readers and higher-level tools.

It contains only facts proven by the source reader. It is not a semantic peer to CW and must not infer business meaning from names, prose, paths, colors or layout.

Examples:

- Canonical reader: explicit canonical identities and relations
- Raw JSON reader: syntax structure only
- future code detectors: parser/AST-provable code facts only

## Mapper

Mapper converts observed structure into CW or maps observed structure against a CW reference model.

```text
native source
    ↓
detector
    ↓
observed facts
    ↓
Mapper
    ↓
CW / Mapping Profile
```

Mapper rules:

- detector facts must be source-provable
- mapping can be many-to-many
- similarity candidates are suggestions, not evidence
- only explicitly accepted mappings become mapping evidence
- overlap is mechanically derived from accepted mappings
- overlap does not by itself prove waste or recommend deletion

The current Mapper foundation contract is [`contracts/CW_StructureMapper_Contract_v1.0.json`](contracts/CW_StructureMapper_Contract_v1.0.json). It predates the final `Structure` product naming and will be versioned as the CW format and Mapper contracts are finalized.

## Planner

Planner authors CW directly.

Typical uses include:

- mind maps
- architectures
- processes
- organizations
- plans
- system designs

Explicit user-created nodes and relations are semantic evidence. Spatial proximity, color and layout are presentation only unless an explicit relation exists.

## Compare / Conformance

Compare evaluates structural differences. Conformance evaluates explicit requirements against observed or mapped structure.

Current conformance statuses are:

- `MATCHED`
- `MISSING_IMPLEMENTATION`
- `UNSPECIFIED_IMPLEMENTATION`
- `MISMATCH`
- `UNRESOLVED`

Important invariant:

> **No mapping does not mean missing implementation. No mapping means `UNRESOLVED`.**

The current engine exists in [`conformance.py`](conformance.py) with its v1.0 contract in [`contracts/Canonical_Conformance_Contract_v1.0.json`](contracts/Canonical_Conformance_Contract_v1.0.json).

A many-to-many CW-oriented revision is the next contract evolution.

## Projector

Projector turns explicit structure into visual projections. Projection layout never becomes source truth.

Current projection-style families include:

- Atlas
- Map
- Matrix
- Lifecycle Lanes
- Dependency Flow
- Galaxy
- Role Layers
- Dependency Tower
- Authority Space
- Relation Orbits
- Hierarchy Tree
- Relation Generations
- Component Islands
- Relation Shells
- Structure Spine

Where a style has both 2D and 3D variants, dimension is selected independently. Missing variants are rejected rather than guessed.

Relation expansion follows explicit graph relations only. Discovery may traverse a relation in either direction to find reachable nodes, but this does not manufacture a reverse semantic edge.

## Scene and Viewer

Scene is projection/composition output, not source truth.

```text
explicit structure
      ↓
projection
      ↓
Scene
├── objects
├── nodes
├── connections
├── cameras
└── presentation state
      ↓
Viewer / Renderer
```

The current 3D viewer uses WebGL2 and keeps projection-instance transforms and style state outside canonical semantics.

## Cameras

Projector 3D uses multiple independent camera objects. A camera is not a bookmark.

Each camera owns its complete state:

```text
Camera
├── id / name
├── position X/Y/Z
├── rotation X/Y/Z
├── zoom
├── move gain
├── rotation gain
├── zoom gain
└── Advanced
    ├── scale X/Y/Z
    ├── FOV
    ├── near clip
    └── far clip
```

Switching cameras restores that camera's complete state.

See [`contracts/Structure_Camera_Contract_v1.0.json`](contracts/Structure_Camera_Contract_v1.0.json).

## Shortcut Registry

Keyboard shortcuts are registered centrally rather than embedded directly into tool semantics.

Initial shortcuts:

```text
C         next camera, looping
Shift+C   previous camera, looping
```

Shortcuts do not fire inside text-entry controls unless explicitly allowed by their context.

See [`contracts/Structure_Shortcut_Registry_Contract_v1.0.json`](contracts/Structure_Shortcut_Registry_Contract_v1.0.json).

## 3D Fun Mode

Fun Mode is deliberately narrow:

> **Fun Mode exists only in the Projector 3D Viewer.**

It does not belong to Inputs, Mapper, Planner, Compare, Conformance, Exporter, 2D views, CW or StructureTree.

Each 3D camera may have its own Fun Mode enabled state, preset and settings. Fun Mode may animate or stylize already-known structure for presentations, but it must never create semantic facts or mutate structural evidence.

See [`contracts/Structure_Projector_Fun_Mode_Contract_v1.0.json`](contracts/Structure_Projector_Fun_Mode_Contract_v1.0.json).

## Exporter

Exporter is a first-class Structure tool.

Export priority:

1. **CW** — primary semantic export
2. **SVG** — derived visual export

SVG is a presentation artifact, not an alternative semantic authority. A 3D Scene can be flattened through a selected camera into a 2D vector view.

See [`contracts/Structure_Exporter_Contract_v1.0.json`](contracts/Structure_Exporter_Contract_v1.0.json).

## AIGMos Business Universal reference model

AIGMos provides the first broad canonical vocabulary for mapping existing business software. The Business Universal family contains **32 universal modules**:

```text
01 Identity
02 Project
03 Location
04 Asset
05 CatalogItem
06 Specification
07 Opportunity
08 LineItem
09 Quote
10 Order
11 Invoice
12 BalanceAccount
13 BalanceTransaction
14 Settlement
15 Account
16 JournalEntry
17 LedgerEntry
18 StockMovement
19 Lot
20 Shipment
21 HandlingUnit
22 Case
23 Assessment
24 Reservation
25 Entitlement
26 Contract
27 Plan
28 Filing
29 Measurement
30 RuleSet
31 Message
32 FileResource
```

These are reference responsibilities, not assumptions about implementation technology. A CRM, ERP, HR system, website or other software can be observed independently and mapped onto the same Universal vocabulary.

Example overlap:

```text
CRM ───┐
ERP ───┼──→ Business Universal: Identity
HR  ───┘
```

This proves structural overlap in accepted mappings. It does not automatically prove that any implementation should be removed.

## Initial use cases

Structure is intentionally developed against two immediate spec-to-code cases:

```text
AIGMos specification + AIGMos implementation
Structure specification + Structure implementation
```

The same detector / Mapper / CW / Conformance / Projector pipeline must work for both without product-specific semantic shortcuts.

A third major use case is mapping customer software onto the AIGMos Business Universal reference model.

## Semantic safety rules

Structure follows these constraints throughout the pipeline:

- source repositories and directories are read-only inputs
- branches are resolved to immutable commit snapshots before parsing
- no semantic inference from file paths, key names, prose, colors or layout
- explicit relations remain dimensioned and directed as declared
- traversal does not create semantic edges
- candidate similarity is not accepted mapping evidence
- presentation state never changes source or CW semantics
- missing or ambiguous evidence is surfaced rather than guessed

## Current runtime implementation

The repository already contains the working Projector foundation, including:

- local HTTP service on `127.0.0.1:6969`
- GitHub branch → exact commit SHA → immutable source snapshot loading
- Canonical Contract reader
- Raw JSON reader
- neutral `StructureTree`
- explicit canonical relation projection, including explicit `references[]`
- degraded-but-projectable canonical results where explicit structure remains usable
- projection style families and independent 2D/3D selection
- explicit relation-depth expansion
- projection instances
- Scene Contract / Scene composition
- WebGL2 3D viewer
- projection-instance transforms and local style tuning
- conformance engine foundation
- versioned contracts for the newer Structure architecture

Some newly locked architecture is specified but not yet fully wired into the current UI/runtime, notably:

- final CW Format Contract
- full multi-input UI/runtime
- full Mapper workflow
- Planner workflow
- many-to-many Conformance revision
- new multi-camera runtime
- SVG Exporter workflow
- Fun Mode presets

This README deliberately distinguishes contract-level architecture from implemented behavior.

## Canonical reader boundary

The canonical reader extracts only explicit canonical structure.

Explicit structural dimensions currently include:

```text
containment
relations
ownership
authority
dependencies
references[]
```

Free-form semantics and prose are never scanned to manufacture relationships.

## Raw JSON boundary

Raw JSON extracts syntax structure only:

- object → structural container
- array → ordered structural container
- object key → key containment
- array index → index containment
- primitive → leaf value
- identity → file path + JSON Pointer

Raw JSON never infers ownership, authority, dependency, domain identity or other meaning from key names or paths.

## Run

Requires Python 3.11+ and network access to the configured GitHub source.

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:6969
```

Historical compatibility environment variables currently include:

```text
STRUCTUREPROJECTOR_HOST
STRUCTUREPROJECTOR_PORT
STRUCTUREPROJECTOR_SOURCE_REPO
```

These may be migrated to Structure-native names without changing the product model.

## Tests

```bash
python -m unittest discover -s tests -v
```

README updates do not imply that tests have been run. Test status should always be reported from an actual execution.

## Contracts

Current architecture contracts are kept under [`contracts/`](contracts/).

The newest locked contracts define:

- input registry
- input/output isolation
- Mapper foundation
- Conformance foundation
- Exporter
- cameras
- shortcut registry
- Projector 3D Fun Mode

Contracts are versioned. Superseded versions remain historical rather than being silently rewritten.

## Direction

Structure is a general structural workbench rather than only a repository visualizer:

> **observe native form → map or author CW → compare → project → export**

The architecture is intentionally domain-neutral. AIGMos is the first strong canonical reference model and Structure itself is the first recursive dogfood target.
