---
name: changelog
description: Generate a changelog entry from recent git commits. Use when preparing a release, writing release notes, bumping a version, or asked to summarize what changed since the last release.
always: false
disable-model-invocation: true
allowed-tools: Bash(git *)
---

# Changelog

## Commits since last release

!`git log --oneline --no-merges $(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)..HEAD`

## Instructions

Generate a changelog entry for the commits above:

1. **Group by category** — use only the categories that have entries:
   - `Breaking Changes` — anything that changes existing behavior or API contracts
   - `Features` — new capabilities
   - `Bug Fixes` — things that were broken and now work
   - `Performance` — measurable speed or memory improvements
   - `Documentation` — user-visible doc changes
   - `Internal` — dependency bumps, CI changes, refactors with no user-facing effect

2. **Write in user-facing language.** Not "fix the null check in UserService" — instead "User lookup no longer crashes when the account has no email address." Someone reading the changelog should understand the impact without knowing the codebase.

3. **One bullet per change.** Merge related commits into a single entry when they're part of the same feature or fix.

4. **Skip pure internals** (CI tweaks, linter fixes, test-only changes) unless they fix something users reported.

5. **Format**:
   ```
   ## [Unreleased] – YYYY-MM-DD

   ### Breaking Changes
   - …

   ### Features
   - …

   ### Bug Fixes
   - …
   ```
