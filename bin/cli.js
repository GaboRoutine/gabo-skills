#!/usr/bin/env node
"use strict";

/*
 * Install gabo-skills into a target project.
 *
 * gabo-skills keeps ONE tool-agnostic canonical source and generates the right
 * files for whichever AI assistant a project uses. The canonical source lives in:
 *
 *   skills/<name>/SKILL.md   one skill per directory, plus bundled assets
 *   skills/<name>/...        (scripts/, reference.md, checklist.md, ...)
 *   agents/<name>.md         subagent definitions (Claude Code native)
 *   personas/<name>.md       voice/output-style definitions
 *   hooks/<file>             hook scripts referenced by settings.json
 *   config/                  repo-level templates: CLAUDE.md, settings.json,
 *                            settings.local.json, mcp.json, worktreeinclude
 *
 * From this one source the installer emits, per tool:
 *
 *   claude-code  →  full native .claude/ + CLAUDE.md + .mcp.json + .worktreeinclude
 *   cursor       →  .cursor/rules/*.mdc, .cursor/mcp.json, bundled scripts
 *   windsurf     →  .windsurf/rules/*.md, .windsurf/mcp_config.json, scripts
 *   copilot      →  .github/instructions/*.instructions.md + copilot-instructions.md
 *   codex        →  AGENTS.md (marker-fenced) + scripts under .agents/skills/<name>/
 *
 * Skill bodies may reference a bundled script with ${SKILL_DIR}; the installer
 * rewrites it to the per-tool location where the script is copied.
 *
 * Usage:
 *   npx @gabo-routine/gabo-skills                       interactive, installs into cwd
 *   npx @gabo-routine/gabo-skills /path/to/project      interactive, custom target
 *   npx @gabo-routine/gabo-skills --tools claude-code,cursor   non-interactive
 *   npx @gabo-routine/gabo-skills --no-engineering
 *   npx @gabo-routine/gabo-skills --yes                 accept defaults, no prompts
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");

const REPO_ROOT = path.resolve(__dirname, "..");
const SKILLS_DIR = path.join(REPO_ROOT, "skills");
const AGENTS_DIR = path.join(REPO_ROOT, "agents");
const PERSONAS_DIR = path.join(REPO_ROOT, "personas");
const HOOKS_DIR = path.join(REPO_ROOT, "hooks");
const CONFIG_DIR = path.join(REPO_ROOT, "config");

const MARK_BEGIN = "<!-- BEGIN gabo-skills -->";
const MARK_END = "<!-- END gabo-skills -->";
const SKILL_DIR_TOKEN = "${SKILL_DIR}";

const ALL_TOOLS = ["claude-code", "cursor", "copilot", "windsurf", "codex"];

const ENGINEERING_MARKETPLACE = "knowledge-work-plugins";
const ENGINEERING_PLUGIN = `engineering@${ENGINEERING_MARKETPLACE}`;
const ENGINEERING_REPO = "anthropics/knowledge-work-plugins";

// ─── Frontmatter parser ─────────────────────────────────────────────────────
// Minimal YAML-ish reader for the small subset we use: scalar strings/bools and
// one-level lists of strings.

function stripQuotes(s) {
  if (s.startsWith('"') && s.endsWith('"')) return s.slice(1, -1);
  if (s.startsWith("'") && s.endsWith("'")) return s.slice(1, -1);
  return s;
}

function parseFrontmatter(text) {
  if (!text.startsWith("---\n")) return [{}, text];
  const end = text.indexOf("\n---\n", 4);
  if (end === -1) return [{}, text];
  const header = text.slice(4, end);
  const body = text.slice(end + 5);
  const meta = {};
  let listKey = null;
  for (const raw of header.split("\n")) {
    const stripped = raw.trim();
    if (!stripped) {
      listKey = null;
      continue;
    }
    if (listKey && (raw.startsWith("  - ") || raw.startsWith("  -"))) {
      const item = raw.split("-").slice(1).join("-").trim();
      meta[listKey].push(stripQuotes(item));
      continue;
    }
    const m = raw.match(/^([A-Za-z_][\w-]*):\s*(.*)$/);
    if (!m) {
      listKey = null;
      continue;
    }
    const key = m[1];
    const value = m[2].trim();
    if (value === "") {
      meta[key] = [];
      listKey = key;
    } else if (value.toLowerCase() === "true" || value.toLowerCase() === "false") {
      meta[key] = value.toLowerCase() === "true";
      listKey = null;
    } else {
      meta[key] = stripQuotes(value);
      listKey = null;
    }
  }
  return [meta, body];
}

// ─── Canonical loaders ──────────────────────────────────────────────────────

function isDir(p) {
  try {
    return fs.statSync(p).isDirectory();
  } catch {
    return false;
  }
}

function walkFiles(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walkFiles(full));
    } else if (entry.isFile()) {
      out.push(full);
    }
  }
  return out;
}

function lstripNewlines(s) {
  return s.replace(/^\n+/, "");
}

function loadSkills() {
  const skills = [];
  if (!isDir(SKILLS_DIR)) return skills;
  const entries = fs
    .readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();
  for (const name of entries) {
    const d = path.join(SKILLS_DIR, name);
    const skillMd = path.join(d, "SKILL.md");
    if (!fs.existsSync(skillMd)) continue;
    const [meta, body] = parseFrontmatter(fs.readFileSync(skillMd, "utf-8"));
    let allowed = meta["allowed-tools"] || "";
    if (Array.isArray(allowed)) allowed = allowed.join(" ");
    const assets = walkFiles(d)
      .filter(
        (p) =>
          p !== skillMd &&
          !p.split(path.sep).includes("__pycache__") &&
          !p.endsWith(".pyc")
      )
      .sort();
    skills.push({
      name: meta.name || name,
      description: meta.description || "",
      globs: meta.globs || [],
      always: Boolean(meta.always),
      "disable-model-invocation": Boolean(meta["disable-model-invocation"]),
      "user-invocable": meta["user-invocable"],
      "allowed-tools": allowed,
      "argument-hint": meta["argument-hint"] || "",
      "when-to-use": meta["when-to-use"] || "",
      "cc-context": meta["cc-context"] || "",
      "cc-agent": meta["cc-agent"] || "",
      body: lstripNewlines(body),
      dir: d,
      assets,
    });
  }
  return skills;
}

function loadDocs(dirPath) {
  const out = [];
  if (!isDir(dirPath)) return out;
  const files = fs
    .readdirSync(dirPath)
    .filter((f) => f.endsWith(".md"))
    .sort();
  for (const f of files) {
    const p = path.join(dirPath, f);
    const raw = fs.readFileSync(p, "utf-8");
    const [meta, body] = parseFrontmatter(raw);
    out.push({
      name: meta.name || path.basename(f, ".md"),
      description: meta.description || "",
      raw,
      body: body.trim(),
    });
  }
  return out;
}

function loadConfig() {
  const readText = (name) => {
    const p = path.join(CONFIG_DIR, name);
    return fs.existsSync(p) ? fs.readFileSync(p, "utf-8") : "";
  };
  const readJson = (name) => {
    const p = path.join(CONFIG_DIR, name);
    return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf-8")) : {};
  };
  return {
    claude_md: readText("CLAUDE.md"),
    worktreeinclude: readText("worktreeinclude"),
    settings: readJson("settings.json"),
    settings_local: readJson("settings.local.json"),
    mcp: readJson("mcp.json"),
  };
}

// ─── Shared helpers ─────────────────────────────────────────────────────────

function slug(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function rel(p, root) {
  return path.relative(root, p);
}

function writeText(p, content, target, written, note = "") {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, content, "utf-8");
  written.push(rel(p, target) + (note ? `  (${note})` : ""));
}

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function deepMerge(base, overlay) {
  for (const [key, val] of Object.entries(overlay)) {
    if (isPlainObject(val) && isPlainObject(base[key])) {
      deepMerge(base[key], val);
    } else if (Array.isArray(val) && Array.isArray(base[key])) {
      const merged = [...base[key]];
      for (const item of val) {
        if (!merged.some((m) => JSON.stringify(m) === JSON.stringify(item))) {
          merged.push(item);
        }
      }
      base[key] = merged;
    } else {
      base[key] = val;
    }
  }
  return base;
}

function mergeJsonFile(overlay, dst, target, written, label) {
  if (!overlay || Object.keys(overlay).length === 0) return;
  let base = {};
  const existed = fs.existsSync(dst);
  if (existed) {
    try {
      base = JSON.parse(fs.readFileSync(dst, "utf-8"));
    } catch {
      console.log(`  warn: existing ${dst} is not valid JSON; leaving it alone`);
      return;
    }
  }
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.writeFileSync(dst, JSON.stringify(deepMerge(base, overlay), null, 2) + "\n", "utf-8");
  written.push(`${rel(dst, target)}  (${existed ? label + " merged" : label})`);
}

function seedIfAbsent(content, dst, target, written) {
  if (fs.existsSync(dst)) {
    console.log(`  skip: ${rel(dst, target)} already exists (left untouched)`);
    return;
  }
  writeText(dst, content, target, written, "seeded");
}

function copyAssets(skill, skillDir, target, written) {
  for (const asset of skill.assets) {
    const sub = path.relative(skill.dir, asset);
    const out = path.join(skillDir, sub);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.copyFileSync(asset, out);
    fs.chmodSync(out, fs.statSync(asset).mode); // preserve executable bit
    written.push(rel(out, target));
  }
}

function bodyFor(skill, skillDirRel) {
  return skill.body.split(SKILL_DIR_TOKEN).join(skillDirRel);
}

// ─── claude-code ────────────────────────────────────────────────────────────

function ccSkillFrontmatter(s) {
  const lines = ["---", `name: ${s.name}`, `description: ${s.description}`];
  if (s["when-to-use"]) lines.push(`when_to_use: ${s["when-to-use"]}`);
  if (s["argument-hint"]) lines.push(`argument-hint: "${s["argument-hint"]}"`);
  if (s["disable-model-invocation"]) lines.push("disable-model-invocation: true");
  if (s["user-invocable"] === false) lines.push("user-invocable: false");
  if (s["allowed-tools"]) lines.push(`allowed-tools: ${s["allowed-tools"]}`);
  if (s["cc-context"]) lines.push(`context: ${s["cc-context"]}`);
  if (s["cc-agent"]) lines.push(`agent: ${s["cc-agent"]}`);
  if (s.globs && s.globs.length) {
    lines.push("paths:");
    for (const g of s.globs) lines.push(`  - "${g}"`);
  }
  lines.push("---");
  return lines.join("\n") + "\n\n";
}

function installClaudeCode(target, skills, agents, personas, config, withEngineering) {
  const written = [];

  for (const s of skills) {
    const skillDirRel = `.claude/skills/${s.name}`;
    const skillDir = path.join(target, skillDirRel);
    writeText(path.join(skillDir, "SKILL.md"), ccSkillFrontmatter(s) + bodyFor(s, skillDirRel), target, written);
    copyAssets(s, skillDir, target, written);
  }

  for (const a of agents) {
    writeText(path.join(target, ".claude", "agents", `${a.name}.md`), a.raw, target, written);
  }

  for (const p of personas) {
    writeText(path.join(target, ".claude", "output-styles", `${slug(p.name)}.md`), p.raw, target, written);
  }

  if (isDir(HOOKS_DIR)) {
    for (const hook of fs.readdirSync(HOOKS_DIR).sort()) {
      const src = path.join(HOOKS_DIR, hook);
      if (fs.statSync(src).isFile()) {
        const out = path.join(target, ".claude", "hooks", hook);
        fs.mkdirSync(path.dirname(out), { recursive: true });
        fs.copyFileSync(src, out);
        fs.chmodSync(out, fs.statSync(src).mode);
        written.push(rel(out, target));
      }
    }
  }

  // settings.json — deep-merge, toggling the engineering plugin.
  const settings = JSON.parse(JSON.stringify(config.settings));
  if (!withEngineering) {
    if (settings.enabledPlugins) delete settings.enabledPlugins[ENGINEERING_PLUGIN];
    if (settings.extraKnownMarketplaces) delete settings.extraKnownMarketplaces[ENGINEERING_MARKETPLACE];
  } else if (Object.keys(settings).length) {
    settings.extraKnownMarketplaces = settings.extraKnownMarketplaces || {};
    settings.extraKnownMarketplaces[ENGINEERING_MARKETPLACE] = {
      source: { source: "github", repo: ENGINEERING_REPO },
    };
    settings.enabledPlugins = settings.enabledPlugins || {};
    settings.enabledPlugins[ENGINEERING_PLUGIN] = true;
  }
  mergeJsonFile(settings, path.join(target, ".claude", "settings.json"), target, written, "settings");

  if (config.settings_local && Object.keys(config.settings_local).length) {
    seedIfAbsent(
      JSON.stringify(config.settings_local, null, 2) + "\n",
      path.join(target, ".claude", "settings.local.json"),
      target,
      written
    );
  }
  if (config.claude_md) {
    seedIfAbsent(config.claude_md, path.join(target, "CLAUDE.md"), target, written);
  }
  mergeJsonFile(config.mcp, path.join(target, ".mcp.json"), target, written, "MCP servers");
  if (config.worktreeinclude) {
    seedIfAbsent(config.worktreeinclude, path.join(target, ".worktreeinclude"), target, written);
  }

  return written;
}

// ─── cursor ─────────────────────────────────────────────────────────────────

function installCursor(target, skills, agents, personas, config) {
  const written = [];
  const rules = path.join(target, ".cursor", "rules");

  for (const s of skills) {
    const skillDirRel = `.cursor/rules/${s.name}`;
    const lines = ["---"];
    if (s.description) lines.push(`description: ${s.description}`);
    if (s.globs.length) {
      lines.push("globs:");
      for (const g of s.globs) lines.push(`  - "${g}"`);
    }
    lines.push(`alwaysApply: ${s.always ? "true" : "false"}`);
    lines.push("---\n");
    writeText(path.join(rules, `${s.name}.mdc`), lines.join("\n") + "\n" + bodyFor(s, skillDirRel), target, written);
    copyAssets(s, path.join(target, skillDirRel), target, written);
  }

  if (config.claude_md) {
    const front = "---\ndescription: Project rules (always applied)\nalwaysApply: true\n---\n\n";
    writeText(path.join(rules, "project.mdc"), front + config.claude_md, target, written);
  }

  for (const [kind, items] of [["persona", personas], ["agent", agents]]) {
    for (const it of items) {
      const front = `---\ndescription: ${cap(kind)} — ${it.description}\nalwaysApply: false\n---\n\n`;
      const header = `# ${cap(kind)}: ${it.name}\n\n`;
      writeText(path.join(rules, `${kind}-${slug(it.name)}.mdc`), front + header + it.body + "\n", target, written);
    }
  }

  mergeJsonFile(config.mcp, path.join(target, ".cursor", "mcp.json"), target, written, "MCP servers");
  return written;
}

// ─── windsurf ───────────────────────────────────────────────────────────────

function installWindsurf(target, skills, agents, personas, config) {
  const written = [];
  const rules = path.join(target, ".windsurf", "rules");

  for (const s of skills) {
    const skillDirRel = `.windsurf/rules/${s.name}`;
    const trigger = s.always ? "always_on" : s.globs.length ? "glob" : "model_decision";
    const lines = ["---", `trigger: ${trigger}`];
    if (s.description) lines.push(`description: ${s.description}`);
    if (s.globs.length && trigger === "glob") {
      lines.push("globs:");
      for (const g of s.globs) lines.push(`  - "${g}"`);
    }
    lines.push("---\n");
    writeText(path.join(rules, `${s.name}.md`), lines.join("\n") + "\n" + bodyFor(s, skillDirRel), target, written);
    copyAssets(s, path.join(target, skillDirRel), target, written);
  }

  if (config.claude_md) {
    writeText(path.join(rules, "project.md"), "---\ntrigger: always_on\n---\n\n" + config.claude_md, target, written);
  }

  for (const [kind, items] of [["persona", personas], ["agent", agents]]) {
    for (const it of items) {
      const front = `---\ntrigger: model_decision\ndescription: ${cap(kind)} — ${it.description}\n---\n\n`;
      const header = `# ${cap(kind)}: ${it.name}\n\n`;
      writeText(path.join(rules, `${kind}-${slug(it.name)}.md`), front + header + it.body + "\n", target, written);
    }
  }

  mergeJsonFile(config.mcp, path.join(target, ".windsurf", "mcp_config.json"), target, written, "MCP servers");
  return written;
}

// ─── copilot ────────────────────────────────────────────────────────────────

function installCopilot(target, skills, agents, personas, config) {
  const written = [];
  const instr = path.join(target, ".github", "instructions");

  for (const s of skills) {
    const skillDirRel = `.github/instructions/${s.name}`;
    const glob = s.globs.length ? s.globs[0] : "**";
    const front = `---\napplyTo: "${glob}"\n---\n\n`;
    writeText(path.join(instr, `${s.name}.instructions.md`), front + bodyFor(s, skillDirRel), target, written);
    copyAssets(s, path.join(target, skillDirRel), target, written);
  }

  for (const [kind, items] of [["persona", personas], ["agent", agents]]) {
    for (const it of items) {
      const front = '---\napplyTo: "**"\n---\n\n';
      const header = `# ${cap(kind)}: ${it.name}\n_${it.description}_\n\n`;
      writeText(path.join(instr, `${kind}-${slug(it.name)}.instructions.md`), front + header + it.body + "\n", target, written);
    }
  }

  if (config.claude_md) {
    seedIfAbsent(config.claude_md, path.join(target, ".github", "copilot-instructions.md"), target, written);
  }
  console.log("  note: Copilot has no standard project MCP config; skipped .mcp for copilot");
  return written;
}

// ─── codex ──────────────────────────────────────────────────────────────────

function installCodex(target, skills, agents, personas, config) {
  const written = [];
  const block = [MARK_BEGIN, "", "# gabo-skills (managed — do not edit inside the markers)", ""];

  if (config.claude_md) {
    block.push("## Project rules", "", config.claude_md.trim(), "");
  }

  block.push("# Skills", "");
  for (const s of skills) {
    const skillDirRel = `.agents/skills/${s.name}`;
    block.push(`## ${s.name}`);
    if (s.description) block.push(`_${s.description}_\n`);
    block.push(bodyFor(s, skillDirRel).replace(/\s+$/, ""));
    block.push("");
    copyAssets(s, path.join(target, skillDirRel), target, written);
  }

  for (const [kind, items] of [["Personas", personas], ["Agents", agents]]) {
    if (!items.length) continue;
    block.push(`# ${kind}`, "");
    for (const it of items) {
      block.push(`## ${it.name}`);
      if (it.description) block.push(`_${it.description}_\n`);
      block.push(it.body.replace(/\s+$/, ""));
      block.push("");
    }
  }

  block.push(MARK_END);
  const newBlock = block.join("\n");

  const out = path.join(target, "AGENTS.md");
  let newText;
  if (fs.existsSync(out)) {
    const existing = fs.readFileSync(out, "utf-8");
    const pattern = new RegExp(escapeRegex(MARK_BEGIN) + "[\\s\\S]*?" + escapeRegex(MARK_END));
    newText = pattern.test(existing)
      ? existing.replace(pattern, () => newBlock)
      : existing.replace(/\s+$/, "") + "\n\n" + newBlock + "\n";
  } else {
    newText = newBlock + "\n";
  }
  fs.writeFileSync(out, newText, "utf-8");
  written.push("AGENTS.md");
  console.log("  note: Codex has no standard project MCP config; skipped .mcp for codex");
  return written;
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function cap(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ─── CLI arg parsing ────────────────────────────────────────────────────────

function parseArgs(argv) {
  const opts = { target: null, tools: null, noEngineering: false, yes: false, help: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") opts.help = true;
    else if (a === "--no-engineering") opts.noEngineering = true;
    else if (a === "--yes" || a === "-y") opts.yes = true;
    else if (a === "--tools") opts.tools = argv[++i];
    else if (a.startsWith("--tools=")) opts.tools = a.slice("--tools=".length);
    else if (a.startsWith("-")) {
      console.error(`error: unknown option: ${a}`);
      process.exit(2);
    } else if (opts.target === null) opts.target = a;
  }
  return opts;
}

function printHelp() {
  console.log(`gabo-skills — install write-once AI skills into your project.

Usage:
  npx @gabo-routine/gabo-skills [target] [options]

Arguments:
  target               Project directory (default: current directory)

Options:
  --tools <list>       Comma-separated: ${ALL_TOOLS.join(",")}
                       (skips the interactive prompt)
  --no-engineering     Skip registering Anthropic's engineering plugin (Claude Code)
  -y, --yes            Accept defaults without prompting (all tools)
  -h, --help           Show this help

Examples:
  npx @gabo-routine/gabo-skills
  npx @gabo-routine/gabo-skills ../my-project --tools claude-code,cursor
  npx @gabo-routine/gabo-skills --yes --no-engineering`);
}

// ─── Interactive prompt ─────────────────────────────────────────────────────

// A small line reader robust to both interactive TTY input and piped/batch
// input. rl.question alone races when all piped lines arrive before the next
// question's handler attaches, dropping answers; a persistent queue avoids that.
function makeReader() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const queue = [];
  let pending = null;
  let closed = false;
  rl.on("line", (line) => {
    if (pending) {
      const { resolve } = pending;
      pending = null;
      resolve(line);
    } else {
      queue.push(line);
    }
  });
  rl.on("close", () => {
    closed = true;
    if (pending) {
      const { resolve } = pending;
      pending = null;
      resolve("");
    }
  });
  return {
    ask(question) {
      process.stdout.write(question);
      if (queue.length) return Promise.resolve(queue.shift());
      if (closed) return Promise.resolve("");
      return new Promise((resolve) => {
        pending = { resolve };
      });
    },
    close() {
      rl.close();
    },
  };
}

async function promptTools(rl) {
  console.log("Which AI tools are you using?\n");
  ALL_TOOLS.forEach((t, i) => console.log(`  ${i + 1}) ${t}`));
  console.log("\nEnter numbers or names (comma/space separated), or press Enter for all.");
  const answer = (await rl.ask("> ")).trim();
  if (!answer) return [...ALL_TOOLS];
  if (answer.toLowerCase() === "all") return [...ALL_TOOLS];

  const picks = answer.split(/[\s,]+/).filter(Boolean);
  const selected = [];
  for (const p of picks) {
    let tool = null;
    if (/^\d+$/.test(p)) {
      const idx = parseInt(p, 10) - 1;
      if (idx >= 0 && idx < ALL_TOOLS.length) tool = ALL_TOOLS[idx];
    } else if (ALL_TOOLS.includes(p)) {
      tool = p;
    }
    if (!tool) {
      console.log(`  ignoring unrecognized choice: "${p}"`);
      continue;
    }
    if (!selected.includes(tool)) selected.push(tool);
  }
  return selected;
}

async function promptYesNo(rl, question, defaultYes) {
  const suffix = defaultYes ? " (Y/n) " : " (y/N) ";
  const answer = (await rl.ask(question + suffix)).trim().toLowerCase();
  if (!answer) return defaultYes;
  return answer === "y" || answer === "yes";
}

// ─── Main ───────────────────────────────────────────────────────────────────

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) {
    printHelp();
    return 0;
  }

  const target = path.resolve(opts.target || process.cwd());
  if (!isDir(target)) {
    console.error(`error: target is not a directory: ${target}`);
    return 2;
  }

  const skills = loadSkills();
  const agents = loadDocs(AGENTS_DIR);
  const personas = loadDocs(PERSONAS_DIR);
  const config = loadConfig();
  if (!skills.length) {
    console.error(`error: no skills found under ${SKILLS_DIR}/ (expected skills/<name>/SKILL.md)`);
    return 1;
  }

  // Resolve tool selection: --tools flag, or --yes (all), or interactive prompt.
  let tools;
  let withEngineering = !opts.noEngineering;

  if (opts.tools) {
    tools = opts.tools.split(",").map((t) => t.trim()).filter(Boolean);
  } else if (opts.yes) {
    tools = [...ALL_TOOLS];
  } else {
    const rl = makeReader();
    try {
      tools = await promptTools(rl);
      if (tools.includes("claude-code") && !opts.noEngineering) {
        withEngineering = await promptYesNo(rl, "\nRegister Anthropic's engineering plugin for Claude Code?", true);
      }
    } finally {
      rl.close();
    }
    console.log("");
  }

  const unknown = tools.filter((t) => !ALL_TOOLS.includes(t));
  if (unknown.length) {
    console.error(`error: unknown tool(s): ${unknown.join(", ")}. Valid: ${ALL_TOOLS.join(", ")}`);
    return 2;
  }
  if (!tools.length) {
    console.error("error: no tools selected; nothing to do.");
    return 2;
  }

  console.log(`Installing → ${target}`);
  console.log(`Canonical source: ${skills.length} skill(s), ${agents.length} agent(s), ${personas.length} persona(s)`);
  console.log(`Tools: ${tools.join(", ")}`);
  if (tools.includes("claude-code") && withEngineering) {
    console.log(`Engineering plugin: ${ENGINEERING_PLUGIN} (Claude Code)`);
  }
  console.log("");

  const handlers = {
    "claude-code": () => installClaudeCode(target, skills, agents, personas, config, withEngineering),
    cursor: () => installCursor(target, skills, agents, personas, config),
    copilot: () => installCopilot(target, skills, agents, personas, config),
    windsurf: () => installWindsurf(target, skills, agents, personas, config),
    codex: () => installCodex(target, skills, agents, personas, config),
  };

  for (const tool of tools) {
    console.log(`[${tool}]`);
    for (const p of handlers[tool]()) {
      console.log(`  → ${p}`);
    }
    console.log("");
  }
  console.log("Done.");
  return 0;
}

main()
  .then((code) => process.exit(code))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
