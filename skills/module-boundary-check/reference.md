# Module boundary rules (full text)

From `docs/architecture.md` → Module Boundary Rules. These are what make future
microservice extraction a refactor rather than a rewrite.

## Rule 1 — No cross-module imports of internals

Each module exposes a public surface through its `__init__.py`. Consumers touch only
that surface.

```python
# good
from gabo.store import Store
from gabo.ingestion import fetch

# bad — reaches into another module's internals
from gabo.store.vector_db import Store
from gabo.ingestion.fetcher import fetch
```

A module importing *its own* internals is fine (`gabo/api/routes.py` importing a
sibling file inside `api/`). Only cross-module reach-ins are violations.

## Rule 2 — Data flows one direction

```
ingestion → embeddings → clustering → store → api
```

No reverse edges. `ingestion` must not import `store`; `embeddings` must not import
`api`. The `scheduler` is the one exception to the linearity: it orchestrates the
others, so it may import them — but nothing imports the scheduler.

## Rule 3 — Shared types live at the top level

Any shape crossing a module boundary (`Article`, `Cluster`) is defined in
`gabo/types.py`. A module may define a *private* helper dataclass for its own use,
but the moment a second module needs it, it moves to `types.py`.

## Rule 4 — No module knows how it's deployed

Deployment concerns (HTTP framework, scheduler, container) stay out of the domain
modules:

- No `fastapi` / `uvicorn` import inside `embeddings/`, `clustering/`, `store/`.
- No `apscheduler` decorators inside `ingestion/`.
- The `api/` module owns FastAPI; the `scheduler/` module owns APScheduler. Domain
  modules expose plain functions and classes those layers call.

## Why it matters

The cost we accept with a monolith is that bottlenecks (likely embedding) can't be
scaled in isolation. These rules keep the *option* to extract a module cheap: a
module with a narrow public surface and no reverse/deploy coupling can become a
service by changing its callers, not by rewriting it.
