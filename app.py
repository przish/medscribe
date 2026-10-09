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
    st.markdown("---")
    
    st.markdown("#### Clinical Encounter")
    preset_options = list(FIXTURE_PRESETS.keys())
    curr_preset = st.session_state.get("loaded_preset", preset_options[0])
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
                def_claim = get_highest_priority_claim(new_draft)
                st.session_state.selected_claim = def_claim
                st.session_state.highlighted_seg_ids = list(def_claim.source_segment_ids) if def_claim else []
                st.rerun()

# Handle Encounter or Engine Changes
if "last_preset_selection" not in st.session_state:
    st.session_state.last_preset_selection = selected_preset
preset_changed = selected_preset != st.session_state.last_preset_selection
engine_changed = (st.session_state.get("loaded_engine") != selected_engine
                  and st.session_state.get("loaded_preset") != "Custom Encounter")

if preset_changed:
    st.session_state.last_preset_selection = selected_preset
    load_preset_encounter(selected_preset, selected_engine)
elif engine_changed or "draft_note" not in st.session_state:
    load_preset_encounter(selected_preset, selected_engine)

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
    div[class*="claim_row_"] button {
        width: 100% !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 7px 12px !important;
        min-height: 38px !important;
        height: auto !important;
        border-radius: 4px !important;
        font-size: 0.9rem !important;
        line-height: 1.45 !important;
        white-space: normal !important;
        word-break: break-word !important;
        border: 1px solid transparent !important;
        border-left-width: 4px !important;
        margin-bottom: 3px !important;
        background: #FFFFFF !important;
        color: var(--ink) !important;
        transition: all 0.12s ease-in-out !important;
        box-shadow: none !important;
    }
    
    div[class*="claim_row_crit"] button {
        background: var(--red-bg) !important;
        border-left: 4px solid var(--red-bar) !important;
        color: var(--red-ink) !important;
    }
    div[class*="claim_row_warn"] button {
        background: var(--amber-bg) !important;
        border-left: 4px solid var(--amber-bar) !important;
        color: var(--amber-ink) !important;
    }
    div[class*="claim_row_ok"] button {
        background: #FFFFFF !important;
        border: 1px solid var(--line) !important;
        border-left: 4px solid #CBD5E1 !important;
        color: var(--ink) !important;
    }
    div[class*="claim_row_sel"] button {
        outline: 2px solid var(--accent) !important;
        outline-offset: 1px !important;
        background: var(--accent-bg) !important;
    }
    
    div[class*="claim_row_"] button:hover {
        background: #F1F5F9 !important;
        border-color: #94A3B8 !important;
        cursor: pointer !important;
    }
    div[class*="claim_row_crit"] button:hover {
        background: #FEE2E2 !important;
        border-left: 4px solid var(--red-bar) !important;
    }
    div[class*="claim_row_warn"] button:hover {
        background: #FEF3C7 !important;
        border-left: 4px solid var(--amber-bar) !important;
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
        border-left: 3px solid var(--ink);
        background: #F1F5F9;
        padding: 8px 12px;
        font-size: 0.92rem;
        line-height: 1.45;
        margin: 4px 0 12px 0;
        border-radius: 0 4px 4px 0;
    }
    
    .alert-card {
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 10px;
        font-size: 0.88rem;
        line-height: 1.5;
        border: 1px solid transparent;
        border-left-width: 4px;
    }
    .alert-card.crit {
        background: var(--red-bg);
        border-color: var(--red-bar);
        color: var(--red-ink);
    }
    .alert-card.warn {
        background: var(--amber-bg);
        border-color: var(--amber-bar);
        color: var(--amber-ink);
    }
    .alert-card.ok {
        background: var(--green-bg);
        border-color: var(--green-bar);
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
        border-radius: 4px !important;
        font-size: 0.84rem !important;
        line-height: 1.4 !important;
        white-space: normal !important;
        word-break: break-word !important;
        border: 1px solid var(--line) !important;
        border-left: 3px solid #CBD5E1 !important;
        margin-bottom: 4px !important;
        background: #FFFFFF !important;
        color: var(--ink) !important;
        box-shadow: none !important;
        transition: all 0.1s ease-in-out !important;
    }
    div[class*="turn_row_hit"] button {
        background: #DBEAFE !important;
        border: 1px solid var(--accent) !important;
        border-left: 4px solid var(--accent) !important;
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

        # Bidirectional Linking: Consultation Dialogue Stream
        st.markdown(
            """
            <div class='dr-title' style='margin-top:18px;'>
                <span>Consultation Dialogue</span>
                <span style='font-size:0.7rem; color:var(--muted); font-weight:400;'>Click turn to focus linked claim</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        hits = set(st.session_state.highlighted_seg_ids)
        for seg in transcript.segments:
            s_id = seg.segment_id
            l_num = line_label(s_id, LINES)
            spk = "Clinician" if seg.speaker.value == "Clinician" else "Patient"
            is_hit = s_id in hits
            
            # Find all claims citing this segment
            linked_claims = [c for c in all_claims if s_id in c.source_segment_ids]
            
            turn_key = f"turn_row_{'hit' if is_hit else 'norm'}_{s_id}"
            with st.container(key=turn_key):
                if linked_claims:
                    flagged_cnt = sum(1 for c in linked_claims if needs_review(c))
                    badge = f" [⚠️ {flagged_cnt} Flagged]" if flagged_cnt else " [✓ Linked]"
                    label = f"{l_num} · {spk}: {seg.text}{badge}"
                    st.button(
                        label,
                        key=f"turn_btn_{s_id}",
                        on_click=select_claim_from_segment,
                        args=(linked_claims[0], s_id),
                        use_container_width=True,
                        help=f"Jump to claim citing {l_num}",
                    )
                else:
                    label = f"{l_num} · {spk}: {seg.text} [Uncited]"
                    st.button(
                        label,
                        key=f"turn_btn_{s_id}",
                        disabled=True,
                        use_container_width=True,
                        help="No generated claims cite this dialogue turn",
                    )
