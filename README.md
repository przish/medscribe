# Medscribe Local: Proof Mode 🩺

> **AppBuildersPH Hackathon 2026 Submission**  
> An offline-first clinical documentation decision-support aid that drafts structured SOAP notes from consultation transcripts, proves every claim with direct source citations, flags unsupported statements or altered negation, and leaves omitted information blank.

---

## 🔒 100% On-Device & Privacy-Preserving
- **Local Speech-to-Text (Whisper):** Real-time microphone and file transcription executes directly on-device on CPU using `faster-whisper` with zero telemetry or network calls.
- **Meaningful Local Inference:** Uses local LLM inference via Ollama (`llama3.2:3b` or compatible local model) or a deterministic local clinical adapter. Zero patient audio or data leaves the device.
- **Offline Proof:** The core speech transcription, note drafting, deterministic grounding audit, and export operate completely offline with no network connection required.
- **Purely Synthetic Scenarios:** All fixtures, audio samples, and demonstrations utilize strictly fictional clinical encounters.

---

## 💡 Why Medscribe Benefits From Running AI Locally
1. **Absolute Patient Health Information (PHI) Privacy:** Clinical conversations and medical histories are sensitive. Running both speech transcription (Whisper) and note extraction on-device guarantees zero cloud leakage, adhering to strict data sovereignty and healthcare privacy expectations.
2. **Zero-Latency Resilience in Clinics & Hospitals:** Medical facilities frequently suffer from unreliable connectivity or dead zones. Medscribe operates continuously without internet dependencies.
3. **Zero Inference Cloud Costs:** Clinics can run speech recognition and structured documentation pipelines without per-minute or per-token cloud API bills.

---

## 🚀 Quick Start & Running the App

### 1. Prerequisites
- macOS (Apple Silicon recommended) or Linux.
- Python 3.9+ installed.

### 2. Setup Environment
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. (Optional) Local Ollama Model Setup
To run live on-device LLM inference:
1. Install [Ollama](https://ollama.com/) or run `brew install ollama`.
2. Start Ollama and pull a lightweight model:
   ```bash
   ollama pull llama3.2:3b
   ```
*Note: If Ollama is not running, Medscribe automatically provides verified deterministic adapters so the entire app, audits, and UI remain 100% testable and demonstrable offline.*

### 4. Run the Streamlit Interface
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`. The app begins with a local demo-access screen. It is a UI preview only—not authentication: no password is requested, verified, or stored. Use synthetic cases only.

---

## 🧪 Testing & Verification

Run the automated test suite (all tests execute locally without network calls, including socket guards):
```bash
source .venv/bin/activate
pytest -v
```

Run the end-to-end offline smoke test across all synthetic fixtures:
```bash
python3 smoke_test.py
```

---

## 🏗️ Architecture & Logical Flow

```
[ Live Microphone Recording / Audio File ]
                 │
                 ▼
[ Local On-Device Whisper (faster-whisper CPU) ]
                 │
                 ▼
[ Consultation Transcript (Speaker Turns & Timestamps) ]
                 │
                 ▼
[ Local Inference Adapter (Ollama / Deterministic) ]
                 │
                 ▼
[ Structured Draft Note (Pydantic Schemas) ]
                 │
                 ▼
[ Deterministic Evidence Validator ]
  ├── Segment ID Existence Verification
  ├── Verbatim Quote Match Audit
  ├── Negation Preservation & Denial Flip Check
  ├── Missingness & Non-Fabrication Audit
  └── Medication Ambiguity Warnings
                 │
                 ▼
[ Proof-Mode UI (Streamlit) ]
  ├── Interactive Claim Citation Inspection
  ├── Physician Override & 1-Click Wording Replacement
  └── Verified Export Gate (Locked until Review Attestation)
```

---

## 📋 Hackathon Disclosures & Deliverables
- **Models Used:** On-device Whisper (`faster-whisper` tiny on CPU) + Ollama local LLMs (default `llama3.2:3b`) + deterministic grounded testing adapters.
- **Technologies & Frameworks:** Python 3.9, Faster-Whisper, Pydantic v2, Streamlit, Pytest, Requests.
- **APIs & Cloud Services:** **None** (100% Offline Local Pipeline).
- **Existing Code & Assets:** None. Built fresh during AppBuildersPH Hackathon 2026.
- **AI Development Tools:** Google Antigravity.

---

## ⚠️ Clinical Disclaimer
Medscribe is an experimental decision-support prototype created for hackathon demonstration. It does not provide medical advice, diagnosis, or treatment. Generated draft notes strictly require review and verification by a licensed healthcare professional before any clinical or legal reliance.
