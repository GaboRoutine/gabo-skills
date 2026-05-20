#!/usr/bin/env python3
"""Install gabo-skills into a target project.

gabo-skills keeps ONE tool-agnostic canonical source and generates the right
files for whichever AI assistant a project uses. The canonical source lives in:

  skills/<name>/SKILL.md   one skill per directory, plus bundled assets
  skills/<name>/...        (scripts/, reference.md, checklist.md, ...)
  agents/<name>.md         subagent definitions (Claude Code native)
  personas/<name>.md       voice/output-style definitions
  hooks/<file>             hook scripts referenced by settings.json
  config/                  repo-level templates: CLAUDE.md, settings.json,
                           settings.local.json, mcp.json, worktreeinclude

From this one source the installer emits, per tool:

  claude-code  →  full native .claude/ (directory skills + scripts, agents,
                  output-styles, hooks, settings) + CLAUDE.md + .mcp.json +
                  .worktreeinclude. Registers Anthropic's engineering plugin.
  cursor       →  .cursor/rules/*.mdc (skills + project/persona/agent rules),
                  .cursor/mcp.json, bundled scripts copied alongside.
  windsurf     →  .windsurf/rules/*.md, .windsurf/mcp_config.json, scripts.
  copilot      →  .github/instructions/*.instructions.md + copilot-instructions.md.
  codex        →  AGENTS.md (rules + skills + personas + agents, marker-fenced),
                  scripts under .agents/skills/<name>/.

Skill bodies may reference a bundled script with the token ${SKILL_DIR}; the
installer rewrites it to the per-tool location where the script is copied.

Usage:
  ./install.py /path/to/project
  ./install.py /path/to/project --tools claude-code,cursor
  ./install.py /path/to/project --no-engineering
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SKILLS_DIR = REPO_ROOT / "skills"
AGENTS_DIR = REPO_ROOT / "agents"
PERSONAS_DIR = REPO_ROOT / "personas"
HOOKS_DIR = REPO_ROOT / "hooks"
CONFIG_DIR = REPO_ROOT / "config"

MARK_BEGIN = "<!-- BEGIN gabo-skills -->"
MARK_END = "<!-- END gabo-skills -->"
SKILL_DIR_TOKEN = "${SKILL_DIR}"

ALL_TOOLS = ["claude-code", "cursor", "copilot", "windsurf", "codex"]

ENGINEERING_MARKETPLACE = "knowledge-work-plugins"
ENGINEERING_PLUGIN = f"engineering@{ENGINEERING_MARKETPLACE}"
ENGINEERING_REPO = "anthropics/knowledge-work-plugins"


# ─── Frontmatter parser ─────────────────────────────────────────────────────
# Minimal YAML-ish reader for the small subset we use: scalar strings/bools and
# one-level lists of strings. Avoids a PyYAML dependency.

def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    header, body = text[4:end], text[end + 5 :]
    meta: dict = {}
    list_key: str | None = None
    for raw in header.splitlines():
        stripped = raw.strip()
        if not stripped:
            list_key = None
            continue
        if list_key and raw.startswith(("  - ", "  -")):
            meta[list_key].append(raw.split("-", 1)[1].strip().strip('"').strip("'"))
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if not m:
            list_key = None
            continue
        key, value = m.group(1), m.group(2).strip()
        if value == "":
            meta[key] = []
            list_key = key
        elif value.lower() in ("true", "false"):
            meta[key] = value.lower() == "true"
            list_key = None
        else:
            meta[key] = value.strip('"').strip("'")
            list_key = None
    return meta, body


# ─── Canonical loaders ──────────────────────────────────────────────────────


def load_skills() -> list[dict]:
    skills: list[dict] = []
    if not SKILLS_DIR.is_dir():
        return skills
    for d in sorted(SKILLS_DIR.iterdir()):
        skill_md = d / "SKILL.md"
        if not d.is_dir() or not skill_md.exists():
            continue
        meta, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        allowed = meta.get("allowed-tools", "")
        if isinstance(allowed, list):
            allowed = " ".join(allowed)
        assets = [
            p
            for p in sorted(d.rglob("*"))
            if p.is_file() and p != skill_md and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ]
        skills.append(
            {
                "name": meta.get("name") or d.name,
                "description": meta.get("description", ""),
                "globs": meta.get("globs") or [],
                "always": bool(meta.get("always", False)),
                "disable-model-invocation": bool(meta.get("disable-model-invocation", False)),
                "user-invocable": meta.get("user-invocable"),
                "allowed-tools": allowed,
                "argument-hint": meta.get("argument-hint", ""),
                "when-to-use": meta.get("when-to-use", ""),
                "cc-context": meta.get("cc-context", ""),
                "cc-agent": meta.get("cc-agent", ""),
                "body": body.lstrip("\n"),
                "dir": d,
                "assets": assets,  # paths relative-to-dir reconstructed at copy time
            }
        )
    return skills


def load_docs(dir_path: Path) -> list[dict]:
    """Load agents/ or personas/ as {name, description, raw, body}."""
    out: list[dict] = []
    if not dir_path.is_dir():
        return out
    for p in sorted(dir_path.glob("*.md")):
        raw = p.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        out.append(
            {
                "name": meta.get("name") or p.stem,
                "description": meta.get("description", ""),
                "raw": raw,
                "body": body.strip(),
            }
        )
    return out


def load_config() -> dict:
    def read_text(name: str) -> str:
        p = CONFIG_DIR / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def read_json(name: str) -> dict:
        p = CONFIG_DIR / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    return {
        "claude_md": read_text("CLAUDE.md"),
        "worktreeinclude": read_text("worktreeinclude"),
        "settings": read_json("settings.json"),
        "settings_local": read_json("settings.local.json"),
        "mcp": read_json("mcp.json"),
    }


# ─── Shared helpers ─────────────────────────────────────────────────────────


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def write_text(path: Path, content: str, target: Path, written: list[str], note: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    written.append(rel(path, target) + (f"  ({note})" if note else ""))


def deep_merge(base: dict, overlay: dict) -> dict:
    """Recurse dicts, union lists (order-preserving, deduped), overlay wins scalars."""
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], val)
        elif isinstance(val, list) and isinstance(base.get(key), list):
            merged = list(base[key])
            for item in val:
                if item not in merged:
                    merged.append(item)
            base[key] = merged
        else:
            base[key] = val
    return base


def merge_json_file(overlay: dict, dst: Path, target: Path, written: list[str], label: str) -> None:
    if not overlay:
        return
    base: dict = {}
    existed = dst.exists()
    if existed:
        try:
            base = json.loads(dst.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  warn: existing {dst} is not valid JSON; leaving it alone")
            return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(deep_merge(base, overlay), indent=2) + "\n", encoding="utf-8")
    written.append(f"{rel(dst, target)}  ({label + ' merged' if existed else label})")


def seed_if_absent(content: str, dst: Path, target: Path, written: list[str]) -> None:
    if dst.exists():
        print(f"  skip: {rel(dst, target)} already exists (left untouched)")
        return
    write_text(dst, content, target, written, "seeded")


def copy_assets(skill: dict, skill_dir: Path, target: Path, written: list[str]) -> None:
    """Copy a skill's bundled files into skill_dir, preserving subpaths + exec bit."""
    for asset in skill["assets"]:
        sub = asset.relative_to(skill["dir"])
        out = skill_dir / sub
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, out)  # copy2 preserves the executable bit
        written.append(rel(out, target))


