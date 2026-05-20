#!/usr/bin/env python3
"""Scaffold a new bounded module for gabo's modular monolith.

Creates `gabo/<module>/__init__.py` (re-exporting the public surface) and a stub
implementation file with a runnable demo. Never overwrites existing files.

Usage:
    scaffold_module.py <module> [--root ./gabo] [--dry-run]

Known modules carry the right public-surface template from architecture.md; an
unknown name gets a generic stub plus a warning.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# module -> (stub filename, public symbols, stub body)
TEMPLATES: dict[str, tuple[str, list[str], str]] = {
    "ingestion": (
        "fetcher.py",
        ["fetch"],
        '''from gabo.types import Article


def fetch(feed_url: str | None = None) -> list[Article]:
    """Fetch and parse a feed into Articles. Stub — real impl uses feedparser."""
    return [Article(title="stub", description=f"feed_url={feed_url!r}", id="stub-1")]


if __name__ == "__main__":
    for a in fetch("https://example.com/feed.xml"):
        print(a)
''',
    ),
    "clustering": (
        "cluster.py",
        ["cluster"],
        '''from gabo.types import Article, Cluster


def cluster(articles: list[Article]) -> list[Cluster]:
    """Group article vectors into labelled clusters. Stub — real impl uses HDBSCAN."""
    if not articles:
        return []
    return [Cluster(id=0, label="all", article_ids=[a.id or str(i) for i, a in enumerate(articles)])]


if __name__ == "__main__":
    from gabo.ingestion import fetch

    for c in cluster(fetch()):
        print(c)
''',
    ),
    "store": (
        "vector_db.py",
        ["Store"],
        '''from gabo.types import Article


class Store:
    """Persist vectors + metadata. Stub — real impl uses Postgres + pgvector."""

    def __init__(self) -> None:
        self._articles: dict[str, Article] = {}

    def upsert(self, articles: list[Article], vectors: list[list[float]] | None = None) -> int:
        for a in articles:
            self._articles[a.id or a.title] = a
        return len(articles)

    def search(self, query_vector: list[float], k: int = 5) -> list[Article]:
        return list(self._articles.values())[:k]


if __name__ == "__main__":
    from gabo.ingestion import fetch

    store = Store()
    print(f"upserted {store.upsert(fetch())}")
''',
    ),
    "api": (
        "routes.py",
        ["feed", "search"],
        '''from gabo.ingestion import fetch
from gabo.store import Store
from gabo.types import Article

_store: Store | None = None


def _get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
        _store.upsert(fetch())
    return _store


def feed() -> list[dict]:
    return [vars(a) for a in _get_store().search(query_vector=[], k=100)]


def search(q: str, k: int = 5) -> list[dict]:
    return [vars(a) for a in _get_store().search(query_vector=[], k=k)]


if __name__ == "__main__":
    import json

    print(json.dumps(feed(), indent=2, default=str))
''',
    ),
    "scheduler": (
        "jobs.py",
        ["run_once"],
        '''from gabo.ingestion import fetch
from gabo.store import Store


def ingestion_job(store: Store) -> int:
    return store.upsert(fetch())


def run_once() -> None:
    store = Store()
    print(f"ingestion_job upserted {ingestion_job(store)}")


if __name__ == "__main__":
    run_once()
''',
    ),
}

GENERIC = (
    "{module}.py",
    ["main"],
    '''def main() -> None:
    """TODO: implement the {module} module's public surface."""
    print("Hello from gabo.{module}")


if __name__ == "__main__":
    main()
''',
)


def write(path: Path, content: str, dry_run: bool) -> str:
    if path.exists():
        return f"skip (exists)  {path}"
    if dry_run:
        return f"would create   {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"created        {path}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a gabo module.")
    parser.add_argument("module", help="module name, e.g. clustering")
    parser.add_argument("--root", default="./gabo", help="package dir (default ./gabo)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:])

    module = args.module.strip().lower()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: package dir not found: {root} (pass --root)", file=sys.stderr)
        return 2

    known = module in TEMPLATES
    fname, symbols, body = TEMPLATES[module] if known else GENERIC
    fname = fname.format(module=module)
    body = body.format(module=module)
    if not known:
        print(f"warn: '{module}' is not a known gabo module; using a generic stub.\n")

    mod_dir = root / module
    init_body = (
        f'"""Public surface of the {module} module.\n\n'
        f"Other modules import only what is re-exported here.\n"
        f'"""\n\n'
        f"from gabo.{module}.{Path(fname).stem} import {', '.join(symbols)}\n\n"
        f"__all__ = [{', '.join(repr(s) for s in symbols)}]\n"
    )

    print(write(mod_dir / "__init__.py", init_body, args.dry_run))
    print(write(mod_dir / fname, body, args.dry_run))
    print(f"\npublic surface: from gabo.{module} import {', '.join(symbols)}")
    print(f"demo:           python -m gabo.{module}.{Path(fname).stem}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
