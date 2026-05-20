#!/usr/bin/env python3
"""PostToolUse hook: format and lint-fix a Python file after Claude edits it.

Claude Code pipes the tool event as JSON on stdin. We pull out the edited file
path and, if it's a .py file and ruff is installed, run `ruff format` and
`ruff check --fix` on it. No-ops cleanly when ruff is absent or the file isn't
Python, so it never blocks an edit.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # nothing to do; never block on a parse error

    path = (event.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        return 0
    if shutil.which("ruff") is None:
        return 0  # ruff not installed in this env — silently skip

    for args in (["ruff", "format", path], ["ruff", "check", "--fix", path]):
        subprocess.run(args, capture_output=True, text=True)

    # Tell Claude what happened (stdout from a hook is surfaced as context).
    print(f"ruff: formatted and lint-fixed {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