def body_for(skill: dict, skill_dir_rel: str) -> str:
    return skill["body"].replace(SKILL_DIR_TOKEN, skill_dir_rel)


# ─── claude-code ────────────────────────────────────────────────────────────


def _cc_skill_frontmatter(s: dict) -> str:
    lines = ["---", f"name: {s['name']}", f"description: {s['description']}"]
    if s.get("when-to-use"):
        lines.append(f"when_to_use: {s['when-to-use']}")
    if s.get("argument-hint"):
        lines.append(f'argument-hint: "{s["argument-hint"]}"')
    if s.get("disable-model-invocation"):
        lines.append("disable-model-invocation: true")
    if s.get("user-invocable") is False:
        lines.append("user-invocable: false")
    if s.get("allowed-tools"):
        lines.append(f"allowed-tools: {s['allowed-tools']}")
    if s.get("cc-context"):
        lines.append(f"context: {s['cc-context']}")
    if s.get("cc-agent"):
        lines.append(f"agent: {s['cc-agent']}")
    if s.get("globs"):
        lines.append("paths:")
        lines.extend(f'  - "{g}"' for g in s["globs"])
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def install_claude_code(
    target: Path, skills: list[dict], agents: list[dict], personas: list[dict], config: dict, with_engineering: bool
) -> list[str]:
    written: list[str] = []

    for s in skills:
        skill_dir_rel = f".claude/skills/{s['name']}"
        skill_dir = target / skill_dir_rel
        write_text(skill_dir / "SKILL.md", _cc_skill_frontmatter(s) + body_for(s, skill_dir_rel), target, written)
        copy_assets(s, skill_dir, target, written)

    for a in agents:
        write_text(target / ".claude" / "agents" / f"{a['name']}.md", a["raw"], target, written)

    for p in personas:
        write_text(target / ".claude" / "output-styles" / f"{slug(p['name'])}.md", p["raw"], target, written)

    for hook in sorted(HOOKS_DIR.glob("*")) if HOOKS_DIR.is_dir() else []:
        if hook.is_file():
            out = target / ".claude" / "hooks" / hook.name
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(hook, out)
            written.append(rel(out, target))

    # settings.json — deep-merge, toggling the engineering plugin.
    settings = json.loads(json.dumps(config["settings"]))  # deep copy
    if not with_engineering:
        settings.get("enabledPlugins", {}).pop(ENGINEERING_PLUGIN, None)
        settings.get("extraKnownMarketplaces", {}).pop(ENGINEERING_MARKETPLACE, None)
    elif settings:
        settings.setdefault("extraKnownMarketplaces", {})[ENGINEERING_MARKETPLACE] = {
            "source": {"source": "github", "repo": ENGINEERING_REPO}
        }
        settings.setdefault("enabledPlugins", {})[ENGINEERING_PLUGIN] = True
    merge_json_file(settings, target / ".claude" / "settings.json", target, written, "settings")

    if config["settings_local"]:
        seed_if_absent(
            json.dumps(config["settings_local"], indent=2) + "\n",
            target / ".claude" / "settings.local.json",
            target,
            written,
        )
    if config["claude_md"]:
        seed_if_absent(config["claude_md"], target / "CLAUDE.md", target, written)
    merge_json_file(config["mcp"], target / ".mcp.json", target, written, "MCP servers")
    if config["worktreeinclude"]:
        seed_if_absent(config["worktreeinclude"], target / ".worktreeinclude", target, written)

    return written


