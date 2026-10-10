# Decisions Log

Use newest-first entries. The user owns product direction; when a new user prompt changes a decision, update this file immediately.

## 2026-10-10 — Multi-Format Documentation Adapter & Soft Elevated Neumorphic Refinement
- **Multi-Format Note Adaptation (SOAP / APSO / General Summary):** Clinic workflows differ across specialties and health systems. The core proof engine uses Canonical Evidence Representation (`ClinicalClaim` with verbatim quotes and segment IDs), decoupling medical claims from presentation layout. Introduced live format switching:
  1. `Standard SOAP (Outpatient)`: Subjective → Objective → Assessment → Plan.
  2. `APSO Format (Epic EHR Standard)`: Assessment → Plan → Subjective → Objective.
  3. `General Clinical Summary`: Reason for Visit & History → Clinical Examination → Impressions & Care Plan.
- **Dynamic Dialogue Extraction:** User-uploaded audio or direct dialogue input is parsed dynamically into clinical claims, extracting actual dialogue turns rather than falling back to hardcoded demo cases.
- **Pure Elevated Neumorphic Design (Zero Outlines):** Eliminated all card borders, button strokes, and side stripes. Styled surfaces with soft dual-direction positive drop shadows (`box-shadow: 8px 8px 18px rgba(160, 172, 188, 0.35), -8px -8px 18px rgba(255, 255, 255, 0.95)`) on a warm-gray canvas (`#eef1f5`), providing pillowy edges matching the design reference.

## 2026-10-10 — On-Device Whisper Audio Capture & Streamlined EHR Audit Drawer
- **On-Device Speech-to-Text:** Integrated local `faster-whisper` (tiny on CPU, int8 quantized) supporting live microphone recording via Streamlit native `st.audio_input` and audio file upload (`.wav`, `.mp3`, `.m4a`). Validated 100% offline with zero network sockets.
- **Drawer Streamlining:** Eliminated repetitive vertical dialogue turn card buttons from the right evidence drawer (removing visual clutter and redundant button stacking). The evidence drawer now focuses strictly on the active statement's verbatim transcript quote, clinical audit translation, suggested verbatim wording 1-click accept, and full inline modification editor.
- **Seamless Audio-to-SOAP Pipeline:** Audio is parsed directly into timestamped speaker turns, analyzed by local inference adapters, and deterministically verified for hallucination, omission, and negation.
- **Visual Direction:** Adopted restrained, tactile neumorphism designed for high clinical credibility, calm focus, and accessible contrast (WCAG AAA/AA).
- **Surface Geometry:** Warm light-gray monochromatic canvas (`#EEF1F4`) with dual-direction soft shadows (`4px 4px 10px rgba(166, 175, 189, 0.45), -4px -4px 10px rgba(255, 255, 255, 0.9)`) on tactile cards, combined with recessed surfaces (`box-shadow: inset 2px 2px 5px...`) for transcript turns and quotation callouts.
- **Color System:** Deep navy typography (`#0F1E36`, 13.35:1 contrast ratio) and muted teal accents (`#0D9488` / `#0F766E`) for primary interactive states. Amber (`#D97706`) and crimson (`#DC2626`) strictly reserved for meaningful verification warnings and critical safety flags.
- **Desktop Ergonomics:** Balanced two-column layout with smooth internal transcript scroll, instant bi-directional claim-to-turn highlighting (`🎯 CITED IN ACTIVE CLAIM` with teal halo), inline clinician override editing with `[✍ CLINICIAN EDITED]` badging, and gated draft export.

