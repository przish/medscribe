# Task Board — Initial Vertical Slice

Status legend: `[ ]` not started · `[-]` in progress · `[x]` verified complete

## P0 — Required
- [x] Inspect repository/runtime and confirm Python version and available resources. (Verified: macOS M4, Python 3.9.6, Node 24.14).
- [x] Create synthetic transcript fixtures with IDs and timestamps. (Verified: `fixtures/` with 3 synthetic clinical encounters).
- [x] Define typed SOAP note + claim/evidence schema. (Verified: `medscribe/schemas.py`).
- [x] Implement local-model adapter and a mock adapter for deterministic tests. (Verified: `OllamaModelAdapter` & `MockModelAdapter` in `medscribe/adapters/`).
- [x] Implement claim-source reference validation; unknown IDs cannot be marked supported. (Verified: `medscribe/validator.py`).
- [x] Implement checks for missing fields, negation/uncertainty changes, medication ambiguity, and contradictions. (Verified: `medscribe/validator.py`).
- [x] Build one screen: transcript / draft SOAP / audit flags / edit / export. (Verified: Streamlit UI in `app.py`).
- [x] Add tests for missing, invalid, and fabricated evidence references. (Verified: 12 unit & integration tests in `tests/`).
- [x] Document install, model setup, run, tests, limitations, and local-vs-internet behavior. (Verified: Updated `README.md`).
- [x] Demonstrate the full main workflow with internet disconnected after setup. (Verified: `smoke_test.py` and `tests/test_offline_privacy.py`).

## P1 — Only after P0 works
- [ ] Add optional local speech-to-text input (e.g. whisper.cpp).
- [x] Improve evidence highlighting and claim navigation. (Verified: restrained neumorphic proof mode, active claim halo, quote preview, and inline editing).
- [x] Desktop-first review workspace replaces mobile simulator (see DECISIONS 2026-10-10). Verified by headless AppTest + 15 pytest tests; not yet visually inspected in a browser.
- [ ] Create one-minute demo video and submission disclosures.

## Explicitly defer unless the user asks
- [ ] EHR integrations, authentication, cloud sync, remote LLM use, production deployment.
- [ ] Diagnosis/treatment recommendations.
- [ ] Real patient data or claims of clinical validation.
