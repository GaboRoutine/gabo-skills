---
name: explain
description: Explain a piece of code in depth. Use when asked to explain, document, walk through, or help understand code — a file, a function, a class, or a concept in the codebase.
always: false
argument-hint: "[file-or-symbol]"
---

# Explain

Target: $ARGUMENTS

## Instructions

Provide a thorough explanation structured as follows:

1. **What it does** — The purpose in one sentence. What problem does this solve?

2. **How it works** — Walk through the logic step by step. Reference specific line numbers, function names, or data structures. Do not paraphrase — point to the actual code.

3. **Why it's written this way** — Non-obvious design decisions, trade-offs, or historical reasons. Check git blame and inline comments before guessing. If the rationale is unclear, say so explicitly.

4. **Inputs and outputs** — What goes in, what comes out, and what side effects occur (mutations, I/O, state changes).

5. **Gotchas** — Edge cases, footguns, implicit assumptions, or anything that would surprise a capable engineer reading this for the first time.

Calibrate depth to complexity: a 10-line utility needs two paragraphs; a 500-line module needs a full section-by-section breakdown. Do not summarize if the user asked to understand — explain.
