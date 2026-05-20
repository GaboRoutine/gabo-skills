---
name: test-gen
description: Generate tests for a file or function. Use when asked to "write tests", "add tests", "test this", "cover this with tests", or "increase test coverage".
always: false
argument-hint: "[file-or-function]"
globs:
  - "**/*.py"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.go"
  - "**/*.rs"
  - "**/*.rb"
---

# Generate Tests

Target: $ARGUMENTS

## Instructions

1. **Read the target** — Understand what `$ARGUMENTS` does before writing a single test.
2. **Discover conventions** — Find two or three existing test files to learn the framework, assertion style, file placement, and mock patterns in use. Follow them exactly.
3. **Place tests correctly** — Next to the source (`foo.ts` → `foo.test.ts`) unless the project uses a top-level `tests/` directory.
4. **Cover these cases**:
   - Happy path: normal inputs produce correct outputs.
   - Edge cases: empty, zero, null/undefined, max values, boundary conditions.
   - Error conditions: invalid inputs, network failures, missing resources — whatever can go wrong.
5. **Mock only at system boundaries** — external HTTP calls, databases, file I/O. Do not mock internal functions or the code under test.
6. **Name tests clearly** — The test name should describe the scenario: `"returns empty list when no users match the filter"`, not `"test 1"`.
7. Do not add test scaffolding or placeholder tests. Every test must assert something meaningful.
