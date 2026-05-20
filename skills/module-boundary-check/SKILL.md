---
name: module-boundary-check
description: Verify gabo's modular-monolith boundary rules are not violated — no cross-module internal imports, one-directional data flow, shared types at the top level. Use after editing anything under gabo/, before committing module changes, or when asked to "check boundaries", "audit imports", or "is this a clean module".
allowed-tools: Read, Grep, Glob, Bash(python3 *), Bash(python *)
argument-hint: "[package-dir, default ./gabo]"
---

# Module boundary check

The modular monolith only stays clean if four rules hold. This skill verifies them
mechanically, then reasons about anything the script can't catch.

## Step 1 — run the static check

The bundled script greps every module for imports that reach into a *sibling
module's internals* (anything deeper than `from gabo.<module> import ...`).

!`python3 ${SKILL_DIR}/scripts/check_boundaries.py ${ARGUMENTS:-./gabo}`

If the script isn't pointed at the right tree, re-run it with the package path:
`python3 ${SKILL_DIR}/scripts/check_boundaries.py /path/to/gabo`.

## Step 2 — review the four rules by hand

The script catches rule 1 (internal imports) reliably. Rules 2–4 need judgement —
read `reference.md` in this skill directory for the full rule text, then check the
changed files against each:

1. **No cross-module imports of internals** — flagged by the script above.
2. **Data flows one direction** (`ingestion → embeddings → clustering → store → api`).
   Look for reverse edges: does `ingestion` import `store`? That's a violation.
3. **Shared types live in `gabo/types.py`** — a dataclass used by two modules must
   not be defined inside one of them.
4. **No module knows how it's deployed** — no `fastapi`/`uvicorn` import inside
   `embeddings/`, no `apscheduler` decorator inside `ingestion/`.

## Step 3 — report

For each violation: the file, the offending line, which rule it breaks, and the
minimal fix (usually: import the public surface, move a type to `types.py`, or
invert the dependency). If everything is clean, say so in one line — don't pad.
