# Suggested Architecture

This is a starting proposal, not an immutable decision. The user's latest instruction can change it.

## Default stack
- Python application with Streamlit for fast, clear demo UX.
- Local LLM via Ollama, configurable model name; exact model selected only after checking the demo machine's memory/performance.
- Typed schemas via Pydantic or equivalent.
- Local transcript segmentation and claim/evidence validation implemented as deterministic code.
- No database required for the first slice; keep state in session memory unless the user requests local persistence.
- Optional local speech-to-text adapter only after transcript-to-note processing works.

## Logical components
1. `input`: accepts synthetic transcript and optional speaker/timestamp metadata.
2. `segmenter`: produces stable source segment IDs.
3. `local_model`: prompts the local model for constrained structured output.
4. `schemas`: validates SOAP draft, claims, evidence IDs, review flags.
5. `evidence_validator`: rejects missing/unknown IDs and mismatched quotes; flags statements without adequate support.
6. `audit`: deterministic checks for required fields, missingness, possible contradictions, negation, and ambiguity.
7. `review_ui`: source + draft + review flags + edit controls.
8. `template_adapter`: maps canonical clinical claims to outpatient SOAP, Epic APSO, or General Clinical Summary structures.
9. `export`: exports a draft with format-specific section headers and an explicit review disclaimer.

## Trust boundaries
- Model output is untrusted and may be wrong or malformed.
- The transcript is the source of what was said, not ground truth of medical facts.
- Schema validity is not clinical correctness.
- An LLM self-report of confidence is not evidence.
- A claim marked “supported” means traceable to text, not medically verified.

## Offline proof
1. Install app dependencies and download the model before disconnecting.
2. Start app with networking disabled.
3. Load a bundled synthetic transcript.
4. Generate and audit the draft.
5. Verify that no external request is needed for the core path.
6. Record what was actually tested; don't claim a complete offline guarantee unless the test covers the intended environment.
