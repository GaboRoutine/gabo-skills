---
name: architecture-sync
description: Detect drift between docs/architecture.md and the actual gabo code — modules that exist vs. documented, interfaces that diverged, build-order claims that no longer hold. Use when asked to "check the architecture doc", "is the doc up to date", "did we drift from the design", or after landing a module slice.
allowed-tools: Read, Grep, Glob, Bash(git *)
---

# Architecture sync

`docs/architecture.md` is intentionally ahead of the code — it's the destination.
But "ahead" should mean *not built yet*, not *built differently*. This skill finds
the second kind of drift, which is the dangerous kind.

## What to compare

1. **Modules: documented vs. present.** The doc's target layout lists `ingestion`,
   `embeddings`, `clustering`, `store`, `api`, `scheduler`. List what actually exists
   under `gabo/` and `embeddings/`. Classify each as: *built as documented*, *built
   but diverged*, or *not built yet* (fine — note it, don't flag it).

2. **Public interfaces.** The doc states each module's surface (e.g. `store` →
   `upsert(articles, vectors)` + `search(query_vector, k)`; `clustering` →
   `cluster(articles) -> list[Cluster]`). Read each module's `__init__.py` and
   compare the real surface to the documented one. A renamed or extra public symbol
   is drift.

3. **Boundary rules in practice.** The doc claims one-directional flow and no
   deploy-coupling. Spot-check that the code matches (hand off to
   `module-boundary-check` for the mechanical part).

4. **Build-order claims.** The doc says packaging/types land first, then ingestion,
   store, api, clustering, scheduler. If the code shows a later slice built before an
   earlier one, the doc's sequencing narrative is stale.

## Report

A short table — `Documented | In code | Status` — followed by the specific drifts
worth fixing. For each drift, recommend the cheaper correction: **update the doc**
(if the code's reality is intentional) or **fix the code** (if the doc is the agreed
design). Don't rewrite architecture.md wholesale; propose the minimal edit.
