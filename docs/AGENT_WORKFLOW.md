# Multi-Agent Workflow

## Work item format
Every task should state:
- User request being implemented (quote or faithful summary).
- Goal and acceptance criteria.
- Owner agent and allowed files.
- Dependencies/interfaces.
- Tests and evidence required.
- Explicit out-of-scope items.

## Suggested order for the first vertical slice
1. Compliance agent extracts the exact Local AI and submission constraints from the original PDF.
2. Clinical agent defines 2–3 synthetic transcript cases and desired note schema.
3. Backend agent implements schema + local model adapter + evidence validation using a mocked model first, then the local model.
4. UX agent builds the single-screen review flow against the agreed schema.
5. QA agent adds synthetic adversarial fixtures and tests missing/incorrect evidence, negation, and blank fields.
6. Integration agent runs the setup and end-to-end workflow and drafts the demo/release checklist.
7. Orchestrator resolves conflicts, runs the final acceptance checklist, and returns a precise status report.

## Change protocol
When the user gives a new prompt mid-build:
1. Pause new work long enough to parse the request.
2. Determine whether it changes a requirement, priority, design, or acceptance criterion.
3. Update `docs/PRODUCT_SPEC.md`, `docs/DECISIONS.md`, and `TASKS.md` first if needed.
4. Notify affected agents and revise the plan.
5. Keep unaffected work; do not discard user work or earlier valid work without reason.
6. If a request is infeasible under the official PDF or safety constraints, state why and propose the nearest alternative.

## Completion report format
- Done (verified)
- Done (not yet verified)
- Tests run and exact result
- Known limitations / risks
- Decisions needed from user (only if blocking)
