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
    initial_sidebar_state="collapsed",
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

FIXTURE_PRESETS = {
    "Maria Santos · Hypertension Follow-up": "encounter_01_hypertension_followup.json",
    "Ethan Ramirez · Pediatric Cough (Edge Case)": "encounter_02_pediatric_cough_edgecase.json",
    "Roberto Cruz · Routine Checkup (Audit Trap)": "encounter_03_adversarial_hallucination_trap.json",
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
    
    def_claim = get_highest_priority_claim(draft)
    st.session_state.selected_claim = def_claim
    st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []

# =============================================================================
# ENTERPRISE CLINICAL DESIGN SYSTEM (CSS)
# =============================================================================
st.markdown(
    """
    <style>
    /* Clean Minimalist Clinical Design System */
    :root {
        --canvas-bg: #F8FAFC;
        --card-bg: #FFFFFF;
        --ink-primary: #0F172A;
        --ink-secondary: #334155;
        --ink-muted: #64748B;
        --border-color: #E2E8F0;
        --brand-teal: #0F766E;
        --brand-teal-light: #F0FDFA;
        --brand-teal-hover: #115E59;
        
        --color-crit-bg: #FFF1F2;
        --color-crit-border: #FECACA;
        --color-crit-text: #991B1B;
        
        --color-warn-bg: #FFFBEB;
        --color-warn-border: #FDE68A;
        --color-warn-text: #92400E;
        
        --color-ok-bg: #ECFDF5;
        --color-ok-border: #A7F3D0;
        --color-ok-text: #065F46;
    }
    
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background-color: var(--canvas-bg) !important;
        color: var(--ink-primary) !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }
    
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer {
        display: none !important;
    }
    
    .block-container {
        padding: 1.2rem 2rem 3rem 2rem !important;
        max-width: 1680px !important;
    }
    
    /* Top Bar Branding */
    .top-navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 14px 22px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
    }
    .brand-title {
        font-size: 1.25rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: var(--ink-primary);
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .brand-badge {
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        background: #CCFBF1;
        color: #0F766E;
        padding: 3px 8px;
        border-radius: 4px;
        border: 1px solid #99F6E4;
    }
    .brand-sub {
        font-size: 0.82rem;
        color: var(--ink-muted);
        margin-top: 2px;
    }
    .user-pill {
        display: flex;
        align-items: center;
        gap: 8px;
        background: #F1F5F9;
        border: 1px solid var(--border-color);
        padding: 6px 14px;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        color: var(--ink-secondary);
    }

    /* Encounter Source Selector Card */
    .source-selector-card {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
    }

    /* Patient Header Banner */
    .patient-banner {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 14px 20px;
        margin-bottom: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02);
    }
    .patient-name {
        font-size: 1.15rem;
        font-weight: 750;
        color: var(--ink-primary);
        letter-spacing: -0.01em;
    }
    .patient-meta {
        font-size: 0.82rem;
        color: var(--ink-muted);
        margin-left: 12px;
    }
    .status-badge-crit {
        background: var(--color-crit-bg);
        border: 1px solid var(--color-crit-border);
        color: var(--color-crit-text);
        font-size: 0.78rem;
        font-weight: 700;
        padding: 5px 12px;
        border-radius: 6px;
        letter-spacing: 0.02em;
    }
    .status-badge-ok {
        background: var(--color-ok-bg);
        border: 1px solid var(--color-ok-border);
        color: var(--color-ok-text);
        font-size: 0.78rem;
        font-weight: 700;
        padding: 5px 12px;
        border-radius: 6px;
        letter-spacing: 0.02em;
    }

    /* Primary Note & Drawer Containers */
    .st-key-note_pane, .st-key-drawer_pane {
        background: var(--card-bg) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        padding: 22px 24px !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04) !important;
    }

    /* Section Headings */
    .soap-sec-title {
        font-size: 0.86rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #0F766E;
        padding-bottom: 6px;
        border-bottom: 2px solid #E2E8F0;
        margin: 20px 0 12px 0;
    }
    .soap-field-title {
        font-size: 0.82rem;
        font-weight: 700;
        color: var(--ink-muted);
        margin: 12px 0 6px 0;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .fld-blank-notice {
        font-size: 0.84rem;
        color: var(--ink-muted);
        font-style: italic;
        padding: 6px 10px;
        background: #F8FAFC;
        border: 1px dashed #CBD5E1;
        border-radius: 6px;
        margin-bottom: 6px;
    }

    /* Crisp Clinical Claim Rows */
    div[class*="claim_row_"] button {
        background: #FFFFFF !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
        padding: 10px 14px !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        color: var(--ink-primary) !important;
        line-height: 1.5 !important;
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        text-align: left !important;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03) !important;
        transition: border-color 0.12s ease, background 0.12s ease !important;
        margin-bottom: 6px !important;
    }
    div[class*="claim_row_"] button:hover {
        background: #F8FAFC !important;
        border-color: #94A3B8 !important;
        cursor: pointer !important;
    }
    div[class*="claim_row_crit"] button {
        background: var(--color-crit-bg) !important;
        border-color: var(--color-crit-border) !important;
        color: var(--color-crit-text) !important;
    }
    div[class*="claim_row_crit"] button:hover {
        background: #FEE2E2 !important;
        border-color: #F87171 !important;
    }
    div[class*="claim_row_warn"] button {
        background: var(--color-warn-bg) !important;
        border-color: var(--color-warn-border) !important;
        color: var(--color-warn-text) !important;
    }
    div[class*="claim_row_warn"] button:hover {
        background: #FEF3C7 !important;
        border-color: #F59E0B !important;
    }
    div[class*="claim_row_sel"] button {
        border: 2px solid var(--brand-teal) !important;
        background: var(--brand-teal-light) !important;
    }

    /* Evidence Drawer Styling */
    .dr-heading {
        font-size: 0.84rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--ink-muted);
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border-color);
        margin-bottom: 12px;
    }
    .quote-box {
        background: #F8FAFC;
        border: 1px solid var(--border-color);
        border-left: 3px solid var(--brand-teal);
        border-radius: 4px;
        padding: 11px 15px;
        font-size: 0.90rem;
        font-style: italic;
        color: #1E293B;
        line-height: 1.55;
        margin: 6px 0 14px 0;
    }
    .alert-card {
        border-radius: 6px;
        padding: 12px 14px;
        margin-bottom: 12px;
        font-size: 0.86rem;
        line-height: 1.5;
        border: 1px solid transparent;
    }
    .alert-card.crit {
        background: var(--color-crit-bg);
        border-color: var(--color-crit-border);
        color: var(--color-crit-text);
    }
    .alert-card.warn {
        background: var(--color-warn-bg);
        border-color: var(--color-warn-border);
        color: var(--color-warn-text);
    }
    .alert-card.ok {
        background: var(--color-ok-bg);
        border-color: var(--color-ok-border);
        color: var(--color-ok-text);
    }
    .alert-card .card-head {
        font-weight: 750;
        font-size: 0.88rem;
        margin-bottom: 4px;
    }

    /* Professional Buttons */
    .stButton > button, .stDownloadButton > button {
        min-height: 38px !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 0.84rem !important;
        box-shadow: 0 1px 2px 0 rgba(0,0,0,0.04) !important;
        transition: all 0.12s ease !important;
    }
    button[kind="primary"] {
        background: var(--brand-teal) !important;
        border-color: var(--brand-teal) !important;
        color: #FFFFFF !important;
    }
    button[kind="primary"]:hover {
        background: var(--brand-teal-hover) !important;
        border-color: var(--brand-teal-hover) !important;
    }
    button[kind="secondary"] {
        background: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        color: #334155 !important;
    }
    button[kind="secondary"]:hover {
        background: #F8FAFC !important;
        border-color: #94A3B8 !important;
        color: var(--ink-primary) !important;
    }

    /* Inputs & Selectboxes */
    [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input, [data-testid="stSelectbox"] [role="combobox"] {
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
        background: #FFFFFF !important;
        color: var(--ink-primary) !important;
        font-size: 0.86rem !important;
    }
    [data-testid="stTextArea"] textarea:focus, [data-testid="stTextInput"] input:focus {
        border-color: var(--brand-teal) !important;
        box-shadow: 0 0 0 1px var(--brand-teal) !important;
    }

    /* Responsive adjustments */
    @media (max-width: 960px) {
        .block-container { padding: 1rem 1rem 2rem !important; }
        .top-navbar { flex-direction: column; align-items: flex-start; gap: 10px; }
        .patient-banner { flex-direction: column; align-items: flex-start; gap: 8px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# TOP HEADER BAR
# =============================================================================
st.markdown(
    """
    <div class='top-navbar'>
        <div>
            <div class='brand-title'>
                <span>⚕ Medscribe Local</span>
                <span class='brand-badge'>Proof Mode</span>
            </div>
            <div class='brand-sub'>Offline-First Clinical Documentation Verification · Decision Support Workstation</div>
        </div>
        <div class='user-pill'>
            <span>👨‍⚕️ Dr. Morgan · Attending Physician</span>
            <span style='color:#0F766E;'>● Local Engine Online</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# ENCOUNTER & WORKSPACE CONTROLS
# =============================================================================
with st.container():
    st.markdown("<div class='source-selector-card'>", unsafe_allow_html=True)
    c_src, c_eng = st.columns([2.2, 1], gap="medium")
    
    with c_src:
        encounter_tab = st.radio(
            "Consultation Source",
            ["📋 Synthetic Presets", "📁 Upload Audio File (.wav, .mp3)", "📝 Custom Dialogue Transcript"],
            horizontal=True,
            key="ctl_encounter_mode",
            label_visibility="collapsed",
        )
    with c_eng:
        engine_options = (
            ["Local Ollama (Active)", "Deterministic Clinical Adapter", "Adversarial Test Mode"]
            if ollama_online else ["Deterministic Clinical Adapter", "Adversarial Test Mode"]
        )
        selected_engine = st.selectbox(
            "Inference Mode",
            engine_options,
            key="ctl_engine_select",
            label_visibility="collapsed",
            help="100% on-device inference for clinical privacy.",
        )
        
    st.markdown("</div>", unsafe_allow_html=True)

# State initialization
if "draft_note" not in st.session_state:
    load_preset_encounter(list(FIXTURE_PRESETS.keys())[0], selected_engine)

# =============================================================================
# TAB 1: SYNTHETIC PRESETS
# =============================================================================
if encounter_tab == "📋 Synthetic Presets":
    col_p, _ = st.columns([2, 1])
    with col_p:
        preset_list = list(FIXTURE_PRESETS.keys())
        active_preset = st.session_state.get("loaded_preset", preset_list[0])
        idx = preset_list.index(active_preset) if active_preset in preset_list else 0
        chosen_preset = st.selectbox(
            "Select Clinical Encounter Case",
            preset_list,
            index=idx,
            key="ctl_preset_select",
        )
        if chosen_preset != st.session_state.get("loaded_preset"):
            load_preset_encounter(chosen_preset, selected_engine)
            st.rerun()

# =============================================================================
# TAB 2: UPLOAD AUDIO FILE (WHISPER LOCAL STT)
# =============================================================================
elif encounter_tab == "📁 Upload Audio File (.wav, .mp3)":
    st.markdown(
        """
        <div style='background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:18px 20px; margin-bottom:14px;'>
            <div style='font-size:0.88rem; font-weight:700; color:#0F766E; margin-bottom:4px;'>📁 On-Device Audio Consultation Processor</div>
            <div style='font-size:0.82rem; color:#64748B; margin-bottom:12px;'>Upload a consultation audio file. Whisper speech-to-text processes audio 100% locally on CPU with zero internet connection or telemetry.</div>
        """,
        unsafe_allow_html=True,
    )
    
    col_up, col_opts = st.columns([1.5, 1], gap="medium")
    with col_up:
        uploaded_file = st.file_uploader(
            "Upload Consultation Recording",
            type=["wav", "mp3", "m4a", "ogg"],
            key="ctl_file_audio_upload",
            label_visibility="collapsed",
        )
    with col_opts:
        chosen_lang = st.selectbox(
            "Audio Language",
            ["Tagalog (Filipino - tl)", "Taglish / Auto-Detect", "English (en)"],
            index=0,
            key="ctl_whisper_lang",
        )
        chosen_model = st.selectbox(
            "Whisper Model Engine",
            ["Medium (Highest Accuracy · 769M)", "Small (Fast & Accurate · 244M)", "Base (Fast · 140M)"],
            index=0,
            key="ctl_whisper_model",
            help="Medium model provides maximum accuracy and vocabulary for clinical Tagalog and English.",
        )

    if uploaded_file is not None:
        audio_bytes = uploaded_file.getvalue()
        st.audio(audio_bytes)
        
        if st.button("🎙️ Transcribe Audio & Generate Audited SOAP Note", type="primary", use_container_width=True, key="btn_run_audio_transcribe"):
            with st.spinner("Transcribing consultation audio locally via Whisper on CPU..."):
                lang_code = "tl" if "Tagalog" in chosen_lang else ("en" if "English" in chosen_lang else None)
                model_code = "medium" if "Medium" in chosen_model else ("small" if "Small" in chosen_model else "base")
                transcribed_text = transcribe_audio_bytes(audio_bytes, language=lang_code, model_size=model_code)
                
                pipeline = MedscribePipeline(adapter=get_adapter(selected_engine))
                new_transcript = pipeline.parse_raw_text_to_transcript(
                    transcribed_text,
                    encounter_id="ENC-UPLOAD-AUDIO",
                    patient_id="SYN-PAT-UPLOADED"
                )
                new_draft = pipeline.process_encounter(new_transcript)
                
                st.session_state.active_transcript = new_transcript
                st.session_state.draft_note = new_draft
                st.session_state.loaded_preset = "Uploaded Audio Consultation"
                st.session_state.transcribed_audio_text = transcribed_text
                
                def_claim = get_highest_priority_claim(new_draft)
                st.session_state.selected_claim = def_claim
                st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
                st.success("Audio transcribed and SOAP draft generated!")
                st.rerun()

    if st.session_state.get("transcribed_audio_text"):
        st.markdown("<div style='margin-top:14px; font-weight:700; font-size:0.84rem; color:#0F766E;'>📝 Verbatim Dialogue Turns (Editable)</div>", unsafe_allow_html=True)
        edited_text = st.text_area(
            "Transcript Turns",
            value=st.session_state.transcribed_audio_text,
            height=130,
            key="area_edit_transcribed",
            label_visibility="collapsed",
        )
        if st.button("🔄 Re-process SOAP Note with Edited Dialogue", type="secondary", key="btn_reprocess_edited_txt", use_container_width=True):
            pipeline = MedscribePipeline(adapter=get_adapter(selected_engine))
            new_t = pipeline.parse_raw_text_to_transcript(
                edited_text,
                encounter_id="ENC-UPLOAD-AUDIO",
                patient_id="SYN-PAT-UPLOADED"
            )
            new_d = pipeline.process_encounter(new_t)
            st.session_state.active_transcript = new_t
            st.session_state.draft_note = new_d
            st.session_state.transcribed_audio_text = edited_text
            def_claim = get_highest_priority_claim(new_d)
            st.session_state.selected_claim = def_claim
            st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
            st.success("SOAP note re-processed with edited dialogue!")
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
# TAB 3: CUSTOM DIALOGUE TRANSCRIPT
# =============================================================================
elif encounter_tab == "📝 Custom Dialogue Transcript":
    st.markdown(
        """
        <div style='background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:18px 20px; margin-bottom:14px;'>
            <div style='font-size:0.88rem; font-weight:700; color:#0F766E; margin-bottom:4px;'>📝 Custom Consultation Dialogue Generator</div>
            <div style='font-size:0.82rem; color:#64748B; margin-bottom:12px;'>Paste arbitrary dialogue lines (e.g. <code>Clinician: ... Patient: ...</code>) to test evidence linking on custom text.</div>
        """,
        unsafe_allow_html=True,
    )
    col_c1, col_c2 = st.columns(2)
    c_enc = col_c1.text_input("Encounter Identifier", value="ENC-CUSTOM-001", key="in_cu_enc")
    c_pat = col_c2.text_input("Synthetic Patient Identifier", value="SYN-PAT-CUSTOM", key="in_cu_pat")
    c_txt = st.text_area(
        "Consultation Dialogue Turns",
        height=140,
        placeholder="Clinician [00:00]: Hello Mr. Cruz, how have you been feeling?\nPatient [00:05]: Masakit po ang ulo ko nitong mga nakaraang araw.",
        key="in_cu_txt",
    )
    if st.button("Generate Audited SOAP Note from Custom Dialogue", type="primary", use_container_width=True, key="btn_gen_custom"):
        if c_txt.strip():
            pipeline = MedscribePipeline(adapter=get_adapter(selected_engine))
            new_t = pipeline.parse_raw_text_to_transcript(c_txt, encounter_id=c_enc, patient_id=c_pat)
            new_d = pipeline.process_encounter(new_t)
            st.session_state.active_transcript = new_t
            st.session_state.draft_note = new_d
            st.session_state.loaded_preset = "Custom Encounter"
            def_claim = get_highest_priority_claim(new_d)
            st.session_state.selected_claim = def_claim
            st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# Fetch active encounter records
draft: SOAPNoteDraft = st.session_state.draft_note
transcript: Transcript = st.session_state.active_transcript
LINES = line_map(transcript)

# Audit state helpers
def needs_review(c) -> bool:
    if c.clinician_reviewed:
        return False
    return c.verification_status != VerificationStatus.SUPPORTED or bool(c.audit_flags)

def is_critical(c) -> bool:
    return (c.verification_status != VerificationStatus.SUPPORTED
            or any(f.severity == AuditFlagSeverity.CRITICAL for f in c.audit_flags))

def edit_key(c) -> str:
    return f"edit_val_{c.claim_id}"

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

# Auto-select fallback
if st.session_state.get("selected_claim") is None and all_claims:
    def_c = get_highest_priority_claim(draft)
    st.session_state.selected_claim = def_c
    st.session_state.highlighted_seg_ids = list(def_c.source_segment_ids) if def_c else []

# =============================================================================
# PATIENT CONTEXT BANNER & QUICK FILTER BAR
# =============================================================================
patient_name = html.escape(patient_display(transcript.patient_synthetic_id))
status_badge_html = (
    f"<span class='status-badge-crit'>🚨 {review_n} Item{'s' if review_n != 1 else ''} Require Review</span>"
    if review_n > 0 else
    "<span class='status-badge-ok'>✓ All Items Verified Grounded</span>"
)

st.markdown(
    f"""
    <div class='patient-banner'>
        <div>
            <span class='patient-name'>{patient_name}</span>
            <span class='patient-meta'>• Encounter ID: {html.escape(transcript.encounter_id)} • Date: {html.escape(transcript.encounter_date)}</span>
        </div>
        <div>
            {status_badge_html}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Filter Controls
if "audit_filter" not in st.session_state:
    st.session_state.audit_filter = "all"
active_filter = st.session_state.audit_filter

def set_filter(k: str):
    st.session_state.audit_filter = k

c_f1, c_f2, c_f3, c_f4 = st.columns([1.2, 1.4, 1.4, 1.8], gap="small")
c_f1.button(
    f"All Statements ({len(all_claims)})",
    key="chip_all",
    on_click=set_filter,
    args=("all",),
    use_container_width=True,
    type="primary" if active_filter == "all" else "secondary",
)
c_f2.button(
    f"Needs Review ({review_n})",
    key="chip_review",
    on_click=set_filter,
    args=("review",),
    use_container_width=True,
    type="primary" if active_filter == "review" else "secondary",
)
c_f3.button(
    f"Unassessed Fields ({blank_n})",
    key="chip_unassessed",
    on_click=set_filter,
    args=("unassessed",),
    use_container_width=True,
    type="primary" if active_filter == "unassessed" else "secondary",
)
c_f4.button(
    "Next Flagged Item ➔",
    on_click=next_item,
    disabled=review_n == 0,
    key="btn_next_review",
    use_container_width=True,
    type="primary" if review_n > 0 else "secondary",
)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# =============================================================================
# WORKSPACE: PRIMARY NOTE CANVAS (LEFT) & EVIDENCE DRAWER (RIGHT)
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

def render_claim_card(c):
    sel = st.session_state.selected_claim
    is_sel = sel and sel.claim_id == c.claim_id
    
    crit = is_critical(c)
    rev = needs_review(c)
    
    status_type = "crit" if (crit and rev) else "warn" if rev else "ok"
    sel_type = "sel" if is_sel else "norm"
    container_key = f"claim_row_{status_type}_{sel_type}_{c.claim_id}"
    
    if crit and rev:
        badge = "🚨 [DISCREPANCY] "
    elif rev:
        badge = "⚠️ [NEEDS REVIEW] "
    elif c.clinician_edited_statement:
        badge = "✎ [MODIFIED] "
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
            help="Click to inspect verbatim transcript citation and audit findings",
        )

# Left Column: Primary Clinical Note
with col_note:
    with st.container(key="note_pane"):
        if active_filter == "unassessed":
            st.markdown("<div class='soap-sec-title'>Unassessed Clinical Parameters</div>", unsafe_allow_html=True)
            if not draft.audit_summary.missing_fields:
                st.markdown("<div class='fld-blank-notice'>Every standard clinical field was addressed during this encounter.</div>", unsafe_allow_html=True)
            for raw in draft.audit_summary.missing_fields:
                st.markdown(
                    f"<div class='fld-blank-notice'><strong>{html.escape(unassessed_label(raw))}</strong>: {UNASSESSED_COPY}</div>",
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
                st.markdown(f"<div class='soap-sec-title'>{sec_title}</div>", unsafe_allow_html=True)
                for f_name, claims in filtered_fields:
                    if active_filter == "review" and not claims:
                        continue
                    st.markdown(f"<div class='soap-field-title'>{f_name}</div>", unsafe_allow_html=True)
                    if not claims:
                        st.markdown(
                            f"<div class='fld-blank-notice'>— Not assessed in consultation (left unpopulated)</div>",
                            unsafe_allow_html=True,
                        )
                    for c in claims:
                        render_claim_card(c)
            if not shown_any:
                st.markdown("<div class='fld-blank-notice'>No items require review in this view.</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        sign_off = st.checkbox(
            "I attest that I have verified this draft against the consultation record.",
            value=draft.clinician_review_confirmed,
            key="chk_attest_note",
        )
        draft.clinician_review_confirmed = sign_off
        if review_n and sign_off:
            st.caption(f"Notice: {review_n} statement(s) remain flagged and will be exported with audit notice.")
            
        st.download_button(
            "Export Attested Clinical Note (.txt)" if sign_off else "Export Restricted (Review Attestation Required)",
            data=MedscribePipeline().export_note_text(draft),
            file_name=f"medscribe_{draft.encounter_id}_{'attested' if sign_off else 'draft'}.txt",
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
                st.markdown("<div class='dr-heading'><span>Evidence & Citation Audit</span></div>", unsafe_allow_html=True)
                st.markdown("<div class='fld-blank-notice'>Select any statement row to inspect its transcript citation.</div>", unsafe_allow_html=True)
            else:
                refs = ", ".join(line_label(i, LINES) for i in sel.source_segment_ids) or "No source line"
                st.markdown(
                    f"""
                    <div class='dr-heading'>
                        <span>Evidence & Citation Audit</span>
                        <span style='font-family:monospace; font-size:0.76rem; color:#0F766E; font-weight:700;'>[{sel.claim_id}] · {refs}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                # Verbatim excerpt
                if sel.source_exact_quote:
                    st.markdown(
                        f"""
                        <div style='font-size:0.74rem; font-weight:700; color:#64748B; text-transform:uppercase;'>Verbatim Consultation Excerpt:</div>
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
                    
                # Audit Guidance Cards
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
                            <div style='font-size:0.80rem;'><strong>Suggested Action:</strong> {html.escape(d['prompt'])}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
    
                # Physician Override Editor
                st.markdown("<div class='dr-heading' style='margin-top:16px;'><span>Physician Override & Resolution</span></div>", unsafe_allow_html=True)
                if sel.source_exact_quote and (sel.clinician_edited_statement or sel.statement) != sel.source_exact_quote:
                    st.caption(f"Suggested verbatim wording: “{html.escape(sel.source_exact_quote)}”")
                    st.button(
                        "Accept Verbatim Transcript Wording",
                        on_click=apply_text,
                        args=(sel, sel.source_exact_quote),
                        type="primary",
                        key="btn_accept_verbatim",
                        use_container_width=True,
                    )
                    
                curr_txt = sel.clinician_edited_statement or sel.statement
                if edit_key(sel) not in st.session_state:
                    st.session_state[edit_key(sel)] = curr_txt
                    
                st.text_area(
                    "Statement in Note",
                    key=edit_key(sel),
                    height=100,
                    help="Edit this statement directly without truncation.",
                )
                
                col_s1, col_s2 = st.columns(2)
                col_s1.button("Save Edit", on_click=save_edit, args=(sel,), key="btn_save_edit", type="primary", use_container_width=True)
                col_s2.button("Keep As Written", on_click=mark_reviewed, args=(sel,), key="btn_keep_written", use_container_width=True)

        with tab_transcript:
            st.markdown(
                f"""
                <div class='dr-heading'>
                    <span>Consultation Transcript Record</span>
                    <span style='font-family:monospace; font-size:0.76rem; color:#0F766E; font-weight:700;'>{len(transcript.segments)} Spoken Turns</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption("Verbatim dialogue turns. Turns cited by the active note statement are highlighted.")
            hits = set(st.session_state.highlighted_seg_ids)
            for seg in transcript.segments:
                s_id = seg.segment_id
                l_num = line_label(s_id, LINES)
                spk = seg.speaker.value
                is_hit = s_id in hits
                
                border_clr = "#0F766E" if is_hit else "#E2E8F0"
                bg_clr = "#F0FDFA" if is_hit else "#FFFFFF"
                badge_html = "<span style='font-size:0.68rem; background:#0F766E; color:#FFFFFF; padding:2px 7px; border-radius:4px; font-weight:700;'>● CITED IN ACTIVE CLAIM</span>" if is_hit else ""
                
                st.markdown(
                    f"""
                    <div style='padding:10px 14px; margin-bottom:8px; border-radius:6px; border:1px solid {border_clr}; background:{bg_clr}; font-size:0.86rem; line-height:1.5;'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;'>
                            <span style='font-weight:750; font-size:0.74rem; color:#64748B; text-transform:uppercase;'>{l_num} · {spk}</span>
                            {badge_html}
                        </div>
                        <div style='color:#0F172A;'>{html.escape(seg.text)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
