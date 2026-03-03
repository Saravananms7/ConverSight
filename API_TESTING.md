# CoverSight API – Testing Guide

How to test all endpoints and edge cases.

---

## Quick Start

1. **Start server**: `python run.py`
2. **Interactive docs**: Open http://localhost:8000/docs (Swagger UI)
3. **Postman**: Import `postman/CoverSight_API.postman_collection.json`

---

## All Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Service info + endpoint list |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc docs |
| POST | `/policy` | Upload policy → embeddings → Supabase bucket |
| POST | `/transcribe/audio` | Audio → transcript + analysis + policy RAG |
| POST | `/synthesize/speech` | Text → MP3 audio |
| POST | `/detect-topics` | JSON text → analysis + policy RAG |
| POST | `/analyze/text` | .txt file → analysis + policy RAG |

---

## 1. GET /

**Purpose**: Service info and endpoint list.

**cURL**:
```bash
curl http://localhost:8000/
```

**Expected**: `{service, version, description, docs, endpoints}`

**Edge cases**:
- None (no input).

---

## 2. GET /health

**Purpose**: Health check.

**cURL**:
```bash
curl http://localhost:8000/health
```

**Expected**: `{"status": "healthy"}`

**Edge cases**:
- None.

---

## 3. POST /policy

**Purpose**: Upload policy text, generate embeddings, store in Supabase bucket (or memory).

**cURL (file)**:
```bash
curl -X POST http://localhost:8000/policy -F "file=@policy.txt"
```

**cURL (text)**:
```bash
curl -X POST http://localhost:8000/policy -F "policy_text=Do not share customer data. Always verify identity."
```

**Expected**: `{message, log, chunks_count, stored, storage}`

**Edge cases**:

| Case | Input | Expected |
|------|-------|----------|
| No file, no policy_text | Empty form | 400: "Provide policy via file upload or policy_text form field" |
| policy_text empty/whitespace | `policy_text=` or `policy_text="   "` | 400 |
| Wrong file type | `.pdf`, `.docx` | 400: "Policy file must be .txt" |
| Non-UTF-8 file | Binary/corrupted file | 400: "File must be valid UTF-8" |
| Very short policy | Single sentence | 200, `chunks_count: 1` |
| Very long policy | Large document | 200, many chunks (may be slow) |
| Supabase not configured | No SUPABASE_URL/KEY | 200, `storage: "memory"` |
| Supabase bucket missing | Bucket doesn't exist | App tries to create bucket, then upload |
| Invalid GOOGLE_API_KEY | Bad key | 500: "Policy storage failed" |
| API key required | Missing/wrong `x-api-key` | 401 (if API_SECRET_KEY set) |

---

## 4. POST /transcribe/audio

**Purpose**: Transcribe audio and return analysis (and policy RAG if policy loaded).

**cURL**:
```bash
curl -X POST http://localhost:8000/transcribe/audio \
  -F "file=@recording.wav" \
  -F "provider=deepgram" \
  -F "client_config={\"business_domain\":\"telecom\"}"
```

**Expected**: `{transcript, detected_language, conversation_summary, overall_sentiment, primary_customer_intents, key_topics, entities, policy_violation_report?, criteria_match_assessment?}`

**Edge cases**:

| Case | Input | Expected |
|------|-------|----------|
| No file | Missing `file` | 422 Unprocessable Entity |
| Wrong format | `.pdf`, `.doc`, `.xyz` | 400: "Unsupported format" |
| Empty audio | Silent or very short file | 200, empty/minimal transcript |
| Non-English audio | Spanish/French/etc. | 200, `translated_transcript` present |
| Invalid provider | `provider=invalid` | Uses Deepgram (default) |
| provider=whisper | - | Uses OpenAI Whisper API (needs OPENAI_API_KEY) |
| provider=whisper-gemini | - | Local Whisper + Gemini translate |
| Invalid client_config JSON | `client_config={invalid}` | 200, config ignored (no criteria_match_assessment) |
| No policy loaded | Policy never uploaded | 200, no `policy_violation_report` |
| Policy loaded | Policy uploaded first | 200, `policy_violation_report` present |
| Corrupted audio | Invalid/corrupt file | 500: "Transcription failed" |
| DEEPGRAM_API_KEY missing | - | 500 (Deepgram) |
| API key required | Missing/wrong `x-api-key` | 401 |

---

## 5. POST /synthesize/speech

**Purpose**: Text-to-speech, returns MP3 (or WAV).