## 2026-10-09 — Initial Vertical Slice Completed
- **Stack Implemented:** Python 3.9 + Pydantic v2 + Streamlit + Pytest.
- **Local Inference Architecture:** Decoupled `BaseModelAdapter` with `OllamaModelAdapter` (local REST API) and `MockModelAdapter` (deterministic fixtures + adversarial trap generation).
- **Audit Rules Engine:** Deterministic `EvidenceValidator` enforcing citation existence, verbatim quote matching, negation flip detection in clinical symptoms, missingness checks, medication ambiguity warnings, and diagnostic hedging preservation.
- **Evidence UI:** Two-column Streamlit application (`app.py`) providing side-by-side source transcript exploration and audited SOAP draft inspection, with interactive source highlighting, claim editing, and a locked export gate requiring clinician sign-off.
- **Offline Proof:** Verified with `tests/test_offline_privacy.py` and `smoke_test.py` with zero outbound network sockets.

## Initial baseline — 2026-10-09
- Working name: Medscribe Local: Proof Mode.
- Core idea: local-first SOAP draft generation with source-linked claims and an evidence/missingness audit.
- First demo starts from a supplied transcript; speech recognition is optional until the core path works.
- Local inference must be meaningful and the core flow must not rely on a cloud AI API.
- Use only synthetic clinical examples.
- Default stack proposal: Python + Streamlit + Ollama + schema validation; subject to user direction and machine constraints.
- The clinician remains responsible for reviewing and editing the draft.

## 2026-10-10 — UI direction change: desktop-first clinical review workspace (user instruction)
- Supersedes the neumorphic mobile-simulator UI. The phone bezel and neumorphism are removed.
- New layout: summary line + filter chips (All / Needs review / Unassessed) + "Next item to review"; left = flat SOAP note with inline amber/red gutter markers; right = sticky evidence drawer (transcript quote, plain-language reason, suggested transcript wording, auto-sized editor, transcript with highlighted lines).
- Internal audit tags are never shown; `medscribe/ui_text.py` maps them to physician-facing wording. Visible line numbers are transcript positions ("Line 03"), not raw segment IDs.
- Suggested replacements are limited to the verbatim transcript excerpt; no model-invented corrections.
- "Needs review" is derived from claims (unsupported or flagged and not yet reviewed); resolving an item (accept, save, keep as written) removes it from the count.

## 2026-10-10 — Clinical Workstation Friction Eradication & Bidirectional Linking
- **Interactive Statement Rows:** Eliminated repetitive vertical "Source" button columns. Each clinical statement is an interactive full-width card with colored left gutter indicators, hover states, and line tags (`Line 03 ↗`).
- **Cold State Elimination:** Encounter loads immediately auto-select the highest-priority item (critical flags > warning flags > first item), instantly illuminating the Evidence Drawer and cited dialogue turns without requiring initial user clicks.
- **Sidebar Relocation:** Encounter switching, local inference engine selection, and custom synthetic consultation generation were relocated into `st.sidebar`, keeping the main dual-pane canvas strictly dedicated to clinical review.
- **Bidirectional Linking:** Clicking a SOAP entry focuses its source transcript turns; clicking a transcript turn immediately focuses its linked SOAP statement in the chart.
- **Visual Rhythm:** Muted and tightened unassessed parameters (`fld-blank-row`) so clinicians can scan past negative observations without distraction. Auto-expanding textareas prevent diagnosis truncation.


## 2026-10-10 — User-requested responsive neumorphic refresh and demo access screen
- **Visual direction:** Latest user instruction supersedes the earlier flat desktop-only choice: use a restrained, professional neumorphic system with a warm cool-gray canvas, soft raised/recessed surfaces, deep slate typography, and teal interaction accents. Amber/red remain reserved for review states.
- **Responsive behavior:** Keep the SOAP/evidence workflow side-by-side on wide screens and stack it on tablet/mobile; remove sticky/max-height drawer behavior on narrow screens and use touch-sized controls.
- **Access screen:** Add an illustrative local demo entry page with optional display name and a lock/continue flow. This is UI-only, collects no password, performs no identity validation, and must disclose that real authentication is not configured. No account/security backend is added.
- **Scope:** Preserve inference, validation, clinical wording, export gating, and evidence-linking behavior.
