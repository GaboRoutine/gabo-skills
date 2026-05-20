# New module checklist

Work top to bottom. Don't mark the module done until every box holds.

## Build order gate

- [ ] The module is the **next** slice in: packaging → ingestion → store → api →
      clustering → scheduler. (Building `api` before `store` exists, or `clustering`
      before there are persisted articles, is out of order — flag it instead.)

## Structure

- [ ] `gabo/<module>/__init__.py` exists and **re-exports the public surface** —
      the one or two names other modules import (`from gabo.<module> import X`).
- [ ] Internal files (`<module>/<file>.py`) are imported *only* by the module's own
      `__init__.py` or its siblings, never by other modules.
- [ ] The module has a `if __name__ == "__main__":` block printing a hello-world
      demo, runnable as `python -m gabo.<module>.<file>`.

## Boundaries (the four rules)

- [ ] No `from gabo.<other_module>.<internal> import ...` — only public surfaces.
- [ ] Imports respect one-directional flow (`ingestion → embeddings → clustering →
      store → api`). No reverse edges.
- [ ] Any type shared with another module is defined in `gabo/types.py`, not here.
- [ ] No deployment concern leaks in: no `fastapi`/`uvicorn`/`apscheduler` unless
      this *is* the `api` or `scheduler` module.

## Per-module interface targets (from architecture.md)

| Module | Public surface |
|---|---|
| `ingestion` | `fetch(feed_url) -> list[Article]` |
| `embeddings` | `encode(texts) -> np.ndarray` |
| `clustering` | `cluster(articles) -> list[Cluster]` |
| `store` | `Store.upsert(articles, vectors)`, `Store.search(vector, k)` |
| `api` | route fns: `feed()`, `search(q, k)` |
| `scheduler` | `run_once()`, job fns |

## Verify

- [ ] `python -m gabo.<module>.<file>` runs and prints its demo.
- [ ] The `module-boundary-check` skill reports clean.
- [ ] If the module has logic worth pinning, a `pytest` test exists next to it.
