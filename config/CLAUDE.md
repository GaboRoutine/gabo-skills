# gabo — project rules

Gabo is a personal **RSS intelligence feed**: it ingests articles, embeds them into
semantic vectors, clusters them, and serves the result over an API. The target
architecture is a **modular monolith** — one deployable Python app split into
bounded modules. See `docs/architecture.md` for the full design.

> These rules live in `gabo-skills` as the canonical template. They are tailored
> to the gabo project so they double as a worked example of a fully-configured
> Claude Code `.claude/` directory.

## Module boundaries (load-bearing — do not violate)

The modular monolith only stays a monolith-not-a-tangle if these hold:

1. **No cross-module imports of internals.** A module exposes a public surface via
   its `__init__.py`. Consumers import `from gabo.store import Store`, never
   `from gabo.store.vector_db import ...`.
2. **Data flows one direction:** `ingestion → embeddings → clustering → store → api`.
   No reverse edges. The scheduler orchestrates; it is not imported by the modules
   it drives.
3. **Shared types live at the top level** in `gabo/types.py` (`Article`, `Cluster`).
   Never define a cross-module shape inside one module.
4. **No module knows how it's deployed.** No `fastapi` import inside `embeddings/`,
   no scheduler decorators inside `ingestion/`.

When you touch module code, run the boundary check skill before declaring done.

## Build order

New modules ship as vertical slices in this sequence (packaging → ingestion →
store → api → clustering → scheduler). Do not build the API before the store
exists — there is nothing to serve. If asked to add a module out of order, flag it.

## Conventions

- **Python 3.11+.** Use `X | None`, `list[X]`, `dataclass` — no `typing.Optional`/`List`.
- **Type everything** that crosses a module boundary. Internal helpers can infer.
- **Each module is runnable standalone:** `python -m gabo.<module>.<file>` prints a
  hello-world demo. Preserve this when editing a module.
- **No premature abstraction.** Extract a helper only when three call sites exist.
- **Embedding backends are pluggable** behind the `EmbeddingModel` ABC. Add backends
  by subclassing `encode(texts) -> np.ndarray`, not by branching inside callers.

## Running things

```bash
python run.py                      # one-shot pipeline (ingestion → store → clustering)
python -m gabo.ingestion.fetcher   # module demos
python -m gabo.store.vector_db
python embeddings/run.py --data examples.json   # embeddings CLI (UMAP default)
```

## Testing

- Tests use `pytest`, placed next to source (`foo.py` → `test_foo.py`) or under `tests/`.
- Mock only at system boundaries (RSS HTTP, the vector DB), never internal functions.
- A boundary-rule test that greps imports is worth more than coverage percentage here.

## What not to do

- Don't add reverse dependency edges to "save an import".
- Don't move `reduce.py` / `plot.py` out of `embeddings/` silently — that's a planned
  slice (`visualization/`), flag it rather than doing it as a side effect.
- Don't commit the embedding cache (`embeddings/embeddings_*.npy`) or `.env`.
