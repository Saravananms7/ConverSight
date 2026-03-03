# CoverSight – Audio to Text + Text to Speech

- **Speech-to-Text**: Deepgram only (auto-detect language, no explicit language option)
- **Text-to-Speech**: Google Cloud TTS

**Requires:** Python 3.10+

---

## Setup

```powershell
cd d:\VAJRA\CoverSight
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env`:

```
DEEPGRAM_API_KEY=your_deepgram_api_key

# Whisper (optional, for provider=whisper)
OPENAI_API_KEY=your_openai_key

# LLM analysis (optional, Gemini; falls back to rule-based if missing)
GOOGLE_API_KEY=your_google_api_key
```

**For Deepgram:** Get key at [console.deepgram.com](https://console.deepgram.com).

**For Text-to-Speech:** Set `GOOGLE_APPLICATION_CREDENTIALS` to your Google Cloud service account JSON path. Enable the [Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com).

---

## Run the Project

The project consists of a FastAPI backend and a React (Vite) frontend. You will need two terminal windows to run both simultaneously.

### 1. Start the Backend
Open a terminal and run the following commands:
```powershell
cd d:\VAJRA\CoverSight
.\venv\Scripts\Activate.ps1
python run.py
```
The backend API and docs will be available at http://localhost:8000/docs.

### 2. Start the Frontend
Open a **new** terminal window and run:
```powershell
cd d:\VAJRA\CoverSight\frontend
npm install   # (only needed the first time)
npm run dev
```
The frontend application will be available at the local URL provided by Vite (usually http://localhost:5173).

---

## API

### POST /transcribe/audio (Speech-to-Text)

Upload an audio file. Uses Deepgram only—language is auto-detected (no explicit language option).

**Form data:** `file` – audio file (mp3, wav, m4a, ogg, webm, flac, mp4)

**Response:**
```json
{
  "transcript": "Transcribed text here...",
  "filename": "recording.wav",
  "detected_language": "en",
  "detected_language_name": "English",
  "language_confidence": 0.95
}
```

### POST /synthesize/speech (Text-to-Speech)

Convert text to speech. Returns MP3 audio.

**Form data:** `text` (required), `language_code` (default: en-US), `voice_name` (optional), `audio_encoding` (default: MP3)

---

## Test

```powershell
# Create sample audio
python scripts\create_test_audio.py

# Test (server must be running)
.\scripts\test_audio.ps1
# or
python scripts\test_audio.py
```

Or use Swagger UI at http://localhost:8000/docs → **POST /transcribe/audio**.


#Policy Checking

┌─────────────────────────────────────────────────────────────────────────┐
│ 1. POST /policy                                                          │
│    policy.txt → chunks → embeddings → Supabase bucket (or memory)        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. POST /transcribe/audio  OR  POST /analyze/text  OR  POST /detect-topics│
│    Audio/Text → transcript                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. Policy RAG (if policy loaded)                                          │
│    transcript chunks → embed → FAISS search → top-k policy chunks          │
│    → LLM violation check per chunk → policy_violation_report              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. Deepgram + structured analysis                                         │
│    transcript → summary, sentiment, intents, topics, entities            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. Response                                                               │
│    transcript, summary, sentiment, intents, topics, entities,             │
│    policy_violation_report, criteria_match_assessment (if applicable)    │
└─────────────────────────────────────────────────────────────────────────┘