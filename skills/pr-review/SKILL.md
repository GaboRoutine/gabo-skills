---
name: pr-review
description: Review a pull request for correctness, security, performance, and gabo's module-boundary rules. Use when asked to review a PR, check a pull request, audit changes before merging, or given a PR number.
disable-model-invocation: true
argument-hint: "[pr-number]"
allowed-tools: Bash(gh *)
---

# PR Review

## Pull request

!`gh pr view $ARGUMENTS`

## Diff

!`gh pr diff $ARGUMENTS`

## Instructions

Review the PR above. Empty `$ARGUMENTS` reviews the current branch's open PR.

**Summary** — one paragraph: what this PR does and why.

**Findings** — grouped by severity:
- `[blocking]` — logic errors, security issues, broken tests, **module-boundary
  violations** (cross-module internal import, reverse dependency, type defined in the
  wrong place, deploy concern leaking into a domain module).
- `[non-blocking]` — missing edge cases, unclear naming, follow-up worthy.
- `[nit]` — style, formatting, minor simplifications.

Check each area:
1. **Correctness** — logic matches intent; edge cases (empty, null, batch) handled.
2. **Boundaries** — does it respect the four rules? (Run / reason like the
   `module-boundary-check` skill.) Diffs touching `gabo/` get this every time.
3. **Embeddings** — if `embeddings/` changed, apply the `embeddings-review` traps
   (pooling mask, device, cache key).
4. **Security** — injection, secrets, unvalidated input at boundaries.
5. **Performance** — N+1, unbounded memory, missing `no_grad`.
6. **Tests** — new paths covered, no mocks hiding real failures.

**Verdict** — `Approve` / `Request changes` / `Needs discussion`.