# ─── cursor ─────────────────────────────────────────────────────────────────


def install_cursor(
    target: Path, skills: list[dict], agents: list[dict], personas: list[dict], config: dict
) -> list[str]:
    written: list[str] = []
    rules = target / ".cursor" / "rules"

    for s in skills:
        skill_dir_rel = f".cursor/rules/{s['name']}"
        lines = ["---"]
        if s["description"]:
            lines.append(f"description: {s['description']}")
        if s["globs"]:
            lines.append("globs:")
            lines.extend(f'  - "{g}"' for g in s["globs"])
        lines.append(f"alwaysApply: {'true' if s['always'] else 'false'}")
        lines.append("---\n")
        write_text(rules / f"{s['name']}.mdc", "\n".join(lines) + "\n" + body_for(s, skill_dir_rel), target, written)
        copy_assets(s, target / skill_dir_rel, target, written)

    if config["claude_md"]:
        front = "---\ndescription: Project rules (always applied)\nalwaysApply: true\n---\n\n"
        write_text(rules / "project.mdc", front + config["claude_md"], target, written)

    for kind, items in (("persona", personas), ("agent", agents)):
        for it in items:
            front = f"---\ndescription: {kind.title()} — {it['description']}\nalwaysApply: false\n---\n\n"
            header = f"# {kind.title()}: {it['name']}\n\n"
            write_text(rules / f"{kind}-{slug(it['name'])}.mdc", front + header + it["body"] + "\n", target, written)

    merge_json_file(config["mcp"], target / ".cursor" / "mcp.json", target, written, "MCP servers")
    return written


