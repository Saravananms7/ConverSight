# CoverSight API – cURL Examples

Base URL: `http://localhost:8000`  
If using API key, add: `-H "x-api-key: YOUR_API_KEY"`

---

## GET Endpoints

### Service info
```bash
curl -X GET http://localhost:8000/
```

### Health check
```bash
curl -X GET http://localhost:8000/health
```

---

## POST Endpoints (JSON body)

### POST /detect-topics
Analyze text. Returns: transcript, detected_language, conversation_summary, overall_sentiment, primary_customer_intents, key_topics, entities.
```bash
curl -X POST http://localhost:8000/detect-topics \
  -H "Content-Type: application/json" \
  -d '{"text": "Agent: Hello. Customer: I need help with my card - there was a fraudulent transaction."}'
```

---

## POST Endpoints (form-data / file upload)

### POST /transcribe/audio
Upload audio file, get transcript + sentiment + intents + topics + summary.

**Query param:** `provider` = `deepgram` (default), `whisper` (OpenAI API), or `whisper-gemini` (local Whisper + Gemini translate + Deepgram analyze).

```bash
# Deepgram (default)
curl -X POST http://localhost:8000/transcribe/audio -F "file=@recording.wav"

# Whisper (local) + Gemini (translate) + Deepgram (analysis)
curl -X POST "http://localhost:8000/transcribe/audio?provider=whisper-gemini" -F "file=@recording.wav"
```

### POST /upload/audio
Upload audio to Supabase Storage, get public URL.
```bash
curl -X POST http://localhost:8000/upload/audio \
  -F "file=@recording.mp3"
```

### POST /synthesize/speech
Text to speech, returns MP3 audio (binary).
```bash
curl -X POST http://localhost:8000/synthesize/speech \
  -F "text=Hello, this is a test." \
  -F "language_code=en-US" \
  -F "audio_encoding=MP3" \
  -o speech.mp3
```

### POST /analyze/text
Upload .txt file. Returns: transcript, detected_language, conversation_summary, overall_sentiment, primary_customer_intents, key_topics, entities.
```bash
curl -X POST http://localhost:8000/analyze/text \
  -F "file=@chats/chat1.txt"
```

---

## With API key

If `API_SECRET_KEY` is set in `.env`, add the header to any request:

```bash
curl -X POST http://localhost:8000/detect-topics \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_SECRET_KEY" \
  -d '{"text": "Your transcript here."}'
```

---

## Summary

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/` | GET | - | Service info (JSON) |
| `/health` | GET | - | `{"status": "healthy"}` |
| `/transcribe/audio` | POST | form-data: `file` | transcript, detected_language, conversation_summary, overall_sentiment, primary_customer_intents, key_topics, entities |
| `/synthesize/speech` | POST | form-data: `text`, `language_code`, etc. | MP3 audio (binary) |
| `/detect-topics` | POST | JSON: `{text}` | transcript, detected_language, conversation_summary, overall_sentiment, primary_customer_intents, key_topics, entities |
| `/analyze/text` | POST | form-data: `file` (.txt) | Same as detect-topics |
