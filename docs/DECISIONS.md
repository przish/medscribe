# Decisions Log

Use newest-first entries. The user owns product direction; when a new user prompt changes a decision, update this file immediately.

## 2026-10-09 — Restrained Neumorphic UI Design Refinement
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