# ─── windsurf ───────────────────────────────────────────────────────────────


def install_windsurf(
    target: Path, skills: list[dict], agents: list[dict], personas: list[dict], config: dict
) -> list[str]:
    written: list[str] = []
    rules = target / ".windsurf" / "rules"

    for s in skills:
        skill_dir_rel = f".windsurf/rules/{s['name']}"
        trigger = "always_on" if s["always"] else ("glob" if s["globs"] else "model_decision")
        lines = ["---", f"trigger: {trigger}"]
        if s["description"]:
            lines.append(f"description: {s['description']}")
        if s["globs"] and trigger == "glob":
            lines.append("globs:")
            lines.extend(f'  - "{g}"' for g in s["globs"])
        lines.append("---\n")
        write_text(rules / f"{s['name']}.md", "\n".join(lines) + "\n" + body_for(s, skill_dir_rel), target, written)
        copy_assets(s, target / skill_dir_rel, target, written)

    if config["claude_md"]:
        write_text(rules / "project.md", "---\ntrigger: always_on\n---\n\n" + config["claude_md"], target, written)

    for kind, items in (("persona", personas), ("agent", agents)):
        for it in items:
            front = f"---\ntrigger: model_decision\ndescription: {kind.title()} — {it['description']}\n---\n\n"
            header = f"# {kind.title()}: {it['name']}\n\n"
            write_text(rules / f"{kind}-{slug(it['name'])}.md", front + header + it["body"] + "\n", target, written)

    merge_json_file(config["mcp"], target / ".windsurf" / "mcp_config.json", target, written, "MCP servers")
    return written


# ─── copilot ────────────────────────────────────────────────────────────────


def install_copilot(
    target: Path, skills: list[dict], agents: list[dict], personas: list[dict], config: dict
) -> list[str]:
    written: list[str] = []
    instr = target / ".github" / "instructions"

    for s in skills:
        skill_dir_rel = f".github/instructions/{s['name']}"
        glob = s["globs"][0] if s["globs"] else "**"
        front = f'---\napplyTo: "{glob}"\n---\n\n'
        write_text(instr / f"{s['name']}.instructions.md", front + body_for(s, skill_dir_rel), target, written)
        copy_assets(s, target / skill_dir_rel, target, written)

    for kind, items in (("persona", personas), ("agent", agents)):
        for it in items:
            front = '---\napplyTo: "**"\n---\n\n'
            header = f"# {kind.title()}: {it['name']}\n_{it['description']}_\n\n"
            write_text(instr / f"{kind}-{slug(it['name'])}.instructions.md", front + header + it["body"] + "\n", target, written)

    if config["claude_md"]:
        seed_if_absent(config["claude_md"], target / ".github" / "copilot-instructions.md", target, written)
    print("  note: Copilot has no standard project MCP config; skipped .mcp for copilot")
    return written


# ─── codex ──────────────────────────────────────────────────────────────────


