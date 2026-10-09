# Product Specification — Medscribe Local: Proof Mode

Status: initial working spec; the user's latest instructions may change it.

## One-line pitch
An offline-first clinical documentation assistant that drafts structured SOAP notes from a supplied consultation transcript and makes every generated claim reviewable against the original source.

## Target user
A clinician or authorized healthcare worker reviewing a draft note. Hackathon demo uses fictional synthetic encounters only.

## Problem statement
AI-generated clinical notes can sound polished while omitting details, changing uncertainty or negation, or introducing unsupported information. Reviewing a full transcript line by line is laborious. Proof Mode helps reviewers see what is supported, what is missing, and what needs confirmation.

## Core workflow
1. Load/paste a synthetic consultation transcript (audio transcription is optional and not required for the first end-to-end version).
2. Segment source text and preserve speaker/timestamp metadata where available.
3. Generate a draft SOAP note using a local model.
4. Attach source segment IDs/evidence to individual claims.
5. Run deterministic validation of references and required fields.
6. Flag unsupported claims, missing fields, possible contradiction, negation/uncertainty changes, and ambiguous medication statements.
7. Let the user inspect evidence, edit the note, and export a clearly labeled draft.

## MVP acceptance criteria
- A user can complete the core workflow without a cloud AI endpoint.
- Each marked-supported claim links to a real transcript span; invalid or absent references cannot display as supported.
- Missing information remains missing, not fabricated.
- Uncertain or contradictory facts are flagged for clinician review.
- User edits are explicit and preserved during the current session.
- The app clearly labels generated output as a draft and requires user review before export.
- The app has synthetic demo cases and automated tests for critical failure modes.
- Startup and model requirements are documented.

## Out of scope for first demo
- Autonomous diagnosis or treatment recommendations.
- Real authentication, account management, cloud sync, remote inference, production deployment, or real patient records.
- The UI may show a clearly disclosed local demo-access screen, but it does not verify, store, or imply secure credentials.
- Claims of medical-device approval, legal compliance, clinical validation, or time saved without evidence.
- Live ambient recording, diarization, or perfect Taglish transcription unless the basic transcript workflow is already reliable.

## Product decisions to confirm by user only if blocking
- Final name/branding.
- Preferred UI framework if different from Streamlit.
- Whether audio transcription is required for the first demo or can follow after text workflow is complete.
