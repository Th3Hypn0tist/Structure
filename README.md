# StructureProjector

Read-only structural projector for repositories and explicit semantic specifications.

## v0.1 scope

- standalone local web service on `127.0.0.1:6969`
- initial source: `Th3Hypn0tist/AIGMos_docs`
- selectable GitHub branch, resolved to an exact commit SHA before parsing
- CanonicalContract (`AIGMOS_CANONICAL_CONTRACT` format `1.0`) detection and validation
- fail-closed semantic graph construction
- one semantic node per identity
- SVG Canonical Structure Map
- separate containment / relations / ownership / authority / dependencies overlays
- read-only Inspector with raw structured source
- no Links, Expose or MetaModule obligations
- no source mutation and no semantic guessing

## Run

Requires Python 3.11+ and network access to GitHub.

```bash
python structureprojector.py
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

## Current intentional limitation

The first implementation only treats JSON files carrying
`format.contract_format = AIGMOS_CANONICAL_CONTRACT` as semantic contracts.
Legacy or unrelated JSON is not guessed into the canonical graph.
