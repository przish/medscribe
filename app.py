import html
import os
import streamlit as st

from medscribe.schemas import (
    Transcript,
    SOAPNoteDraft,
    VerificationStatus,
    AuditFlagSeverity,
)
from medscribe.adapters.mock_adapter import MockModelAdapter
from medscribe.adapters.ollama_adapter import OllamaModelAdapter
from medscribe.pipeline import MedscribePipeline
from medscribe.audio import transcribe_audio_bytes
from medscribe.ui_text import (
    describe_flag, friendly, line_label, line_map, patient_display,
    unassessed_label, UNASSESSED_COPY,
)

# Configure Streamlit Page
st.set_page_config(
    page_title="Medscribe · Clinical Documentation Audit",
    page_icon="⚕",
    layout="wide",
    initial_sidebar_state="expanded",
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

FIXTURE_PRESETS = {
    "Maria Santos · Hypertension follow-up": "encounter_01_hypertension_followup.json",
    "Ethan Ramirez · Pediatric cough": "encounter_02_pediatric_cough_edgecase.json",
    "Roberto Cruz · Routine checkup (audit case)": "encounter_03_adversarial_hallucination_trap.json",
    "Ginoong Dela Cruz · Tagalog Consultation": "encounter_04_tagalog_consultation.json",
}

# =============================================================================
# INFERENCE ENGINE DETECTION & ADAPTERS
# =============================================================================
ollama_adapter = OllamaModelAdapter()
ollama_online = ollama_adapter.is_available()

def get_adapter(engine_mode: str) -> object:
    if "Ollama" in engine_mode and ollama_online:
        installed = ollama_adapter.get_installed_models()
        model_name = installed[0] if installed else "llama3.2:3b"
        return OllamaModelAdapter(model_name=model_name)
    elif "Adversarial" in engine_mode:
        return MockModelAdapter(mode="adversarial")
    return MockModelAdapter(mode="standard")

def get_highest_priority_claim(draft: SOAPNoteDraft):
    claims = draft.all_claims()
    # 1. Critical severity or unverified/contradicted
    for c in claims:
        if any(f.severity == AuditFlagSeverity.CRITICAL for f in c.audit_flags) or c.verification_status == VerificationStatus.UNSUPPORTED:
            return c
    # 2. Warning / Needs review
    for c in claims:
        if bool(c.audit_flags) or c.verification_status != VerificationStatus.SUPPORTED:
            return c
    # 3. First claim if all supported
    return claims[0] if claims else None

def load_preset_encounter(preset_name: str, engine_mode: str):
    target_file = os.path.join(FIXTURES_DIR, FIXTURE_PRESETS[preset_name])
    adapter = get_adapter(engine_mode)
    pipeline = MedscribePipeline(adapter=adapter)
    transcript = pipeline.load_transcript_from_file(target_file)
    draft = pipeline.process_encounter(transcript)
    
    st.session_state.active_transcript = transcript
    st.session_state.draft_note = draft
    st.session_state.loaded_preset = preset_name
    st.session_state.loaded_engine = engine_mode
    st.session_state.audio_expanded = False
    st.session_state.transcribed_audio_text = None
    
    # Auto-initialize right-hand pane with highest-priority flagged item
    def_claim = get_highest_priority_claim(draft)
    st.session_state.selected_claim = def_claim
    st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []

# =============================================================================
# SIDEBAR: ENCOUNTER, INFERENCE ENGINE & SYNTHETIC TESTING CONTROLS
# =============================================================================
with st.sidebar:
    st.markdown("### ⚕ Medscribe Workstation")
    st.caption("Offline-first clinical decision support for SOAP documentation verification.")
    st.caption("Local demo session · not authenticated")
    if st.button("Lock demo workspace", key="btn_lock_demo", use_container_width=True):
        st.session_state.local_demo_access = False
        st.rerun()
    st.markdown("---")
    
    st.markdown("#### Clinical Encounter")
    preset_options = list(FIXTURE_PRESETS.keys())
    curr_preset = st.session_state.get("loaded_preset", preset_options[0])
    if curr_preset not in preset_options:
        preset_options.append(curr_preset)
    idx_preset = preset_options.index(curr_preset) if curr_preset in preset_options else 0
    selected_preset = st.selectbox(
        "Select Encounter",
        preset_options,
        index=idx_preset,
        key="ctl_preset",
        help="Load pre-calibrated synthetic patient encounters or recorded consultations.",
    )
    
    st.markdown("#### Inference Engine")
    engine_options = (
        ["Local Ollama (Active)", "Deterministic Clinical Adapter", "Adversarial Test Mode"]
        if ollama_online else ["Deterministic Clinical Adapter", "Adversarial Test Mode"]
    )
    curr_engine = st.session_state.get("loaded_engine", engine_options[0])
    idx_engine = engine_options.index(curr_engine) if curr_engine in engine_options else 0
    selected_engine = st.selectbox(
        "Local Inference Engine",
        engine_options,
        index=idx_engine,
        key="ctl_engine",
        help="On-device inference pipeline ensuring 100% offline privacy.",
    )
    
    st.markdown("---")
    with st.expander("🧪 Custom Consultation Generator", expanded=False):
        st.caption("Paste arbitrary consultation dialogue to evaluate on-device evidence linking.")
        cu_enc = st.text_input("Encounter Code", value="ENC-CUSTOM-001", key="sb_cu_enc")
        cu_pat = st.text_input("Patient Identifier (Synthetic)", value="SYN-PAT-CUSTOM", key="sb_cu_pat")
        cu_txt = st.text_area(
            "Consultation Dialogue",
            height=180,
            key="sb_cu_txt",
            placeholder="Clinician: How have you been feeling?\nPatient: The headache has subsided, but blood pressure is still high.",
        )
        if st.button("Generate SOAP Draft", type="primary", key="sb_btn_generate", use_container_width=True):
            if cu_txt.strip():
                pipeline = MedscribePipeline(adapter=get_adapter(selected_engine))
                new_t = pipeline.parse_raw_text_to_transcript(cu_txt, encounter_id=cu_enc, patient_id=cu_pat)
                new_draft = pipeline.process_encounter(new_t)
                st.session_state.active_transcript = new_t
                st.session_state.draft_note = new_draft
                st.session_state.loaded_preset = "Custom Encounter"
                st.session_state.last_preset_selection = "Custom Encounter"
                def_claim = get_highest_priority_claim(new_draft)
                st.session_state.selected_claim = def_claim
                st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
                st.rerun()

# Handle Encounter or Engine Changes
if "last_preset_selection" not in st.session_state:
    st.session_state.last_preset_selection = selected_preset
preset_changed = (selected_preset != st.session_state.last_preset_selection
                  and selected_preset in FIXTURE_PRESETS)
engine_changed = (st.session_state.get("loaded_engine") != selected_engine
                  and st.session_state.get("loaded_preset") in FIXTURE_PRESETS)

if preset_changed:
    st.session_state.last_preset_selection = selected_preset
    load_preset_encounter(selected_preset, selected_engine)
elif engine_changed:
    if selected_preset in FIXTURE_PRESETS:
        load_preset_encounter(selected_preset, selected_engine)
elif "draft_note" not in st.session_state:
    fallback = selected_preset if selected_preset in FIXTURE_PRESETS else list(FIXTURE_PRESETS.keys())[0]
    load_preset_encounter(fallback, selected_engine)

draft: SOAPNoteDraft = st.session_state.draft_note
transcript: Transcript = st.session_state.active_transcript
LINES = line_map(transcript)

# Auto-select if selected_claim became None or uninitialized
if st.session_state.get("selected_claim") is None:
    def_claim = get_highest_priority_claim(draft)
    st.session_state.selected_claim = def_claim
    st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []

# =============================================================================
# STYLE SYSTEM: ENTERPRISE EHR AUDIT WORKSTATION
# =============================================================================
st.markdown(
    """
    <style>
    :root {
        --bg: #F8FAFC;
        --ink: #0F172A;
        --muted: #475569;
        --line: #E2E8F0;
        --accent: #1D4ED8;
        --accent-bg: #EFF6FF;
        --amber-bg: #FEF3C7;
        --amber-ink: #78350F;
        --amber-bar: #B45309;
        --red-bg: #FEE2E2;
        --red-ink: #7F1D1D;
        --red-bar: #B91C1C;
        --green-bg: #ECFDF5;
        --green-ink: #065F46;
        --green-bar: #059669;
    }
    
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background: var(--bg) !important;
        color: var(--ink);
        font-family: Inter, "Source Sans 3", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }
    
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer {
        display: none !important;
    }
    
    .block-container {
        padding: 0.8rem 1.5rem 2.5rem 1.5rem !important;
        max-width: 1600px !important;
    }
    
    .mono {
        font-family: "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace !important;
        font-variant-numeric: tabular-nums;
    }

    /* Primary Note & Evidence Pane Containers */
    .st-key-note_pane, .st-key-drawer_pane {
        background: #FFFFFF !important;
        border: 1px solid var(--line) !important;
        border-radius: 8px !important;
        padding: 20px 24px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    
    .st-key-drawer_pane {
        position: sticky !important;
        top: 12px !important;
        max-height: calc(100vh - 28px) !important;
        overflow-y: auto !important;
    }

    /* Top Patient Summary Bar */
    .patient-header {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        padding: 0 2px 10px 2px;
        margin-bottom: 8px;
        border-bottom: 1px solid var(--line);
    }
    .patient-header .title {
        font-size: 1.15rem;
        font-weight: 800;
        color: var(--ink);
        letter-spacing: -0.01em;
    }
    .patient-header .meta {
        font-size: 0.88rem;
        color: var(--muted);
        font-weight: 500;
        margin-left: 8px;
    }
    .badge-review-count {
        background: var(--amber-bg);
        color: var(--amber-ink);
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.82rem;
        border: 1px solid rgba(180, 83, 9, 0.2);
    }
    .badge-ok-count {
        background: var(--green-bg);
        color: var(--green-ink);
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.82rem;
        border: 1px solid rgba(5, 150, 105, 0.2);
    }

    /* Section Typography */
    .sec-header {
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border-bottom: 2px solid var(--ink);
        padding-bottom: 3px;
        margin: 20px 0 6px 0;
        color: var(--ink);
    }
    .sec-header:first-of-type {
        margin-top: 0;
    }
    
    .field-label {
        font-size: 0.76rem;
        font-weight: 700;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 10px 0 2px 0;
    }
    
    /* Compact negative / unassessed statements */
    .fld-blank-row {
        font-size: 0.8rem !important;
        color: #94A3B8 !important;
        font-style: italic !important;
        line-height: 1.3 !important;
        padding: 2px 8px !important;
        margin-bottom: 4px !important;
    }

    /* Statement Row Clickable Buttons */
    /* Statement Row Clickable Buttons - Sleek EHR Style (No Side Stripes) */
    div[class*="claim_row_"] button {
        width: 100% !important;
        text-align: left !important;
        justify-content: flex-start !important;
        align-items: flex-start !important;
        padding: 9px 14px !important;
        min-height: 42px !important;
        height: auto !important;
        border-radius: 8px !important;
        font-size: 0.9rem !important;
        line-height: 1.5 !important;
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        border: 1px solid var(--line) !important;
        border-left: 1px solid var(--line) !important;
        margin-bottom: 5px !important;
        background: #FFFFFF !important;
        color: var(--ink) !important;
        transition: all 0.12s ease-in-out !important;
        box-shadow: none !important;
    }
    div[class*="claim_row_"] button p,
    div[class*="claim_row_"] button div {
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        text-align: left !important;
    }
    
    div[class*="claim_row_crit"] button {
        background: #FFF1F2 !important;
        border: 1px solid #FECACA !important;
        border-left: 1px solid #FECACA !important;
        color: #991B1B !important;
    }
    div[class*="claim_row_warn"] button {
        background: #FFFBEB !important;
        border: 1px solid #FDE68A !important;
        border-left: 1px solid #FDE68A !important;
        color: #92400E !important;
    }
    div[class*="claim_row_ok"] button {
        background: #FFFFFF !important;
        border: 1px solid var(--line) !important;
        border-left: 1px solid var(--line) !important;
        color: var(--ink) !important;
    }
    div[class*="claim_row_sel"] button {
        outline: 2px solid var(--accent) !important;
        outline-offset: 1px !important;
        background: var(--accent-bg) !important;
    }
    
    div[class*="claim_row_"] button:hover {
        background: #F8FAFC !important;
        border-color: #94A3B8 !important;
        cursor: pointer !important;
    }
    div[class*="claim_row_crit"] button:hover {
        background: #FEE2E2 !important;
        border-color: #EF4444 !important;
    }
    div[class*="claim_row_warn"] button:hover {
        background: #FEF3C7 !important;
        border-color: #F59E0B !important;
    }

    /* Right Evidence Pane Styling */
    .dr-title {
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .quote-box {
        border: 1px solid var(--line);
        background: #F1F5F9;
        padding: 8px 12px;
        font-size: 0.92rem;
        line-height: 1.45;
        margin: 4px 0 12px 0;
        border-radius: 6px;
    }
    
    .alert-card {
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 10px;
        font-size: 0.88rem;
        line-height: 1.5;
        border: 1px solid transparent;
    }
    .alert-card.crit {
        background: var(--red-bg);
        border: 1px solid var(--red-bar);
        color: var(--red-ink);
    }
    .alert-card.warn {
        background: var(--amber-bg);
        border: 1px solid var(--amber-bar);
        color: var(--amber-ink);
    }
    .alert-card.ok {
        background: var(--green-bg);
        border: 1px solid var(--green-bar);
        color: var(--green-ink);
    }
    .alert-card .card-head {
        font-weight: 700;
        font-size: 0.9rem;
        margin-bottom: 2px;
    }

    /* Transcript Turns in Evidence Drawer */
    div[class*="turn_row_"] button {
        width: 100% !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 6px 10px !important;
        min-height: 34px !important;
        height: auto !important;
        border-radius: 6px !important;
        font-size: 0.84rem !important;
        line-height: 1.4 !important;
        white-space: normal !important;
        word-break: break-word !important;
        border: 1px solid var(--line) !important;
        margin-bottom: 4px !important;
        background: #FFFFFF !important;
        color: var(--ink) !important;
        box-shadow: none !important;
        transition: all 0.1s ease-in-out !important;
    }
    div[class*="turn_row_hit"] button {
        background: #DBEAFE !important;
        border: 1px solid var(--accent) !important;
        color: #1E3A8A !important;
    }
    div[class*="turn_row_"] button:hover {
        background: #F8FAFC !important;
        border-color: var(--accent) !important;
        cursor: pointer !important;
    }

    /* Streamlit Global Widget Polish */
    .stButton > button, .stDownloadButton > button {
        border-radius: 6px !important;
        border: 1px solid #64748B !important;
        background: #FFFFFF !important;
        color: var(--ink) !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        min-height: 32px !important;
        box-shadow: none !important;
    }
    .stButton > button:hover {
        border-color: var(--accent) !important;
        color: var(--accent) !important;
    }
    button[kind="primary"] {
        background: var(--ink) !important;
        color: #FFFFFF !important;
        border-color: var(--ink) !important;
    }
    button[kind="primary"]:hover {
        background: #1E293B !important;
        color: #FFFFFF !important;
    }
    [data-testid="stTextArea"] textarea {
        border: 1px solid #64748B !important;
        border-radius: 6px !important;
        background: #FFFFFF !important;
        font-size: 0.92rem !important;
        line-height: 1.5 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# VISUAL REFINEMENT: RESTRAINED NEUMORPHISM + MOBILE ADAPTATION
# =============================================================================
st.markdown(
    """
    <style>
    :root {
        --bg: #eef1f4;
        --ink: #172638;
        --muted: #647487;
        --line: #d8dee6;
        --accent: #0f766e;
        --accent-bg: #e4f2ef;
        --shadow-out: 5px 5px 12px rgba(160, 171, 185, .32), -5px -5px 12px rgba(255,255,255,.88);
        --shadow-in: inset 2px 2px 5px rgba(160,171,185,.25), inset -2px -2px 5px rgba(255,255,255,.82);
    }
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background: var(--bg) !important;
        color: var(--ink) !important;
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    }
    [data-testid="stSidebar"] { background: #e9edf1 !important; border-right: 1px solid #dbe1e8; }
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.35rem; }
    .block-container { max-width: 1680px !important; padding: 1.4rem clamp(1rem, 2.4vw, 2.4rem) 3rem !important; container-type: inline-size; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-color: transparent !important; }
    .st-key-note_pane, .st-key-drawer_pane {
        background: var(--bg) !important; border: 1px solid rgba(255,255,255,.68) !important;
        border-radius: 22px !important; padding: clamp(16px, 2vw, 26px) !important;
        box-shadow: var(--shadow-out) !important;
    }
    .st-key-drawer_pane { position: sticky !important; top: 14px !important; max-height: calc(100vh - 28px) !important; overflow-y: auto !important; }
    .patient-header { align-items: center !important; border: 0 !important; margin: 0 0 1rem !important; padding: 6px 4px 14px !important; }
    .patient-header .title { font-size: clamp(1.1rem, 1.6vw, 1.4rem) !important; letter-spacing: -.025em !important; }
    .patient-header .meta { color: var(--muted) !important; line-height: 1.7; }
    .badge-ok-count, .badge-review-count { padding: 7px 12px !important; border-radius: 999px !important; }
    .sec-header { color: var(--ink) !important; border-bottom: 1px solid #bfcbd5 !important; margin: 22px 0 11px !important; padding-bottom: 7px !important; letter-spacing: .12em !important; }
    .field-label { margin: 14px 0 6px !important; font-size: .7rem !important; letter-spacing: .1em !important; color: #536579 !important; }
    div[class*="claim_row_"] button, div[class*="turn_row_"] button {
        border-radius: 8px !important; border: 1px solid #d2dbe3 !important;
        border-left: 1px solid #d2dbe3 !important;
        background: #ffffff !important; color: var(--ink) !important;
        box-shadow: 2px 2px 6px rgba(163,174,187,.18) !important;
        transition: transform .14s ease, border-color .14s ease, background .14s ease !important;
        white-space: normal !important; word-break: break-word !important; overflow-wrap: break-word !important; height: auto !important;
    }
    div[class*="claim_row_"] button p, div[class*="claim_row_"] button div {
        white-space: normal !important; word-break: break-word !important; overflow-wrap: break-word !important; text-align: left !important;
    }
    div[class*="claim_row_"] button { padding: 10px 14px !important; min-height: 44px !important; line-height: 1.55 !important; border: 1px solid #d2dbe3 !important; border-left: 1px solid #d2dbe3 !important; text-align: left !important; justify-content: flex-start !important; }
    div[class*="claim_row_crit"] button { background: #fff5f5 !important; border: 1px solid #fca5a5 !important; border-left: 1px solid #fca5a5 !important; color: #991b1b !important; }
    div[class*="claim_row_warn"] button { background: #fffbeb !important; border: 1px solid #fcd34d !important; border-left: 1px solid #fcd34d !important; color: #92400e !important; }
    div[class*="claim_row_sel"] button { outline: 2px solid #0f766e !important; outline-offset: 2px !important; background: #e3f1ee !important; }
    div[class*="claim_row_"] button:hover, div[class*="turn_row_"] button:hover { transform: translateY(-1px); box-shadow: 3px 4px 9px rgba(163,174,187,.24) !important; border-color: #0f766e !important; }
    .dr-title { color: #41566b !important; letter-spacing: .11em !important; padding-bottom: 7px; border-bottom: 1px solid #d3dce4; }
    .quote-box { background: #e9edf1 !important; border: 1px solid #cbd5e1 !important; border-radius: 8px !important; padding: 13px 15px !important; box-shadow: var(--shadow-in) !important; }
    .alert-card { border-radius: 8px !important; padding: 13px 15px !important; border: 1px solid transparent !important; }
    .alert-card.ok { background: #e7f3ed !important; border-color: #b4d4c1 !important; color: #205b3a !important; }
    .stButton > button, .stDownloadButton > button {
        min-height: 42px !important; border-radius: 13px !important; border: 1px solid rgba(255,255,255,.85) !important;
        background: #eef1f4 !important; color: var(--ink) !important; font-weight: 650 !important;
        box-shadow: 4px 4px 9px rgba(163,174,187,.28), -4px -4px 9px rgba(255,255,255,.84) !important;
        transition: transform .15s ease, box-shadow .15s ease !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px); border-color: #9abdb7 !important; color: #0f625d !important; }
    button[kind="primary"] { background: #176e67 !important; color: white !important; border-color: #176e67 !important; box-shadow: 3px 4px 9px rgba(23,110,103,.22) !important; }
    button[kind="primary"]:hover { background: #125c56 !important; color: white !important; }
    [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input, [data-testid="stSelectbox"] [role="combobox"] {
        border: 1px solid #d2dbe3 !important; border-radius: 12px !important; background: #edf0f3 !important;
        color: var(--ink) !important; box-shadow: var(--shadow-in) !important;
    }
    [data-testid="stCheckbox"] label { line-height: 1.55 !important; }
    [data-testid="stAlert"] { background: #e5f1ef !important; border-color: #a7cbc5 !important; color: #204d49 !important; border-radius: 13px !important; }
    @container (max-width: 1000px) {
        [data-testid="stHorizontalBlock"]:has(.st-key-note_pane) { flex-direction: column !important; align-items: stretch !important; }
        [data-testid="stHorizontalBlock"]:has(.st-key-note_pane) > [data-testid="stColumn"] { flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important; }
        .st-key-drawer_pane { position: static !important; max-height: none !important; overflow: visible !important; }
    }
    .st-key-auth_wrap { max-width: 1040px; margin: clamp(20px, 7vh, 76px) auto; }
    .st-key-auth_card { padding: clamp(24px, 5vw, 54px); border-radius: 28px; background: #eef1f4; box-shadow: 12px 12px 28px rgba(160,171,185,.34), -12px -12px 28px rgba(255,255,255,.92); border: 1px solid rgba(255,255,255,.75); }
    .auth-eyebrow { color: #0f766e; font-size: .72rem; font-weight: 750; letter-spacing: .16em; text-transform: uppercase; }
    .auth-title { color: #172638; font-size: clamp(2rem, 4vw, 3.25rem); line-height: 1.05; letter-spacing: -.045em; font-weight: 760; margin: 14px 0; }
    .auth-subtitle { color: #536579; font-size: 1rem; line-height: 1.7; max-width: 42rem; }
    .auth-feature { padding: 14px 16px; border-radius: 14px; margin: 10px 0; color: #31485b; background: #eef1f4; box-shadow: var(--shadow-in); line-height: 1.5; }
    .auth-note { font-size: .78rem; color: #647487; line-height: 1.6; padding-top: 12px; }
    @media (max-width: 960px) {
        .block-container { padding: 1rem .9rem 2rem !important; }
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 1rem !important; }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] { flex: 1 1 100% !important; min-width: 100% !important; }
        .st-key-drawer_pane { position: static !important; top: auto !important; max-height: none !important; overflow: visible !important; }
        .patient-header { align-items: flex-start !important; flex-direction: column; gap: 10px; }
    }
    @media (max-width: 600px) {
        [data-testid="stSidebar"] { min-width: 0 !important; }
        .st-key-note_pane, .st-key-drawer_pane { padding: 14px !important; border-radius: 17px !important; }
        .stButton > button, .stDownloadButton > button { min-height: 46px !important; }
        .st-key-auth_wrap { margin: 12px auto; }
        .st-key-auth_card { border-radius: 20px; }
        .auth-title { font-size: 2.1rem; }
    }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: .01ms !important; scroll-behavior: auto !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)

# UI-only demo access gate: no credentials are collected, stored, or validated.
if not st.session_state.get("local_demo_access", False):
    st.markdown("<style>[data-testid='stSidebar']{display:none!important}[data-testid='stAppViewContainer']{margin-left:0!important}</style>", unsafe_allow_html=True)
    with st.container(key="auth_wrap"):
      with st.container(key="auth_card"):
        left, right = st.columns([1.25, 1], gap="large")
        with left:
            st.markdown("<div class='auth-eyebrow'>Medscribe · Proof Mode</div><div class='auth-title'>A clearer path from conversation to note.</div><div class='auth-subtitle'>Review a locally generated SOAP draft alongside the exact conversation evidence behind it. Built for calm, focused clinician review.</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
            st.markdown("<div class='auth-feature'><strong>01 · Source-linked</strong><br/>Inspect the cited transcript wording for each statement.</div><div class='auth-feature'><strong>02 · Review-aware</strong><br/>Spot unsupported claims, uncertainty changes, and unassessed fields.</div><div class='auth-feature'><strong>03 · Local-first demo</strong><br/>Synthetic encounters and local adapters; no cloud sign-in is configured.</div>", unsafe_allow_html=True)
        with right:
            st.markdown("### Open your local workspace")
            st.caption("Demo access · no account required")
            st.info("This prototype does not provide real authentication. Do not enter a password or real patient information.", icon="🔒")
            clinician_label = st.text_input("Display name (optional)", placeholder="e.g. Dr. Morgan", key="demo_display_name")
            if st.button("Continue to demo workspace", type="primary", use_container_width=True, key="btn_demo_access"):
                st.session_state.local_demo_access = True
                st.session_state.demo_clinician_label = clinician_label.strip()
                st.rerun()
            st.markdown("<div class='auth-note'>Medscribe is an experimental documentation prototype, not a diagnostic or treatment system. All built-in cases are fictional. Review every draft before export.</div>", unsafe_allow_html=True)
    st.stop()

# =============================================================================
# CLINICAL AUDIT STATE HELPERS
# =============================================================================
def needs_review(c) -> bool:
    if c.clinician_reviewed:
        return False
    return c.verification_status != VerificationStatus.SUPPORTED or bool(c.audit_flags)

def is_critical(c) -> bool:
    return (c.verification_status != VerificationStatus.SUPPORTED
            or any(f.severity == AuditFlagSeverity.CRITICAL for f in c.audit_flags))

def edit_key(c) -> str:
    return f"edit_{c.claim_id}"

def select_claim(c):
    st.session_state.selected_claim = c
    st.session_state.highlighted_seg_ids = list(c.source_segment_ids)

def select_claim_from_segment(c, seg_id: str):
    st.session_state.selected_claim = c
    st.session_state.highlighted_seg_ids = [seg_id]

def clear_selection():
    st.session_state.selected_claim = None
    st.session_state.highlighted_seg_ids = []

def apply_text(c, text: str):
    c.clinician_edited_statement = text.strip() or None
    c.clinician_reviewed = True
    st.session_state[edit_key(c)] = text.strip() or c.statement

def save_edit(c):
    apply_text(c, st.session_state.get(edit_key(c), c.statement))

def mark_reviewed(c):
    c.clinician_reviewed = True

def next_item():
    pending = [c for c in draft.all_claims() if needs_review(c)]
    if not pending:
        return
    cur = st.session_state.selected_claim
    ids = [c.claim_id for c in pending]
    nxt = pending[(ids.index(cur.claim_id) + 1) % len(pending)] if cur and cur.claim_id in ids else pending[0]
    select_claim(nxt)
    st.session_state.audit_filter = "review"

all_claims = draft.all_claims()
review_n = sum(1 for c in all_claims if needs_review(c))
blank_n = len(draft.audit_summary.missing_fields)

# =============================================================================
# AUDIO CONSULTATION CAPTURE (LOCAL ON-DEVICE WHISPER)
# =============================================================================
is_audio_open = bool(st.session_state.get("audio_expanded", False) or st.session_state.get("loaded_preset") == "Live Audio Consultation")
with st.expander("🎙️ Capture Live Consultation Audio (Local On-Device Whisper)", expanded=is_audio_open):
    st.markdown(
        "<div style='font-size:0.86rem; color:var(--muted); margin-bottom:10px;'>"
        "Record live dialogue or upload a consultation audio file (.wav, .mp3, .m4a). "
        "Speech recognition executes <strong>100% locally on-device via Whisper</strong> on CPU with zero internet connection or telemetry."
        "</div>",
        unsafe_allow_html=True,
    )
    c_lang_col, _ = st.columns([1.2, 1])
    with c_lang_col:
        chosen_lang = st.selectbox(
            "Spoken Language",
            ["Tagalog / Taglish / English (Auto-Detect)", "Tagalog (Filipino - tl)", "English (en)"],
            index=0,
            key="ctl_whisper_lang",
            help="Multilingual Whisper detects and transcribes Filipino/Tagalog and English accurately.",
        )

    c_aud_rec, c_aud_up = st.columns(2, gap="medium")
    with c_aud_rec:
        st.markdown("<div style='font-size:0.82rem; font-weight:700; color:var(--ink); margin-bottom:4px;'>Option A: Microphone Capture</div>", unsafe_allow_html=True)
        mic_audio = st.audio_input("Record live consultation", key="ctl_mic_audio")
    with c_aud_up:
        st.markdown("<div style='font-size:0.82rem; font-weight:700; color:var(--ink); margin-bottom:4px;'>Option B: Upload Audio File</div>", unsafe_allow_html=True)
        file_audio = st.file_uploader("Upload audio recording", type=["wav", "mp3", "m4a", "ogg"], key="ctl_file_audio")

    active_audio = mic_audio or file_audio
    if active_audio:
        st.audio(active_audio)
        if st.button("Transcribe On-Device & Generate Audited SOAP Note", type="primary", key="btn_transcribe_audio", use_container_width=True):
            with st.spinner("Transcribing consultation audio locally via Whisper (100% on-device)..."):
                audio_bytes = active_audio.read()
                lang_code = "tl" if "Tagalog (Filipino" in chosen_lang else ("en" if "English (en)" in chosen_lang else None)
                st_text = transcribe_audio_bytes(audio_bytes, language=lang_code)
                pipeline = MedscribePipeline(adapter=get_adapter(selected_engine))
                new_transcript = pipeline.parse_raw_text_to_transcript(
                    st_text,
                    encounter_id="ENC-LIVE-AUDIO-001",
                    patient_id="SYN-PAT-LIVE"
                )
                new_draft = pipeline.process_encounter(new_transcript)
                st.session_state.active_transcript = new_transcript
                st.session_state.draft_note = new_draft
                st.session_state.loaded_preset = "Live Audio Consultation"
                st.session_state.last_preset_selection = "Live Audio Consultation"
                st.session_state.transcribed_audio_text = st_text
                st.session_state.audio_expanded = True
                def_claim = get_highest_priority_claim(new_draft)
                st.session_state.selected_claim = def_claim
                st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
                st.rerun()

    if st.session_state.get("transcribed_audio_text"):
        st.markdown("---")
        st.markdown(
            """
            <div style='background:#f1f5f9; border:1px solid #cbd5e1; padding:10px 14px; border-radius:6px; margin-bottom:8px;'>
                <div style='font-weight:750; font-size:0.82rem; color:#0f766e; text-transform:uppercase;'>📝 Whisper On-Device Transcription Output</div>
                <div style='margin:4px 0 0; font-size:0.82rem; color:#475569;'>Review or correct the dialogue turns below. You can edit any word and re-generate the clinical draft.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        edited_transcription = st.text_area(
            "Verbatim Dialogue Turns (Editable)",
            value=st.session_state.transcribed_audio_text,
            height=140,
            key="area_transcribed_audio",
            help="Edit transcript lines to correct any audio misunderstandings before regenerating the note.",
        )
        if st.button("Re-process SOAP Note with Edited Transcription", key="btn_reprocess_audio", type="secondary", use_container_width=True):
            pipeline = MedscribePipeline(adapter=get_adapter(selected_engine))
            new_t = pipeline.parse_raw_text_to_transcript(
                edited_transcription,
                encounter_id="ENC-LIVE-AUDIO-001",
                patient_id="SYN-PAT-LIVE",
            )
            new_draft = pipeline.process_encounter(new_t)
            st.session_state.active_transcript = new_t
            st.session_state.draft_note = new_draft
            st.session_state.transcribed_audio_text = edited_transcription
            def_claim = get_highest_priority_claim(new_draft)
            st.session_state.selected_claim = def_claim
            st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
            st.success("SOAP note updated from edited transcript!")
            st.rerun()

# =============================================================================
# SUMMARY & QUICK AUDIT FILTER BAR
# =============================================================================
patient_name = html.escape(patient_display(transcript.patient_synthetic_id))
if review_n:
    count_badge = f"<span class='badge-review-count'>{review_n} item{'s' if review_n != 1 else ''} require review</span>"
else:
    count_badge = "<span class='badge-ok-count'>✓ All items verified</span>"

st.markdown(
    f"""
    <div class='patient-header'>
        <div>
            <span class='title'>{patient_name}</span>
            <span class='meta'>• Date: {html.escape(transcript.encounter_date)} • ID: {html.escape(transcript.encounter_id)}</span>
        </div>
        <div>
            {count_badge}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

def set_filter(key: str):
    st.session_state.audit_filter = key

if "audit_filter" not in st.session_state:
    st.session_state.audit_filter = "all"
active_filter = st.session_state.audit_filter

FILTERS = {
    "all": f"All Statements ({len(all_claims)})",
    "review": f"Needs Review ({review_n})",
    "unassessed": f"Unassessed ({blank_n})",
}

col_f1, col_f2, col_f3, col_f4 = st.columns([1.2, 1.4, 1.4, 1.8], gap="small")
col_f1.button(
    FILTERS["all"],
    key="chip_all",
    on_click=set_filter,
    args=("all",),
    use_container_width=True,
    type="primary" if active_filter == "all" else "secondary",
)
col_f2.button(
    FILTERS["review"],
    key="chip_review",
    on_click=set_filter,
    args=("review",),
    use_container_width=True,
    type="primary" if active_filter == "review" else "secondary",
)
col_f3.button(
    FILTERS["unassessed"],
    key="chip_unassessed",
    on_click=set_filter,
    args=("unassessed",),
    use_container_width=True,
    type="primary" if active_filter == "unassessed" else "secondary",
)
col_f4.button(
    "Next Item to Review ➔",
    on_click=next_item,
    disabled=review_n == 0,
    key="btn_next",
    use_container_width=True,
    type="primary" if review_n > 0 else "secondary",
)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# =============================================================================
# WORKSPACE LAYOUT: PRIMARY SOAP CHART (LEFT) & EVIDENCE DRAWER (RIGHT)
# =============================================================================
col_note, col_drawer = st.columns([1.45, 1.05], gap="large")

SECTIONS = [
    ("Subjective", [
        ("Chief Complaint", draft.subjective.chief_complaint),
        ("History of Present Illness", draft.subjective.history_of_present_illness),
        ("Current Regimen", draft.subjective.current_medications),
        ("Allergies", draft.subjective.allergies),
    ]),
    ("Objective", [
        ("Vital Signs", draft.objective.vital_signs),
        ("Physical Examination", draft.objective.physical_exam),
        ("Diagnostic Tests", draft.objective.diagnostic_tests),
    ]),
    ("Assessment", [
        ("Clinical Impressions", draft.assessment.clinical_impressions),
    ]),
    ("Plan", [
        ("Prescriptions Advised", draft.plan.medications_advised),
        ("Non-Pharmacologic Care", draft.plan.non_pharmacologic_care),
        ("Follow-up & Return Precautions", draft.plan.follow_up_and_red_flags),
    ]),
]

def render_claim_row(c):
    sel = st.session_state.selected_claim
    is_sel = sel and sel.claim_id == c.claim_id
    
    crit = is_critical(c)
    rev = needs_review(c)
    
    status_type = "crit" if (crit and rev) else "warn" if rev else "ok"
    sel_type = "sel" if is_sel else "norm"
    container_key = f"claim_row_{status_type}_{sel_type}_{c.claim_id}"
    
    # Badge and label prefix
    if crit and rev:
        badge = "🚨 [HIGH PRIORITY] "
    elif rev:
        badge = "⚠️ [REVIEW] "
    elif c.clinician_edited_statement:
        badge = "✎ [EDITED] "
    else:
        badge = "✓ "
        
    refs = ", ".join(line_label(i, LINES) for i in c.source_segment_ids)
    ref_suffix = f"   ·   [{refs} ↗]" if refs else "   ·   [No Citation ↗]"
    text = c.clinician_edited_statement or c.statement
    
    full_label = f"{badge}{text}{ref_suffix}"
    
    with st.container(key=container_key):
        st.button(
            full_label,
            key=f"btn_claim_{c.claim_id}",
            on_click=select_claim,
            args=(c,),
            use_container_width=True,
            help="Click to inspect supporting transcript evidence and clinical audit guidance",
        )

with col_note:
    with st.container(key="note_pane"):
        if active_filter == "unassessed":
            st.markdown("<div class='sec-header'>Unassessed Clinical Parameters</div>", unsafe_allow_html=True)
            if not draft.audit_summary.missing_fields:
                st.markdown("<div class='fld-blank-row'>Every standard clinical field was addressed during the encounter.</div>", unsafe_allow_html=True)
            for raw in draft.audit_summary.missing_fields:
                st.markdown(
                    f"<div class='fld-blank-row'><strong>{html.escape(unassessed_label(raw))}</strong>: {UNASSESSED_COPY}</div>",
                    unsafe_allow_html=True,
                )
        else:
            shown_any = False
            for sec_title, fields in SECTIONS:
                filtered_fields = [
                    (n, [c for c in cl if active_filter == "all" or needs_review(c)])
                    for n, cl in fields
                ]
                if active_filter == "review" and not any(cl for _, cl in filtered_fields):
                    continue
                shown_any = True
                st.markdown(f"<div class='sec-header'>{sec_title}</div>", unsafe_allow_html=True)
                for f_name, claims in filtered_fields:
                    if active_filter == "review" and not claims:
                        continue
                    st.markdown(f"<div class='field-label'>{f_name}</div>", unsafe_allow_html=True)
                    if not claims:
                        st.markdown(
                            f"<div class='fld-blank-row'>— Not assessed in consultation (left unpopulated)</div>",
                            unsafe_allow_html=True,
                        )
                    for c in claims:
                        render_claim_row(c)
            if not shown_any:
                st.markdown("<div class='fld-blank-row'>No items require review in this view.</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
        sign_off = st.checkbox(
            "I attest that I have reviewed this clinical documentation against the consultation record.",
            value=draft.clinician_review_confirmed,
            key="chk_attest",
        )
        draft.clinician_review_confirmed = sign_off
        if review_n and sign_off:
            st.caption(f"Notice: {review_n} statement(s) are still flagged for review and will be exported as documented.")
            
        st.download_button(
            "Export Attested Clinical Note (.txt)" if sign_off else "Export Restricted (Review Attestation Required)",
            data=MedscribePipeline().export_note_text(draft),
            file_name=f"medscribe_{draft.encounter_id}_{'reviewed' if sign_off else 'draft'}.txt",
            mime="text/plain",
            disabled=not sign_off,
            type="primary" if sign_off else "secondary",
            use_container_width=True,
        )

def edit_height(text: str) -> int:
    lines = text.count("\n") + 1
    wrap_lines = max(1, len(text) // 46)
    total_lines = max(lines, wrap_lines)
    return max(90, min(320, 24 * total_lines + 36))

with col_drawer:
    with st.container(key="drawer_pane"):
        tab_audit, tab_transcript = st.tabs(["⚡ Evidence & Resolution", "📜 Consultation Transcript"])
        with tab_audit:
            sel = st.session_state.selected_claim
            if sel is None:
                # Fallback if no claim selected
                st.markdown("<div class='dr-title'><span>Evidence & Citation Audit</span></div>", unsafe_allow_html=True)
                st.markdown("<div class='fld-blank-row'>Select any statement row to inspect its transcript citation.</div>", unsafe_allow_html=True)
            else:
                refs = ", ".join(line_label(i, LINES) for i in sel.source_segment_ids) or "No source line"
                st.markdown(
                    f"""
                    <div class='dr-title'>
                        <span>Evidence & Citation Audit</span>
                        <span class='mono' style='font-size:0.75rem; color:#1D4ED8; font-weight:700;'>[{sel.claim_id}] · {refs}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                # Verbatim transcript excerpt
                if sel.source_exact_quote:
                    st.markdown(
                        f"""
                        <div style='font-size:0.72rem; font-weight:700; color:var(--muted); text-transform:uppercase;'>Verbatim Consultation Excerpt:</div>
                        <div class='quote-box'>“{html.escape(sel.source_exact_quote)}”</div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        """
                        <div class='alert-card crit'>
                            <div class='card-head'>⚠️ No Supporting Transcript Excerpt</div>
                            <div>This claim was generated without an explicit verbatim consultation excerpt.</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    
                # Audit Guidance & Translation
                if not sel.audit_flags and sel.verification_status == VerificationStatus.SUPPORTED:
                    st.markdown(
                        """
                        <div class='alert-card ok'>
                            <div class='card-head'>✓ Verified Grounded Statement</div>
                            <div>This statement is supported by the cited consultation turn. Verify clinical relevance.</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                for fl in sel.audit_flags:
                    d = describe_flag(fl, sel, LINES)
                    card_cls = "crit" if fl.severity == AuditFlagSeverity.CRITICAL else "warn"
                    st.markdown(
                        f"""
                        <div class='alert-card {card_cls}'>
                            <div class='card-head'>⚠️ {html.escape(d['title'])}</div>
                            <div style='margin-bottom:4px;'>{html.escape(d['why'])}</div>
                            <div style='font-size:0.8rem;'><strong>Suggested:</strong> {html.escape(d['prompt'])}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
    
                # Physician Modification Editor
                st.markdown("<div class='dr-title' style='margin-top:14px;'><span>Physician Override & Resolution</span></div>", unsafe_allow_html=True)
                if sel.source_exact_quote and (sel.clinician_edited_statement or sel.statement) != sel.source_exact_quote:
                    st.caption(f"Suggested transcript wording: “{html.escape(sel.source_exact_quote)}”")
                    st.button(
                        "Accept Verbatim Transcript Wording",
                        on_click=apply_text,
                        args=(sel, sel.source_exact_quote),
                        type="primary",
                        key="btn_accept",
                        use_container_width=True,
                    )
                    
                current_val = sel.clinician_edited_statement or sel.statement
                if edit_key(sel) not in st.session_state:
                    st.session_state[edit_key(sel)] = current_val
                    
                st.text_area(
                    "Statement in Note",
                    key=edit_key(sel),
                    height=edit_height(st.session_state[edit_key(sel)]),
                    help="Edit this statement directly without truncation. Click 'Save Edit' to apply.",
                )
                
                c_b1, c_b2 = st.columns(2)
                c_b1.button("Save Edit", on_click=save_edit, args=(sel,), key="btn_save", type="primary", use_container_width=True)
                c_b2.button("Keep As Written", on_click=mark_reviewed, args=(sel,), key="btn_keep", use_container_width=True)
        with tab_transcript:
            st.markdown(
                f"""
                <div class='dr-title'>
                    <span>Consultation Transcript Record</span>
                    <span class='mono' style='font-size:0.75rem; color:#1D4ED8; font-weight:700;'>{len(transcript.segments)} Dialogue Turns</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption("Verbatim dialogue turns. Spoken turns cited by the active note statement are highlighted.")
            hits = set(st.session_state.highlighted_seg_ids)
            for seg in transcript.segments:
                s_id = seg.segment_id
                l_num = line_label(s_id, LINES)
                spk = seg.speaker.value
                is_hit = s_id in hits
                
                border_clr = "#0f766e" if is_hit else "#cbd5e1"
                bg_clr = "#e3f1ee" if is_hit else "#f8fafc"
                badge_html = "<span style='font-size:0.68rem; background:#0f766e; color:#ffffff; padding:2px 7px; border-radius:4px; font-weight:700;'>● CITED IN ACTIVE CLAIM</span>" if is_hit else ""
                
                st.markdown(
                    f"""
                    <div style='padding:9px 13px; margin-bottom:8px; border-radius:8px; border:1px solid {border_clr}; background:{bg_clr}; font-size:0.86rem; line-height:1.5;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;'>
                            <span style='font-weight:750; font-size:0.74rem; color:var(--muted); text-transform:uppercase;'>{l_num} · {spk}</span>
                            {badge_html}
                        </div>
                        <div style='color:var(--ink);'>{html.escape(seg.text)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
