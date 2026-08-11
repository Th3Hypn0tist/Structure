# StructureProjector

Read-only structural projector for repositories and explicit semantic specifications.

## v0.2 scope

- standalone local web service on `127.0.0.1:6969`
- initial source: `Th3Hypn0tist/AIGMos_docs`
- selectable GitHub branch, resolved to an exact commit SHA before parsing
- pluggable ruleset boundary
- `CanonicalContract` ruleset for `AIGMOS_CANONICAL_CONTRACT` format `1.0`
- `RawJSON` ruleset for arbitrary valid JSON structure
- fail-closed CanonicalContract semantic graph construction
- RawJSON object / array / key / index / primitive mapping without domain-semantic inference
- SVG structural projection shared by both rulesets
- read-only Inspector with source provenance and raw structured data
- no Links, Expose or MetaModule obligations
- no source mutation and no semantic guessing

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

## Rulesets

### CanonicalContract

Reads only JSON carrying:

```json
{
  "format": {
    "contract_format": "AIGMOS_CANONICAL_CONTRACT",
    "format_version": "1.0"
  }
}
```

It extracts explicit canonical identity, containment, relations, ownership, authority and dependencies. Required unresolved references fail closed.

### RawJSON

Maps one selected `.json` file at a time using only JSON syntax:

- object -> structural container
- array -> ordered structural container
- object key -> containment relation labelled `key`
- array position -> containment relation labelled `index`
- primitive -> leaf value
- JSON Pointer -> stable path-local node identity

RawJSON never promotes names, keys or nesting into domain ownership, authority, dependency or other semantic relation types.

## Tests

```bash
python -m unittest discover -s tests -v
```

The test suite covers both CanonicalContract core behavior and RawJSON structural mapping.
