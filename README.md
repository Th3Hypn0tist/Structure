# Structure

## Simple, yet so powerful.

Structure is a domain-neutral environment for structural thinking, modelling and progressive formalization.

A Structure model can start as a loose mindmap and grow into a precise software architecture, a theatre scene, a factory process, an organization model, a service flow, or another structured system without rebuilding the model in a different format.

The central idea is deliberately small:

```text
Entity + Properties + Rulesets
```

That is enough to describe surprisingly complex systems.

## One model from sketch to formal structure

Most modelling tools force the user to choose the final modelling language before the structure is understood. Structure works in the opposite direction.

Start with names and relationships. Add meaning when it becomes known. Apply stricter Rulesets when more precision is required.

```text
idea
  -> mindmap
  -> named Entities
  -> Properties
  -> typed relationships
  -> dependencies / ownership / authority
  -> Events / Effects / data flow
  -> formal architecture
  -> implementation-ready model
```

The canonical structure does not need to be replaced between those stages. The same identities can survive the whole process.

The UX follows the same principle: missing information should normally not block work. It should be visible as incomplete. The only information that needs to exist when creating a node is its name; everything else can be formalized later.

`UNRESOLVED != INVALID`

Incomplete structure is useful structure.

## Everything is a contract

Structure treats semantics as contracts rather than as a large collection of unrelated special-case object types.

An Event is a contract. A dependency is a contract. Ownership is a contract. Data meaning is a contract. An Effect is a contract. A relationship is a contract.

The recurring model is:

### Entity

An Entity gives something stable identity.

It can represent almost anything that needs to be addressed independently:

- a software service
- a database
- a person or role
- a theatre scene
- a lighting fixture
- a sound cue
- a machine
- a production cell
- a material stream
- an organization
- a process step
- a document
- a concept in a mindmap

### Property

Properties describe what is meaningful about an Entity.

A Property can carry data, behaviour, an Event, an Effect, a relationship, a function, metadata, or another explicit fact about the Entity.

Relationships are therefore not detached visual lines. Their canonical meaning remains data. The line shown in the UI is only a projection of that meaning.

### Ruleset

A Ruleset describes how a pattern of Entities and Properties should be interpreted and what requirements that pattern should satisfy.

A Ruleset can answer questions such as:

```text
Does this structure qualify as a dependency?
Does this Event have a resolvable Effect target?
Is this software component sufficiently specified?
Is this theatre scene performance-ready?
Is this factory process missing an input or output?
```

Rulesets do not need to own the canonical data. Multiple Rulesets can evaluate the same structure independently and simultaneously.

This gives Structure a major property: **domain meaning can change without changing the underlying modelling language.**

## Mindmapping

At the loosest level, Structure is a mindmap.

```text
Customer
  -> Order
  -> Product
```

That can be useful before anyone knows whether the arrows mean dependency, ownership, data flow, sequence, containment, or simply "these ideas are related".

Nothing needs to be guessed prematurely.

As understanding grows, the same objects can be formalized:

```text
Order Service
  depends on Customer API
  writes Orders
  reads Inventory
  emits Order Created
```

The sketch was not thrown away. It became architecture.

## Software development

In software design the same model can represent:

- systems and subsystems
- services and modules
- databases, schemas and fields
- APIs and commands
- dependencies
- ownership and authority
- Events and Effects
- data inputs and outputs
- implementation boundaries

A dependency can target the narrowest known canonical identity. A service does not need to depend vaguely on an entire database if the real dependency is one table, field, Event, or function.

That makes dependency analysis more useful and makes missing contracts visible before implementation.

The same graph can progress from architecture sketch to a machine-readable implementation contract without changing its basic identity model.

## Theatre and live production

A theatre scene has structure just as a software system does.

Entities may include:

- scenes
- characters
- actors
- stage areas
- props
- lighting fixtures
- lighting states
- sound effects
- media
- cues

Properties and links describe what each scene requires. Events describe what happens. Effects describe what those Events change.

For example:

```text
SCENE START
  -> activate MOONLIGHT
  -> start WIND SFX
  -> enable STAGE LEFT
```

