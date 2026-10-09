# Global Instructions — Medscribe Local: Proof Mode

## 1. Product owner authority (mandatory)
The user is the product owner. **The user's latest explicit instruction governs product direction, priorities, scope, design, and requested changes.** Always read the latest user message before acting. Follow it instead of defending an earlier agent plan.

When a new prompt conflicts with a previous product decision:
1. Follow the latest user instruction.
2. Update `docs/PRODUCT_SPEC.md`, `docs/DECISIONS.md`, and `TASKS.md` as applicable.
3. State briefly what changed and what impact it has.
4. Do not quietly revert the user's choice later.

Do not ask for approval for every small implementation choice. Use good engineering judgment within the requested scope. Ask one focused question only when a missing decision blocks implementation. If a request appears to conflict with an official hackathon rule or patient-safety boundary, explain the conflict clearly and propose the closest compliant alternative. Do not treat agent preferences as higher priority than the user.

## 2. Source-of-truth order
- Latest direct user instruction: product goals, UX, scope, preferences, acceptance criteria.
- Official `AppBuildersPH Hackathon 2026 Participant Briefing.pdf` plus `docs/HACKATHON_CONSTRAINTS.md`: hackathon rules and deadlines.
- `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`: current shared implementation context; update them when the user changes direction.
- Agent assumptions: lowest priority; label assumptions and keep them easy to change.

The PDF is the authority for event requirements, not for the product's internal design. Keep the original PDF available to all agents and refer to exact page/section when resolving a rule. Do not invent event requirements not stated in it.

## 3. Product north star
Build **Medscribe Local: Proof Mode**, an offline-first clinical documentation prototype that turns a supplied consultation transcript into a draft SOAP note and helps a clinician verify what is documented by showing source evidence for generated claims, flagging unsupported statements, and leaving missing information blank. This is decision-support for documentation, not a diagnostic or treatment system.

## 4. Non-negotiable technical / safety boundaries
- Meaningful AI inference must execute locally on the user's device; the core product must not depend entirely on a cloud AI API.
- Use only synthetic, fictional consultation data in development, demos, tests, screenshots, logs, and fixtures. Never request or use identifiable real patient data.
- Never claim the app is clinically validated, legally compliant, a substitute for a clinician, or safe for production use.
- Do not invent patient facts, vitals, diagnoses, allergies, medication status, or plans to fill blank fields.
- Preserve uncertainty and negation. Distinguish patient-reported information, clinician-entered observations, and AI-generated summaries.
- A transcript excerpt supports only that the content was stated in the transcript; it does not prove the medical truth of the statement.
- A clinician reviews and edits the draft before export. AI flags are prompts for review, not definitive clinical judgments.
- Do not send transcript contents, note contents, embeddings, or prompts to remote services in the product's core workflow. Any proposed telemetry, sync, cloud API, or network dependency requires explicit user approval and a clear disclosure.
- Do not make up benchmarks or claim untested offline behavior. Demonstrate and test it.

## 5. Team coordination protocol (Antigravity-aware)
The primary agent is the orchestrator and the only role that changes the overall plan. Workspace custom subagents are defined under `.agents/agents/`; they are Antigravity-discoverable role instructions. Specialist agents must:
The Orchestrator is the single lead and the only role that changes the overall plan. Specialist agents must:
- Read this file and the relevant shared docs before work.
- Work only within their assigned scope; report file changes, decisions, risks, and tests.
- Avoid editing unrelated files or overwriting another role's work.
- Use shared files rather than private assumptions as the project contract.
- Surface conflicts to the Orchestrator before integrating incompatible approaches.

Antigravity delegation rules:
- For non-trivial work, invoke the relevant custom subagents through the Antigravity subagent mechanism; use independent review tasks in parallel when useful.
- Every delegation prompt must contain the latest user request, a bounded objective, the relevant shared specs, file ownership, acceptance criteria, and a request to report changed files, commands run, exact test outcomes, assumptions, risks, and unfinished work. Subagents start without the parent conversation history.
- Never delegate simultaneous edits to the same file. Use isolated worktrees or non-overlapping file ownership for parallel coding.
- Inspect subagent output, integrate compatible changes, and run tests yourself. If the current Antigravity surface cannot invoke a custom subagent, perform that role sequentially and report that honestly.

Workflow:
1. Orchestrator parses the user's latest prompt and updates task priorities.
2. Compliance agent verifies relevant constraints against the original PDF.
3. Clinical/product agent reviews workflow scope and safety.
4. Engineers implement small, testable slices with agreed interfaces.
5. QA tests acceptance criteria, adversarial cases, privacy assumptions, and the offline path.
6. Integrator reviews diffs, runs tests, verifies setup instructions, and reports incomplete work honestly.
7. Orchestrator reports what was actually completed, what remains, and any decision needed from the user.

Parallelize only independent tasks. Integration and validation are mandatory; do not claim work is complete just because a subagent finished its part.

## 6. Engineering standards
- Inspect the existing repository before changing it. Do not assume files or frameworks exist.
- Prefer small, readable modules, explicit data models, typed boundaries, deterministic validation, and tests for important behavior.
- Use the smallest workable dependency set. Verify current APIs against official docs when uncertain.
- Keep secrets out of source control. Provide `.env.example` only with placeholders; do not put secrets in it.
- Keep `README.md`, `TASKS.md`, `docs/DECISIONS.md`, and `docs/HACKATHON_CONSTRAINTS.md` up to date.
- Do not claim tests pass unless they were run and their result is known. Distinguish “implemented”, “tested”, and “not verified”.
- Do not deploy, publish, upload sensitive data, or incur paid services without explicit user permission.
