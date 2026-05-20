---
name: commit
description: Stage and commit the current changes with a well-crafted message. Use when asked to "commit", "create a commit", "save my work", or "git commit".
disable-model-invocation: true
allowed-tools: Bash(git *)
---

# Commit

## Current state

!`git status --short`

## Staged and unstaged diff

!`git diff HEAD`

## Recent commits (for message style)

!`git log --oneline -5`

## Instructions

Stage and commit the changes above:

1. Review the diff to understand what changed.
2. Stage relevant files by name (avoid `git add -A` / `git add .` unless every file belongs).
3. Do not commit anything that looks like a secret (`.env`, tokens) or the embedding
   cache (`embeddings/embeddings_*.npy`). Warn the user if you see them staged.
4. Write the message:
   - First line: imperative, under 72 chars, no trailing period. Match the tone of the
     recent commits shown above.
   - Blank line, then body (optional): explain *why*, not *what*.
   - For module changes, name the module: `store: add pgvector upsert`.
5. `git commit -m "..."`, then confirm with `git log --oneline -1`.
