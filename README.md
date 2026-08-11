# StructureProjector

Read-only structural projector for repositories and explicit semantic specifications.

## v0.3 scope

- standalone local web service on `127.0.0.1:6969`
- initial source: `Th3Hypn0tist/AIGMos_docs`
- selectable GitHub branch, resolved to an exact commit SHA before parsing
- nanoCMS-style recursive Page + ordered children + placement shell for view navigation
- current nanoCMS pages: `Canonical Structure`, `Raw JSON`
- CanonicalContract (`AIGMOS_CANONICAL_CONTRACT` format `1.0`) ruleset
- RawJSON structural ruleset
- fail-closed CanonicalContract semantic graph construction
- JSON object / array / key / index / primitive mapping without domain-semantic guessing
- SVG views and read-only Inspector
- no Links, Expose, AccessCore or MetaModule obligation in this standalone implementation
- no source mutation and no semantic guessing

## View ownership

The local nanoCMS shell owns only recursive Page structure, navigation order and view placements.
It does not own StructureProjector ruleset, graph or renderer semantics.

Current mapping:

```text
StructureProjector
├── Canonical Structure -> view.canonical_structure_map -> CanonicalContract -> SVG
└── Raw JSON            -> view.raw_json_tree           -> RawJSON           -> SVG
```

Adding a new view should normally mean adding a Page/placement and the corresponding view implementation, not redesigning the shell.

## Run

Requires Python 3.11+ and network access to GitHub.

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:6969
```

Optional environment variables:

```text
STRUCTUREPROJECTOR_HOST
STRUCTUREPROJECTOR_PORT
STRUCTUREPROJECTOR_SOURCE_REPO
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## Ruleset boundary

`CanonicalContract` extracts only explicit Canonical Contract semantics.

`RawJSON` extracts only JSON syntax structure:

- object -> structural container
- array -> ordered structural container
- object key -> key containment
- array index -> index containment
- primitive -> leaf value
- identity -> file path + JSON Pointer

RawJSON never infers ownership, authority, dependency, domain identity or other meaning from key names or paths.
