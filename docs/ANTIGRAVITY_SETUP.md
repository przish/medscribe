# Using this agent team in Google Antigravity

This package is formatted for Antigravity workspace rules and custom subagents.

## Open the correct workspace

1. Extract `medscribe-antigravity-agent-team.zip` to a normal writable folder.
2. Open that extracted `medscribe-agent-team` folder as the Antigravity workspace. Do not open only `START_PROMPT.md`.
3. Keep `AppBuildersPH Hackathon 2026 Participant Briefing.pdf` in the workspace root so the lead and compliance subagent can read the actual source.
4. Ensure `.agents/agents/` remains in place. These Markdown files contain Antigravity custom-agent YAML frontmatter; do not move them into the legacy `agents/` folder.

## First run

1. Start a conversation in the workspace and paste `START_PROMPT.md` (or use its contents as the initial prompt).
2. Ask the primary agent to read `AGENTS.md`, the PDF, `docs/`, and `TASKS.md` first.
3. Ask it to invoke relevant custom subagents via Antigravity's subagent mechanism for non-trivial work. For the first implementation, use parallel review for compliance and clinical safety; keep coding tasks bounded and avoid concurrent edits to the same files; integrate and run tests afterward.
4. Inspect plans, file diffs, command executions, browser/UI test artifacts, and subagent results yourself. Approve risky or destructive actions manually.

## Available custom agents

- `medscribe-orchestrator` — primary lead and integration owner.
- `hackathon-compliance` — validates claims against the supplied official PDF.
- `clinical-product-safety` — checks source fidelity and clinical safety boundaries.
- `local-ai-engineer` — local runtime, typed schema, claims, and evidence validation.
- `frontend-ux` — evidence-first review UI.
- `qa-security` — adversarial tests, privacy checks, and offline verification.
- `integration-release` — end-to-end integration and submission readiness.

Antigravity's custom subagents are discovered from `.agents/agents/<name>.md` or `.agents/agents/<name>/agent.md`. The files in this pack include frontmatter to register them. Custom-agent discovery and whether a particular UI build invokes parallel subagents depends on the Antigravity product surface/version and available agent capabilities. If it cannot invoke a custom subagent, instruct the primary agent to execute that role sequentially and report this honestly—never pretend delegation occurred.

## Collaboration discipline

- The newest explicit user message is the product-direction source of truth.
- Every subagent starts with isolated conversation context: include the user's latest requirement and relevant project-spec sections in each delegation prompt.
- Parallel work should use non-overlapping file ownership or isolated worktrees; never let multiple agents modify the same file concurrently.
- Integrate all changes and run relevant tests before claiming completion.
- Keep core inference local. Do not add remote model inference, transcript upload, telemetry, or sync without explicit owner approval and a disclosure.
- Use fictional synthetic clinical data only.

## Antigravity references

- Custom subagents: https://antigravity.google/docs/subagents/
- Workspace rules: https://www.antigravity.google/docs/rules/
- Agent overview: https://www.antigravity.google/docs/agent/

This is configuration and instruction scaffolding—not a guarantee of perfectly autonomous execution. You remain the reviewer and product owner.
