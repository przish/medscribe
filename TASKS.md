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
- [x] Add on-device local speech-to-text input (Verified: `faster-whisper-medium` 769M parameters on CPU, multilingual Tagalog/Taglish/English, upload-only, 100% offline socket guarded).
- [x] Improve evidence highlighting and claim navigation. (Verified: elevated neumorphic proof mode, active claim halo, verbatim quote preview, and physician override editing).
- [x] Streamline EHR audit workspace by removing repetitive dialogue card button strip and colored card side stripes.
- [x] Unify all features into a single-page workspace with custom SVG medical logo, elevated top navigation bar, and consultation source switcher (Verified in `app.py`).
- [x] Eradicate mock terminology across adapters, pipeline, and UI (`DeterministicClinicalEngine`).
- [x] 20/20 automated pytest suite and end-to-end offline smoke test passing.
- [-] Create one-minute demo video script and submission disclosures.

## Explicitly defer unless the user asks
- [ ] Real authentication/account management, EHR integrations, cloud sync, remote LLM use, production deployment.
- [ ] Diagnosis/treatment recommendations.
- [ ] Real patient data or claims of clinical validation.
