---
name: fix-issue
description: Fix a GitHub issue by number. Use when given an issue number and asked to fix, resolve, close, or implement it.
always: false
disable-model-invocation: true
argument-hint: "[issue-number]"
allowed-tools: Bash(gh *) Bash(git *)
---

# Fix Issue #$ARGUMENTS

## Issue

!`gh issue view $ARGUMENTS`

## Instructions

Fix GitHub issue #$ARGUMENTS:

1. Read the issue body and comments above carefully.
2. Identify expected behavior vs. current behavior.
3. Search the codebase for the relevant code (use Grep and Glob).
4. Implement the fix following the project's existing conventions (naming, error handling, style).
5. Write or update tests that reproduce the bug and confirm the fix — the test should fail before the fix and pass after.
6. Verify nothing else broke (run the test suite if a command is known).
7. Create a commit: `fix: <short description> (closes #$ARGUMENTS)`.

Do not change unrelated code. If you notice a separate bug while fixing this one, open a note for the user rather than fixing it silently.