**cURL**:
```bash
curl -X POST http://localhost:8000/synthesize/speech \
  -F "text=Hello, this is a test." \
  -F "language_code=en-US" \
  -F "audio_encoding=MP3" \
  -o speech.mp3
```

**Expected**: Binary audio file (MP3 or WAV).

**Edge cases**:

| Case | Input | Expected |
|------|-------|----------|
| Empty text | `text=` or `text="   "` | 400: "Text cannot be empty" |
| Missing text | No `text` field | 422 |
| Invalid language_code | `language_code=xx-YY` | 500 or fallback (TTS may fail) |
| Very long text | 5000+ chars | 200 or 500 (TTS limits) |
| audio_encoding=LINEAR16 | - | Returns WAV |
| GOOGLE_APPLICATION_CREDENTIALS not set | - | 500: "Ensure GOOGLE_APPLICATION_CREDENTIALS is set" |
| API key required | Missing/wrong `x-api-key` | 401 |

---

## 6. POST /detect-topics

**Purpose**: Analyze text from JSON body (same output as transcribe/analyze).

**cURL**:
```bash
curl -X POST http://localhost:8000/detect-topics \
  -H "Content-Type: application/json" \
  -d '{"text": "Agent: Hello. Customer: I need help with my card."}'
```

**With client_config**:
```bash
curl -X POST http://localhost:8000/detect-topics \
  -H "Content-Type: application/json" \
  -d '{"text": "...", "client_config": {"business_domain": "telecom", "products_or_services": ["mobile plans"]}}'
```

**Expected**: Same structure as transcribe/audio.

**Edge cases**:

| Case | Input | Expected |
|------|-------|----------|
| No body | Empty request | 422 |
| Not JSON | `Content-Type: text/plain` or invalid JSON | 422 |
| Missing `text` | `{}` or `{"other": "x"}` | 400: "Missing 'text' field" |
| `text` not string | `{"text": 123}` | 400: "'text' must be a string" |
| Empty text | `{"text": ""}` | 200, placeholder values ("Not specified") |
| Whitespace-only text | `{"text": "   "}` | 200, placeholder values |
| Invalid client_config | `{"text": "x", "client_config": "not-json"}` | 200, config ignored |
| No policy loaded | - | 200, no `policy_violation_report` |
| Non-English text | Spanish/French | 200, `translated_transcript` |
| API key required | Missing/wrong `x-api-key` | 401 |

---

## 7. POST /analyze/text

**Purpose**: Analyze text from uploaded .txt file.

**cURL**:
```bash
curl -X POST http://localhost:8000/analyze/text \
  -F "file=@transcript.txt" \
  -F "client_config={\"business_domain\":\"banking\"}"
```

**Expected**: Same structure as transcribe/audio.

**Edge cases**:

| Case | Input | Expected |
|------|-------|----------|
| No file | Missing `file` | 422 |
| Wrong extension | `.pdf`, `.doc`, `.csv` | 400: "Unsupported format" |
| Non-UTF-8 file | Binary/corrupted | 400: "File must be valid UTF-8 text" |
| Empty file | 0 bytes | 200, placeholder values |
| Very large file | 1MB+ text | 200 (may be slow) |
| Invalid client_config | Malformed JSON string | 200, config ignored |
| No policy loaded | - | 200, no `policy_violation_report` |
| API key required | Missing/wrong `x-api-key` | 401 |

---

## API Key (Optional)

If `API_SECRET_KEY` is set in `.env`, all POST endpoints require:

```
x-api-key: YOUR_API_SECRET_KEY
```

**Edge cases**:
- Missing header → 401
- Wrong key → 401
- `API_SECRET_KEY` not set → No auth required

---

## Recommended Test Order

1. **GET /health** – Server up
2. **GET /** – Service info
3. **POST /policy** – Upload policy (file or text)
4. **POST /detect-topics** – Text analysis (no audio)
5. **POST /analyze/text** – File analysis
6. **POST /transcribe/audio** – Audio (needs sample file)
7. **POST /synthesize/speech** – TTS (needs Google credentials)

---

## PowerShell Quick Test

```powershell
$base = "http://localhost:8000"

# Health
Invoke-RestMethod "$base/health"

# Detect topics
Invoke-RestMethod "$base/detect-topics" -Method Post -ContentType "application/json" `
  -Body '{"text": "Customer: I want to cancel my subscription."}'
```

---

## Postman Collection

Import `postman/CoverSight_API.postman_collection.json`. Set collection variables:

- `base_url`: http://localhost:8000
- `api_key`: (optional) Your API_SECRET_KEY
