import html
import os
import re
import streamlit as st

from medscribe.schemas import (
    Transcript,
    SOAPNoteDraft,
    VerificationStatus,
    AuditFlagSeverity,
)
from medscribe.adapters.mock_adapter import DeterministicModelAdapter
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
    page_title="Medscribe · Clinical Documentation Proof Mode",
    page_icon="⚕",
    layout="wide",
    initial_sidebar_state="collapsed",
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

FIXTURE_PRESETS = {
    "Maria Santos · Hypertension follow-up": "encounter_01_hypertension_followup.json",
    "Ethan Ramirez · Pediatric cough": "encounter_02_pediatric_cough_edgecase.json",
    "Roberto Cruz · Routine checkup (audit case)": "encounter_03_adversarial_hallucination_trap.json",
    "Ginoong Juan Dela Cruz · Tagalog Consultation": "encounter_04_tagalog_consultation.json",
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
        return DeterministicModelAdapter(mode="adversarial")
    return DeterministicModelAdapter(mode="standard")

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

# State initialization
DEFAULT_ENGINE = "Deterministic Clinical Engine"
DEFAULT_PRESET = list(FIXTURE_PRESETS.keys())[0]

if "loaded_engine" not in st.session_state:
    st.session_state.loaded_engine = DEFAULT_ENGINE

if "draft_note" not in st.session_state or "active_transcript" not in st.session_state:
    load_preset_encounter(DEFAULT_PRESET, st.session_state.loaded_engine)

def on_preset_change():
    new_preset = st.session_state.main_ctl_preset
    st.session_state.last_preset_selection = new_preset
    load_preset_encounter(new_preset, st.session_state.get("main_ctl_engine", DEFAULT_ENGINE))

def on_engine_change():
    new_engine = st.session_state.main_ctl_engine
    curr_preset = st.session_state.get("loaded_preset", DEFAULT_PRESET)
    if curr_preset in FIXTURE_PRESETS:
        load_preset_encounter(curr_preset, new_engine)

# =============================================================================
# ELEVATED NEUMORPHIC DESIGN SYSTEM (NEVER CARVED · MATCHING REFERENCE DESIGN)
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
       - Complete eradication of sidebar and header clutter
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
    
    /* COMPLETE ERADICATION OF SIDEBAR & STREAMLIT HEADER CLUTTER */
    header[data-testid="stHeader"],
    [data-testid="stHeader"],
    [data-testid="stSidebar"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarNav"],
    footer,
    #MainMenu {
        display: none !important;
        height: 0 !important;
        width: 0 !important;
        visibility: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    [data-testid="stAppViewContainer"] {
        margin-left: 0 !important;
        padding-left: 0 !important;
    }
    
    .block-container {
        max-width: 1560px !important;
        padding-top: 1.4rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: clamp(1rem, 2.4vw, 2.6rem) !important;
        padding-right: clamp(1rem, 2.4vw, 2.6rem) !important;
        margin: 0 auto !important;
    }

    /* SLEEK ELEVATED TOP NAVIGATION BAR */
    .medscribe-navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--bg);
        border-radius: 22px;
        padding: 12px 22px;
        margin-bottom: 16px;
        box-shadow: var(--elevated-card);
        border: 1px solid rgba(255, 255, 255, 0.9);
    }
    .nav-left {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .nav-logo-badge {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border-radius: 12px;
        background: var(--bg);
        box-shadow: var(--elevated-pill);
        border: 1px solid rgba(255, 255, 255, 0.95);
    }
    .nav-brand-group {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .nav-brand-title {
        font-size: 1.25rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        color: var(--ink);
    }
    .nav-brand-tag {
        font-size: 0.66rem;
        font-weight: 750;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #0f766e;
        background: #e1f1ee;
        padding: 3px 9px;
        border-radius: 999px;
        box-shadow: var(--elevated-pill);
        border: 1px solid rgba(255, 255, 255, 0.85);
    }
    .nav-status-group {
        display: flex;
        align-items: center;
        gap: 10px;
        background: var(--bg);
        padding: 7px 18px;
        border-radius: 999px;
        box-shadow: var(--elevated-pill);
        border: 1px solid rgba(255, 255, 255, 0.88);
        font-size: 0.78rem;
        color: var(--muted);
        font-weight: 600;
    }
    .status-pill-sep {
        color: rgba(160, 172, 188, 0.6);
    }
    .status-pill-item.clinician {
        color: var(--ink);
        font-weight: 700;
    }

    /* CONSULTATION SOURCE WORKSTATION */
    .st-key-source_workspace {
        background: var(--bg) !important;
        border: 1px solid rgba(255, 255, 255, 0.85) !important;
        border-radius: 22px !important;
        padding: 18px 22px 16px !important;
        box-shadow: var(--elevated-card) !important;
        margin-bottom: 16px !important;
    }
    .source-panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .source-panel-title {
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        color: #334155;
        text-transform: uppercase;
    }
    .source-panel-sub {
        font-size: 0.74rem;
        color: var(--muted);
    }

    [data-testid="stFileUploaderDropzone"] {
        background: var(--bg) !important;
        border: 1.5px dashed rgba(160, 172, 188, 0.45) !important;
        border-radius: 16px !important;
        box-shadow: var(--elevated-pill) !important;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: #0f766e !important;
    }
    
    /* MAIN ELEVATED CONTAINERS */
    .st-key-note_pane, .st-key-drawer_pane {
        background: var(--bg) !important;
        border: 1px solid rgba(255, 255, 255, 0.8) !important;
        border-radius: 24px !important;
        padding: 22px 24px !important;
        box-shadow: var(--elevated-card) !important;
    }
    .st-key-drawer_pane {
        position: sticky !important;
        top: 14px !important;
        max-height: calc(100vh - 28px) !important;
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
        margin: 0 0 14px 0;
        padding: 13px 22px;
        background: var(--bg);
        border-radius: 20px;
        box-shadow: var(--elevated-pill);
        border: 1px solid rgba(255, 255, 255, 0.88);
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
        gap: 12px !important;
        background: transparent !important;
        border-bottom: none !important;
        padding: 4px 0 14px 0 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        border-radius: 999px !important;
        padding: 8px 20px !important;
        background: var(--bg) !important;
        box-shadow: var(--elevated-pill) !important;
        border: 1px solid rgba(255, 255, 255, 0.9) !important;
        color: var(--muted) !important;
        font-weight: 650 !important;
        font-size: 0.82rem !important;
        transition: all 0.14s ease !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: var(--elevated-hover) !important;
        color: #0f766e !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
        color: #0f766e !important;
        border-color: rgba(15, 118, 110, 0.3) !important;
        background: #e1f1ee !important;
        font-weight: 750 !important;
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

    /* FOOTER */
    .medscribe-footer {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 12px;
        font-size: 0.74rem;
        color: var(--muted);
        margin-top: 24px;
        padding-top: 14px;
        border-top: 1px solid rgba(160, 172, 188, 0.2);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# TOP NAVIGATION BAR (ELEVATED NEUMORPHIC HEADER WITH CUSTOM SVG MEDICAL LOGO)
# =============================================================================
current_engine_name = st.session_state.get("loaded_engine", DEFAULT_ENGINE)

navbar_html = f"""
<div class='medscribe-navbar'>
    <div class='nav-left'>
        <div class='nav-logo-badge'>
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="32" height="32" rx="9" fill="#e1f1ee"/>
              <path d="M13 7h6v6h6v6h-6v6h-6v-6H7v-6h6V7z" fill="#0f766e" fill-opacity="0.22"/>
              <path d="M5 16h6l2-4 3 8 2.5-6 1.5 2H27" stroke="#0f766e" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </div>
        <div class='nav-brand-group'>
            <span class='nav-brand-title'>Medscribe</span>
            <span class='nav-brand-tag'>PROOF MODE</span>
        </div>
    </div>
    <div class='nav-status-group'>
        <span class='status-pill-item'>🛡️ 100% Offline</span>
        <span class='status-pill-sep'>•</span>
        <span class='status-pill-item'>⚡ Whisper Medium</span>
        <span class='status-pill-sep'>•</span>
        <span class='status-pill-item clinician'>⚕ Dr. Morgan (Attending)</span>
    </div>
</div>
"""
st.markdown(navbar_html, unsafe_allow_html=True)

# =============================================================================
# CONSULTATION SOURCE WORKSTATION (ALL FEATURES IN ONE PAGE)
# =============================================================================
with st.container(key="source_workspace"):
    st.markdown(
        """
        <div class='source-panel-header'>
            <span class='source-panel-title'>Consultation Source Workstation</span>
            <span class='source-panel-sub'>Upload consultation audio (Whisper Medium), switch clinical encounters, or enter direct dialogue</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    src_tab_audio, src_tab_enc, src_tab_custom = st.tabs([
        "📁 Upload Audio Recording (Whisper Medium)",
        "📋 Clinical Encounters Library",
        "✍️ Direct Consultation Input",
    ])
    
    with src_tab_audio:
        c_up1, c_up2, c_up3 = st.columns([1.5, 1.2, 1.3], gap="medium")
        with c_up1:
            uploaded_audio = st.file_uploader(
                "Upload Consultation Audio",
                type=["wav", "mp3", "m4a", "ogg"],
                key="main_file_audio",
                help="Supported audio formats: WAV, MP3, M4A, OGG. Speech recognition runs 100% on-device on CPU.",
            )
        with c_up2:
            c_lang = st.selectbox(
                "Spoken Language",
                ["Tagalog (Filipino - tl)", "Taglish / Auto-Detect", "English (en)"],
                index=0,
                key="main_audio_lang",
            )
            c_model = st.selectbox(
                "Whisper STT Model",
                ["Medium (Highest Accuracy · 769M)", "Small (Fast & Accurate · 244M)", "Base (140M)"],
                index=0,
                key="main_whisper_model",
            )
        with c_up3:
            if uploaded_audio is not None:
                st.audio(uploaded_audio)
                if st.button("Transcribe Audio & Generate Draft", type="primary", key="main_btn_transcribe", use_container_width=True):
                    with st.spinner("Transcribing consultation audio locally via Whisper Medium..."):
                        raw_bytes = uploaded_audio.getvalue()
                        lang_code = "tl" if "Tagalog" in c_lang else ("en" if "English" in c_lang else None)
                        model_code = "medium" if "Medium" in c_model else ("small" if "Small" in c_model else "base")
                        txt = transcribe_audio_bytes(raw_bytes, language=lang_code, model_size=model_code)
                        pipeline = MedscribePipeline(adapter=get_adapter(current_engine_name))
                        new_t = pipeline.parse_raw_text_to_transcript(txt, encounter_id="ENC-UPLOAD-001", patient_id="PT-UPLOAD-8812")
                        new_draft = pipeline.process_encounter(new_t)
                        st.session_state.active_transcript = new_t
                        st.session_state.draft_note = new_draft
                        st.session_state.loaded_preset = "Uploaded Audio Consultation"
                        st.session_state.transcribed_audio_text = txt
                        def_claim = get_highest_priority_claim(new_draft)
                        st.session_state.selected_claim = def_claim
                        st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
                        st.rerun()
            else:
                st.caption("Upload consultation audio to run on-device transcription. Whisper Medium delivers high accuracy for Tagalog, English, and Taglish clinical conversations.")

    with src_tab_enc:
        c_enc1, c_enc2 = st.columns([1.5, 1.5], gap="medium")
        with c_enc1:
            preset_options = list(FIXTURE_PRESETS.keys())
            curr_preset = st.session_state.get("loaded_preset", preset_options[0])
            if curr_preset not in preset_options:
                preset_options.append(curr_preset)
            idx_preset = preset_options.index(curr_preset) if curr_preset in preset_options else 0
            st.selectbox(
                "Select Clinical Encounter",
                preset_options,
                index=idx_preset,
                key="main_ctl_preset",
                on_change=on_preset_change,
                help="Select clinical consultation case to audit.",
            )
        with c_enc2:
            engine_options = (
                ["Deterministic Clinical Engine", "Local Ollama (Active)", "Adversarial Test Mode"]
                if ollama_online else ["Deterministic Clinical Engine", "Adversarial Test Mode"]
            )
            curr_engine = st.session_state.get("loaded_engine", engine_options[0])
            idx_engine = engine_options.index(curr_engine) if curr_engine in engine_options else 0
            st.selectbox(
                "Inference Engine",
                engine_options,
                index=idx_engine,
                key="main_ctl_engine",
                on_change=on_engine_change,
                help="On-device inference pipeline ensuring 100% offline privacy.",
            )

    with src_tab_custom:
        c_c1, c_c2 = st.columns([1, 2], gap="medium")
        with c_c1:
            cu_enc = st.text_input("Encounter Code", value="ENC-CLINIC-001", key="main_cu_enc")
            cu_pat = st.text_input("Patient Identifier", value="PT-60291", key="main_cu_pat")
        with c_c2:
            cu_txt = st.text_area(
                "Verbatim Dialogue Turns (e.g. Clinician: ... / Patient: ...)",
                height=90,
                key="main_cu_txt",
                placeholder="Clinician: Magandang umaga, kumusta po kayo ngayon?\nPatient: Masakit po ang ulo ko nitong nakaraang tatlong araw.",
            )
            if st.button("Generate Verified SOAP Draft", type="primary", key="main_btn_generate", use_container_width=True):
                if cu_txt.strip():
                    pipeline = MedscribePipeline(adapter=get_adapter(current_engine_name))
                    new_t = pipeline.parse_raw_text_to_transcript(cu_txt, encounter_id=cu_enc, patient_id=cu_pat)
                    new_draft = pipeline.process_encounter(new_t)
                    st.session_state.active_transcript = new_t
                    st.session_state.draft_note = new_draft
                    st.session_state.loaded_preset = "Custom Consultation"
                    def_claim = get_highest_priority_claim(new_draft)
                    st.session_state.selected_claim = def_claim
                    st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
                    st.rerun()

draft: SOAPNoteDraft = st.session_state.draft_note
transcript: Transcript = st.session_state.active_transcript
LINES = line_map(transcript)

# Auto-select if selected_claim became None or uninitialized
if st.session_state.get("selected_claim") is None:
    def_claim = get_highest_priority_claim(draft)
    st.session_state.selected_claim = def_claim
    st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []

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
clean_encounter_code = re.sub(r"ENC-SYN-", "ENC-", transcript.encounter_id)
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
            <span class='meta'>• Date: {html.escape(transcript.encounter_date)} • ID: {html.escape(clean_encounter_code)}</span>
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

# Subtle footer
st.markdown(
    """
    <div class='medscribe-footer'>
        <span>⚕ Medscribe Local: Proof Mode · 100% On-Device CPU Inference · Zero Cloud API Dependencies</span>
        <span>•</span>
        <span>Clinical documentation decision support · Clinician verification required before export</span>
    </div>
    """,
    unsafe_allow_html=True,
)
