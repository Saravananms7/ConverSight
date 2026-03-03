# CoverSight Postman Collection

## Import

1. Open Postman
2. Click **Import** → **Upload Files**
3. Select `CoverSight_API.postman_collection.json`

## Setup

1. Start the server: `python run.py`
2. Base URL is set to `http://localhost:8000` (edit collection variables if needed)
3. If using API key: set `api_key` in collection variables and enable the `x-api-key` header in each request

## Endpoints

| Method | Endpoint | Body | Returns |
|--------|----------|------|---------|
| GET | `/` | - | Service info and endpoint list |
| GET | `/health` | - | `{"status": "healthy"}` |
| POST | `/policy` | form-data: `file` (.txt) or `policy_text` | Policy stored (embeddings in Supabase) |
| POST | `/transcribe/audio` | form-data: `file` (audio), `provider`, `client_config` | transcript, sentiment, intents, topics, summary, policy_violation_report |
| POST | `/detect-topics` | JSON: `{"text": "...", "client_config": {...}}` | Full analysis + policy_violation_report |
| POST | `/analyze/text` | form-data: `file` (.txt), `client_config` | Full analysis + policy_violation_report |
| POST | `/synthesize/speech` | form-data: `text`, `language_code`, `voice_name`, `audio_encoding` | MP3 audio file |

## Quick test

- **GET /health** – verify server is running
- **POST /policy** – upload policy first (required for policy RAG in transcribe/analyze)
- **POST /detect-topics** – paste transcript in JSON body, send
- **POST /synthesize/speech** – convert text to speech, save response as .mp3
