# CoverSight API – Audio to Text

## Base URL

```
http://localhost:8000
```

Docs: http://localhost:8000/docs

---

## Transcription (Deepgram only)

Uses **Deepgram** exclusively. Language is auto-detected—no explicit language option. If Deepgram cannot detect the language, the request fails (no fallback).

**Supported languages:** bg, ca, cs, da, de, el, en, es, et, fi, fr, hi, hu, id, it, ja, ko, lt, lv, ms, nl, no, pl, pt, ro, ru, sk, sv, th, tr, uk, vi, zh, and more.

---

## Endpoints

### GET /

Service info.

### GET /health

Health check.

### POST /transcribe/audio

Transcribe an audio file. Multi-language support.

**Form fields:** `file` (required)

**Request:** `multipart/form-data`

| Field | Type   | Required | Description                    |
|-------|--------|----------|--------------------------------|
| file  | File   | Yes      | Audio (mp3, wav, m4a, ogg, webm, flac, mp4) |

**Response:**
```json
{
  "transcript": "Transcribed text...",
  "filename": "recording.wav",
  "detected_language": "fr",
  "detected_language_name": "French",
  "language_confidence": 0.95,
  "sentiment_segments": [
    {"text": "I love my phone.", "start_word": 0, "end_word": 4, "sentiment": "positive", "sentiment_score": 0.44}
  ],
  "sentiment_average": {"sentiment": "positive", "sentiment_score": 0.36},
  "intent_segments": [
    {"text": "Can I upgrade my phone?", "start_word": 12, "end_word": 16, "intents": [{"intent": "Upgrade phone", "confidence_score": 0.97}]}
  ],
  "topic_segments": [
    {"text": "Can I upgrade my phone?", "start_word": 13, "end_word": 17, "topics": [{"topic": "Phone upgrade", "confidence_score": 0.97}]}
  ],
  "summary": {"result": "success", "short": "Jake calls the Honda dealership and schedules a test drive for Friday."}
}
```
- `detected_language`, `detected_language_name`, `language_confidence`: when using Deepgram with auto-detect.
- `sentiment_segments`, `sentiment_average`: when using Deepgram with English audio (sentiment is English-only).
- `intent_segments`: when using Deepgram with English audio (intents is English-only).
- `topic_segments`: when using Deepgram with English audio (topics is English-only).
- `summary`: when using Deepgram with English audio (50+ words; result + short summary).

**Example (curl):**
```bash
curl -X POST http://localhost:8000/transcribe/audio -F "file=@recording.wav"
```

---

### POST /detect-topics

Analyze text/transcript and return **full results** (same format as audio transcription). Uses Deepgram's Text Intelligence API. English only.

**Request:** `application/json`

| Field | Type   | Required | Description                    |
|-------|--------|----------|--------------------------------|
| text  | string | Yes      | Text or transcript to analyze |

**Response:** Same structure as `/transcribe/audio`:
```json
{
  "transcript": "Input text...",
  "detected_language": "en",
  "detected_language_name": "English",
  "sentiment_segments": [...],
  "sentiment_average": {...},
  "intent_segments": [...],
  "topic_segments": [...],
  "summary": {"result": "success", "short": "Brief summary..."}
}
```

**Example (curl):**
```bash
curl -X POST http://localhost:8000/detect-topics \
  -H "Content-Type: application/json" \
  -d '{"text": "Can I upgrade my phone? I need a new battery."}'
```

---

### POST /analyze/text

Analyze a text file (e.g. chat transcript). Same full results as `/detect-topics`. Upload a `.txt` file.

**Request:** `multipart/form-data`

| Field | Type   | Required | Description        |
|-------|--------|----------|--------------------|
| file  | File   | Yes      | Text file (.txt)   |

**Response:** Same as `/transcribe/audio` plus `filename`.

**Example (curl):**
```bash
curl -X POST http://localhost:8000/analyze/text -F "file=@chats/chat1.txt"
```

