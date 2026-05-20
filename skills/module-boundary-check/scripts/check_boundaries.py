#!/usr/bin/env python3
"""Static check for gabo's modular-monolith boundary rule #1.

Flags imports that reach into a *sibling module's internals* — anything deeper
than the public surface `from gabo.<module> import ...`. Importing the top-level
shared types (`gabo.types`) or a module's own internals is allowed.

Usage:
    check_boundaries.py [PACKAGE_DIR]      # default: ./gabo

Exit code 0 = clean, 1 = violations found, 2 = bad invocation.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Top-level modules that are allowed to be imported by their public surface,
# plus shared modules everyone may import from directly.
SHARED_TOP_LEVEL = {"types", "__init__"}
# The scheduler orchestrates other modules, so it is permitted to import them.
ORCHESTRATORS = {"scheduler"}


def module_of(file: Path, root: Path) -> str | None:
    """Return the top-level module a file belongs to, or None if it sits at root."""
    rel = file.relative_to(root)
    return rel.parts[0] if len(rel.parts) > 1 else None


def violations_in(file: Path, root: Path, pkg: str) -> list[tuple[int, str, str]]:
    """Return (lineno, import_text, reason) for each boundary breach in `file`."""
    owner = module_of(file, root)
    found: list[tuple[int, str, str]] = []
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    except SyntaxError as exc:
        return [(exc.lineno or 0, "<syntax error>", str(exc))]

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        parts = node.module.split(".")
        if parts[0] != pkg or len(parts) < 2:
            continue  # not an intra-package import
        target = parts[1]
        if target in SHARED_TOP_LEVEL:
            continue  # gabo.types etc. — always allowed
        if target == owner:
            continue  # importing your own module's internals is fine
        if owner in ORCHESTRATORS:
            continue  # the scheduler may wire modules together
        if len(parts) > 2:  # gabo.<module>.<internal> from another module
            imported = ", ".join(a.name for a in node.names)
            found.append(
                (
                    node.lineno,
                    f"from {node.module} import {imported}",
                    f"reaches into '{target}' internals; import the public surface "
                    f"`from {pkg}.{target} import ...` instead",
                )
            )
    return found


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else "./gabo").resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    pkg = root.name
    files = sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    if not files:
        print(f"no .py files under {root}", file=sys.stderr)
        return 2

    total = 0
    for file in files:
        for lineno, text, reason in violations_in(file, root, pkg):
            total += 1
            rel = file.relative_to(root.parent)
            print(f"{rel}:{lineno}: {text}")
            print(f"    ↳ {reason}")

    if total:
        print(f"\n{total} boundary violation(s) found.")
        return 1
    print(f"clean: no cross-module internal imports under {pkg}/ ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
