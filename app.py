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

# =============================================================================
# STREAMLIT PAGE CONFIGURATION
# =============================================================================
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
    st.session_state.transcribed_audio_text = None
    
    # Auto-initialize right-hand pane with highest-priority flagged item
    def_claim = get_highest_priority_claim(draft)
    st.session_state.selected_claim = def_claim
    st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []

# =============================================================================
# SIDEBAR CONTROLS (ENCOUNTER, INFERENCE, UPLOAD AUDIO)
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
        help="Load pre-calibrated synthetic patient encounters.",
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
    # AUDIO UPLOAD ONLY (Microphone recording removed)
    with st.expander("📁 Upload Audio Consultation (Whisper Medium)", expanded=False):
        st.caption("Upload consultation audio (.wav, .mp3, .m4a). Speech-to-text executes 100% on-device on CPU.")
        uploaded_audio = st.file_uploader("Audio File", type=["wav", "mp3", "m4a", "ogg"], key="sb_file_audio")
        c_lang = st.selectbox(
            "Language",
            ["Tagalog (Filipino - tl)", "Taglish / Auto-Detect", "English (en)"],
            index=0,
            key="sb_audio_lang",
        )
        c_model = st.selectbox(
            "Whisper Model",
            ["Medium (Highest Accuracy · 769M)", "Small (Fast & Accurate · 244M)", "Base (Fast · 140M)"],
            index=0,
            key="sb_whisper_model",
        )
        if uploaded_audio is not None:
            st.audio(uploaded_audio)
            if st.button("Transcribe Audio & Generate Draft", type="primary", key="sb_btn_transcribe_audio", use_container_width=True):
                with st.spinner("Transcribing consultation audio locally via Whisper Medium..."):
                    raw_bytes = uploaded_audio.getvalue()
                    lang_code = "tl" if "Tagalog" in c_lang else ("en" if "English" in c_lang else None)
                    model_code = "medium" if "Medium" in c_model else ("small" if "Small" in c_model else "base")
                    txt = transcribe_audio_bytes(raw_bytes, language=lang_code, model_size=model_code)
                    pipeline = MedscribePipeline(adapter=get_adapter(selected_engine))
                    new_t = pipeline.parse_raw_text_to_transcript(txt, encounter_id="ENC-UPLOAD-001", patient_id="SYN-PAT-UPLOAD")
                    new_draft = pipeline.process_encounter(new_t)
                    st.session_state.active_transcript = new_t
                    st.session_state.draft_note = new_draft
                    st.session_state.loaded_preset = "Uploaded Audio Consultation"
                    st.session_state.transcribed_audio_text = txt
                    def_claim = get_highest_priority_claim(new_draft)
                    st.session_state.selected_claim = def_claim
                    st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
                    st.rerun()

    with st.expander("🧪 Custom Consultation Generator", expanded=False):
        st.caption("Paste arbitrary consultation dialogue to evaluate on-device evidence linking.")
        cu_enc = st.text_input("Encounter Code", value="ENC-CUSTOM-001", key="sb_cu_enc")
        cu_pat = st.text_input("Patient Identifier (Synthetic)", value="SYN-PAT-CUSTOM", key="sb_cu_pat")
        cu_txt = st.text_area(
            "Consultation Dialogue",
            height=160,
            key="sb_cu_txt",
            placeholder="Clinician: How have you been feeling?\nPatient: Masakit po ang ulo ko nitong nakaraang tatlong araw.",
        )
        if st.button("Generate SOAP Draft", type="primary", key="sb_btn_generate", use_container_width=True):
            if cu_txt.strip():
                pipeline = MedscribePipeline(adapter=get_adapter(selected_engine))
                new_t = pipeline.parse_raw_text_to_transcript(cu_txt, encounter_id=cu_enc, patient_id=cu_pat)
                new_draft = pipeline.process_encounter(new_t)
                st.session_state.active_transcript = new_t
                st.session_state.draft_note = new_draft
                st.session_state.loaded_preset = "Custom Encounter"
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
# ELEVATED NEUMORPHIC STYLE SYSTEM (NEVER CARVED · MATCHING REFERENCE DESIGN)
# =============================================================================
st.markdown(
    """
    <style>
    /* Elevated Neumorphic Design System matching attached reference:
       - Soft silky warm-gray canvas (#eef1f5)
       - All cards & elements are SLIGHTLY ELEVATED (dual-direction positive drop shadows)
       - NEVER carved (zero inset shadows)
       - Smooth pillowy rounded corners (16px to 24px)
       - NO side stripes on cards
       - Systematic, tight, consistent spacing rhythm (King-Julyan frontend design)
    */
    :root {
        --bg: #eef1f5;
        --ink: #1e293b;
        --muted: #64748b;
        --line: rgba(255, 255, 255, 0.75);
        --accent: #0f766e;
        --accent-bg: #e2f2ef;
        
        /* Dual-direction realistic elevation */
        --elevated-card: 8px 8px 18px rgba(160, 172, 188, 0.38), -8px -8px 18px rgba(255, 255, 255, 0.92);
        --elevated-pill: 4px 4px 10px rgba(160, 172, 188, 0.30), -4px -4px 10px rgba(255, 255, 255, 0.88);
        --elevated-hover: 6px 6px 14px rgba(160, 172, 188, 0.40), -6px -6px 14px rgba(255, 255, 255, 0.95);
    }
    
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background: var(--bg) !important;
        color: var(--ink) !important;
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }
    
    [data-testid="stSidebar"] {
        background: #e8ecf2 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.6) !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.2rem;
    }
    
    .block-container {
        max-width: 1680px !important;
        padding: 1.2rem clamp(1rem, 2.2vw, 2.2rem) 2.5rem !important;
    }
    
    /* Main Elevated Containers */
    .st-key-note_pane, .st-key-drawer_pane {
        background: var(--bg) !important;
        border: 1px solid rgba(255, 255, 255, 0.8) !important;
        border-radius: 24px !important;
        padding: 22px 24px !important;
        box-shadow: var(--elevated-card) !important;
    }
    .st-key-drawer_pane {
        position: sticky !important;
        top: 12px !important;
        max-height: calc(100vh - 24px) !important;
        overflow-y: auto !important;
    }
    
    /* Systematic Vertical Spacing Control */
    .st-key-note_pane [data-testid="stVerticalBlock"],
    .st-key-drawer_pane [data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
    }
    .st-key-note_pane [data-testid="element-container"],
    .st-key-drawer_pane [data-testid="element-container"] {
        margin: 0 !important;
    }
    
    /* Patient Header (Elevated Pill Bar) */
    .patient-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 0 0 12px 0;
        padding: 12px 20px;
        background: var(--bg);
        border-radius: 20px;
        box-shadow: var(--elevated-pill);
        border: 1px solid rgba(255, 255, 255, 0.85);
    }
    .patient-header .title {
        font-size: clamp(1.1rem, 1.5vw, 1.35rem);
        font-weight: 750;
        letter-spacing: -0.025em;
        color: var(--ink);
    }
    .patient-header .meta {
        color: var(--muted);
        font-size: 0.84rem;
        margin-left: 10px;
    }
    .badge-ok-count, .badge-review-count {
        padding: 6px 14px !important;
        border-radius: 999px !important;
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        box-shadow: var(--elevated-pill) !important;
        border: 1px solid rgba(255, 255, 255, 0.85) !important;
    }
    .badge-ok-count {
        background: #e7f3ed !important;
        color: #1e5a39 !important;
    }
    .badge-review-count {
        background: #fff0ee !important;
        color: #991b1b !important;
    }

    /* Section & Field Labels with Crisp Rhythmic Spacing */
    .sec-header {
        color: var(--ink) !important;
        border-bottom: 1px solid rgba(160, 172, 188, 0.25) !important;
        margin: 16px 0 8px !important;
        padding-bottom: 5px !important;
        letter-spacing: .12em !important;
        font-size: 0.82rem !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
    }
    .sec-header:first-of-type {
        margin-top: 0 !important;
    }
    .field-label {
        margin: 10px 0 4px !important;
        font-size: 0.70rem !important;
        letter-spacing: .1em !important;
        color: #536579 !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
    }
    .fld-blank-row {
        font-size: 0.84rem !important;
        color: var(--muted) !important;
        font-style: italic !important;
        padding: 8px 14px !important;
        background: var(--bg) !important;
        border-radius: 14px !important;
        box-shadow: 2px 2px 6px rgba(160, 172, 188, 0.2), -2px -2px 6px rgba(255, 255, 255, 0.8) !important;
        margin-bottom: 6px !important;
    }

    /* Elevated Pill Cards (Matching Air Conditioner, Wi-Fi Router, Smart TV in Reference) */
    div[class*="claim_row_"] {
        margin-bottom: 6px !important;
    }
    div[class*="claim_row_"] button, div[class*="turn_row_"] button {
        border-radius: 16px !important;
        border: 1px solid rgba(255, 255, 255, 0.85) !important;
        background: var(--bg) !important;
        color: var(--ink) !important;
        box-shadow: var(--elevated-pill) !important;
        padding: 11px 16px !important;
        min-height: 44px !important;
        line-height: 1.5 !important;
        text-align: left !important;
        justify-content: flex-start !important;
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        transition: transform 0.14s ease, box-shadow 0.14s ease, background 0.14s ease !important;
        margin: 0 !important;
        border-left: 1px solid rgba(255, 255, 255, 0.85) !important; /* NO side strip! */
    }
    div[class*="claim_row_"] button:hover, div[class*="turn_row_"] button:hover {
        transform: translateY(-2px) !important;
        box-shadow: var(--elevated-hover) !important;
        cursor: pointer !important;
    }
    div[class*="claim_row_crit"] button {
        background: #fff3f1 !important;
        border-color: #fecaca !important;
        color: #881c1c !important;
    }
    div[class*="claim_row_warn"] button {
        background: #fff8eb !important;
        border-color: #fde68a !important;
        color: #853e09 !important;
    }
    div[class*="claim_row_sel"] button {
        outline: 2px solid #0f766e !important;
        outline-offset: 2px !important;
        background: #e1f1ee !important;
    }

    /* Evidence Drawer Components (Elevated · Never Carved) */
    .dr-title {
        color: #334155 !important;
        font-size: 0.80rem !important;
        font-weight: 800 !important;
        letter-spacing: .10em !important;
        text-transform: uppercase !important;
        padding-bottom: 6px !important;
        border-bottom: 1px solid rgba(160, 172, 188, 0.25) !important;
        margin: 6px 0 10px 0 !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
    }
    .quote-box {
        background: var(--bg) !important;
        border: 1px solid rgba(255, 255, 255, 0.85) !important;
        border-radius: 16px !important;
        padding: 12px 16px !important;
        box-shadow: var(--elevated-pill) !important; /* Elevated · Never Carved */
        font-style: italic !important;
        line-height: 1.5 !important;
        color: var(--ink) !important;
        margin: 4px 0 12px 0 !important;
    }
    .alert-card {
        border-radius: 16px !important;
        padding: 12px 16px !important;
        box-shadow: var(--elevated-pill) !important; /* Elevated · Never Carved */
        border: 1px solid rgba(255, 255, 255, 0.8) !important;
        margin: 4px 0 12px 0 !important;
    }
    .alert-card.crit {
        background: #fff3f1 !important;
        color: #881c1c !important;
    }
    .alert-card.warn {
        background: #fff8eb !important;
        color: #853e09 !important;
    }
    .alert-card.ok {
        background: #e7f3ed !important;
        color: #1e5a39 !important;
    }

    /* Streamlit Tabs Styled as Elevated Switch Pills */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 10px !important;
        background: transparent !important;
        border-bottom: none !important;
        padding: 2px 0 12px 0 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        border-radius: 999px !important;
        padding: 7px 18px !important;
        background: var(--bg) !important;
        box-shadow: var(--elevated-pill) !important;
        border: 1px solid rgba(255, 255, 255, 0.85) !important;
        color: var(--muted) !important;
        font-weight: 650 !important;
        font-size: 0.80rem !important;
        transition: all 0.14s ease !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: var(--elevated-hover) !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
        color: #0f766e !important;
        border-color: #0f766e !important;
        background: #e1f1ee !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"],
    [data-testid="stTabs"] [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Streamlit Buttons (Slightly Elevated Pills) */
    .stButton > button, .stDownloadButton > button {
        min-height: 40px !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255, 255, 255, 0.85) !important;
        background: var(--bg) !important;
        color: var(--ink) !important;
        font-weight: 650 !important;
        font-size: 0.83rem !important;
        box-shadow: var(--elevated-pill) !important;
        transition: transform .14s ease, box-shadow .14s ease !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: var(--elevated-hover) !important;
        border-color: #9abdb7 !important;
        color: #0f625d !important;
    }
    button[kind="primary"] {
        background: #176e67 !important;
        color: white !important;
        border-color: #176e67 !important;
        box-shadow: 4px 4px 12px rgba(23, 110, 103, 0.28), -4px -4px 12px rgba(255, 255, 255, 0.85) !important;
    }
    button[kind="primary"]:hover {
        background: #125c56 !important;
        color: white !important;
        transform: translateY(-2px) !important;
    }

    /* Textareas and Inputs (Slightly Elevated · Never Carved) */
    [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input, [data-testid="stSelectbox"] [role="combobox"] {
        border: 1px solid rgba(255, 255, 255, 0.85) !important;
        border-radius: 16px !important;
        background: var(--bg) !important;
        color: var(--ink) !important;
        box-shadow: 3px 3px 8px rgba(160, 172, 188, 0.20), -3px -3px 8px rgba(255, 255, 255, 0.85) !important;
    }
    [data-testid="stCheckbox"] label {
        line-height: 1.5 !important;
        font-size: 0.86rem !important;
    }

    /* Auth Gate Card (Elevated Neumorphic Modal) */
    .st-key-auth_wrap {
        max-width: 1040px;
        margin: clamp(20px, 7vh, 76px) auto;
    }
    .st-key-auth_card {
        padding: clamp(24px, 5vw, 54px);
        border-radius: 28px;
        background: var(--bg);
        box-shadow: 12px 12px 28px rgba(160, 171, 185, .38), -12px -12px 28px rgba(255, 255, 255, .95);
        border: 1px solid rgba(255, 255, 255, .8);
    }
    .auth-eyebrow {
        color: #0f766e;
        font-size: .74rem;
        font-weight: 750;
        letter-spacing: .16em;
        text-transform: uppercase;
    }
    .auth-title {
        color: #172638;
        font-size: clamp(2rem, 4vw, 3.25rem);
        line-height: 1.05;
        letter-spacing: -.045em;
        font-weight: 760;
        margin: 14px 0;
    }
    .auth-subtitle {
        color: #536579;
        font-size: 1rem;
        line-height: 1.7;
        max-width: 42rem;
    }
    .auth-feature {
        padding: 16px 18px;
        border-radius: 16px;
        margin: 10px 0;
        color: #31485b;
        background: var(--bg);
        box-shadow: var(--elevated-pill); /* Elevated · Never Carved */
        border: 1px solid rgba(255, 255, 255, 0.7);
        line-height: 1.5;
    }
    .auth-note {
        font-size: .78rem;
        color: #647487;
        line-height: 1.6;
        padding-top: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# DEMO ACCESS GATE (MANUS AI ELEVATED MODAL)
# =============================================================================
if not st.session_state.get("local_demo_access", False):
    st.markdown("<style>[data-testid='stSidebar']{display:none!important}[data-testid='stAppViewContainer']{margin-left:0!important}</style>", unsafe_allow_html=True)
    with st.container(key="auth_wrap"):
        with st.container(key="auth_card"):
            left, right = st.columns([1.25, 1], gap="large")
            with left:
                st.markdown("<div class='auth-eyebrow'>Medscribe · Proof Mode</div><div class='auth-title'>A clearer path from conversation to note.</div><div class='auth-subtitle'>Review a locally generated SOAP draft alongside the exact conversation evidence behind it. Built for calm, focused clinician review.</div>", unsafe_allow_html=True)
                st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
                st.markdown("<div class='auth-feature'><strong>01 · Source-linked</strong><br/>Inspect the cited transcript wording for each statement.</div><div class='auth-feature'><strong>02 · Review-aware</strong><br/>Spot unsupported claims, uncertainty changes, and unassessed fields.</div><div class='auth-feature'><strong>03 · Local-first demo</strong><br/>Synthetic encounters and local adapters; 100% offline with zero cloud API dependencies.</div>", unsafe_allow_html=True)
            with right:
                st.markdown("### Open your local workspace")
                st.caption("Demo access · no account required")
                st.info("This prototype does not provide real authentication. Do not enter real patient information.", icon="🔒")
                clinician_label = st.text_input("Display name (optional)", placeholder="e.g. Dr. Morgan", key="demo_display_name")
                if st.button("Continue to demo workspace", type="primary", use_container_width=True, key="btn_demo_access"):
                    st.session_state.local_demo_access = True
                    st.session_state.demo_clinician_label = clinician_label.strip() or "Dr. Morgan"
                    st.rerun()
                st.markdown("<div class='auth-note'>Medscribe is an experimental documentation prototype, not a diagnostic system. All built-in cases are synthetic. Review every draft before export.</div>", unsafe_allow_html=True)
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

def apply_text(c, text: str):
    c.clinician_edited_statement = text.strip() or None
    c.clinician_reviewed = True
    st.session_state[edit_key(c)] = text.strip() or c.statement

def save_edit(c):
    apply_text(c, st.session_state.get(edit_key(c), c.statement))

def mark_reviewed(c):
    c.clinician_reviewed = True

all_claims = draft.all_claims()
review_n = sum(1 for c in all_claims if needs_review(c))
blank_n = len(draft.audit_summary.missing_fields)

def next_item():
    pending = [c for c in all_claims if needs_review(c)]
    if not pending:
        return
    cur = st.session_state.selected_claim
    ids = [c.claim_id for c in pending]
    nxt = pending[(ids.index(cur.claim_id) + 1) % len(pending)] if cur and cur.claim_id in ids else pending[0]
    select_claim(nxt)
    st.session_state.audit_filter = "review"

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

col_f1, col_f2, col_f3, col_f4 = st.columns(4, gap="small")
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

# =============================================================================
# WORKSPACE LAYOUT: PRIMARY SOAP CHART (LEFT) & EVIDENCE DRAWER (RIGHT)
# =============================================================================
col_note, col_drawer = st.columns([1.4, 1.0], gap="medium")

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
        badge = "🚨 [DISCREPANCY] "
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

# Left Column: Primary Note Pane
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

        st.markdown("<div style='margin-top:14px; border-top:1px solid rgba(160,172,188,0.2); padding-top:10px;'></div>", unsafe_allow_html=True)
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

# Right Column: Evidence & Resolution Drawer
with col_drawer:
    with st.container(key="drawer_pane"):
        tab_audit, tab_transcript = st.tabs(["⚡ Evidence & Resolution", "📜 Consultation Transcript"])
        
        with tab_audit:
            sel = st.session_state.selected_claim
            if sel is None:
                st.markdown("<div class='dr-title'><span>Evidence & Citation Audit</span></div>", unsafe_allow_html=True)
                st.markdown("<div class='fld-blank-row'>Select any statement row to inspect its transcript citation.</div>", unsafe_allow_html=True)
            else:
                refs = ", ".join(line_label(i, LINES) for i in sel.source_segment_ids) or "No source line"
                st.markdown(
                    f"""
                    <div class='dr-title'>
                        <span>Evidence & Citation Audit</span>
                        <span style='font-family:monospace; font-size:0.75rem; color:#0f766e; font-weight:700;'>[{sel.claim_id}] · {refs}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                # Verbatim excerpt
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
                            <div style='font-weight:750; font-size:0.88rem; margin-bottom:2px;'>⚠️ No Supporting Transcript Excerpt</div>
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
                            <div style='font-weight:750; font-size:0.88rem; margin-bottom:2px;'>✓ Verified Grounded Statement</div>
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
                            <div style='font-weight:750; font-size:0.88rem; margin-bottom:2px;'>⚠️ {html.escape(d['title'])}</div>
                            <div style='margin-bottom:4px;'>{html.escape(d['why'])}</div>
                            <div style='font-size:0.80rem;'><strong>Suggested:</strong> {html.escape(d['prompt'])}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
    
                # Physician Override Editor
                st.markdown("<div class='dr-title' style='margin-top:16px;'><span>Physician Override & Resolution</span></div>", unsafe_allow_html=True)
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
                    height=100,
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
                    <span style='font-family:monospace; font-size:0.75rem; color:#0f766e; font-weight:700;'>{len(transcript.segments)} Dialogue Turns</span>
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
                
                border_clr = "#0f766e" if is_hit else "rgba(255,255,255,0.85)"
                bg_clr = "#e1f1ee" if is_hit else "var(--bg)"
                badge_html = "<span style='font-size:0.68rem; background:#0f766e; color:#ffffff; padding:2px 7px; border-radius:4px; font-weight:700;'>● CITED IN ACTIVE CLAIM</span>" if is_hit else ""
                
                st.markdown(
                    f"""
                    <div style='padding:12px 16px; margin-bottom:8px; border-radius:16px; border:1px solid {border_clr}; background:{bg_clr}; box-shadow:var(--elevated-pill); font-size:0.86rem; line-height:1.5;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;'>
                            <span style='font-weight:750; font-size:0.72rem; color:var(--muted); text-transform:uppercase;'>{l_num} · {spk}</span>
                            {badge_html}
                        </div>
                        <div style='color:var(--ink);'>{html.escape(seg.text)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
