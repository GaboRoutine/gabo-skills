---
name: refactor
description: Safely refactor a piece of code without changing behavior. Use when asked to refactor, clean up, simplify, restructure, or improve code quality.
always: false
argument-hint: "[file-or-description]"
---

# Refactor

Target: $ARGUMENTS

## Checklist

Work through this in order — do not skip steps:

1. **Read first.** Understand what the code does and why it's written this way. Check git blame and nearby comments before assuming something is wrong.
2. **Tests first.** Confirm existing tests pass. If none exist, write a characterization test that pins the current behavior before you change anything.
3. **One transformation at a time.** Each logical step (rename, extract function, inline variable, flatten nesting) is its own commit. Do not batch multiple transformations.
4. **No behavior changes.** Refactoring means structure changes only — inputs, outputs, and side effects must remain identical. If you find a bug, note it separately rather than fixing it silently.
5. **Verify after each step.** Run the tests. If anything breaks, stop and diagnose before continuing.
6. **Name things for what they are.** Rename variables and functions to match their actual current purpose, not what they were originally called.

**Do not introduce new abstractions** unless three distinct call sites already exist for the extracted logic. Premature abstraction is its own form of tech debt.

**Do not rewrite.** Refactor is an incremental transformation, not a blank-slate rewrite. If the code needs a rewrite, flag it to the user explicitly.
