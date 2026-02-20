# CoverSight Postman Collection

## Import

1. Open Postman
2. Click **Import** → **Upload Files**
3. Select `CoverSight_API.postman_collection.json`

## Setup

1. Start the server: `python run.py`
2. Base URL is set to `http://localhost:8000` (edit collection variables if needed)
3. If using API key: set `api_key` in collection variables and enable the `x-api-key` header in each request

## Endpoints (all return JSON)

| Method | Endpoint | Body | Returns |
|--------|----------|------|---------|
| GET | `/` | - | Service info |
| GET | `/health` | - | `{"status": "healthy"}` |
| POST | `/transcribe/audio` | form-data: `file` (audio) | transcript, sentiment, intents, topics, summary |
| POST | `/detect-topics` | JSON: `{"text": "..."}` | Full analysis |
| POST | `/analyze/structured` | JSON: `{"text": "..."}` | Strict JSON (conversation_summary, entities, etc.) |
| POST | `/analyze/text` | form-data: `file` (.txt) | Full analysis |
| POST | `/analyze/structured/file` | form-data: `file` (.txt) | Strict JSON |

## Quick test

- **GET /health** – verify server is running
- **POST /detect-topics** – paste transcript in JSON body, send
- **POST /analyze/structured** – same, returns compact structured JSON