A Theatre Ruleset can then evaluate whether the scene is complete while a Performance Ready Ruleset can ask stricter questions:

```text
Scene structure            complete
Characters                 complete
Lighting                    complete
Sound                       incomplete
HAMLET actor assignment    missing
Bell media source           missing
```

The same Event/Effect mechanism used for software behaviour can therefore describe stage cues without inventing a separate engine for theatre.

## Factory and process modelling

A factory can be represented with the same primitives.

Entities may be:

- machines
- conveyors
- cells
- operators
- sensors
- products
- materials
- buffers
- process stages
- quality gates

Properties describe capacities, states, measurements and functions. Relationships describe dependencies and flows. Events describe changes in the process.

```text
PART ARRIVES
  -> reserve MACHINE_2
  -> start PROCESS_A
  -> update BUFFER_COUNT

TEMPERATURE HIGH
  -> stop HEATER
  -> emit QUALITY_CHECK_REQUIRED
```

A process Ruleset can detect missing inputs, outputs, dependencies, safety conditions, ownership or control points while leaving the source structure untouched.

This allows the same Structure engine to reason about process topology, causality and readiness without being hard-coded as a factory application.

## Other domains

The model is intentionally not limited to the examples above. The same approach applies to any problem where identity, structure, relationships and requirements matter, including:

- organization design
- service design
- infrastructure
- systems engineering
- AV and production systems
- logistics
- workflows
- product architecture
- documentation architecture
- knowledge structures

The domain is expressed through contracts and Rulesets rather than through a different application for every problem.

## Progressive formalization

Structure separates **technical validity** from **contract completeness**.

A broken canonical reference can be invalid. Missing optional or not-yet-defined meaning is simply incomplete.

That enables a workflow such as:

```text
MINDMAP              complete
DEPENDENCY MODEL     incomplete
  missing ownership
  missing exact target
EVENT MODEL          incomplete
  missing Effect target
CW                   incomplete
  7 requirements remaining
```

Rulesets therefore act as live formalization guides rather than form validators that prevent the user from continuing.

The model can stay loose where looseness is useful and become strict only where strictness creates value.

## Multiple projections, one truth

Canonical semantics must never depend on where a node happens to be placed, what color a line uses, whether a label is visible, or which projection is currently selected.

The UI is free to show the same structure in different ways:

- mindmap
- dependency graph
- architecture view
- causal Event -> Effect paths
- ownership view
- 2D projection
- 3D projection
- filtered domain-specific views

These are projections of the same underlying structure, not separate copies of truth.

This also keeps dense models readable. For example, multiple canonical links of the same relationship type can be visually aggregated while the individual contracts remain available in the canonical model.

## Why the small model matters

A small semantic core has several advantages:

- fewer special cases
- less schema fragmentation
- domain-neutral tooling
- stable identities throughout design maturity
- progressive rather than forced formalization
- machine-readable structure from the beginning
- multiple simultaneous interpretations
- easier visualization and projection
- explicit gaps instead of hidden assumptions
- reusable validation logic
- easier AI-assisted structural work

Before introducing a new primitive, Structure can ask a useful question:

> Can this be represented as an Entity, a Property, or a Ruleset?

If the answer is yes, another special-case subsystem may not be necessary.

## Architecture principle

Structure separates semantic authority from representation.

```text
Server
  canonical structure
  validation
  persistence
  Ruleset evaluation

Client
  representation
  interaction
  projections
  animation
```

An Entity is semantic. A rendered node is only an instance representing that Entity. A link color is visual. An Event path animation is visual. Neither is canonical authority.

## Current MVP direction

The current implementation is an evolving clean-slate MVP focused on establishing the interaction and semantic model before adding broader product surface.

Current work includes:

- 3D Entity nodes
- Entity authoring
- Property visualization
- typed Link Properties
- Event Properties
- Event -> Effect -> target causal projection
- world-space child UI for Events and Properties
- Ruleset/color-space driven relationship views
- save/load
- progressive UI controls for reducing visual density

The intended next layers include stronger external Ruleset evaluation, abstraction composition/imports and progressively stricter contract formalization.

## Run

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8765/
```

---

**Structure — Simple, yet so powerful.**
