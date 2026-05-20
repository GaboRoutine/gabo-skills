---
name: new-module
description: Scaffold a new bounded module in gabo's modular monolith, following the architecture's build order and boundary rules. Use when asked to "add a module", "create the clustering/store/api module", "scaffold a new slice", or to stand up a new package under gabo/.
allowed-tools: Read, Write, Edit, Bash(python3 *)
argument-hint: "<module-name>"
---

# New module

Stand up a new bounded module under `gabo/<module>/` that satisfies the boundary
rules from the start. Target module: **$ARGUMENTS**

## Before you scaffold — check the build order

Modules ship in a fixed sequence (see `checklist.md` in this skill directory):

```
packaging → ingestion → store → api → clustering → scheduler
```

Building out of order is the single most common mistake here — e.g. an `api/` with
no `store/` to serve. **If `$ARGUMENTS` is ahead of what exists, stop and tell the
user** which prerequisite slice is missing and why it should land first. Don't
scaffold it anyway.

## Scaffold

Run the generator (writes `__init__.py` exposing the public surface + a runnable
stub, never overwrites existing files):

!`python3 ${SKILL_DIR}/scripts/scaffold_module.py $ARGUMENTS --dry-run`

Review the dry-run plan above. If it's correct, re-run without `--dry-run` against
the gabo package:

```bash
python3 ${SKILL_DIR}/scripts/scaffold_module.py $ARGUMENTS --root /path/to/gabo/gabo
```

## After scaffolding — work the checklist

Open `checklist.md` and complete every item: public surface in `__init__.py`, shared
types in `gabo/types.py` (not in the module), one-directional imports, a standalone
`python -m gabo.$ARGUMENTS.<file>` demo, and the boundary check passing. Then hand
off to the `module-boundary-check` skill to verify.