def install_codex(
    target: Path, skills: list[dict], agents: list[dict], personas: list[dict], config: dict
) -> list[str]:
    written: list[str] = []
    block: list[str] = [MARK_BEGIN, "", "# gabo-skills (managed — do not edit inside the markers)", ""]

    if config["claude_md"]:
        block.append("## Project rules")
        block.append("")
        block.append(config["claude_md"].strip())
        block.append("")

    block.append("# Skills")
    block.append("")
    for s in skills:
        skill_dir_rel = f".agents/skills/{s['name']}"
        block.append(f"## {s['name']}")
        if s["description"]:
            block.append(f"_{s['description']}_\n")
        block.append(body_for(s, skill_dir_rel).rstrip())
        block.append("")
        copy_assets(s, target / skill_dir_rel, target, written)

    for kind, items in (("Personas", personas), ("Agents", agents)):
        if not items:
            continue
        block.append(f"# {kind}")
        block.append("")
        for it in items:
            block.append(f"## {it['name']}")
            if it["description"]:
                block.append(f"_{it['description']}_\n")
            block.append(it["body"].rstrip())
            block.append("")

    block.append(MARK_END)
    new_block = "\n".join(block)

    out = target / "AGENTS.md"
    if out.exists():
        existing = out.read_text(encoding="utf-8")
        pattern = re.compile(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END), re.DOTALL)
        # Replace via a function so backslash sequences in the block (e.g. "\w" in
        # skill bodies) aren't interpreted as regex replacement templates.
        new_text = pattern.sub(lambda _: new_block, existing) if pattern.search(existing) else existing.rstrip() + "\n\n" + new_block + "\n"
    else:
        new_text = new_block + "\n"
    out.write_text(new_text, encoding="utf-8")
    written.append("AGENTS.md")
    print("  note: Codex has no standard project MCP config; skipped .mcp for codex")
    return written


# ─── Main ───────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install gabo-skills into a target project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ./install.py ../gabo\n"
            "  ./install.py ../gabo --tools claude-code,cursor\n"
            "  ./install.py ../gabo --no-engineering\n"
        ),
    )
    parser.add_argument("target", help="Path to the project directory")
    parser.add_argument("--tools", default=",".join(ALL_TOOLS), help=f"Comma-separated. Default: {','.join(ALL_TOOLS)}")
    parser.add_argument(
        "--no-engineering", action="store_true", help="Skip registering Anthropic's engineering plugin (Claude Code)"
    )
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        print(f"error: target is not a directory: {target}", file=sys.stderr)
        return 2

    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    unknown = [t for t in tools if t not in ALL_TOOLS]
    if unknown:
        print(f"error: unknown tool(s): {unknown}. Valid: {ALL_TOOLS}", file=sys.stderr)
        return 2

    skills = load_skills()
    agents = load_docs(AGENTS_DIR)
    personas = load_docs(PERSONAS_DIR)
    config = load_config()
    if not skills:
        print(f"error: no skills found under {SKILLS_DIR}/ (expected skills/<name>/SKILL.md)", file=sys.stderr)
        return 1

    print(f"Installing → {target}")
    print(f"Canonical source: {len(skills)} skill(s), {len(agents)} agent(s), {len(personas)} persona(s)")
    print(f"Tools: {', '.join(tools)}")
    if "claude-code" in tools and not args.no_engineering:
        print(f"Engineering plugin: {ENGINEERING_PLUGIN} (Claude Code)")
    print()

    handlers = {
        "claude-code": lambda: install_claude_code(target, skills, agents, personas, config, not args.no_engineering),
        "cursor": lambda: install_cursor(target, skills, agents, personas, config),
        "copilot": lambda: install_copilot(target, skills, agents, personas, config),
        "windsurf": lambda: install_windsurf(target, skills, agents, personas, config),
        "codex": lambda: install_codex(target, skills, agents, personas, config),
    }
    for tool in tools:
        print(f"[{tool}]")
        for path in handlers[tool]():
            print(f"  → {path}")
        print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
