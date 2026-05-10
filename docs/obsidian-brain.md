# Obsidian Brain

## Purpose

Use Obsidian Mind as an optional persistent memory layer for AI coding workflows.

This is not application code.

## Source

- Repository: `https://github.com/breferrari/obsidian-mind`
- Purpose: Obsidian vault template for persistent AI-agent memory.
- Agent support: Claude Code, Codex CLI, Gemini CLI.
- License: MIT.

## Boundary Rules

- Keep `service-crm` standalone.
- Do not copy Obsidian Mind hooks into the Flask runtime.
- Do not make Obsidian, ShardMind, QMD, or Node required to run `service-crm`.
- Do not store customer/service production data in the AI memory vault.
- Use the vault for agent memory, decisions, assumptions, architecture notes, and session summaries.
- Keep app documentation in this repo when it is required to build or run the app.
- Keep personal notes, meeting notes, review notes, and cross-project memory in the vault.

## Recommended Local Layout

Use a sibling folder outside this app repository:

```text
c:/Users/vdzoo/Documents/GitHub/
  service-crm/
  service-crm-brain/
```

Do not install Obsidian Mind inside `service-crm` unless explicitly approved.

## Install Options

### ShardMind

```powershell
npm install -g shardmind
New-Item -ItemType Directory ..\service-crm-brain
Set-Location ..\service-crm-brain
shardmind install github:breferrari/obsidian-mind
```

### Direct Clone

```powershell
git clone https://github.com/breferrari/obsidian-mind.git ..\service-crm-brain
```

## Optional Semantic Search

QMD is optional. Use it only if semantic vault search is wanted.

```powershell
npm install -g @tobilu/qmd
Set-Location ..\service-crm-brain
node --experimental-strip-types scripts/qmd-bootstrap.ts
```

Notes:

- QMD downloads embedding/search models on first use.
- If QMD is not installed, agents can still use grep and normal file reads.
- Keep the QMD index scoped to the brain vault, not the app repo.

## Codex Usage

- Codex reads `AGENTS.md` natively.
- Obsidian Mind command files can be used as normal prompts without `/`.
- Example prompt names:
  - `om-standup`
  - `om-dump`
  - `om-wrap-up`
  - `om-weekly`
  - `om-vault-audit`

## What To Store

- Project decisions.
- Architecture assumptions.
- Design-source decisions.
- Open questions.
- Cross-session summaries.
- Risks and gotchas.
- Future integration notes for VMES/OEE.
- Links back to canonical repo docs.

## What Not To Store

- Secrets.
- Passwords.
- API keys.
- Customer private data.
- Production database exports.
- Large generated artifacts.
- Source files that belong in `service-crm`.

## Suggested First Notes

- `brain/North Star.md`: standalone service-management app, OEE UI language, architecture-first workflow.
- `work/active/service-crm.md`: current implementation status, next tasks, blockers.
- `brain/Key Decisions.md`: standalone boundary, Flask/Jinja stack, light-mode dashboard requirement.
- `brain/Gotchas.md`: do not invent UI; use exact OEE references from `service-crm/docs/ui-reference.md`.

## Linking Rule

When the vault records a decision about this app, link back to the canonical app doc:

- `service-crm/AGENTS.md`
- `service-crm/docs/ui-reference.md`
- `service-crm/docs/service-domain.md`
- `service-crm/docs/tasks.md`
- `service-crm/docs/commands.md`

## Integration Decision

Default integration level:

- External sibling vault.
- Linked from `AGENTS.md`.
- No Flask dependency.
- No runtime dependency.
- No app-code changes.

Escalate before:

- Adding hooks to this repo.
- Adding `.codex/hooks.json`.
- Adding `.mcp.json`.
- Installing QMD.
- Moving memory files inside `service-crm`.
