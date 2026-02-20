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

## Run

```powershell
python run.py
```

API docs: http://localhost:8000/docs

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
