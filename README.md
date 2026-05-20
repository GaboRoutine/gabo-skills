# gabo-skills

One **tool-agnostic canonical source** of AI coding skills, agents, personas, and
config — authored once, **generated** into the right shape for whichever assistant a
project uses: **Claude Code**, **Cursor**, **GitHub Copilot**, **Windsurf**, **Codex**.

![No deps](https://img.shields.io/badge/deps-node%20stdlib%20only-green)

## The idea

Every AI tool wants its instructions somewhere different, and the richer features
(subagents, personas, hooks, MCP) don't exist in all of them. So this repo keeps a
single canonical source and the installer *generates* per-tool output — the full
native `.claude/` for Claude Code, and best-effort equivalents everywhere else.

```
                         ┌── .claude/  (skills + scripts, agents, output-styles,
                         │              hooks, settings) + CLAUDE.md + .mcp.json
   canonical source ─────┤── .cursor/  (rules/*.mdc + scripts + mcp.json)
   (this repo)           ├── .windsurf/(rules/*.md + scripts + mcp_config.json)
                         ├── .github/  (instructions/*.md + copilot-instructions.md)
                         └── AGENTS.md (Codex: rules + skills + personas + agents)
```

## Canonical source layout

```
skills/<name>/SKILL.md     one skill per directory (+ bundled scripts/refs/checklists)
agents/<name>.md           subagent definitions
personas/<name>.md         voice / output-style definitions
hooks/<file>               hook scripts referenced by settings.json
config/                    repo-level templates:
  CLAUDE.md                  project rules
  settings.json              permissions, env, hooks, MCP enablement, engineering plugin
  settings.local.json        local/personal overrides (seeded only if absent)
  mcp.json                   MCP servers
  worktreeinclude            files to copy into new git worktrees
bin/cli.js                 the generator (Node, zero dependencies)
install.py                 the same generator in Python (kept as an alternative)
```

Each piece has its own README/format notes — start with [`skills/README.md`](skills/README.md).

## Install

Run it straight from npm with `npx` — no clone, no Python. It installs into the
**current directory** and asks which AI tools you use:

```bash
npx @gabo-routine/gabo-skills                              # interactive, into cwd
npx @gabo-routine/gabo-skills ../my-project                # pick a different target
npx @gabo-routine/gabo-skills --tools claude-code,cursor   # non-interactive
npx @gabo-routine/gabo-skills --yes                         # all tools, no prompts
npx @gabo-routine/gabo-skills --no-engineering              # skip the engineering plugin
```

The interactive prompt lets you choose tools by number or name (Enter selects all),
and — if Claude Code is selected — whether to register the engineering plugin.

<details>
<summary>Prefer Python? The original generator still works.</summary>

```bash
git clone https://github.com/yourusername/gabo-skills.git
cd gabo-skills
./install.py ../gabo                       # all five tools
./install.py ../gabo --tools claude-code   # just one
./install.py ../gabo --no-engineering      # skip the engineering plugin
```

Both generators produce byte-identical output.
</details>

Re-running is safe: file outputs are overwritten in place, JSON settings/`.mcp.json`
are **deep-merged** (your keys are preserved, lists unioned), and files that are
yours to own — `CLAUDE.md`, `settings.local.json`, `.worktreeinclude` — are seeded
only if absent, never clobbered.

## What each tool gets

| Capability | Claude Code | Cursor | Windsurf | Copilot | Codex |
|---|---|---|---|---|---|
| Skills | `.claude/skills/<n>/SKILL.md` | `.cursor/rules/<n>.mdc` | `.windsurf/rules/<n>.md` | `.github/instructions/<n>.instructions.md` | section in `AGENTS.md` |
| Bundled scripts | in the skill dir, runnable | copied + referenced | copied + referenced | copied + referenced | under `.agents/skills/<n>/` |
| Project rules (`CLAUDE.md`) | `CLAUDE.md` | `rules/project.mdc` (always) | `rules/project.md` (always_on) | `.github/copilot-instructions.md` | top of `AGENTS.md` |
| Subagents | `.claude/agents/*.md` (native) | `rules/agent-*.mdc` | `rules/agent-*.md` | `instructions/agent-*` | `AGENTS.md` section |
| Personas | `.claude/output-styles/*.md` (native) | `rules/persona-*.mdc` | `rules/persona-*.md` | `instructions/persona-*` | `AGENTS.md` section |
| Hooks | `.claude/hooks/*` + `settings.json` | — | — | — | — |
| MCP servers | `.mcp.json` | `.cursor/mcp.json` | `.windsurf/mcp_config.json` | — | — |
| worktree include | `.worktreeinclude` | — | — | — | — |

**Native** = first-class support. Everything else for non-Claude tools is best-effort:
subagents and personas become extra rule files the assistant can pull in on demand,
and bundled scripts are copied alongside the rule and referenced by path (via the
`${SKILL_DIR}` token, rewritten per tool — see [`skills/README.md`](skills/README.md)).

For **Claude Code**, the install also registers Anthropic's
[`engineering`](https://github.com/anthropics/knowledge-work-plugins) plugin
(`engineering:debug`, `engineering:code-review`, `engineering:architecture`, …) in
`settings.json`. Disable with `--no-engineering`.

## The skills (tailored to [`gabo`](../gabo))

gabo is a modular-monolith RSS intelligence feed; the skills encode its rules.

| Skill | What it does | Bundled assets |
|---|---|---|
| `module-boundary-check` | Verify the four modular-monolith boundary rules | `scripts/check_boundaries.py` (runnable AST check), `reference.md` |
| `new-module` | Scaffold a new bounded module in build order | `scripts/scaffold_module.py`, `checklist.md` |
| `embeddings-review` | Catch silent embedding bugs (pooling, device, cache) | `reference.md` of correctness traps |
| `architecture-sync` | Detect drift between `docs/architecture.md` and code | — |
| `commit` / `pr-review` | Git/PR workflows with the boundary rules baked in | dynamic `!`-command context |
| `changelog` `explain` `fix-issue` `refactor` `test-gen` | General-purpose dev skills | — |

**Agents:** `module-boundary-auditor`, `embeddings-reviewer`, `test-writer`.
**Personas:** `Senior Reviewer` (blunt, verdict-first), `Mentor` (teaching voice).

The two scripts are real and tested — `check_boundaries.py` flags cross-module
internal imports; `scaffold_module.py` generates a module's public surface + stub.

## Authoring

Add or edit a skill under `skills/<name>/` (see [`skills/README.md`](skills/README.md)
for the `SKILL.md` format and the `${SKILL_DIR}` script-reference token), drop agents
in `agents/`, personas in `personas/`, repo config in `config/`. Then re-run
`npx @gabo-routine/gabo-skills <project>` (or `./install.py <project>`) to regenerate
every tool's output.

## Uninstall

No uninstall command — each tool keeps its files in a known directory:

```bash
rm -rf .claude .cursor/rules .cursor/mcp.json .github/instructions \
       .github/copilot-instructions.md .windsurf .agents
# AGENTS.md / CLAUDE.md / .mcp.json: delete by hand (or just the marker block in AGENTS.md)
```

Dropping a tool from `--tools` on a re-run does **not** remove its previously-written
files — clean those up manually.

## Requirements

- Node 16+ (stdlib only — no `npm install` step) for `npx @gabo-routine/gabo-skills`
- or Python 3.8+ (stdlib only) for `./install.py`
- macOS / Linux / WSL

## Known caveats

- The JSON shape for Claude Code marketplace registration may evolve; verify against
  current docs if the engineering plugin doesn't auto-load.
- Cursor `.mdc` `globs` format varies between versions (string vs. list). The script
  emits the list form.
- Windsurf MCP config is often global, not per-project; the script writes a project
  `.windsurf/mcp_config.json` you may need to relocate.
- Copilot and Codex have no standard project-scoped MCP config, so MCP is skipped for
  them (you'll see a note during install).
- The script does **not** check that the target's Git is clean before writing — commit
  first if you want a safety net.

## License

MIT
